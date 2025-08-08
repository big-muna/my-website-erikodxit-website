from flask import Flask, request, redirect, render_template, session, url_for, flash
from flask_mail import Mail, Message
from flask_sqlalchemy import SQLAlchemy
from werkzeug.utils import secure_filename
from werkzeug.security import generate_password_hash, check_password_hash
from datetime import datetime, timedelta
import os
import csv

# =====================================
# ✅ Flask App Initialization
# =====================================
app = Flask(__name__)
app.secret_key = 'super-secret-key'

# =====================================
# ✅ Upload Folders
# =====================================
VIDEO_FOLDER = 'static/uploads/videos'
CERT_FOLDER = 'static/certificates'
os.makedirs(VIDEO_FOLDER, exist_ok=True)
os.makedirs(CERT_FOLDER, exist_ok=True)
app.config['UPLOAD_FOLDER'] = VIDEO_FOLDER

# =====================================
# ✅ Database Configuration
# =====================================
app.config['SQLALCHEMY_DATABASE_URI'] = "postgresql://erikodxit_db_user:qVGnuLYV2FAgFnXcAqq4Fw8nKLqub4Pb@dpg-d24v9nili9vc73eo9he0-a.frankfurt-postgres.render.com/erikodxit_db"
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False


if os.environ.get("FLASK_ENV") == "production":
    app.config['SQLALCHEMY_DATABASE_URI'] = "postgresql://erikodxit_db_user:qVGnuLYV2FAgFnXcAqq4Fw8nKLqub4Pb@dpg-d24v9nili9vc73eo9he0-a.frankfurt-postgres.render.com/erikodxit_db"
else:
    app.config['SQLALCHEMY_DATABASE_URI'] = "sqlite:///local.db"

# =====================================
# ✅ Import models and initialize DB
# =====================================
from models import db, Course, Video, Student, Enrollment  # make sure models.py defines db = SQLAlchemy()

db.init_app(app)

# Only create tables once (avoid repeated drop_all!)
with app.app_context():
    db.create_all()

# =====================================
# ✅ Mail Configuration
# =====================================
app.config['MAIL_SERVER'] = 'smtp.gmail.com'
app.config['MAIL_PORT'] = 587
app.config['MAIL_USE_TLS'] = True
app.config['MAIL_USERNAME'] = 'your_email@gmail.com'       # Replace this
app.config['MAIL_PASSWORD'] = 'your_app_password'          # Use Gmail App Password
app.config['MAIL_DEFAULT_SENDER'] = app.config['MAIL_USERNAME']
mail = Mail(app)

# =====================================
# ✅ Course Setup
# =====================================
COURSES = {
    'ai': 'AI',
    'data-analysis': 'DA',
    'ml': 'ML',
    'viz': 'DV',
    'ai-projects': 'PR'
}
COURSE_MAP = {v.upper(): k for k, v in COURSES.items()}
VALID_COURSES = list(COURSES.keys())
COURSE_ALIAS = {
    'AI': 'ai',
    'DA': 'data-analysis',
    'ML': 'ml',
    'DV': 'viz',
    'PR': 'ai-projects'
}

ADMIN_USERNAME = 'bigjoe'
ADMIN_PASSWORD = 'mypass2025'

# =====================================
# ✅ Initial Course Entries
# =====================================
with app.app_context():
    if Course.query.count() == 0:  # Prevent duplicates
        db.session.add(Course(name="AI"))
        db.session.add(Course(name="AI Project"))
        db.session.add(Course(name="Data Analysis"))
        db.session.add(Course(name="Data Visualization"))
        db.session.add(Course(name="Machine Learning"))
        db.session.commit()

# =====================================
# ✅ File Paths
# =====================================
BASE_DIR = os.path.abspath(os.path.dirname(__file__))
CSV_FILE = os.path.join(BASE_DIR, 'your_file.csv')
ASSIGNED_FILE = os.path.join(BASE_DIR, 'assigned.csv')
PROGRESS_FILE = 'user_progress.txt'

