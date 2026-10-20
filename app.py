"""
app.py - Flask Web Application & REST API Server
Provides a modern SaaS-grade web interface for the Online Course Tracker.
Includes per-user authentication, modules management, exams, and priority revision.
"""

import os
import webbrowser
from datetime import datetime, date
from functools import wraps
from flask import Flask, render_template, request, jsonify, session, redirect, url_for
from werkzeug.security import generate_password_hash, check_password_hash
from database import Database
from analytics import AnalyticsManager

app = Flask(__name__)
# Secret key for cryptographically secure session signing
app.secret_key = os.environ.get("FLASK_SECRET_KEY", "learntrack-super-secret-ip-project-key-2026")
app.config["SESSION_COOKIE_HTTPONLY"] = True
app.config["SESSION_COOKIE_SAMESITE"] = "Lax"

db = Database(force_sqlite=True)
analytics = AnalyticsManager(db)


def login_required(f):
    """Decorator ensuring endpoints are only accessible by authenticated users."""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if "user_id" not in session:
            if request.path.startswith("/api/"):
                return jsonify({"error": "Authentication required. Please sign in.", "authenticated": False}), 401
            return redirect(url_for("index"))
        return f(*args, **kwargs)
    return decorated_function


# ========================================================
# Page Routes
# ========================================================

@app.route("/")
def index():
    return render_template("index.html", engine_name=db.engine_name)


# ========================================================
# Authentication & User Profile API
# ========================================================

@app.route("/api/auth/register", methods=["POST"])
def auth_register():
    data = request.json or {}
    username = data.get("username", "").strip()
    password = data.get("password", "")
    name = data.get("name", "").strip()
    subject = data.get("subject", "").strip()
    roll_no = data.get("roll_no", "").strip()
    email = data.get("email", "").strip()
    avatar_color = data.get("avatar_color", "#4F46E5").strip()

    if not username or len(username) < 3:
        return jsonify({"error": "Username must be at least 3 characters."}), 400
    if not password or len(password) < 4:
        return jsonify({"error": "Password must be at least 4 characters."}), 400
    if not name:
        return jsonify({"error": "Full Name is required."}), 400
    if not subject:
        return jsonify({"error": "Subject / Grade is required."}), 400

    # Check for existing username or email
    existing = db.get_user_by_username(username)
    if existing:
        return jsonify({"error": "Username is already taken. Please choose another."}), 409
    if email:
        existing_email = db.get_user_by_username(email)
        if existing_email:
            return jsonify({"error": "An account with this email already exists."}), 409

    pwd_hash = generate_password_hash(password)
    user_id = db.create_user(
        username=username,
        password_hash=pwd_hash,
        name=name,
        subject=subject,
        roll_no=roll_no,
        email=email,
        avatar_color=avatar_color
    )

    session["user_id"] = user_id
    session.permanent = True

    user = db.get_user_by_id(user_id)
    if user:
        user.pop("password_hash", None)
    return jsonify({"success": True, "user": user})


@app.route("/api/auth/login", methods=["POST"])
def auth_login():
    data = request.json or {}
    identifier = data.get("username", "").strip()
    password = data.get("password", "")

    if not identifier or not password:
        return jsonify({"error": "Username and password are required."}), 400

    user = db.get_user_by_username(identifier)
    if not user or not check_password_hash(user.get("password_hash", ""), password):
        return jsonify({"error": "Invalid username or password."}), 401

    session["user_id"] = user["user_id"]
    session.permanent = True

    safe_user = dict(user)
    safe_user.pop("password_hash", None)
    return jsonify({"success": True, "user": safe_user})


@app.route("/api/auth/logout", methods=["POST"])
def auth_logout():
    session.clear()
    return jsonify({"success": True})


@app.route("/api/auth/me", methods=["GET"])
def auth_me():
    user_id = session.get("user_id")
    if not user_id:
        return jsonify({"authenticated": False, "user": None})

    user = db.get_user_by_id(user_id)
    if not user:
        session.clear()
        return jsonify({"authenticated": False, "user": None})

    safe_user = dict(user)
    safe_user.pop("password_hash", None)
    return jsonify({"authenticated": True, "user": safe_user})


@app.route("/api/auth/profile", methods=["PUT"])
@login_required
def update_profile():
    user_id = session["user_id"]
    data = request.json or {}
    name = data.get("name", "").strip()
    subject = data.get("subject", "").strip()
    roll_no = data.get("roll_no", "").strip()
    email = data.get("email", "").strip()
    avatar_color = data.get("avatar_color", "#4F46E5").strip()

    if not name or not subject:
        return jsonify({"error": "Name and Subject are required."}), 400

    db.update_user_profile(
        user_id=user_id,
        name=name,
        subject=subject,
        roll_no=roll_no,
        email=email,
        avatar_color=avatar_color
    )
    user = db.get_user_by_id(user_id)
    if user:
        user.pop("password_hash", None)
    return jsonify({"success": True, "user": user})


