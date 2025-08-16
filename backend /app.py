from flask import Flask, render_template, request, redirect, url_for, jsonify, flash, session, send_from_directory
from flask_sqlalchemy import SQLAlchemy
from flask_migrate import Migrate
from werkzeug.security import generate_password_hash, check_password_hash
from werkzeug.utils import secure_filename
from flask import Flask, render_template
from flask_mail import Mail, Message
from datetime import datetime, timedelta
import urllib.parse
import pandas as pd
import csv
import os
import random
import string

# =====================
# APP CONFIGURATION
# =====================
app = Flask(__name__)
app.secret_key = "supersecretkey"  # Change this in production

# Email configuration
app.config['MAIL_SERVER'] = 'smtp.gmail.com'
app.config['MAIL_PORT'] = 587
app.config['MAIL_USE_TLS'] = True
app.config['MAIL_USERNAME'] = 'your_gmail@gmail.com'  # Change
app.config['MAIL_PASSWORD'] = 'your_email_password'   # Change
mail = Mail(app)

# =====================
# ADMIN CREDENTIALS
# =====================
ADMIN_USERNAME = 'bigjoe'
ADMIN_PASSWORD = 'mypass2025'

# =====================
# COURSE SETUP
# =====================
COURSES = {
    'ai': 'AI',
    'data-analysis': 'DA',
    'ml': 'ML',
    'viz': 'DV',
    'ai-projects': 'PR',
    'python': 'PY',
    'sql': 'SQL'
}

# =====================
# DATABASE CONFIGURATION
# =====================
try:
    app.config['SQLALCHEMY_DATABASE_URI'] = (
        "postgresql://erikodxit_db_user:qVGnuLYV2FAgFnXcAqq4Fw8nKLqub4Pb@"
        "dpg-d24v9nili9vc73eo9he0-a.frankfurt-postgres.render.com/erikodxit_db"
    )
    print("✅ Using Cloud PostgreSQL database")
except Exception:
    app.config['SQLALCHEMY_DATABASE_URI'] = "sqlite:///local.db"
    print("⚠️ Using local SQLite database (fallback)")

app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

# =====================
# UPLOAD CONFIGURATION
# =====================
UPLOAD_FOLDER = "static/uploads/videos"
app.config["UPLOAD_FOLDER"] = UPLOAD_FOLDER
os.makedirs(UPLOAD_FOLDER, exist_ok=True)

CERTIFICATE_FOLDER = os.path.join("static", "uploads", "certificates")
app.config["CERTIFICATE_FOLDER"] = CERTIFICATE_FOLDER
os.makedirs(CERTIFICATE_FOLDER, exist_ok=True)

ASSIGNED_FILE = os.path.join("uploads", "certificate_records.csv")
os.makedirs("uploads", exist_ok=True)

ALLOWED_EXTENSIONS = {"mp4", "webm", "ogg", "mov"}

# =====================
# DATABASE INIT
# =====================
db = SQLAlchemy(app)
migrate = Migrate(app, db)

# =====================
# MODELS
# =====================

class User(db.Model):
    __tablename__ = "user"
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(150), nullable=False)
    email = db.Column(db.String(150), unique=True, nullable=False)
    password_hash = db.Column(db.String(255), nullable=False)

    def set_password(self, password):
        self.password_hash = generate_password_hash(password)

    def check_password(self, password):
        return check_password_hash(self.password_hash, password)


class CourseAccessCode(db.Model):
    __tablename__ = "course_access_code"
    id = db.Column(db.Integer, primary_key=True)
    code = db.Column(db.String(50), nullable=False)
    course_slug = db.Column(db.String(50), nullable=False)
    expires_at = db.Column(db.DateTime, nullable=False)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=True)


class CourseVideo(db.Model):
    __tablename__ = "course_video"
    id = db.Column(db.Integer, primary_key=True)
    course_slug = db.Column(db.String(50), nullable=False)
    title = db.Column(db.String(200), nullable=False)
    video_url = db.Column(db.String(500), nullable=False)
    is_youtube = db.Column(db.Boolean, default=False)


class Notification(db.Model):
    __tablename__ = "notification"
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    message = db.Column(db.String(500), nullable=False)
    is_read = db.Column(db.Boolean, default=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)


class Certificate(db.Model):
    __tablename__ = "certificates"
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, nullable=False)
    title = db.Column(db.String(255), nullable=False)
    course_slug = db.Column(db.String(50), nullable=False)
    file_url = db.Column(db.String(500), nullable=False)
    uploaded_at = db.Column(db.DateTime, default=datetime.utcnow)


class StudentQuestion(db.Model):
    __tablename__ = "student_question"
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=False)
    course_slug = db.Column(db.String(100), nullable=False)
    question_text = db.Column(db.Text, nullable=False)
    asked_at = db.Column(db.DateTime, default=datetime.utcnow)


