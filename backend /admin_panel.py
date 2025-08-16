from flask import Flask, request, redirect, render_template, session, flash
import csv
import os
from datetime import datetime

app = Flask(__name__)
app.secret_key = 'super-secret-key'

# =============================
# Course Code Mappings
# =============================
COURSES = {
    'ai': 'AI',
    'data-analysis': 'DA',
    'ml': 'ML',
    'viz': 'DV',
    'ai-projects': 'PR'
}

CSV_FILE = 'code.csv'
ASSIGNED_FILE = 'assigned.csv'
STUDENT_FILE = 'students.csv'
CERTIFICATE_FILE = 'certificates.csv'
VIDEOS_FILE = 'videos.csv'
NOTIFY_FILE = 'notifications.csv'

# =============================
# Admin Credentials
# =============================
ADMIN_USERNAME = 'bigjoe'
ADMIN_PASSWORD = 'mypass2025'

# =============================
# Admin Login
# =============================
@app.route('/admin-login', methods=['GET', 'POST'])
def admin_login():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        if username == ADMIN_USERNAME and password == ADMIN_PASSWORD:
            session['admin'] = True
            return redirect('/admin-panel')
        else:
            flash("❌ Invalid admin credentials")
    return render_template('admin_login.html')


# =============================
# Admin Panel
# =============================
@app.route('/admin-panel', methods=['GET', 'POST'])
def admin_panel():
    if not session.get('admin'):
        return redirect('/admin-login')

    generated_codes = []
    selected_courses = []
    count = 1

    if request.method == 'POST':
        selected_courses = list(set(request.form.getlist('courses')))

        try:
            count = int(request.form.get('count', 1))
            if count < 1:
                count = 1
        except ValueError:
            flash("❗ Invalid count. Defaulting to 1.")
            count = 1

        if selected_courses:
            course_abbr = "-".join(COURSES[c] for c in selected_courses if c in COURSES)

            for _ in range(count):
                code_row = get_any_unused_code()
                if code_row:
                    base_code = code_row['code'].split('-')[-1]
                    full_code = f"{course_abbr}-{base_code}"
                    new_entry = {
                        'code': full_code,
                        'course': ",".join(COURSES[c] for c in selected_courses if c in COURSES),
                        'expires': code_row['expires']
                    }
                    mark_code_as_used(code_row)
                    save_combined_code(new_entry)
                    generated_codes.append(new_entry)
                else:
                    flash("⚠️ Not enough codes available.")
                    break
        else:
            flash("⚠️ Please select at least one course.")

    return render_template(
        'admin_panel.html',
        courses=COURSES,
        codes=generated_codes,
        selected=selected_courses,
        count=count
    )


# =============================
# Manage Students
# =============================
@app.route('/enroll-student', methods=['POST'])
def enroll_student():
    if not session.get('admin'):
        return redirect('/admin-login')

    name = request.form['name']
    email = request.form['email']
    course = request.form['course']
    with open(STUDENT_FILE, 'a', newline='') as file:
        writer = csv.writer(file)
        writer.writerow([name, email, course, "incomplete"])
    flash("✅ Student enrolled successfully!")
    return redirect('/admin-panel')


@app.route('/remove-student', methods=['POST'])
def remove_student():
    if not session.get('admin'):
        return redirect('/admin-login')

    email = request.form['email']
    rows = []
    with open(STUDENT_FILE, 'r') as file:
        reader = csv.reader(file)
        rows = [row for row in reader if row[1] != email]

    with open(STUDENT_FILE, 'w', newline='') as file:
        writer = csv.writer(file)
        writer.writerows(rows)

    send_notification(email, "❌ Your course access has expired. Please renew.")
    flash("🚫 Student removed and notified!")
    return redirect('/admin-panel')


# =============================
# Track Progress & Upload Certificate
# =============================
@app.route('/complete-course', methods=['POST'])
def complete_course():
    if not session.get('admin'):
        return redirect('/admin-login')

    email = request.form['email']
    course = request.form['course']

    updated = False
    students = []
    with open(STUDENT_FILE, 'r') as file:
        reader = csv.reader(file)
        for row in reader:
            if row[1] == email and row[2] == course:
                row[3] = 'completed'
                updated = True
            students.append(row)

    with open(STUDENT_FILE, 'w', newline='') as file:
        writer = csv.writer(file)
        writer.writerows(students)

    if updated:
        with open(CERTIFICATE_FILE, 'a', newline='') as certs:
            writer = csv.writer(certs)
            writer.writerow([email, course, datetime.now().strftime("%Y-%m-%d")])
        send_notification(email, f"🎉 You've completed {course.upper()}! Your certificate is ready.")
        flash("🎓 Certificate issued and student notified.")
    else:
        flash("⚠️ No matching student found.")
    return redirect('/admin-panel')