# ========================================================
# KPI & Analytics API (Scoped per User)
# ========================================================

@app.route("/api/kpi")
@login_required
def get_kpis():
    user_id = session["user_id"]
    kpis = analytics.get_kpi_summary(user_id)
    kpis["engine_name"] = db.engine_name
    return jsonify(kpis)


@app.route("/api/analytics/charts")
@login_required
def get_chart_data():
    """Returns aggregated datasets formatted specifically for Chart.js rendering."""
    user_id = session["user_id"]
    s_df = analytics.get_study_logs_df(user_id)
    c_df = analytics.get_courses_df(user_id)

    # 1. Hours per course
    if not s_df.empty:
        hours_grouped = s_df.groupby("course_name")["hours_spent"].sum().sort_values(ascending=False)
        hours_labels = hours_grouped.index.tolist()
        hours_values = [round(float(v), 1) for v in hours_grouped.values.tolist()]
    else:
        hours_labels, hours_values = [], []

    # 2. Status distribution
    if not c_df.empty:
        status_counts = c_df["status"].value_counts()
        status_labels = status_counts.index.tolist()
        status_values = [int(v) for v in status_counts.values.tolist()]
    else:
        status_labels, status_values = [], []

    # 3. Daily / weekly trend
    if not s_df.empty:
        daily = s_df.dropna(subset=["study_date"]).groupby("study_date")["hours_spent"].sum().reset_index()
        daily = daily.sort_values("study_date")
        trend_labels = [d.strftime("%b %d") for d in daily["study_date"]]
        trend_values = [round(float(v), 1) for v in daily["hours_spent"]]
    else:
        trend_labels, trend_values = [], []

    # 4. Platform breakdown
    if not c_df.empty:
        platform_counts = c_df["platform"].value_counts()
        platform_labels = platform_counts.index.tolist()
        platform_values = [int(v) for v in platform_counts.values.tolist()]
    else:
        platform_labels, platform_values = [], []

    return jsonify({
        "hours_per_course": {"labels": hours_labels, "values": hours_values},
        "status_distribution": {"labels": status_labels, "values": status_values},
        "study_trend": {"labels": trend_labels, "values": trend_values},
        "platform_breakdown": {"labels": platform_labels, "values": platform_values}
    })


# ========================================================
# Courses Endpoints (Scoped per User)
# ========================================================

@app.route("/api/courses", methods=["GET"])
@login_required
def list_courses():
    user_id = session["user_id"]
    search = request.args.get("search", "").strip()
    status = request.args.get("status", "").strip()
    platform = request.args.get("platform", "").strip()
    courses = db.get_courses(user_id=user_id, search=search, status_filter=status, platform_filter=platform)
    return jsonify(courses)


@app.route("/api/courses", methods=["POST"])
@login_required
def create_course():
    user_id = session["user_id"]
    data = request.json or {}
    name = data.get("course_name", "").strip()
    platform = data.get("platform", "").strip()

    if not name or not platform:
        return jsonify({"error": "Course name and platform are required."}), 400

    # Anti-duplicate check
    if db.course_exists(user_id, name):
        return jsonify({"error": f"You already have an active or tracked course titled '{name}'."}), 400

    cid = db.add_course(
        user_id=user_id,
        course_name=name,
        platform=platform,
        instructor=data.get("instructor", "").strip(),
        start_date=data.get("start_date", "").strip(),
        end_date=data.get("end_date", "").strip(),
        status=data.get("status", "Not Started"),
        progress_percent=0,
        priority=data.get("priority", "Medium"),
        course_link=data.get("course_link", "").strip(),
        notes=data.get("notes", "").strip()
    )
    return jsonify({"success": True, "course_id": cid})


@app.route("/api/courses/<int:cid>", methods=["GET"])
@login_required
def get_course(cid):
    user_id = session["user_id"]
    course = db.get_course_by_id(user_id, cid)
    if not course:
        return jsonify({"error": "Course not found"}), 404
    return jsonify(course)