class Student(db.Model):
    __tablename__ = "student"
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(150), nullable=False)
    email = db.Column(db.String(150), nullable=False)
    phone = db.Column(db.String(20), nullable=False)
    course_slug = db.Column(db.String(50), nullable=False)
    enrolled_at = db.Column(db.DateTime, default=datetime.utcnow)


class Course(db.Model):
    __tablename__ = "course"
    id = db.Column(db.Integer, primary_key=True)
    slug = db.Column(db.String(50), unique=True, nullable=False)
    name = db.Column(db.String(100), nullable=False)


class Video(db.Model):
    __tablename__ = "video"
    id = db.Column(db.Integer, primary_key=True)
    course_id = db.Column(db.Integer, db.ForeignKey("course.id"), nullable=False)
    title = db.Column(db.String(200), nullable=False)
    video_url = db.Column(db.String(500), nullable=False)


class Enrollment(db.Model):
    __tablename__ = "enrollment"
    id = db.Column(db.Integer, primary_key=True)
    student_id = db.Column(db.Integer, db.ForeignKey("student.id"), nullable=False)
    course_id = db.Column(db.Integer, db.ForeignKey("course.id"), nullable=False)
    enrolled_at = db.Column(db.DateTime, default=datetime.utcnow)

# =====================
# Helper: Allowed file check
# =====================
def allowed_file(filename):
    return "." in filename and filename.rsplit(".", 1)[1].lower() in ALLOWED_EXTENSIONS


# =====================
# ✅ Generate Unique Code Helper
# =====================
def generate_unique_code(prefix, length=8):
    """Generate a truly unique course access code."""
    while True:
        code = prefix + ''.join(random.choices(string.ascii_uppercase + string.digits, k=length))
        # Check in DB to ensure it doesn't already exist
        existing = CourseAccessCode.query.filter_by(code=code).first()
        if not existing:
            return code


# =====================
# Helper: Allowed file check
# =====================
def allowed_file(filename):
    return "." in filename and filename.rsplit(".", 1)[1].lower() in ALLOWED_EXTENSIONS

# =====================
# ROUTES
# =====================
@app.route("/")
def index():
    return render_template("index.html")

@app.route("/about")
def about():
    return render_template("about.html")

@app.route("/contact")
def contact():
    return render_template("contact.html")

@app.route("/courses")
def show_courses():
    return render_template("courses.html")

# =====================
# REGISTER
# =====================
@app.route("/register", methods=["GET", "POST"])
def register():
    if request.method == "POST":
        name = request.form.get("name")
        email = request.form.get("email")
        password = request.form.get("password")

        existing_user = User.query.filter_by(email=email).first()
        if existing_user:
            flash("❌ Email already registered. Please login.", "danger")
            return redirect(url_for("register"))

        new_user = User(name=name, email=email)
        new_user.set_password(password)
        db.session.add(new_user)
        db.session.commit()

        session["user_id"] = new_user.id
        session["user_name"] = new_user.name

        return render_template("register_success.html", name=name)

    return render_template("register.html")
# =====================
# LOGIN (With optional registration code unlock)
# =====================
@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        email = request.form.get("email", "").strip().lower()
        password = request.form.get("password", "").strip()
        reg_code_entered = request.form.get("reg_code", "").strip().upper()

        # Find the user
        user = User.query.filter_by(email=email).first()

        if not user or not user.check_password(password):
            flash("❌ Invalid email or password.", "danger")
            return redirect(url_for("login"))

        # ✅ If a registration code is entered, apply it
        if reg_code_entered:
            matching_codes = CourseAccessCode.query.filter_by(code=reg_code_entered).all()

            if matching_codes:
                for code in matching_codes:
                    code.user_id = user.id
                db.session.commit()
                flash("✅ Your registration code has been applied. Courses unlocked!", "success")
            else:
                flash("⚠️ Invalid registration code.", "warning")

        # ✅ Store user session
        session["user_id"] = user.id
        session["user_name"] = user.name

        flash(f"✅ Welcome back, {user.name}!", "success")
        return redirect(url_for("dashboard"))

    return render_template("login.html")


# =====================
# DASHBOARD (Only show unlocked courses for logged-in user)
# =====================
@app.route("/dashboard")
def dashboard():
    if "user_id" not in session:
        flash("⚠️ Please log in to access the dashboard.", "warning")
        return redirect(url_for("login"))

    user = User.query.get(session["user_id"])
    if not user:
        flash("⚠️ User not found. Please log in again.", "warning")
        return redirect(url_for("login"))

    # ✅ Get all active (non-expired) course access codes for this user
    active_codes = CourseAccessCode.query.filter(
        CourseAccessCode.user_id == user.id,
        CourseAccessCode.expires_at > datetime.utcnow()
    ).all()

    # ✅ List of unlocked course slugs
    user_courses = [c.course_slug for c in active_codes]

    # ✅ Build status info (optional)
    course_status = []
    for c in active_codes:
        days_left = (c.expires_at - datetime.utcnow()).days
        course_status.append({
            "course_slug": c.course_slug,
            "expires_at": c.expires_at.strftime("%Y-%m-%d"),
            "days_left": days_left,
            "expired": False
        })

    # ✅ If no unlocked courses
    if not user_courses:
        flash("⚠️ You currently have no active courses linked to your account.", "warning")

    return render_template(
        "dashboard.html",
        user=user,
        user_courses=user_courses,  # Controls locked/unlocked status in HTML
        course_status=course_status
    )