# =====================================
# ✅ Utility Functions
# =====================================
def normalize_courses_field(raw_value: str):
    if not raw_value:
        return []
    raw_value = raw_value.replace('"', '').replace(' ', '')
    parts = [p for p in raw_value.replace('-', ',').split(',') if p]

    normalized = []
    for p in parts:
        up = p.upper()
        if up in COURSE_ALIAS:
            normalized.append(COURSE_ALIAS[up])
        elif p.lower() in VALID_COURSES:
            normalized.append(p.lower())

    seen = set()
    result = []
    for c in normalized:
        if c not in seen:
            seen.add(c)
            result.append(c)
    return result

def get_progress_key(course: str) -> str:
    return f"progress_{course}"

def save_user_progress(email: str, course: str, lesson_number: int):
    try:
        with open(PROGRESS_FILE, 'a') as f:
            f.write(f"{email},{course},{lesson_number}\n")
    except Exception as e:
        print("save_user_progress error:", e)

def get_user_progress(email, course):
    try:
        with open(PROGRESS_FILE, 'r') as f:
            for line in reversed(f.readlines()):
                e, c, l = line.strip().split(',')
                if e == email and c == course:
                    return int(l)
    except Exception:
        pass
    return 0

def find_valid_code(code):
    code = code.strip().upper()
    updated_rows = []
    found = False
    unlocked_courses = []

    try:
        with open(ASSIGNED_FILE, newline='') as f:
            reader = csv.DictReader(f)
            for row in reader:
                row_code = row.get('code', '').strip().upper()
                row_course = row.get('course', '').strip()
                row_expires = (row.get('expires') or '').strip()

                if row_code == code and not row_expires:
                    found = True
                    unlocked_courses = normalize_courses_field(row_course)
                    row['expires'] = datetime.now().isoformat()
                updated_rows.append(row)
    except FileNotFoundError:
        return None

    if found:
        with open(ASSIGNED_FILE, 'w', newline='') as f:
            fieldnames = ['code', 'course', 'expires']
            writer = csv.DictWriter(f, fieldnames=fieldnames)
            writer.writeheader()
            writer.writerows(updated_rows)
        return unlocked_courses

    return None

def _csv_filter_out(path, key_col, key_value_lower):
    try:
        with open(path, 'r', newline='') as f:
            reader = csv.reader(f)
            rows = list(reader)
        if not rows: 
            return
        header, *data = rows
        kept = [header] + [r for r in data if r and r[key_col].strip().lower() != key_value_lower]
        with open(path, 'w', newline='') as f:
            writer = csv.writer(f)
            writer.writerows(kept)
    except FileNotFoundError:
        pass

def get_unused_code(course_key):
    return db.session.query(GeneratedCode).filter_by(course=course_key, used=False).first()

def mark_code_as_used(code_obj):
    code_obj.used = True
    db.session.commit()

def save_generated_code(course_key, code):
    new_code = GeneratedCode(code=code, used=True, course=course_key)
    db.session.add(new_code)
    db.session.commit()

# =====================================
# ✅ Routes
# =====================================
@app.route('/video-manager')
def video_manager():
    return render_template('video_manager.html')

@app.route('/ask-question', methods=['GET', 'POST'])
def ask_question():
    if request.method == 'POST':
        student_email = request.form.get('email')
        question = request.form.get('question')

        # Save question to file
        with open("questions.txt", "a") as f:
            f.write(f"{datetime.now()} - {student_email}: {question}\n")

        # Email instructor
        msg = Message(
            subject="New Student Question",
            recipients=['instructor_email@example.com'],
            body=f"From: {student_email}\n\nQuestion:\n{question}"
        )

        try:
            mail.send(msg)
            flash('Your question has been sent successfully!', 'success')
        except Exception as e:
            flash('Failed to send your question. Please try again later.', 'danger')
            print("Email error:", e)

        return redirect(url_for('ask_question'))

    return render_template('ask_question.html')

