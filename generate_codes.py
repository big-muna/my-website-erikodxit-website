import csv
import random
import string
from datetime import datetime, timedelta
from fpdf import FPDF  # pip install fpdf

# === Configuration ===
COURSE_KEYS = {
    'ai': 'AI',
    'data-analysis': 'DA',
    'ml': 'ML',
    'viz': 'DV',
    'ai-projects': 'PR'
}

# === Generate a single formatted code ===
def generate_code(prefix, length=6):
    suffix = ''.join(random.choices(string.ascii_uppercase + string.digits, k=length))
    return f"{prefix}-{suffix}"

# === Generate multiple codes for a single course ===
def generate_bulk_codes(course, count, expires_in_days=None):
    prefix = COURSE_KEYS.get(course)
    if not prefix:
        raise ValueError(f"Invalid course name: {course}")

    expiry_date = (datetime.today() + timedelta(days=expires_in_days)).strftime('%Y-%m-%d') if expires_in_days else ''
    codes = []

    for _ in range(count):
        code = generate_code(prefix)
        codes.append({
            'code': code,
            'course': course,
            'expires': expiry_date
        })

    return codes

# === Save codes to CSV ===
def save_codes_to_csv(codes, file_path='code.csv'):
    with open(file_path, 'a', newline='') as csvfile:
        writer = csv.DictWriter(csvfile, fieldnames=['code', 'course', 'expires'])
        if csvfile.tell() == 0:
            writer.writeheader()
        writer.writerows(codes)

# === Save to TXT file ===
def save_codes_to_txt(codes, file_path='codes.txt'):
    with open(file_path, 'a') as f:
        for c in codes:
            f.write(f"{c['code']} -> {c['course']} (expires: {c['expires'] or 'Never'})\n")

# === Save to PDF file ===
def save_codes_to_pdf(codes, file_path='codes.pdf'):
    pdf = FPDF()
    pdf.add_page()
    pdf.set_font("Arial", size=12)

    pdf.cell(0, 10, "Generated Course Codes", ln=True, align='C')
    pdf.ln(5)

    for c in codes:
        line = f"{c['code']} -> {c['course']} (expires: {c['expires'] or 'Never'})"
        pdf.cell(0, 10, line, ln=True)

    pdf.output(file_path)

# === Save Predefined Manual Codes ===
def save_manual_codes():
    print("📝 Saving predefined manual codes to CSV...")
    manual_codes = [
        ("AI-1A2B3C", "ai"),
        ("DA-4D5E6F", "data-analysis"),
        ("ML-7G8H9I", "ml"),
        ("DV-0J1K2L", "viz"),
        ("PR-3M4N5O", "ai-projects"),
        ("AI-DA-6P7Q8R", "ai,data-analysis"),
        ("ML-DV-9S0T1U", "ml,viz"),
        ("ALL-2V3W4X", "ai,data-analysis,ml,viz,ai-projects"),
        ("AI-X1Y2Z3", "ai"),
        ("AI-9A8B7C", "ai"),
        ("DA-JK3L4M", "data-analysis"),
        ("DA-R5T6Y7", "data-analysis"),
        ("ML-P0O9I8", "ml"),
        ("ML-K3J2H1", "ml"),
        ("DV-LMN456", "viz"),
        ("DV-QWE123", "viz"),
        ("PR-ZXC789", "ai-projects"),
        ("PR-ASD234", "ai-projects"),
        ("AI-DA-GHT567", "ai,data-analysis"),
        ("DA-ML-LOP456", "data-analysis,ml"),
        ("ML-DV-XCV098", "ml,viz"),
        ("DA-ML-Q28D2M","data-analysis,ml")
        ("ALL-ABCDE1", "ai,data-analysis,ml,viz,ai-projects")
    ]
    with open("code.csv", "a", newline='') as file:
        writer = csv.writer(file)
        if file.tell() == 0:
            writer.writerow(["code", "course", "expires"])
        for code, course in manual_codes:
            writer.writerow([code, course, ""])
    print("✅ Manual codes added.\n")

# === Main Execution ===
if __name__ == '__main__':
    # Step 1: Save manual codes
    save_manual_codes()

    # Step 2: Generate dynamic codes
    course_config = {
        'ai': 5,
        'data-analysis': 3,
        'ml': 3,
        'viz': 2,
        'ai-projects': 4
    }

    expires_in_days = 30
    all_generated = []

    print("📦 Generating course codes...\n")

    for course, count in course_config.items():
        try:
            codes = generate_bulk_codes(course, count, expires_in_days)
            save_codes_to_csv(codes)
            all_generated.extend(codes)

            print(f"✅ {count} codes for '{course}':")
            for c in codes:
                print(f"  {c['code']} -> {c['course']} (expires: {c['expires'] or 'Never'})")
            print()

        except ValueError as e:
            print(f"❌ Error: {e}")

    # Step 3: Save all to TXT & PDF
    save_codes_to_txt(all_generated, 'codes.txt')
    save_codes_to_pdf(all_generated, 'codes.pdf')

    print(f"📄 Saved to CSV (code.csv), TXT (codes.txt), and PDF (codes.pdf)")