# =====================
# OPEN A COURSE (Only if unlocked for this user)
# =====================
@app.route("/courses/<course_slug>")
def open_course(course_slug):
    if "user_id" not in session:
        flash("⚠️ Please log in to access this course.", "warning")
        return redirect(url_for("login"))

    user = User.query.get(session["user_id"])
    if not user:
        flash("⚠️ User not found. Please log in again.", "warning")
        return redirect(url_for("login"))

    # ✅ Check if course is unlocked for this user
    active_access = CourseAccessCode.query.filter(
        CourseAccessCode.user_id == user.id,
        CourseAccessCode.course_slug == course_slug,
        CourseAccessCode.expires_at > datetime.utcnow()
    ).first()

    if not active_access:
        flash("❌ You don't have access to this course.", "danger")
        return redirect(url_for("dashboard"))

    # ✅ Map slug to template
    template_map = {
    "ai": "courses/ai.html",
    "data-analysis": "courses/data-analysis.html",
    "ml": "courses/ml.html",
    "viz": "courses/data-viz.html",
    "ai-projects": "courses/ai-projects.html",
    "python": "courses/python.html",
    "sql": "courses/sql.html"
}

    template = template_map.get(course_slug)
    if not template:
        return "❌ Course template not found.", 404

    return render_template(template, user=user)

@app.route('/ai-training', methods=['GET', 'POST'])
def ai_training():
    if request.method == 'GET':
        return render_template('ai_training.html')

    data = request.get_json()
    question = data.get('question')
    course = data.get('course')

    prompt = f"You are an expert AI trainer for the course: {course}. Answer this question in a helpful and practical way:\n{question}"

    try:
        response = openai.ChatCompletion.create(
            model="gpt-3.5-turbo",
            messages=[{"role": "user", "content": prompt}],
            max_tokens=500
        )
        answer = response['choices'][0]['message']['content'].strip()
        return jsonify({"response": answer})
    except Exception as e:
        return jsonify({"response": f"❌ Error: {str(e)}"})

@app.route('/data-tools')
def data_tools():
    return render_template('data-tools.html')

@app.route('/tools/csv-analyzer', methods=['GET', 'POST'])
def csv_analyzer():
    table = None
    if request.method == 'POST':
        file = request.files.get('csv_file')
        if file:
            df = pd.read_csv(file)
            table = df.head().to_html(classes='table table-bordered', index=False)
    return render_template('csv-analyzer.html', table=table)

@app.route("/tools/data-visualizer", methods=["GET", "POST"])
def data_visualizer():
    if request.method == "POST":
        file = request.files.get("csv_file")
        if not file:
            return render_template("data-visualizer.html", error="No file uploaded.")

        filename = file.filename.lower()

        try:
            # Handle CSV files
            if filename.endswith(".csv"):
                df = pd.read_csv(file, encoding="latin1", engine="python", on_bad_lines="skip")
            
            # Handle Excel files (.xls, .xlsx, .ods)
            elif filename.endswith((".xls", ".xlsx", ".ods")):
                df = pd.read_excel(file, engine="openpyxl")  # For .xlsx
            
            else:
                return render_template("data-visualizer.html", error="Unsupported file type. Please upload CSV or Excel.")

        except Exception as e:
            return render_template("data-visualizer.html", error=f"❌ Error reading file: {e}")

        # No axes selected yet, just show columns
        if not request.form.get("x_axis"):
            return render_template("data-visualizer.html", columns=list(df.columns))

        # Plot data
        x_axis = request.form.get("x_axis")
        y_axis = request.form.get("y_axis")
        chart_type = request.form.get("chart_type")

        if x_axis not in df.columns or y_axis not in df.columns:
            return render_template("data-visualizer.html", error="Invalid column selection.")

        labels = df[x_axis].astype(str).tolist()
        data = df[y_axis].tolist()

        return render_template(
            "data-visualizer.html",
            columns=list(df.columns),
            chart_labels=labels,
            chart_data=data,
            x_axis=x_axis,
            y_axis=y_axis,
            chart_type=chart_type
        )

    return render_template("data-visualizer.html")