# -----------------------------------------
# ✅ Routes
# -----------------------------------------
@app.route('/')
@app.route('/home')
def index():
    return render_template('index.html')

@app.route('/about')
def about():
    return render_template('about.html')

@app.route('/contact')
def contact():
    return render_template('contact.html')

@app.route('/courses')
def show_courses():
    user = session.get('user')
    user_courses = session.get('courses', [])
    return render_template('courses.html', user=user, user_courses=user_courses)

# -----------------------------------------
# ✅ Register Route
# -----------------------------------------
@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        name     = request.form.get('name', '').strip()
        email    = request.form.get('email', '').strip().lower()
        password = request.form.get('password', '')
        reg_code = request.form.get('reg_code', '').strip().upper()

        if not all([name, email, password, reg_code]):
            flash("Please fill in all the fields.", "warning")
            return render_template('register.html')

        if Student.query.filter_by(email=email).first():
            flash("Email is already registered.", "danger")
            return render_template('register.html')

        try:
            unlocked_courses = find_valid_code(reg_code)
        except Exception as e:
            flash("Something went wrong validating your code.", "danger")
            return render_template('register.html')

        if not unlocked_courses:
            flash("Invalid or already used registration code.", "danger")
            return render_template('register.html')

        if isinstance(unlocked_courses, str):
            unlocked_courses = [c.strip() for c in unlocked_courses.split(',') if c.strip()]

        expiry_date = datetime.now().replace(microsecond=0)
        expiry_date += timedelta(days=30 if reg_code == 'FREE30' else 7)

        try:
            hashed_password = generate_password_hash(password)
            new_student = Student(
                name=name,
                email=email,
                password=hashed_password,
                reg_code=reg_code,
                expiry_date=expiry_date.isoformat(),
                course=",".join(unlocked_courses),
                completed_lessons=0,
                quizzes_passed=0
            )
            db.session.add(new_student)
            db.session.commit()

            return render_template('register_success.html', email=email, courses=unlocked_courses)

        except Exception:
            db.session.rollback()
            flash('An error occurred during registration.', 'danger')

    return render_template('register.html')

@app.route('/register-success')
def register_success():
    email = session.pop('just_registered_email', None)
    courses = session.pop('just_registered_courses', [])
    return render_template('register_success.html', email=email, courses=courses)

# -----------------------------------------
# ✅ Login Route
# -----------------------------------------
@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        email    = request.form.get('email', '').strip().lower()
        password = request.form.get('password', '')
        reg_code = request.form.get('reg_code', '').strip().upper()

        if not all([email, password, reg_code]):
            flash("Please fill in all fields.", "warning")
            return redirect('/login')

        user = Student.query.filter_by(email=email, reg_code=reg_code).first()

        if user and check_password_hash(user.password, password):
            try:
                expiry = datetime.fromisoformat(user.expiry_date)
                if datetime.now() > expiry:
                    flash("Account expired. Please renew your registration code.", "warning")
                    return redirect('/login')
            except ValueError:
                flash("Invalid expiry date format for this account.", "danger")
                return redirect('/login')

            unlocked_courses = normalize_courses_field(user.course)

            session['user'] = {
                'id': user.id,
                'name': user.name,
                'email': user.email,
                'course': user.course
            }
            session['courses'] = unlocked_courses

            return redirect('/dashboard')

        flash('Invalid login credentials.', 'danger')

    return render_template('login.html')

@app.route('/dashboard')
def dashboard():
    if 'user' in session:
        return render_template('dashboard.html',
                               user=session['user'],
                               user_courses=session.get('courses', []))
    return redirect('/login')

@app.route('/logout')
def logout():
    session.clear()
    return redirect('/')