# =============================
# Add or Remove Videos
# =============================
@app.route('/video-manager', methods=['GET', 'POST'])
def video_manager():
    if not session.get('admin'):
        return redirect('/admin-login')

    selected_course = request.args.get('course_id')
    videos = []

    # Load all courses for dropdown
    course_list = [{'id': key, 'name': val} for key, val in COURSES.items()]

    # Load videos for selected course
    if selected_course:
        with open(VIDEOS_FILE, 'r') as f:
            reader = csv.reader(f)
            videos = [row for row in reader if row[1] == selected_course]

    return render_template(
        'video_manager.html',
        courses=course_list,
        selected_course=next((c for c in course_list if c['id'] == selected_course), None),
        videos=[{'title': v[0], 'filename': v[2], 'id': v[0]} for v in videos]
    )


@app.route('/upload-video/<course_id>', methods=['POST'])
def upload_video(course_id):
    if not session.get('admin'):
        return redirect('/admin-login')

    title = request.form['title']
    description = request.form.get('description', '')
    file = request.form['file']  # assuming it's a YouTube link or filename

    with open(VIDEOS_FILE, 'a', newline='') as f:
        writer = csv.writer(f)
        writer.writerow([title, course_id, file, description])
    flash("✅ Video uploaded successfully.")
    return redirect(f'/video-manager?course_id={course_id}')

@app.route('/delete-video/<course_id>/<video_id>', methods=['POST'])
def delete_video(course_id, video_id):
    if not session.get('admin'):
        return redirect('/admin-login')

    updated_videos = []

    with open(VIDEOS_FILE, 'r') as f:
        reader = csv.reader(f)
        for row in reader:
            if not (row[0] == video_id and row[1] == course_id):
                updated_videos.append(row)

    with open(VIDEOS_FILE, 'w', newline='') as f:
        writer = csv.writer(f)
        writer.writerows(updated_videos)

    flash("🗑️ Video deleted successfully.")
    return redirect(f'/video-manager?course_id={course_id}')


# =============================
# Send Notifications (CSV-based)
# =============================
def send_notification(email, message):
    with open(NOTIFY_FILE, 'a', newline='') as file:
        writer = csv.writer(file)
        writer.writerow([email, message, datetime.now().strftime("%Y-%m-%d %H:%M:%S")])


# =============================
# Get Unused Code
# =============================
def get_any_unused_code():
    if not os.path.exists(CSV_FILE):
        return None
    with open(CSV_FILE, 'r') as file:
        reader = csv.DictReader(file)
        for row in reader:
            return row
    return None


# =============================
# Save Generated Code
# =============================
def save_combined_code(code_row):
    dir_path = os.path.dirname(ASSIGNED_FILE)
    if dir_path:
        os.makedirs(dir_path, exist_ok=True)
    with open(ASSIGNED_FILE, 'a', newline='') as assigned:
        writer = csv.DictWriter(assigned, fieldnames=['code', 'course', 'expires'])
        if os.stat(ASSIGNED_FILE).st_size == 0:
            writer.writeheader()
        writer.writerow(code_row)


# =============================
# Mark Code as Used
# =============================
def mark_code_as_used(code_row):
    original_code = code_row['code'].split('-')[-1]
    with open(CSV_FILE, 'r') as f:
        rows = list(csv.DictReader(f))
    with open(CSV_FILE, 'w', newline='') as f:
        writer = csv.DictWriter(f, fieldnames=['code', 'course', 'expires'])
        writer.writeheader()
        for row in rows:
            if not row['code'].endswith(original_code):
                writer.writerow(row)


# =============================
# Logout
# =============================
@app.route('/admin-logout')
def admin_logout():
    session.pop('admin', None)
    return redirect('/admin-login')


# =============================
# Run the App
# =============================
if __name__ == '__main__':
    app.run(debug=True)