@app.route("/tools/api-connector", methods=["GET", "POST"])
def api_connector():
    response_data = None
    error_message = None

    if request.method == "POST":
        api_url = request.form.get("api_url")
        method = request.form.get("method", "GET")
        headers_raw = request.form.get("headers", "").strip()
        body_raw = request.form.get("body", "").strip()

        # Convert headers from text area to dictionary
        headers = {}
        if headers_raw:
            try:
                headers = json.loads(headers_raw)
            except:
                error_message = "❌ Headers must be in valid JSON format."

        # Convert body to dictionary if JSON
        data = None
        if body_raw:
            try:
                data = json.loads(body_raw)
            except:
                data = body_raw  # send as raw text

        try:
            # Send request
            if method == "GET":
                r = requests.get(api_url, headers=headers)
            elif method == "POST":
                r = requests.post(api_url, headers=headers, json=data)
            elif method == "PUT":
                r = requests.put(api_url, headers=headers, json=data)
            elif method == "DELETE":
                r = requests.delete(api_url, headers=headers, json=data)
            else:
                error_message = "❌ Unsupported method."

            if not error_message:
                try:
                    response_data = json.dumps(r.json(), indent=4)
                except:
                    response_data = r.text  # if not JSON
        except Exception as e:
            error_message = f"❌ Error: {str(e)}"

    return render_template("api-connector.html",
                           response_data=response_data,
                           error_message=error_message)


@app.route("/tools/data-cleaner", methods=["GET", "POST"])
def data_cleaner():
    cleaned_table = None
    summary = None
    download_link = None

    if request.method == "POST":
        file = request.files.get("csv_file")
        if not file:
            return render_template("data-cleaner.html", error="❌ Please upload a CSV file.")

        try:
            # Read CSV
            df = pd.read_csv(file)

            # Summary before cleaning
            summary = {
                "Rows": len(df),
                "Columns": len(df.columns),
                "Missing Values": df.isnull().sum().sum(),
                "Duplicate Rows": df.duplicated().sum()
            }

            # Cleaning Process
            df = df.drop_duplicates()  # Remove duplicates
            df = df.fillna("N/A")      # Fill missing values

            # Generate HTML preview
            cleaned_table = df.head(50).to_html(classes="table table-striped", index=False)

            # Save cleaned file to memory for download
            output = io.BytesIO()
            df.to_csv(output, index=False)
            output.seek(0)
            download_link = True

            # Store in session or pass as file stream
            return send_file(output, mimetype="text/csv", as_attachment=True, download_name="cleaned_data.csv")

        except Exception as e:
            return render_template("data-cleaner.html", error=f"❌ Error: {e}")

    return render_template("data-cleaner.html", table=cleaned_table, summary=summary, download=download_link)


# ==============================
# STUDENT - Collect Certificate
# ==============================
@app.route('/certificate', methods=['GET', 'POST'])
def collect_certificate():
    if request.method == 'POST':
        email = request.form.get('email', '').strip().lower()
        course = request.form.get('course', '').strip().lower()

        # Search in DB for a completed course certificate
        cert = Certificate.query.join(User).filter(
            User.email == email,
            Certificate.course_slug == course,  # Ensure course_slug matches stored format
        ).first()

        if cert:
            cert_filename = os.path.basename(cert.file_url)
            cert_path = os.path.join(CERTIFICATE_FOLDER, cert_filename)

            if os.path.exists(cert_path):
                return render_template(
                    'certificate_found.html',
                    cert_filename=cert_filename
                )
            else:
                return render_template(
                    'certificate.html',
                    error="⚠️ Certificate record found but file is missing."
                )
        else:
            return render_template(
                'certificate.html',
                error="❌ No certificate found for this email and course."
            )

    return render_template('certificate.html')


# ==============================
# DOWNLOAD CERTIFICATE FILE
# ==============================
@app.route('/download-certificate/<filename>')
def download_certificate(filename):
    return send_from_directory(CERTIFICATE_FOLDER, filename, as_attachment=True)

# =====================
# INSTRUCTOR CONTACT INFO
# =====================
INSTRUCTOR_CONTACTS = {
    'data-analysis': {
        'email': 'da-instructor@example.com',
        'whatsapp': '+2348012345678',  # Nigerian example
        'name': 'Data Analysis Instructor'
    },
    'ai': {
        'email': 'ai-instructor@example.com',
        'whatsapp': '+2348098765432',
        'name': 'AI Instructor'
    }
    # Add more courses here
}