@app.route('/buy-course/<course>')
def buy_course(course):
    if 'user' not in session:
        return redirect('/login')

    if course not in VALID_COURSES:
        return "❌ Invalid course name.", 400

    if 'courses' not in session:
        session['courses'] = []

    if course not in session['courses']:
        session['courses'].append(course)
        session[get_progress_key(course)] = 0

    return redirect('/dashboard')

@app.route('/courses/<course_name>')
def access_course(course_name):
    template_map = {
        'ai': 'courses/ai.html',
        'data-analysis': 'courses/data-analysis.html',
        'ml': 'courses/ml.html',
        'viz': 'courses/data-viz.html',
        'ai-projects': 'courses/ai-projects.html'
    }

    if 'user' not in session:
        return redirect('/login')

    if course_name not in session.get('courses', []):
        return "❌ Access denied. You are not authorized for this course.", 403

    template = template_map.get(course_name)
    full_template_path = os.path.join(app.root_path, 'templates', template) if template else None

    if template and os.path.exists(full_template_path):
        email = session['user']['email']
        progress_key = get_progress_key(course_name)
        current_progress = get_user_progress(email, course_name)
        session[progress_key] = current_progress
        return render_template(template,
                               user=session['user'],
                               progress=current_progress,
                               course=course_name)

    return f"⚠️ Template for '{course_name}' not found.", 500

@app.route('/collect-certificate', methods=['GET', 'POST'])
def collect_certificate():
    if request.method == 'POST':
        email = request.form.get('email', '').strip()
        course = request.form.get('course', '').strip().lower()
        cert_path = None

        with open(ASSIGNED_FILE, newline='') as file:
            reader = csv.DictReader(file)
            for row in reader:
                if row['Email'].strip().lower() == email and row['Course'].strip().lower() == course:
                    cert_path = row['Certificate'].strip()
                    break

        if cert_path:
            return render_template('certificate_found.html', cert_image=cert_path)
        else:
            return render_template('collect_certificate.html',
                                   error="❌ No certificate found for this email and course.")

    return render_template('collect_certificate.html')

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

# =====================================
# QUIZ SYSTEM
# =====================================
@app.route('/quiz/<course>/<int:lesson_number>', methods=['GET', 'POST'])
def quiz(course, lesson_number):
    if 'user' not in session or course not in session.get('courses', []):
        return redirect('/login')

    quiz_template = f'quizzes/{course}_quiz{lesson_number}.html'
    full_quiz_path = os.path.join(app.root_path, 'templates', quiz_template)
    progress_key = get_progress_key(course)
    email = session.get('email')

    # Load progress
    current_progress = session.get(progress_key)
    if current_progress is None and email:
        current_progress = get_user_progress(email, course)
        session[progress_key] = current_progress

    # Check lesson access
    if lesson_number > session.get(progress_key, 0) + 1:
        flash(f"❌ You must complete Lesson {session[progress_key] + 1} first.", "error")
        return redirect(url_for('access_course', course_name=course))

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

        passed = score == total

        if passed:
            if lesson_number > session[progress_key]:
                session[progress_key] = lesson_number
                if email:
                    save_user_progress(email, course, lesson_number)
            flash("✅ Great job! You’ve passed the quiz. The next lesson is now unlocked.", "success")
            return redirect(url_for('access_course', course_name=course))
        else:
            flash("❌ You didn’t pass. Please rewatch the video and try again.", "error")
            return render_template(quiz_template, lesson=lesson_number, course=course,
                                   score=score, total=total, passed=False, feedback=feedback)

    if os.path.exists(full_quiz_path):
        return render_template(quiz_template, lesson=lesson_number, course=course)

    return f"❌ Quiz for lesson {lesson_number} not found.", 404