@app.route("/api/courses/<int:cid>", methods=["PUT"])
@login_required
def update_course(cid):
    user_id = session["user_id"]
    course = db.get_course_by_id(user_id, cid)
    if not course:
        return jsonify({"error": "Course not found"}), 404

    data = request.json or {}
    name = data.get("course_name", "").strip()
    platform = data.get("platform", "").strip()
    if not name or not platform:
        return jsonify({"error": "Course name and platform are required."}), 400

    if db.course_exists(user_id, name, exclude_id=cid):
        return jsonify({"error": f"Another course with title '{name}' already exists."}), 400

    db.update_course(
        user_id=user_id,
        course_id=cid,
        course_name=name,
        platform=platform,
        instructor=data.get("instructor", "").strip(),
        start_date=data.get("start_date", "").strip(),
        end_date=data.get("end_date", "").strip(),
        status=data.get("status", course.get("status", "Not Started")),
        priority=data.get("priority", "Medium"),
        course_link=data.get("course_link", "").strip(),
        notes=data.get("notes", "").strip()
    )
    updated = db.get_course_by_id(user_id, cid)
    return jsonify({"success": True, "course": updated})


@app.route("/api/courses/<int:cid>", methods=["DELETE"])
@login_required
def delete_course(cid):
    user_id = session["user_id"]
    course = db.get_course_by_id(user_id, cid)
    if not course:
        return jsonify({"error": "Course not found"}), 404
    db.delete_course(user_id, cid)
    return jsonify({"success": True})


# ========================================================
# Modules Endpoints (Scoped per User & Course)
# ========================================================

@app.route("/api/courses/<int:cid>/modules", methods=["GET"])
@login_required
def list_course_modules(cid):
    user_id = session["user_id"]
    course = db.get_course_by_id(user_id, cid)
    if not course:
        return jsonify({"error": "Course not found"}), 404
    modules = db.get_course_modules(user_id, cid)
    return jsonify({"course": course, "modules": modules})


@app.route("/api/courses/<int:cid>/modules", methods=["POST"])
@login_required
def create_course_module(cid):
    user_id = session["user_id"]
    course = db.get_course_by_id(user_id, cid)
    if not course:
        return jsonify({"error": "Course not found"}), 404

    data = request.json or {}
    title = data.get("title", "").strip()
    if not title:
        return jsonify({"error": "Module title is required."}), 400

    mid = db.add_module(
        user_id=user_id,
        course_id=cid,
        title=title,
        notes=data.get("notes", "").strip(),
        reference_links=data.get("reference_links", []),
        is_important=1 if data.get("is_important") else 0,
        is_weak=1 if data.get("is_weak") else 0,
        key_points=data.get("key_points", "").strip()
    )
    course_updated = db.get_course_by_id(user_id, cid)
    module_created = db.get_module_by_id(user_id, mid)
    return jsonify({"success": True, "module": module_created, "course": course_updated})


@app.route("/api/modules/<int:mid>", methods=["GET"])
@login_required
def get_module(mid):
    user_id = session["user_id"]
    mod = db.get_module_by_id(user_id, mid)
    if not mod:
        return jsonify({"error": "Module not found"}), 404
    return jsonify(mod)


@app.route("/api/modules/<int:mid>", methods=["PUT"])
@login_required
def update_module(mid):
    user_id = session["user_id"]
    mod = db.get_module_by_id(user_id, mid)
    if not mod:
        return jsonify({"error": "Module not found"}), 404

    data = request.json or {}
    title = data.get("title", "").strip()
    if not title:
        return jsonify({"error": "Module title is required."}), 400

    db.update_module(
        user_id=user_id,
        module_id=mid,
        title=title,
        notes=data.get("notes", "").strip(),
        reference_links=data.get("reference_links", []),
        is_important=1 if data.get("is_important") else 0,
        is_weak=1 if data.get("is_weak") else 0,
        key_points=data.get("key_points", "").strip()
    )
    updated = db.get_module_by_id(user_id, mid)
    return jsonify({"success": True, "module": updated})


@app.route("/api/modules/<int:mid>/toggle", methods=["POST"])
@login_required
def toggle_module(mid):
    user_id = session["user_id"]
    mod = db.get_module_by_id(user_id, mid)
    if not mod:
        return jsonify({"error": "Module not found"}), 404

    data = request.json or {}
    is_completed = 1 if data.get("is_completed") else 0
    res = db.toggle_module_completion(user_id, mid, is_completed)
    return jsonify({"success": True, **res})


@app.route("/api/modules/<int:mid>", methods=["DELETE"])
@login_required
def delete_module(mid):
    user_id = session["user_id"]
    mod = db.get_module_by_id(user_id, mid)
    if not mod:
        return jsonify({"error": "Module not found"}), 404
    cid = mod["course_id"]
    db.delete_module(user_id, mid)
    course_updated = db.get_course_by_id(user_id, cid)
    return jsonify({"success": True, "course": course_updated})