# =====================
# ASK QUESTION ROUTE (NO COURSE SLUG)
# =====================
@app.route("/ask-question", methods=["GET", "POST"])
def ask_question():
    if request.method == "POST":
        # Ensure user is logged in
        if "user_id" not in session:
            flash("⚠️ Please log in to ask a question.", "warning")
            return redirect(url_for("login"))

        user = User.query.get(session["user_id"])
        if not user:
            flash("⚠️ User not found. Please log in again.", "warning")
            return redirect(url_for("login"))

        # Get and validate question text
        question = request.form.get("question", "").strip()
        if not question:
            flash("⚠️ Please type a question before sending.", "warning")
            return redirect(url_for("ask_question"))

        # Save question to DB (set course_slug to "general")
        new_question = StudentQuestion(
            user_id=user.id,
            course_slug="general",  # Always set to a default value
            question_text=question,
            asked_at=datetime.utcnow()
        )
        db.session.add(new_question)
        db.session.commit()

        # Optional: Send to a general instructor
        instructor = INSTRUCTOR_CONTACTS.get("general")
        email_sent = False
        whatsapp_link = None

        # Send Email
        if instructor and instructor.get('email'):
            try:
                msg = Message(
                    subject=f"New Question from {user.name}",
                    recipients=[instructor['email']],
                    body=f"""
Instructor: {instructor['name']},

You have a new student question.

From: {user.name} ({user.email})

Question:
{question}
                    """
                )
                mail.send(msg)
                email_sent = True
            except Exception as e:
                print("Email send failed:", e)

        # Create WhatsApp link
        if instructor and instructor.get('whatsapp'):
            try:
                message_text = f"New Question from {user.name} ({user.email})\n\n{question}"
                whatsapp_link = f"https://wa.me/{instructor['whatsapp'].replace('+','')}?text={urllib.parse.quote(message_text)}"
                print("WhatsApp Link:", whatsapp_link)
            except Exception as e:
                print("WhatsApp link generation failed:", e)

        # Flash success
        if email_sent and whatsapp_link:
            flash("✅ Your question was sent via email and WhatsApp!", "success")
        elif email_sent:
            flash("✅ Your question was sent via email!", "success")
        elif whatsapp_link:
            flash("✅ WhatsApp link generated for the instructor!", "success")
        else:
            flash("✅ Your question has been saved. The instructor will be notified.", "success")

        # ✅ Stay on ask_question page
        return redirect(url_for("ask_question"))

    # GET request → Show all previous questions
    questions = StudentQuestion.query.order_by(StudentQuestion.asked_at.asc()).all()

    return render_template("ask_question.html", questions=questions)

# =====================================
# QUIZ SYSTEM WITH LESSON LOCKING (Login check only)
# =====================================
@app.route('/quiz/<course>/<int:lesson_number>', methods=['GET', 'POST'])
def quiz(course, lesson_number):
    # ✅ Only check if user is logged in
    if 'user_id' not in session:
        flash("⚠️ Please log in first.", "warning")
        return redirect(url_for('login'))

    # Quiz template file
    quiz_template = f'quizzes/{course}_quiz{lesson_number}.html'
    full_quiz_path = os.path.join(app.root_path, 'templates', quiz_template)

    # Track user progress key
    progress_key = f"{course}_progress"
    email = session.get('email')

    # Load user progress
    current_progress = session.get(progress_key)
    if current_progress is None and email:
        current_progress = get_user_progress(email, course)  # Your function to load DB progress
        session[progress_key] = current_progress or 0

    # Prevent skipping lessons
    if lesson_number > (session.get(progress_key, 0) + 1):
        flash(f"❌ You must complete Lesson {session.get(progress_key, 0) + 1} first.", "danger")
        return redirect(url_for('access_course', course_name=course))

    # Handle quiz submission
    if request.method == 'POST':
        total = int(request.form.get("total", 0))
        score = 0
        feedback = []

        for i in range(total):
            user_ans = request.form.get(f"q{i}")
            correct_ans = request.form.get(f"correct{i}")

            if user_ans == correct_ans:
                score += 1
                feedback.append({
                    'q': i + 1,
                    'your_answer': user_ans,
                    'correct_answer': correct_ans,
                    'status': '✅ Correct'
                })
            else:
                feedback.append({
                    'q': i + 1,
                    'your_answer': user_ans or "No answer",
                    'correct_answer': correct_ans,
                    'status': '❌ Incorrect'
                })

        # Must pass ALL questions
        passed = score == total

        if passed:
            # Unlock next lesson
            if lesson_number > session[progress_key]:
                session[progress_key] = lesson_number
                if email:
                    save_user_progress(email, course, lesson_number)  # Save in DB

            flash("✅ Great job! You’ve passed the quiz. The next lesson is now unlocked.", "success")
            return redirect(url_for('access_course', course_name=course))

        else:
            flash("❌ You didn’t pass. Please rewatch the video and try again.", "danger")
            return render_template(quiz_template, lesson=lesson_number, course=course,
                                   score=score, total=total, passed=False, feedback=feedback)

    # Serve quiz page if file exists
    if os.path.exists(full_quiz_path):
        return render_template(quiz_template, lesson=lesson_number, course=course)

    return f"❌ Quiz for lesson {lesson_number} not found.", 404