# =====================================
# ADMIN FORM-BASED CERTIFICATE UPLOAD
# =====================================
@app.route('/admin/upload-certificate', methods=['GET', 'POST'])
def upload_certificate():
    if request.method == 'POST':
        name = request.form.get('name', '').strip()
        email = request.form.get('email', '').strip().lower()
        file = request.files.get('certificate')

        if file and file.filename.endswith('.pdf'):
            filename = f"{email}.pdf"
            save_path = os.path.join(UPLOAD_FOLDER, filename)
            os.makedirs(UPLOAD_FOLDER, exist_ok=True)
            file.save(save_path)

            # Save record to CSV
            os.makedirs(os.path.dirname(CSV_FILE), exist_ok=True)
            with open(CSV_FILE, 'a', newline='') as csvfile:
                writer = csv.writer(csvfile)
                writer.writerow([email, name, datetime.now().strftime("%Y-%m-%d")])

            flash('✅ Certificate uploaded and assigned successfully.')
            return redirect('/admin/upload-certificate')
        else:
            flash('❌ Invalid file format. Please upload a PDF.')

    return render_template('upload_certificate.html')

# =====================================
# BACKEND PANEL CERTIFICATE UPLOAD
# =====================================
@app.route('/admin-upload-certificate', methods=['POST'])
def admin_upload_certificate():
    if not session.get('admin'):
        return redirect('/admin-secret-login-2025')

    username = request.form.get('username', '').strip().lower()
    cert_file = request.files.get('certificate')

    if cert_file and cert_file.filename.endswith('.pdf'):
        save_path = os.path.join(UPLOAD_FOLDER, f"{username}.pdf")
        os.makedirs(UPLOAD_FOLDER, exist_ok=True)
        cert_file.save(save_path)

        # Log certificate assignment
        with open(CSV_FILE, 'a', newline='') as f:
            writer = csv.writer(f)
            writer.writerow([username, '', datetime.now().strftime("%Y-%m-%d")])

        flash(f"✅ Certificate uploaded for {username}")
    else:
        flash("❌ Upload failed: Only PDF files are allowed.")

    return redirect('/admin-secret-panel-2025')


# =====================================
# STUDENT CERTIFICATE LOOKUP
# =====================================
@app.route('/certificate')
def show_certificate_page():
    return render_template('certificate.html')


@app.route('/check_certificate', methods=['POST'])
def check_certificate():
    data = request.get_json()
    user_input = data.get('input', '').strip().lower()

    found = False
    cert_filename = None

    try:
        with open(CSV_FILE, 'r') as file:
            reader = csv.reader(file)
            for row in reader:
                if user_input in [cell.strip().lower() for cell in row]:
                    found = True
                    cert_filename = f"{row[0].strip().lower()}.pdf"
                    break
    except FileNotFoundError:
        return jsonify({'status': 'nocsv'})  # CSV not found

    if found:
        cert_path = os.path.join(UPLOAD_FOLDER, cert_filename)
        if os.path.exists(cert_path):
            return jsonify({'status': 'success', 'filename': cert_filename})
        else:
            return jsonify({'status': 'nofile'})  # CSV entry found but file missing
    else:
        return jsonify({'status': 'notcompleted'})  # Not found in CSV


# =====================================
# SERVE CERTIFICATE FILE
# =====================================
@app.route('/certificates/<filename>')
def download_certificate(filename):
    return send_from_directory(UPLOAD_FOLDER, filename)


# =====================================
# MATERIAL SYSTEM
# =====================================
@app.route('/learning-materials/<course>/<int:lesson_number>')
def learning_materials(course, lesson_number):
    if 'user' not in session or course not in session.get('courses', []):
        return redirect('/login')

    # Path to lesson snippet (e.g., materials/snippets/ai_lesson1.html)
    content_template = f'materials/snippets/{course}_lesson{lesson_number}.html'
    full_material_path = os.path.join(app.root_path, 'templates', content_template)

    if os.path.exists(full_material_path):
        return render_template(
            'learning-material.html',
            content_template=content_template,
            lesson=lesson_number,
            course=course
        )

    return f"❌ Notes for lesson {lesson_number} not found.", 404


# =====================================
# ADMIN ROUTES
# =====================================
@app.route('/admin')
def admin_redirect():
    return redirect('/admin-secret-login-2025')