# ========================================================
# Study Logs Endpoints (Scoped per User)
# ========================================================

@app.route("/api/study-logs", methods=["GET"])
@login_required
def list_study_logs():
    user_id = session["user_id"]
    cid = request.args.get("course_id", type=int)
    logs = db.get_study_logs(user_id=user_id, course_id=cid)
    return jsonify(logs)


@app.route("/api/study-logs", methods=["POST"])
@login_required
def create_study_log():
    user_id = session["user_id"]
    data = request.json or {}
    cid = int(data.get("course_id", 0))
    s_date = data.get("study_date", date.today().strftime("%Y-%m-%d"))
    hours = float(data.get("hours_spent", 0))
    topic = data.get("topic_covered", "").strip()

    if cid <= 0 or hours <= 0:
        return jsonify({"error": "Valid course and positive hours are required."}), 400

    course = db.get_course_by_id(user_id, cid)
    if not course:
        return jsonify({"error": "Course not found in your catalog."}), 404

    # Anti-duplicate check
    if db.study_log_exists(user_id, cid, s_date, topic):
        return jsonify({"error": "A study session with this topic has already been logged for this date."}), 400

    lid = db.add_study_log(user_id=user_id, course_id=cid, study_date=s_date, hours_spent=hours, topic_covered=topic)
    return jsonify({"success": True, "log_id": lid})


@app.route("/api/study-logs/<int:lid>", methods=["DELETE"])
@login_required
def delete_study_log(lid):
    user_id = session["user_id"]
    db.delete_study_log(user_id, lid)
    return jsonify({"success": True})


# ========================================================
# Deadlines Endpoints (Scoped per User)
# ========================================================

@app.route("/api/deadlines", methods=["GET"])
@login_required
def list_deadlines():
    user_id = session["user_id"]
    deadlines = db.get_deadlines(user_id=user_id, include_completed=True)
    today = date.today()
    for d in deadlines:
        try:
            due = datetime.strptime(str(d["due_date"])[:10], "%Y-%m-%d").date()
            d["days_left"] = (due - today).days
        except Exception:
            d["days_left"] = 999
    return jsonify(deadlines)


@app.route("/api/deadlines", methods=["POST"])
@login_required
def create_deadline():
    user_id = session["user_id"]
    data = request.json or {}
    cid = int(data.get("course_id", 0))
    task = data.get("task_name", "").strip()
    due = data.get("due_date", "").strip()

    if cid <= 0 or not task or not due:
        return jsonify({"error": "Course, task name, and due date are required."}), 400

    course = db.get_course_by_id(user_id, cid)
    if not course:
        return jsonify({"error": "Course not found in your catalog."}), 404

    # Anti-duplicate check
    if db.deadline_exists(user_id, cid, task, due):
        return jsonify({"error": "This task deadline has already been added."}), 400

    did = db.add_deadline(user_id=user_id, course_id=cid, task_name=task, due_date=due, is_done=0)
    return jsonify({"success": True, "deadline_id": did})


@app.route("/api/deadlines/<int:did>/toggle", methods=["POST"])
@login_required
def toggle_deadline(did):
    user_id = session["user_id"]
    data = request.json or {}
    is_done = 1 if data.get("is_done") else 0
    db.toggle_deadline(user_id, did, is_done)
    return jsonify({"success": True})


@app.route("/api/deadlines/<int:did>", methods=["DELETE"])
@login_required
def delete_deadline(did):
    user_id = session["user_id"]
    db.delete_deadline(user_id, did)
    return jsonify({"success": True})


# ========================================================
# Certificates Endpoints (Scoped per User)
# ========================================================

@app.route("/api/certificates", methods=["GET"])
@login_required
def list_certificates():
    user_id = session["user_id"]
    certs = db.get_certificates(user_id=user_id)
    return jsonify(certs)


@app.route("/api/certificates", methods=["POST"])
@login_required
def create_certificate():
    user_id = session["user_id"]
    data = request.json or {}
    cid = int(data.get("course_id", 0))
    url = data.get("certificate_link", "").strip()
    issue = data.get("issue_date", "").strip()
    grade = data.get("grade", "Certificate of Completion").strip()

    if cid <= 0 or not url:
        return jsonify({"error": "Valid course and certificate link are required."}), 400

    course = db.get_course_by_id(user_id, cid)
    if not course:
        return jsonify({"error": "Course not found in your catalog."}), 404

    cert_id = db.add_certificate(user_id=user_id, course_id=cid, certificate_link=url, issue_date=issue, grade=grade)
    return jsonify({"success": True, "cert_id": cert_id})


