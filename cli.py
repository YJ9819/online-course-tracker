"""
cli.py - Menu-Driven Console Application
Provides a classic CLI interface for Informatics Practices (IP) examinations and viva demonstrations.
Includes user authentication, module progress, and priority revision.
"""

import sys
from datetime import date
from werkzeug.security import generate_password_hash, check_password_hash
from database import Database
from analytics import AnalyticsManager
import matplotlib.pyplot as plt
from matplotlib.figure import Figure


def print_header(title: str):
    print("\n" + "=" * 65)
    print(f" {title.upper()} ".center(65, "="))
    print("=" * 65)


def print_table(rows: list, headers: list):
    """Simple clean tabular formatter without requiring external tabulate lib."""
    if not rows:
        print("\n  [No records found.]")
        return

    col_widths = [len(h) for h in headers]
    for row in rows:
        for idx, val in enumerate(row):
            col_widths[idx] = max(col_widths[idx], len(str(val)))

    sep_line = "+-" + "-+-".join("-" * w for w in col_widths) + "-+"
    hdr_line = "| " + " | ".join(f"{h:<{w}}" for h, w in zip(headers, col_widths)) + " |"
    print("\n" + sep_line)
    print(hdr_line)
    print(sep_line)

    for row in rows:
        r_line = "| " + " | ".join(f"{str(val):<{w}}" for val, w in zip(row, col_widths)) + " |"
        print(r_line)
    print(sep_line + "\n")