@app.route('/admin-secret-login-2025', methods=['GET', 'POST'])
def admin_login():
    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')
        if username == ADMIN_USERNAME and password == ADMIN_PASSWORD:
            session['admin'] = True
            return redirect('/admin-secret-panel-2025')
        flash("❌ Invalid admin credentials")
    return render_template('admin_login.html')


@app.route('/admin-secret-panel-2025', methods=['GET', 'POST'])
def admin_panel():
    if not session.get('admin'):
        return redirect('/admin-secret-login-2025')

    generated_codes = []
    selected_courses = []
    count = 1

    if request.method == 'POST':
        action = request.form.get('action')

        if action == 'generate_code':
            selected_courses = request.form.getlist('courses')
            count = int(request.form.get('count', 1))

            for course_key in selected_courses:
                for _ in range(count):
                    code = get_unused_code(course_key)
                    if code:
                        mark_code_as_used(code)
                        generated_codes.append(code.code)
                    else:
                        new_code = secrets.token_hex(4).upper()
                        save_generated_code(course_key, new_code)
                        generated_codes.append(new_code)

    return render_template(
        'admin_panel.html',
        courses=COURSES,
        codes=generated_codes,
        selected=selected_courses,
        count=count
    )


# =====================================
# VIDEO MANAGER
# =====================================
@app.route('/admin/video-manager', methods=['GET', 'POST'])
def video_manager_page():
    courses = Course.query.all()
    selected_course = None
    videos = []

    course_id = request.args.get('course_id')
    if course_id:
        try:
            selected_course = Course.query.get(int(course_id))
            if selected_course:
                videos = Video.query.filter_by(course_id=selected_course.id).all()
            else:
                flash("❌ Selected course not found.", "warning")
        except (ValueError, TypeError):
            flash("❌ Invalid course ID.", "danger")
            return redirect(url_for('video_manager_page'))

    return render_template(
        'video_manager.html',
        courses=courses,
        selected_course=selected_course,
        videos=videos
    )


@app.route('/admin/upload-video/<int:course_id>', methods=['POST'])
def upload_video(course_id):
    course = Course.query.get_or_404(course_id)
    title = request.form.get('title')
    description = request.form.get('description')
    source_type = request.form.get('source_type')  # 'file' or 'url'

    if source_type == 'file':
        file = request.files.get('file')
        if file and file.filename != '':
            filename = secure_filename(file.filename)
            filepath = os.path.join(app.config['UPLOAD_FOLDER'], filename)
            file.save(filepath)
            video = Video(title=title, filename=filename, description=description, course_id=course.id)
            db.session.add(video)
            db.session.commit()
            flash('✅ Video uploaded from file.', 'success')
        else:
            flash('❌ No video file selected.', 'danger')

    elif source_type == 'url':
        video_url = request.form.get('video_url')
        if video_url:
            video = Video(title=title, filename=video_url, description=description, course_id=course.id)
            db.session.add(video)
            db.session.commit()
            flash('✅ Video linked from URL.', 'success')
        else:
            flash('❌ No URL provided.', 'danger')

    else:
        flash('❌ Invalid source type.', 'danger')

    return redirect(url_for('video_manager_page', course_id=course.id))


@app.route('/admin/delete-video/<int:video_id>', methods=['POST'])
def delete_video(video_id):
    video = Video.query.get_or_404(video_id)
    course_id = video.course_id

    # If it's a file path, attempt deletion
    if not video.filename.startswith('http'):
        file_path = os.path.join(app.config['UPLOAD_FOLDER'], video.filename)
        if os.path.exists(file_path):
            os.remove(file_path)

    db.session.delete(video)
    db.session.commit()
    flash('✅ Video deleted.', 'success')

    return redirect(url_for('video_manager_page', course_id=course_id))