@app.route("/api/certificates/<int:cert_id>", methods=["DELETE"])
@login_required
def delete_certificate(cert_id):
    user_id = session["user_id"]
    db.delete_certificate(user_id, cert_id)
    return jsonify({"success": True})


# ========================================================
# Exams & Priority Revision Lists Endpoints (Scoped per User)
# ========================================================

@app.route("/api/exams", methods=["GET"])
@login_required
def list_exams():
    user_id = session["user_id"]
    exams = db.get_exams(user_id)
    return jsonify(exams)


@app.route("/api/exams", methods=["POST"])
@login_required
def create_exam():
    user_id = session["user_id"]
    data = request.json or {}
    cid = int(data.get("course_id", 0))
    name = data.get("exam_name", "").strip()
    exam_date = data.get("exam_date", "").strip()
    exam_time = data.get("exam_time", "").strip()
    syllabus = data.get("syllabus_notes", "").strip()
    covered_module_ids = data.get("covered_module_ids", [])

    if cid <= 0 or not name or not exam_date:
        return jsonify({"error": "Course, exam name, and exam date are required."}), 400

    course = db.get_course_by_id(user_id, cid)
    if not course:
        return jsonify({"error": "Course not found in your catalog."}), 404

    eid = db.add_exam(
        user_id=user_id,
        course_id=cid,
        exam_name=name,
        exam_date=exam_date,
        exam_time=exam_time,
        syllabus_notes=syllabus,
        covered_module_ids=covered_module_ids
    )
    return jsonify({"success": True, "exam_id": eid})


@app.route("/api/exams/<int:eid>", methods=["GET"])
@login_required
def get_exam(eid):
    user_id = session["user_id"]
    exam = db.get_exam_by_id(user_id, eid)
    if not exam:
        return jsonify({"error": "Exam not found"}), 404
    return jsonify(exam)


@app.route("/api/exams/<int:eid>", methods=["PUT"])
@login_required
def update_exam(eid):
    user_id = session["user_id"]
    exam = db.get_exam_by_id(user_id, eid)
    if not exam:
        return jsonify({"error": "Exam not found"}), 404

    data = request.json or {}
    cid = int(data.get("course_id", exam["course_id"]))
    name = data.get("exam_name", "").strip()
    exam_date = data.get("exam_date", "").strip()
    exam_time = data.get("exam_time", "").strip()
    syllabus = data.get("syllabus_notes", "").strip()
    covered_module_ids = data.get("covered_module_ids", [])

    if cid <= 0 or not name or not exam_date:
        return jsonify({"error": "Course, exam name, and exam date are required."}), 400

    db.update_exam(
        user_id=user_id,
        exam_id=eid,
        course_id=cid,
        exam_name=name,
        exam_date=exam_date,
        exam_time=exam_time,
        syllabus_notes=syllabus,
        covered_module_ids=covered_module_ids
    )
    return jsonify({"success": True})


@app.route("/api/exams/<int:eid>", methods=["DELETE"])
@login_required
def delete_exam(eid):
    user_id = session["user_id"]
    exam = db.get_exam_by_id(user_id, eid)
    if not exam:
        return jsonify({"error": "Exam not found"}), 404
    db.delete_exam(user_id, eid)
    return jsonify({"success": True})


@app.route("/api/exams/<int:eid>/revision", methods=["GET"])
@login_required
def get_exam_revision(eid):
    user_id = session["user_id"]
    exam = db.get_exam_by_id(user_id, eid)
    if not exam:
        return jsonify({"error": "Exam not found"}), 404
    checklist = db.get_exam_revision_checklist(user_id, eid)
    return jsonify(checklist)


@app.route("/api/exams/<int:eid>/revision/<int:mid>/toggle", methods=["POST"])
@login_required
def toggle_revision_item(eid, mid):
    user_id = session["user_id"]
    exam = db.get_exam_by_id(user_id, eid)
    if not exam:
        return jsonify({"error": "Exam not found"}), 404

    data = request.json or {}
    is_revised = 1 if data.get("is_revised") else 0
    db.toggle_revision_item(user_id, eid, mid, is_revised)
    checklist = db.get_exam_revision_checklist(user_id, eid)
    return jsonify({"success": True, "checklist": checklist})


# ========================================================
# Server Runner
# ========================================================

def run_web(host="127.0.0.1", port=5000, open_browser=True):
    if open_browser:
        webbrowser.open(f"http://{host}:{port}")

    print(f"\n[READY] Online Course Tracker Web Dashboard is live at http://{host}:{port}")
    app.run(host=host, port=port, debug=False)


if __name__ == "__main__":
    run_web(open_browser=True)
