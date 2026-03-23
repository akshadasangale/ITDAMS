from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table
from reportlab.lib import colors
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.lib import pagesizes
from reportlab.platypus import TableStyle
from flask import send_file
import io
from flask import Flask, render_template, request, redirect, session
import sqlite3
from werkzeug.security import generate_password_hash, check_password_hash
from datetime import date
import smtplib

app = Flask(__name__)
app.secret_key = "secret123"


def get_db():
    conn = sqlite3.connect("database.db")
    conn.row_factory = sqlite3.Row
    return conn


# ---------------- HOME ----------------
@app.route("/")
def home():
    return render_template("home.html")


# ---------------- LOGIN ----------------
@app.route("/login", methods=["GET", "POST"])
def login():

    if request.method == "POST":

        email = request.form["email"]
        password = request.form["password"]

        conn = get_db()
        user = conn.execute(
            "SELECT * FROM users WHERE email = ?", (email,)
        ).fetchone()

        if user and check_password_hash(user["password"], password):

            session["user_id"] = user["id"]
            session["role"] = user["role"]

            if user["role"] == "faculty":
                 return redirect("/faculty")
            elif user["role"] == "admin":
                return redirect("/admin")
            else:
                return redirect("/student")
            
        return "Invalid Login"

    return render_template("login.html")


# ---------------- LOGOUT ----------------
@app.route("/logout")
def logout():
    session.clear()
    return redirect("/")


# ---------------- FACULTY DASHBOARD ----------------
@app.route("/faculty")
def faculty():

    if session.get("role") != "faculty":
        return redirect("/login")

    conn = get_db()

    assignments = conn.execute(
        "SELECT * FROM assignments"
    ).fetchall()

    events = conn.execute(
        "SELECT * FROM events"
    ).fetchall()

    total_students = conn.execute(
        "SELECT COUNT(*) as count FROM users WHERE role='student'"
    ).fetchone()["count"]

    return render_template(
        "faculty.html",
        assignments=assignments,
        events=events,
        total_students=total_students
    )
# ---------------- ADMIN DASHBOARD ----------------
@app.route("/admin")
def admin():

    if session.get("role") != "admin":
        return redirect("/login")

    conn = get_db()

    total_students = conn.execute(
        "SELECT COUNT(*) as count FROM users WHERE role='student'"
    ).fetchone()["count"]

    total_faculty = conn.execute(
        "SELECT COUNT(*) as count FROM users WHERE role='faculty'"
    ).fetchone()["count"]

    total_assignments = conn.execute(
        "SELECT COUNT(*) as count FROM assignments"
    ).fetchone()["count"]

    total_events = conn.execute(
        "SELECT COUNT(*) as count FROM events"
    ).fetchone()["count"]

    return render_template(
        "admin.html",
        total_students=total_students,
        total_faculty=total_faculty,
        total_assignments=total_assignments,
        total_events=total_events
    )


# ---------------- ADD ASSIGNMENT ----------------
@app.route("/add-assignment", methods=["GET", "POST"])
def add_assignment():

    if session.get("role") != "faculty":
        return redirect("/login")

    if request.method == "POST":

        title = request.form["title"]
        due_date = request.form["due_date"]

        conn = get_db()
        conn.execute(
            "INSERT INTO assignments (title, due_date) VALUES (?,?)",
            (title, due_date),
        )
        conn.commit()

        return redirect("/faculty")

    return render_template("add_assignment.html")


# ---------------- ADD EVENT ----------------
@app.route("/add-event", methods=["GET", "POST"])
def add_event():

    if session.get("role") != "faculty":
        return redirect("/login")

    if request.method == "POST":

        title = request.form["title"]
        event_date = request.form["event_date"]

        conn = get_db()
        conn.execute(
            "INSERT INTO events (title, event_date) VALUES (?,?)",
            (title, event_date),
        )
        conn.commit()

        return redirect("/faculty")

    return render_template("add_event.html")