# =====================
# NOTIFY STUDENT
# =====================
@app.route('/notify_student', methods=['POST'])
def notify_student():
    if "admin" not in session:
        flash("⚠️ Admin access required.", "warning")
        return redirect(url_for('admin_login'))

    email = request.form.get('email', '').strip().lower()
    message = request.form.get('message', '').strip()

    student = User.query.filter_by(email=email).first()
    if not student:
        flash("❌ Student not found", "danger")
        return redirect(url_for('admin_panel'))

    notif = Notification(user_id=student.id, message=message)
    db.session.add(notif)
    db.session.commit()

    flash(f"✅ Notification sent to {email}", "success")
    return redirect(url_for('admin_panel'))

# =====================
# ADMIN GENERATE CODE (Multi-Course with Dynamic Expiry)
# =====================
@app.route("/admin/generate-code", methods=["POST"])
def admin_generate_code():
    if "admin" not in session:
        flash("⚠️ Admin access required.", "warning")
        return redirect(url_for("admin_login"))

    # ✅ Get all selected courses from the form
    selected_courses = request.form.getlist("courses")  # multiple course slugs
    count = int(request.form.get("count", 1))

    # ✅ Get duration from form (either in days or months)
    paid_days = request.form.get("duration_days")
    paid_months = request.form.get("duration_months")

    if paid_days:
        try:
            duration_days = int(paid_days)
        except ValueError:
            duration_days = 30  # fallback
    elif paid_months:
        try:
            duration_days = int(paid_months) * 30
        except ValueError:
            duration_days = 30  # fallback
    else:
        duration_days = 30  # default if nothing provided

    if not selected_courses:
        flash("❌ Please select at least one course.", "danger")
        return redirect(url_for("admin_panel"))

    generated_codes = []

    for _ in range(count):
        # ✅ Generate a truly unique code (avoids UNIQUE constraint errors)
        timestamp = datetime.utcnow().strftime('%Y%m%d%H%M%S%f')
        code = f"ADM-{'-'.join(c.upper() for c in selected_courses)}-{timestamp}"

        # ✅ Calculate expiry based on payment duration
        expires_at = datetime.utcnow() + timedelta(days=duration_days)

        # ✅ Save the same code for each selected course
        for course in selected_courses:
            new_access = CourseAccessCode(
                code=code,
                course_slug=course,
                expires_at=expires_at,
                user_id=None
            )
            db.session.add(new_access)

        db.session.commit()
        generated_codes.append(code)

    flash(f"✅ Generated {len(generated_codes)} code(s) for {duration_days} days.", "success")

    # ✅ Pass back to the admin panel with generated codes
    return render_template(
        "admin_panel.html",
        courses=COURSES,
        codes=[{
            "code": c,
            "course": ', '.join(selected_courses),
            "expires": expires_at.strftime("%Y-%m-%d")
        } for c in generated_codes]
    )


# =====================
# TRACK STUDENT PROGRESS (Shows a Page)
# =====================
@app.route("/track-progress", methods=["POST"])
def track_student_progress():
    if "admin" not in session:
        flash("⚠️ Admin access required.", "warning")
        return redirect(url_for("admin_login"))

    email = request.form.get("email", "").strip().lower()
    if not email:
        flash("❌ Please provide an email address.", "danger")
        return redirect(url_for("admin_panel"))

    # Get student
    student = User.query.filter_by(email=email).first()
    if not student:
        flash("❌ Student not found.", "danger")
        return redirect(url_for("admin_panel"))

    # Get student progress
    progress_data = StudentProgress.query.filter_by(user_id=student.id).all()

    if not progress_data:
        flash(f"⚠️ No progress data found for {email}.", "warning")
        return redirect(url_for("admin_panel"))

    # Send to template
    return render_template("student_progress.html", student=student, progress_data=progress_data)

# =====================
# ADMIN RENEWAL NOTIFY (With Expiry Date)
# =====================
@app.route('/renewal_notify', methods=['POST'])
def renewal_notify():
    if "admin" not in session:
        flash("⚠️ Admin access required.", "warning")
        return redirect(url_for("admin_login"))

    email = request.form.get("email", "").strip().lower()
    course_code = request.form.get("course", "").strip()
    custom_message = request.form.get("message", "").strip()

    if not email or not course_code:
        flash("❌ Missing email or course", "danger")
        return redirect(url_for("admin_panel"))

    # Find student
    student = User.query.filter_by(email=email).first()
    if not student:
        flash(f"❌ No student found with email {email}", "danger")
        return redirect(url_for("admin_panel"))

    # Find course access
    access = CourseAccessCode.query.filter_by(user_id=student.id, course_slug=course_code).first()
    if not access:
        flash(f"⚠️ {email} does not have active access to {course_code}", "warning")
        return redirect(url_for("admin_panel"))

    # Format expiry date
    expiry_str = access.expires_at.strftime("%Y-%m-%d")
    days_left = (access.expires_at - datetime.utcnow()).days

    # Build message
    message = (
        f"🔔 Renewal Notice for {course_code.upper()}:\n"
        f"Your current access expires on {expiry_str} "
        f"({days_left} days remaining).\n"
    )
    if custom_message:
        message += f"\n{custom_message}"

    # Save notification
    notif = Notification(user_id=student.id, message=message)
    db.session.add(notif)
    db.session.commit()

    flash(f"✅ Renewal notification sent to {email} (expires {expiry_str})", "success")
    return redirect(url_for("admin_panel"))