# =====================================
# ENROLL STUDENT
# =====================================
@app.route('/enroll', methods=['POST'])
def enroll_student():
    email = request.form.get('email', '').strip().lower()
    course_raw = request.form.get('course', '').strip()
    course_title = normalize_course(course_raw)

    if not email or not course_title:
        flash("❌ Missing or invalid enrollment info.", "danger")
        return redirect('/admin-secret-panel-2025')

    try:
        student = Student.query.filter_by(email=email).first()
        if not student:
            flash("❌ Student not found.", "danger")
            return redirect('/admin-secret-panel-2025')

        existing_enrollment = Enrollment.query.filter_by(student_id=student.id, course=course_title).first()
        if existing_enrollment:
            flash("⚠️ This student is already enrolled in that course.", "warning")
            return redirect('/admin-secret-panel-2025')

        new_enrollment = Enrollment(student_id=student.id, course=course_title)
        db.session.add(new_enrollment)
        db.session.commit()
        flash("✅ Student enrolled successfully", "success")

    except Exception as e:
        db.session.rollback()
        flash(f"❌ Error enrolling student: {str(e)}", "danger")

    return redirect('/admin-secret-panel-2025')


# =====================================
# REMOVE STUDENT FROM CSV
# =====================================
@app.route('/remove-student', methods=['POST'])
def remove_student():
    email = request.form.get('email', '').strip().lower()
    if not email:
        flash("❌ Email required.")
        return redirect('/admin-secret-panel-2025')

    try:
        with open(USERS_CSV, 'r', newline='') as f:
            reader = csv.reader(f)
            rows = list(reader)
    except FileNotFoundError:
        flash("⚠️ No enrollment records found.")
        return redirect('/admin-secret-panel-2025')

    if not rows:
        flash("⚠️ No enrollment records.")
        return redirect('/admin-secret-panel-2025')

    header, *data_rows = rows
    kept = [header] + [r for r in data_rows if len(r) > 0 and r[0].strip().lower() != email]

    with open(USERS_CSV, 'w', newline='') as f:
        writer = csv.writer(f)
        writer.writerows(kept)

    flash(f"🗑️ {email} removed from enrollments.")
    return redirect('/admin-secret-panel-2025')


# =====================================
# TRACK PROGRESS
# =====================================
@app.route('/track-progress', methods=['POST'])
def track_progress():
    email = request.form.get('email', '').strip().lower()
    if not email:
        flash("❌ Email not provided.")
        return redirect(url_for('admin_panel'))

    progress_rows = []
    try:
        with open('students_progress.csv', 'r') as file:
            reader = csv.DictReader(file)
            for row in reader:
                if row['email'].lower() == email.lower():
                    progress_rows.append({
                        'course': row.get('course', 'N/A'),
                        'percent': row.get('percent', '0'),
                        'last_seen': row.get('last_seen', 'N/A'),
                        'updated_at': row.get('updated_at', 'N/A')
                    })
    except FileNotFoundError:
        flash("❌ Progress data not found.")
        return redirect(url_for('admin_panel'))

    if not progress_rows:
        flash("❌ No progress found for this email.")
        return redirect(url_for('admin_panel'))

    return render_template('admin_panel.html', courses=COURSES, progress_rows=progress_rows)


# =====================================
# NOTIFY STUDENT
# =====================================
@app.route('/notify', methods=['POST'])
def notify_student():
    email = request.form.get('email', '').strip().lower()
    message = request.form.get('message', '').strip()

    if not email:
        flash("❌ Email not provided.")
        return redirect('/admin-secret-panel-2025')

    enrolled = False
    try:
        with open(USERS_CSV, 'r') as f:
            reader = csv.DictReader(f)
            for row in reader:
                if row['email'].strip().lower() == email:
                    enrolled = True
                    break
    except FileNotFoundError:
        pass

    try:
        send_email(
            to=email,
            subject="Course Update / Completion",
            html_body=message or "<p>Congratulations! Your course status has been updated.</p>"
        )
        flash(f"📩 Notification sent to {email}." if enrolled else f"📩 Notification sent to {email} (note: not in enrollments).")
    except Exception as e:
        flash(f"❌ Could not send notification: {e}")

    return redirect('/admin-secret-panel-2025')