class CourseTrackerCLI:
    def __init__(self, db: Database):
        self.db = db
        self.analytics = AnalyticsManager(db)
        self.current_user = None

    @property
    def user_id(self) -> int:
        return self.current_user["user_id"] if self.current_user else 0

    def authenticate(self):
        while not self.current_user:
            print_header("STUDENT AUTHENTICATION (IP CLASS 12 / COLLEGE)")
            print(" 1. Sign In to Existing Account")
            print(" 2. Create New Student Account")
            print(" 3. Exit")
            print("-" * 65)

            choice = input("Enter choice (1-3): ").strip()
            if choice == "1":
                ident = input("Username or Email: ").strip()
                pwd = input("Password: ").strip()
                user = self.db.get_user_by_username(ident)
                if user and check_password_hash(user["password_hash"], pwd):
                    self.current_user = user
                    print(f"\n[SUCCESS] Welcome back, {user['name']} ({user['subject']})!")
                else:
                    print("\n[ERROR] Invalid username/email or password.")
            elif choice == "2":
                uname = input("Choose Username: ").strip().lower()
                if len(uname) < 3:
                    print("[ERROR] Username must be at least 3 characters.")
                    continue
                if self.db.get_user_by_username(uname):
                    print("[ERROR] Username already taken.")
                    continue
                pwd = input("Choose Password: ").strip()
                if len(pwd) < 4:
                    print("[ERROR] Password must be at least 4 characters.")
                    continue
                name = input("Full Name: ").strip()
                subject = input("Subject / Stream (e.g. Informatics Practices): ").strip()
                roll = input("Roll No / Student ID (optional): ").strip()
                email = input("Email (optional): ").strip()

                pwd_hash = generate_password_hash(pwd)
                uid = self.db.create_user(uname, pwd_hash, name, subject, roll, email)
                self.current_user = self.db.get_user_by_id(uid)
                print(f"\n[SUCCESS] Account created! Welcome, {name}.")
            elif choice == "3":
                sys.exit(0)
            else:
                print("\n[ERROR] Invalid option.")

    def run(self):
        self.authenticate()
        while True:
            print_header(f"LEARNTRACK CLI - {self.current_user['name'].upper()}")
            print(f" Subject: {self.current_user['subject']} | Database: {self.db.engine_name}")
            print("-" * 65)
            print(" 1. Course Catalog & Curriculum Modules")
            print(" 2. Daily Study Hours Log")
            print(" 3. Deadlines & Exam Tasks")
            print(" 4. Target Exams & Priority Revision (Weak Topics First)")
            print(" 5. Certificates & Notes")
            print(" 6. Pandas Data Analysis & Summary Reports")
            print(" 7. Matplotlib Visualizations")
            print(" 8. Switch Student / Logout")
            print(" 9. Exit")
            print("=" * 65)

            choice = input("Enter choice (1-9): ").strip()
            if choice == "1":
                self.menu_courses()
            elif choice == "2":
                self.menu_study_log()
            elif choice == "3":
                self.menu_deadlines()
            elif choice == "4":
                self.menu_exams()
            elif choice == "5":
                self.menu_certificates()
            elif choice == "6":
                self.menu_pandas_analysis()
            elif choice == "7":
                self.menu_visualizations()
            elif choice == "8":
                self.current_user = None
                self.authenticate()
            elif choice == "9":
                print("\nThank you for using LearnTrack. Goodbye!\n")
                break
            else:
                print("\n[ERROR] Invalid choice. Please select 1 through 9.")

    # ========================================================
    # 1. Courses & Modules
    # ========================================================

    def menu_courses(self):
        while True:
            print_header("COURSE CATALOG & MODULE MANAGEMENT")
            print(" 1. View All Courses")
            print(" 2. Add New Course")
            print(" 3. View / Manage Course Modules & Syllabus")
            print(" 4. Delete Course")
            print(" 5. Back to Main Menu")
            print("-" * 65)

            ch = input("Enter choice (1-5): ").strip()
            if ch == "1":
                courses = self.db.get_courses(self.user_id)
                rows = [
                    [c["course_id"], c["course_name"], c["platform"], f"{c.get('completed_modules', 0)}/{c.get('total_modules', 0)} ({c['progress_percent']}%)", c["status"], c["priority"]]
                    for c in courses
                ]
                print_table(rows, ["ID", "Course Name", "Platform", "Modules Done", "Status", "Priority"])
            elif ch == "2":
                name = input("Course Name: ").strip()
                if not name:
                    print("[ERROR] Course name cannot be empty.")
                    continue
                if self.db.course_exists(self.user_id, name):
                    print(f"[ERROR] You already have a course titled '{name}'.")
                    continue
                platform = input("Platform (Coursera/Udemy/NPTEL/YouTube/edX/Other): ").strip() or "Other"
                instructor = input("Instructor / Provider: ").strip()
                cid = self.db.add_course(self.user_id, name, platform, instructor)
                print(f"\n[SUCCESS] Course added with ID #{cid}. Add modules to track progress!")
            elif ch == "3":
                self.menu_modules()
            elif ch == "4":
                cid_str = input("Enter Course ID to delete: ").strip()
                if cid_str.isdigit():
                    cid = int(cid_str)
                    course = self.db.get_course_by_id(self.user_id, cid)
                    if course:
                        confirm = input(f"Confirm deleting '{course['course_name']}' and all its modules? (y/n): ").strip().lower()
                        if confirm == 'y':
                            self.db.delete_course(self.user_id, cid)
                            print("\n[SUCCESS] Course and all associated records deleted.")
                    else:
                        print("[ERROR] Course not found.")
            elif ch == "5":
                break

    def menu_modules(self):
        courses = self.db.get_courses(self.user_id)
        if not courses:
            print("\n[INFO] No courses found. Add a course first.")
            return

        print("\nSelect Course:")
        for c in courses:
            print(f"  #{c['course_id']} - {c['course_name']} ({c['progress_percent']}%)")
        cid_str = input("Enter Course ID: ").strip()
        if not cid_str.isdigit():
            return
        cid = int(cid_str)
        course = self.db.get_course_by_id(self.user_id, cid)
        if not course:
            print("[ERROR] Course not found.")
            return

        while True:
            print_header(f"MODULES: {course['course_name'].upper()}")
            print(f" Progress: {course['progress_percent']}% | Status: {course['status']}")
            print("-" * 65)
            print(" 1. List Modules")
            print(" 2. Add New Module")
            print(" 3. Toggle Module Complete / Incomplete")
            print(" 4. Delete Module")
            print(" 5. Back")
            print("-" * 65)

            ch = input("Enter choice (1-5): ").strip()
            if ch == "1":
                mods = self.db.get_course_modules(self.user_id, cid)
                rows = [
                    [m["module_id"], m["title"], "Done" if m["is_completed"] else "Pending", "Yes" if m["is_weak"] else "No", "Yes" if m["is_important"] else "No"]
                    for m in mods
                ]
                print_table(rows, ["MID", "Module Title", "Completion", "Weak Topic?", "Important?"])
            elif ch == "2":
                title = input("Module Title: ").strip()
                if not title:
                    continue
                kp = input("Key points / formulas: ").strip()
                weak = 1 if input("Is this a weak topic? (y/n): ").strip().lower() == 'y' else 0
                imp = 1 if input("Is this an important concept? (y/n): ").strip().lower() == 'y' else 0
                mid = self.db.add_module(self.user_id, cid, title, key_points=kp, is_weak=weak, is_important=imp)
                course = self.db.get_course_by_id(self.user_id, cid)
                print(f"\n[SUCCESS] Module added #{mid}. Course progress recalculated to {course['progress_percent']}%.")
            elif ch == "3":
                mid_str = input("Enter Module ID to toggle: ").strip()
                if mid_str.isdigit():
                    mod = self.db.get_module_by_id(self.user_id, int(mid_str))
                    if mod:
                        new_state = 0 if mod["is_completed"] else 1
                        res = self.db.toggle_module_completion(self.user_id, mod["module_id"], new_state)
                        course = self.db.get_course_by_id(self.user_id, cid)
                        print(f"\n[SUCCESS] Module '{mod['title']}' updated. Course is now {course['progress_percent']}% ({course['status']}).")
                    else:
                        print("[ERROR] Module not found.")
            elif ch == "4":
                mid_str = input("Enter Module ID to delete: ").strip()
                if mid_str.isdigit():
                    self.db.delete_module(self.user_id, int(mid_str))
                    course = self.db.get_course_by_id(self.user_id, cid)
                    print(f"\n[SUCCESS] Module deleted. Course progress recalculated to {course['progress_percent']}%.")
            elif ch == "5":
                break

    # ========================================================
    # 2. Daily Study Logs
    # ========================================================

    def menu_study_log(self):
        while True:
            print_header("DAILY STUDY HOURS LOG")
            print(" 1. View All Study Sessions")
            print(" 2. Record New Study Session")
            print(" 3. Delete Study Session")
            print(" 4. Back to Main Menu")
            print("-" * 65)

            ch = input("Enter choice (1-4): ").strip()
            if ch == "1":
                logs = self.db.get_study_logs(self.user_id)
                rows = [[l["log_id"], l["study_date"], l["course_name"], f"{l['hours_spent']} hrs", l["topic_covered"]] for l in logs]
                print_table(rows, ["ID", "Date", "Course", "Hours", "Topics Covered"])
            elif ch == "2":
                courses = self.db.get_courses(self.user_id)
                if not courses:
                    print("\n[INFO] Please add a course before logging study hours.")
                    return
                for c in courses:
                    print(f"  #{c['course_id']} - {c['course_name']}")
                cid_str = input("Enter Course ID: ").strip()
                if not cid_str.isdigit():
                    continue
                cid = int(cid_str)
                s_date = input(f"Study Date (YYYY-MM-DD) [{date.today()}]: ").strip() or str(date.today())
                hours_str = input("Hours Spent: ").strip()
                topic = input("Topics / Practical concepts covered: ").strip()
                try:
                    hours = float(hours_str)
                    if hours <= 0:
                        raise ValueError()
                except ValueError:
                    print("[ERROR] Please enter a positive numeric hours value.")
                    continue
                lid = self.db.add_study_log(self.user_id, cid, s_date, hours, topic)
                print(f"\n[SUCCESS] Study session logged #{lid}!")
            elif ch == "3":
                lid_str = input("Enter Log ID to delete: ").strip()
                if lid_str.isdigit():
                    self.db.delete_study_log(self.user_id, int(lid_str))
                    print("\n[SUCCESS] Study log deleted.")
            elif ch == "4":
                break

    # ========================================================
    # 3. Deadlines & Tasks
    # ========================================================

    def menu_deadlines(self):
        while True:
            print_header("ASSIGNMENT DEADLINES & TASKS")
            print(" 1. View All Deadlines")
            print(" 2. Add New Deadline")
            print(" 3. Toggle Complete / Incomplete")
            print(" 4. Delete Deadline")
            print(" 5. Back to Main Menu")
            print("-" * 65)

            ch = input("Enter choice (1-5): ").strip()
            if ch == "1":
                dls = self.db.get_deadlines(self.user_id)
                rows = [[d["deadline_id"], d["task_name"], d["course_name"], d["due_date"], "Completed" if d["is_done"] else "Pending"] for d in dls]
                print_table(rows, ["ID", "Task Name", "Course", "Due Date", "Status"])
            elif ch == "2":
                courses = self.db.get_courses(self.user_id)
                if not courses:
                    print("\n[INFO] Add a course first.")
                    return
                for c in courses:
                    print(f"  #{c['course_id']} - {c['course_name']}")
                cid_str = input("Enter Course ID: ").strip()
                if not cid_str.isdigit():
                    continue
                cid = int(cid_str)
                task = input("Task / Assignment Name: ").strip()
                due = input("Due Date (YYYY-MM-DD): ").strip()
                did = self.db.add_deadline(self.user_id, cid, task, due)
                print(f"\n[SUCCESS] Deadline recorded #{did}!")
            elif ch == "3":
                did_str = input("Enter Deadline ID to toggle: ").strip()
                if did_str.isdigit():
                    did = int(did_str)
                    dls = self.db.get_deadlines(self.user_id)
                    cur = next((d for d in dls if d["deadline_id"] == did), None)
                    if cur:
                        new_done = 0 if cur["is_done"] else 1
                        self.db.toggle_deadline(self.user_id, did, new_done)
                        print("\n[SUCCESS] Deadline status updated.")
                    else:
                        print("[ERROR] Deadline not found.")
            elif ch == "4":
                did_str = input("Enter Deadline ID to delete: ").strip()
                if did_str.isdigit():
                    self.db.delete_deadline(self.user_id, int(did_str))
                    print("\n[SUCCESS] Deadline deleted.")
            elif ch == "5":
                break

    # ========================================================
    # 4. Exams & Priority Revision
    # ========================================================

    def menu_exams(self):
        while True:
            print_header("EXAMS & AUTOMATED PRIORITY REVISION")
            print(" 1. View Scheduled Exams & Countdowns")
            print(" 2. Schedule New Exam")
            print(" 3. View Automated 'What to Revise' Checklist (Weak Topics First)")
            print(" 4. Delete Exam")
            print(" 5. Back to Main Menu")
            print("-" * 65)

            ch = input("Enter choice (1-5): ").strip()
            if ch == "1":
                exams = self.db.get_exams(self.user_id)
                rows = [
                    [e["exam_id"], e["exam_name"], e["course_name"], e["exam_date"], e["countdown_text"], f"{e['revision_done']}/{e['revision_total']} revised"]
                    for e in exams
                ]
                print_table(rows, ["EID", "Exam Name", "Course", "Date", "Countdown", "Revision Status"])
            elif ch == "2":
                courses = self.db.get_courses(self.user_id)
                if not courses:
                    print("\n[INFO] Please add a course first.")
                    continue
                for c in courses:
                    print(f"  #{c['course_id']} - {c['course_name']}")
                cid_str = input("Enter Course ID: ").strip()
                if not cid_str.isdigit():
                    continue
                cid = int(cid_str)
                name = input("Exam Name (e.g. CBSE Practical Exam): ").strip()
                ex_date = input("Exam Date (YYYY-MM-DD): ").strip()
                ex_time = input("Exam Time (e.g. 10:00 AM): ").strip()
                notes = input("Syllabus notes: ").strip()

                eid = self.db.add_exam(self.user_id, cid, name, ex_date, ex_time, notes)
                print(f"\n[SUCCESS] Exam scheduled #{eid}! Automated revision checklist ready.")
            elif ch == "3":
                exams = self.db.get_exams(self.user_id)
                if not exams:
                    print("\n[INFO] No exams scheduled.")
                    continue
                for e in exams:
                    print(f"  #{e['exam_id']} - {e['exam_name']} ({e['countdown_text']})")
                eid_str = input("Enter Exam ID: ").strip()
                if not eid_str.isdigit():
                    continue
                eid = int(eid_str)
                chk = self.db.get_exam_revision_checklist(self.user_id, eid)
                print_header(f"REVISION CHECKLIST: {chk['exam']['exam_name'].upper()}")
                print(f" Progress: {chk['revised_items']}/{chk['total_items']} revised ({chk['progress_percent']}%)")
                print("-" * 65)

                rows = [
                    [it["module_id"], it["title"], it["reason"], "Yes" if it["is_revised"] else "No", it["key_points"] or "—"]
                    for it in chk["items"]
                ]
                print_table(rows, ["MID", "Topic Title", "Priority Rank & Reason", "Revised?", "Key Formulas / Concepts"])

                toggle_mid = input("Enter Module ID to toggle revised status (or Enter to go back): ").strip()
                if toggle_mid.isdigit():
                    mid = int(toggle_mid)
                    cur_it = next((it for it in chk["items"] if it["module_id"] == mid), None)
                    if cur_it:
                        new_r = 0 if cur_it["is_revised"] else 1
                        self.db.toggle_revision_item(self.user_id, eid, mid, new_r)
                        print("\n[SUCCESS] Revision item updated!")
            elif ch == "4":
                eid_str = input("Enter Exam ID to delete: ").strip()
                if eid_str.isdigit():
                    self.db.delete_exam(self.user_id, int(eid_str))
                    print("\n[SUCCESS] Exam and its revision checklist deleted.")
            elif ch == "5":
                break

    # ========================================================
    # 5. Certificates
    # ========================================================

    def menu_certificates(self):
        while True:
            print_header("CERTIFICATES VAULT")
            print(" 1. View Certificates")
            print(" 2. Add Certificate Link")
            print(" 3. Delete Certificate")
            print(" 4. Back")
            print("-" * 65)

            ch = input("Enter choice (1-4): ").strip()
            if ch == "1":
                certs = self.db.get_certificates(self.user_id)
                rows = [[c["cert_id"], c["course_name"], c["platform"], c["certificate_link"], c["grade"]] for c in certs]
                print_table(rows, ["ID", "Course", "Platform", "Verification Link", "Grade"])
            elif ch == "2":
                courses = self.db.get_courses(self.user_id)
                if not courses:
                    print("\n[INFO] Add a course first.")
                    return
                for c in courses:
                    print(f"  #{c['course_id']} - {c['course_name']}")
                cid_str = input("Enter Course ID: ").strip()
                if not cid_str.isdigit():
                    continue
                cid = int(cid_str)
                url = input("Certificate Link URL: ").strip()
                issue = input(f"Issue Date (YYYY-MM-DD) [{date.today()}]: ").strip() or str(date.today())
                grade = input("Grade / Distinction: ").strip() or "Certificate of Completion"
                cid_res = self.db.add_certificate(self.user_id, cid, url, issue, grade)
                print(f"\n[SUCCESS] Certificate link saved #{cid_res}!")
            elif ch == "3":
                cid_str = input("Enter Certificate ID to delete: ").strip()
                if cid_str.isdigit():
                    self.db.delete_certificate(self.user_id, int(cid_str))
                    print("\n[SUCCESS] Certificate deleted.")
            elif ch == "4":
                break

    # ========================================================
    # 6. Pandas Analytics
    # ========================================================

    def menu_pandas_analysis(self):
        print_header("PANDAS DATA ANALYSIS REPORTS (INFORMATICS PRACTICES)")
        kpi = self.analytics.get_kpi_summary(self.user_id)
        print("\n  [EXECUTIVE KPI SUMMARY]")
        print(f"  • Total Courses Tracked : {kpi['total_courses']}")
        print(f"  • Completed Courses     : {kpi['completed_courses']}")
        print(f"  • In-Progress Courses   : {kpi['in_progress_courses']}")
        print(f"  • Average Progress      : {kpi['avg_progress']}%")
        print(f"  • Total Study Hours     : {kpi['total_hours']} hrs")
        print(f"  • Pending Deadlines     : {kpi['pending_deadlines']}")
        print(f"  • Target Upcoming Exams : {kpi['upcoming_exams']}")
        print(f"  • Primary Platform      : {kpi['most_used_platform']}\n")

        print("Generating Pandas aggregations...")
        c_df = self.analytics.get_courses_df(self.user_id)
        s_df = self.analytics.get_study_logs_df(self.user_id)

        if not c_df.empty:
            print("\n--- Platform Distribution (Pandas value_counts) ---")
            print(c_df["platform"].value_counts().to_string())

            print("\n--- Status Breakdown ---")
            print(c_df["status"].value_counts().to_string())

        if not s_df.empty:
            print("\n--- Total Hours per Course (Pandas groupby) ---")
            grouped = s_df.groupby("course_name")["hours_spent"].sum().sort_values(ascending=False)
            print(grouped.to_string())

        input("\nPress Enter to return to main menu...")

    # ========================================================
    # 7. Matplotlib Visualizations
    # ========================================================

    def menu_visualizations(self):
        while True:
            print_header("MATPLOTLIB GRAPHICAL VISUALIZATIONS")
            print(" 1. Hours Studied per Course (Horizontal Bar Chart)")
            print(" 2. Course Status Breakdown (Donut Chart)")
            print(" 3. Daily Study Hours Trend (Time-Series Plot)")
            print(" 4. Course Distribution by Platform (Column Chart)")
            print(" 5. Export All Charts to PNG Directory")
            print(" 6. Back to Main Menu")
            print("-" * 65)

            ch = input("Enter choice (1-6): ").strip()
            if ch in ["1", "2", "3", "4"]:
                fig = plt.figure(figsize=(9, 5))
                if ch == "1":
                    self.analytics.plot_hours_per_course(fig, user_id=self.user_id)
                elif ch == "2":
                    self.analytics.plot_status_distribution(fig, user_id=self.user_id)
                elif ch == "3":
                    self.analytics.plot_weekly_trend(fig, user_id=self.user_id)
                elif ch == "4":
                    self.analytics.plot_platform_breakdown(fig, user_id=self.user_id)
                plt.show()
            elif ch == "5":
                paths = self.analytics.export_all_charts("exported_charts", user_id=self.user_id)
                print("\n[SUCCESS] Charts successfully saved:")
                for p in paths:
                    print(f"  • {p}")
            elif ch == "6":
                break


def launch_cli(db: Database):
    app = CourseTrackerCLI(db)
    app.run()


if __name__ == "__main__":
    db = Database()
    launch_cli(db)