# ---------------- STUDENT DASHBOARD ----------------
@app.route("/student")
def student():

    if session.get("role") != "student":
        return redirect("/login")

    conn = get_db()

    assignments = conn.execute(
        "SELECT * FROM assignments"
    ).fetchall()

    events = conn.execute(
        "SELECT * FROM events"
    ).fetchall()

    submissions = conn.execute(
        "SELECT assignment_id FROM submissions WHERE student_id = ?",
        (session["user_id"],)
    ).fetchall()

    submitted_ids = [s["assignment_id"] for s in submissions]

    today = date.today().isoformat()
    attendance_records = conn.execute(
        "SELECT * FROM attendance WHERE student_id = ?",
        (session["user_id"],)
    ).fetchall()
    attendance_count = len(attendance_records)
    return render_template(
    "student.html",
    assignments=assignments,
    events=events,
    submitted_ids=submitted_ids,
    today=today,
    attendance_count=attendance_count
)
# ---------------- DOWNLOAD REPORT CARD ----------------
@app.route("/download-report")
def download_report():

    if session.get("role") != "student":
        return redirect("/login")

    conn = get_db()

    student = conn.execute(
        "SELECT email FROM users WHERE id=?",
        (session["user_id"],)
    ).fetchone()

    marks = conn.execute(
        "SELECT subject, score FROM marks WHERE student_id=?",
        (session["user_id"],)
    ).fetchall()

    buffer = io.BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=pagesizes.A4)
    elements = []

    styles = getSampleStyleSheet()
    elements.append(Paragraph("IT Department Academic Report Card", styles["Title"]))
    elements.append(Spacer(1, 20))

    elements.append(Paragraph(f"Student Email: {student['email']}", styles["Normal"]))
    elements.append(Spacer(1, 20))

    data = [["Subject", "Marks"]]

    for m in marks:
        data.append([m["subject"], m["score"]])

    table = Table(data)
    table.setStyle(TableStyle([
        ('BACKGROUND', (0,0), (-1,0), colors.grey),
        ('TEXTCOLOR',(0,0),(-1,0),colors.whitesmoke),
        ('GRID', (0,0), (-1,-1), 1, colors.black),
    ]))

    elements.append(table)

    doc.build(elements)

    buffer.seek(0)

    return send_file(
        buffer,
        as_attachment=True,
        download_name="ReportCard.pdf",
        mimetype="application/pdf"
    )


# ---------------- SUBMIT ASSIGNMENT ----------------
@app.route("/submit/<int:assignment_id>")
def submit(assignment_id):

    if session.get("role") != "student":
        return redirect("/login")

    conn = get_db()

    conn.execute(
    "INSERT INTO submissions (assignment_id, student_id, submitted_at) VALUES (?,?,?)",
    (assignment_id, session["user_id"], date.today().isoformat())
)
    conn.commit()

    return redirect("/student")
# ---------------- VIEW SUBMISSIONS (FACULTY) ----------------
@app.route("/view-submissions/<int:assignment_id>")
def view_submissions(assignment_id):

    if session.get("role") != "faculty":
        return redirect("/login")

    conn = get_db()

    submissions = conn.execute("""
    SELECT users.id, users.email, submissions.submitted_at
    FROM users
    LEFT JOIN submissions 
        ON users.id = submissions.student_id 
        AND submissions.assignment_id = ?
    WHERE users.role = 'student'
""", (assignment_id,)).fetchall()

    total_students = len(submissions)
       
    submitted_count = sum(1 for s in submissions if s["submitted_at"])
    pending_count = total_students - submitted_count

    return render_template(
        "view_submissions.html",
        submissions=submissions,
        total_students=total_students,
        submitted_count=submitted_count,
        pending_count=pending_count
    )


# ---------------- EMAIL BROADCAST ----------------
@app.route("/send-message", methods=["POST"])
def send_message():

    if session.get("role") != "faculty":
        return redirect("/login")

    message = request.form["message"]

    conn = get_db()
    students = conn.execute(
        "SELECT email FROM users WHERE role='student'"
    ).fetchall()

    # Replace with your Gmail
    sender_email = "yourgmail@gmail.com"
    sender_password = "yourapppassword"

    server = smtplib.SMTP("smtp.gmail.com", 587)
    server.starttls()
    server.login(sender_email, sender_password)

    for student in students:
        server.sendmail(
            sender_email,
            student["email"],
            message
        )

    server.quit()

    return redirect("/faculty")