# =====================
# ADMIN ENROLL STUDENT
# =====================
@app.route("/admin/enroll-student", methods=["POST"])
def enroll_student():
    if "admin" not in session:
        flash("⚠️ Admin access required.", "warning")
        return redirect(url_for("admin_login"))

    email = request.form.get("email").strip().lower()
    course_code = request.form.get("course")

    if not email or not course_code:
        flash("❌ Missing enrollment information", "danger")
        return redirect(url_for("admin_panel"))

    student = User.query.filter_by(email=email).first()
    if not student:
        flash(f"❌ No student found with email {email}", "danger")
        return redirect(url_for("admin_panel"))

    existing_access = CourseAccessCode.query.filter_by(user_id=student.id, course_slug=course_code).first()
    if existing_access:
        flash(f"⚠️ {email} is already enrolled in {course_code}", "warning")
        return redirect(url_for("admin_panel"))

    new_access = CourseAccessCode(
        code=f"ADMIN-{course_code.upper()}-{datetime.utcnow().strftime('%Y%m%d%H%M%S')}",
        course_slug=course_code,
        expires_at=datetime.utcnow() + timedelta(days=30),
        user_id=student.id
    )

    db.session.add(new_access)
    db.session.commit()

    flash(f"✅ {email} successfully enrolled in {course_code} (valid 30 days)", "success")
    return redirect(url_for("admin_panel"))
# =====================
# ADMIN UPLOAD CERTIFICATE (Dashboard)
# =====================
@app.route("/admin/upload-certificate", methods=["POST"])
def upload_certificate():
    if not session.get("admin"):
        return redirect("/admin-secret-login-2025")

    # Get form data
    email = request.form.get("email", "").strip().lower()
    course_slug = request.form.get("course", "").strip().lower()
    file = request.files.get("certificate")

    # Validate student exists
    student = User.query.filter_by(email=email).first()
    if not student:
        flash("❌ Student not found.", "danger")
        return redirect(url_for("admin_panel"))

    # Validate file
    if not file or file.filename == "":
        flash("❌ Please select a certificate file.", "danger")
        return redirect(url_for("admin_panel"))

    if not file.filename.lower().endswith((".pdf", ".png", ".jpg", ".jpeg")):
        flash("❌ Invalid file format. Please upload PDF or image.", "danger")
        return redirect(url_for("admin_panel"))

    # Ensure folder exists
    os.makedirs(CERTIFICATE_FOLDER, exist_ok=True)

    # Save file using email as filename
    filename = secure_filename(f"{email}_{course_slug}{os.path.splitext(file.filename)[1]}")
    save_path = os.path.join(CERTIFICATE_FOLDER, filename)
    file.save(save_path)

    # Save to database
    new_cert = Certificate(
        user_id=student.id,
        title=f"Certificate for {student.name}",
        course_slug=course_slug,
        file_url=f"static/uploads/certificates/{filename}"
    )
    db.session.add(new_cert)
    db.session.commit()

    flash(f"✅ Certificate uploaded for {student.name} ({email}).", "success")
    return redirect(url_for("admin_panel"))

# =====================
# VIDEO MANAGER
# =====================
@app.route("/admin/video-manager", methods=["GET", "POST"])
def video_manager():
    if "admin" not in session:
        flash("⚠️ Admin access required.", "warning")
        return redirect(url_for("admin_login"))

    selected_course = request.args.get("course")  # Course selection from dropdown

    if request.method == "POST":
        course_slug = request.form.get("course_slug")
        title = request.form.get("title")
        youtube_url = request.form.get("youtube_url")
        file = request.files.get("video_file")

        if not course_slug:
            flash("❌ Please select a course.", "danger")
            return redirect(url_for("video_manager", course=selected_course))

        if youtube_url:
            # Save YouTube video
            new_video = CourseVideo(
                course_slug=course_slug,
                title=title,
                video_url=youtube_url,
                is_youtube=True
            )
            db.session.add(new_video)
            db.session.commit()
            flash("✅ YouTube video added successfully!", "success")

        elif file and allowed_file(file.filename):
            # Save uploaded file
            filename = secure_filename(file.filename)
            save_path = os.path.join(app.config["UPLOAD_FOLDER"], filename)
            file.save(save_path)
            file_url = f"/{app.config['UPLOAD_FOLDER']}/{filename}"

            new_video = CourseVideo(
                course_slug=course_slug,
                title=title,
                video_url=file_url,
                is_youtube=False
            )
            db.session.add(new_video)
            db.session.commit()
            flash("✅ Local video uploaded successfully!", "success")
        else:
            flash("❌ Please provide a YouTube link or upload a valid video file.", "danger")

        return redirect(url_for("video_manager", course=course_slug))

    # Show videos for selected course
    videos = []
    if selected_course:
        videos = CourseVideo.query.filter_by(course_slug=selected_course).all()

    # Pass courses as a list of {slug, name} for dropdown
    course_list = [{"slug": slug, "name": name} for slug, name in COURSES.items()]

    return render_template(
        "video_manager.html",
        courses=course_list,
        selected_course=selected_course,
        videos=videos
    )