# =====================================
# RENEWAL REMINDER
# =====================================
@app.route('/renewal', methods=['POST'])
def renewal_notify():
    email = request.form.get('email', '').strip().lower()
    if not email:
        flash("❌ Email not provided.")
        return redirect('/admin-secret-panel-2025')

    enrolled = False
    try:
        with open(USERS_CSV, 'r') as f:
            reader = csv.DictReader(f)
            for row in reader:
                if row['email'].strip().lower() == email:
                    enrolled = True
                    break
    except FileNotFoundError:
        pass

    try:
        send_email(
            to=email,
            subject="Your subscription/course is expiring soon",
            html_body="""
                <p>Hi,</p>
                <p>Your plan/course is nearing its renewal date. Please log in to renew.</p>
                <p>Thanks!</p>
            """
        )
        flash(f"🔔 Renewal reminder sent to {email}." if enrolled else f"🔔 Reminder sent to {email} (not in enrollments).")
    except Exception as e:
        flash(f"❌ Could not send renewal reminder: {e}")

    return redirect('/admin-secret-panel-2025')


# =====================================
# ADMIN LOGOUT
# =====================================
@app.route('/admin-logout')
def admin_logout():
    session.pop('admin', None)
    return redirect('/admin-secret-login-2025')


def get_unused_code(course_key):
    """Retrieve an unused code from CSV_FILE for a specific course."""
    if not os.path.exists(CSV_FILE):
        return None
    with open(CSV_FILE, 'r') as file:
        reader = csv.DictReader(file)
        for row in reader:
            if row['course'].strip().lower() == course_key.strip().lower():
                return row
    return None

def mark_code_as_used(code_row):
    """Mark a code as used by moving it from CSV_FILE to ASSIGNED_FILE."""
    dir_path = os.path.dirname(ASSIGNED_FILE)
    if dir_path:
        os.makedirs(dir_path, exist_ok=True)

    # Append to ASSIGNED_FILE
    with open(ASSIGNED_FILE, 'a', newline='') as assigned:
        writer = csv.DictWriter(assigned, fieldnames=['code', 'course', 'expires'])
        if os.stat(ASSIGNED_FILE).st_size == 0:
            writer.writeheader()
        writer.writerow(code_row)

    # Remove from CSV_FILE
    with open(CSV_FILE, 'r') as f:
        rows = list(csv.DictReader(f))

    with open(CSV_FILE, 'w', newline='') as f:
        writer = csv.DictWriter(f, fieldnames=['code', 'course', 'expires'])
        writer.writeheader()
        for row in rows:
            if row['code'].strip() != code_row['code'].strip():
                writer.writerow(row)

def find_valid_code(code):
    """Search both CSV_FILE and ASSIGNED_FILE for a code and return the course name if found."""
    for file_path in [CSV_FILE, ASSIGNED_FILE]:
        if not os.path.exists(file_path):
            continue
        with open(file_path, "r") as f:
            reader = csv.DictReader(f)
            for row in reader:
                if row['code'].strip().upper() == code.strip().upper():
                    return row['course']
    return None

# =====================================
# RUN APP
# =====================================
if __name__ == '__main__':
    with app.app_context():
        try:
            db.create_all()  # Creates tables if not present

            # Add default courses if they don't exist
            default_courses = ["AI", "AI project", "Data analysis", "Data viz", "ml"]
            existing_courses = {course.name for course in Course.query.all()}
            for course_name in default_courses:
                if course_name not in existing_courses:
                    new_course = Course(name=course_name)
                    db.session.add(new_course)
            db.session.commit()
            print("✅ Default courses inserted (if not already present).")
        except Exception as e:
            print("❌ Error initializing database:", str(e))

    app.run(host='0.0.0.0', port=8000, debug=True)