@app.route("/mark-attendance/<int:student_id>")
def mark_attendance(student_id):

    if session.get("role") != "faculty":
        return redirect("/login")

    conn = get_db()

    conn.execute(
        "INSERT INTO attendance (student_id, date, status) VALUES (?,?,?)",
        (student_id, date.today().isoformat(), "Present")
    )
    conn.commit()

    return redirect("/faculty")
# ---------------- ATTENDANCE PAGE (FACULTY) ----------------
@app.route("/mark-attendance-page")
def mark_attendance_page():

    if session.get("role") != "faculty":
        return redirect("/login")

    conn = get_db()

    students = conn.execute(
        "SELECT * FROM users WHERE role='student'"
    ).fetchall()

    return render_template("attendance.html", students=students)
# ---------------- ADD MARKS ----------------
@app.route("/add-marks", methods=["GET", "POST"])
def add_marks():

    if session.get("role") != "faculty":
        return redirect("/login")

    conn = get_db()

    students = conn.execute(
        "SELECT * FROM users WHERE role='student'"
    ).fetchall()

    if request.method == "POST":

        student_id = request.form["student_id"]
        subject = request.form["subject"]
        score = request.form["score"]

        conn.execute(
            "INSERT INTO marks (student_id, subject, score) VALUES (?,?,?)",
            (student_id, subject, score),
        )
        conn.commit()

        return redirect("/faculty")

    return render_template("add_marks.html", students=students)

# ---------------- DATABASE INIT ----------------
@app.route("/init")
def init_db():

    conn = get_db()

    # Create users table FIRST
    conn.execute("""
    CREATE TABLE IF NOT EXISTS users (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        email TEXT,
        password TEXT,
        role TEXT
    )
    """)

    # Create assignments table
    conn.execute("""
    CREATE TABLE IF NOT EXISTS assignments (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        title TEXT,
        due_date TEXT
    )
    """)

    # Create submissions table
    conn.execute("""
    CREATE TABLE IF NOT EXISTS submissions (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        assignment_id INTEGER,
        student_id INTEGER,
        submitted_at TEXT
    )
    """)

    # Create events table
    conn.execute("""
    CREATE TABLE IF NOT EXISTS events (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        title TEXT,
        event_date TEXT
    )
    """)

    # Create attendance table
    conn.execute("""
    CREATE TABLE IF NOT EXISTS attendance (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        student_id INTEGER,
        date TEXT,
        status TEXT
    )
    """)
        # Create PBL table
    conn.execute("""
    CREATE TABLE IF NOT EXISTS pbl (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        title TEXT,
        description TEXT,
        due_date TEXT
    )
    """)

    # Create marks table
    conn.execute("""
    CREATE TABLE IF NOT EXISTS marks (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        student_id INTEGER,
        subject TEXT,
        score INTEGER
    )
    """)

    # Create admin user if not exists
    existing_admin = conn.execute(
        "SELECT * FROM users WHERE email = ?",
        ("admin@test.com",)
    ).fetchone()

    if not existing_admin:
        conn.execute(
            "INSERT INTO users (email, password, role) VALUES (?,?,?)",
            ("admin@test.com", generate_password_hash("1234"), "admin"),
        )

    # Now check if demo users exist
    existing = conn.execute(
        "SELECT * FROM users WHERE email = ?",
        ("faculty@test.com",)
    ).fetchone()

    if not existing:
        conn.execute(
            "INSERT INTO users (email, password, role) VALUES (?,?,?)",
            ("faculty@test.com", generate_password_hash("1234"), "faculty"),
        )

        conn.execute(
            "INSERT INTO users (email, password, role) VALUES (?,?,?)",
            ("student@test.com", generate_password_hash("1234"), "student"),
        )

    conn.commit()

    return "Database initialized successfully!"

if __name__ == "__main__":
    app.run(debug=True)