# =====================
# DELETE VIDEO
# =====================
@app.route("/admin/delete-video/<int:video_id>", methods=["POST"])
def delete_video(video_id):
    if "admin" not in session:
        flash("⚠️ Admin access required.", "warning")
        return redirect(url_for("admin_login"))

    video = CourseVideo.query.get(video_id)
    if video:
        if not video.is_youtube:
            # Remove local file if it exists
            file_path = video.video_url.lstrip("/")
            if os.path.exists(file_path):
                os.remove(file_path)
        db.session.delete(video)
        db.session.commit()
        flash("✅ Video deleted successfully!", "success")
    else:
        flash("❌ Video not found.", "danger")

    return redirect(url_for("video_manager", course=video.course_slug if video else None))


# =====================
# ADMIN REMOVE STUDENT
# =====================
@app.route("/admin/remove-student", methods=["POST"])
def remove_student():
    if "admin" not in session:
        flash("⚠️ Admin access required.", "warning")
        return redirect(url_for("admin_login"))

    email = request.form.get("email", "").strip().lower()
    course_code = request.form.get("course", "").strip()

    if not email or not course_code:
        flash("❌ Missing student email or course", "danger")
        return redirect(url_for("admin_panel"))

    student = User.query.filter_by(email=email).first()
    if not student:
        flash(f"❌ No student found with email {email}", "danger")
        return redirect(url_for("admin_panel"))

    # Find and delete the course access record
    access = CourseAccessCode.query.filter_by(user_id=student.id, course_slug=course_code).first()
    if not access:
        flash(f"⚠️ {email} is not enrolled in {course_code}", "warning")
        return redirect(url_for("admin_panel"))

    db.session.delete(access)
    db.session.commit()

    flash(f"✅ Removed {email} from {course_code} successfully", "success")
    return redirect(url_for("admin_panel"))

# =====================
# MANAGE USERS - Search & View Courses
# =====================
@app.route("/manage-users", methods=["POST"])
def manage_users():
    if "admin" not in session:
        flash("⚠️ Admin access required.", "warning")
        return redirect(url_for("admin_login"))

    query = request.form.get("query", "").strip().lower()
    if not query:
        flash("❌ Please enter a username or email.", "danger")
        return redirect(url_for("admin_panel"))

    # Search only by email
    student = User.query.filter(User.email.ilike(f"%{query}%")).first()

    if not student:
        flash(f"❌ No user found matching '{query}'.", "danger")
        return redirect(url_for("admin_panel"))

    # Instead of StudentProgress, show course codes
    access_codes = CourseAccessCode.query.filter_by(user_id=student.id).all()

    return render_template(
        "manage_user.html",
        student=student,
        access_codes=access_codes
    )

# =====================
# ADMIN PANEL
# =====================
@app.route("/admin-panel")
def admin_panel():
    if "admin" not in session:
        flash("⚠️ Admin access required.", "warning")
        return redirect(url_for("admin_login"))
    
    return render_template("admin_panel.html", courses=COURSES)

# =====================
# ADMIN LOGIN
# =====================
@app.route("/admin-login", methods=["GET", "POST"])
def admin_login():
    if request.method == "POST":
        username = request.form.get("username")
        password = request.form.get("password")
        if username == ADMIN_USERNAME and password == ADMIN_PASSWORD:
            session["admin"] = True
            flash("✅ Admin login successful", "success")
            return redirect(url_for("admin_panel"))
        else:
            flash("❌ Invalid admin credentials", "danger")
    return render_template("admin_login.html")

# =====================
# LOGOUT
# =====================
@app.route("/logout")
def logout():
    session.clear()
    flash("✅ Logged out successfully", "success")
    return redirect(url_for("index"))

# =====================
# MAIN
# =====================
if __name__ == "__main__":
    with app.app_context():
        db.create_all()
    app.run(debug=True)
