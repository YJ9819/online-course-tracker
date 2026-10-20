"""
test_system.py - Comprehensive Unit & Integration Test Suite
Validates:
1. User Authentication (Password hashing, registration, login, profile).
2. Strict Per-User Data Isolation (Cross-user access denial).
3. Modules Management & Automatic Course Progress Calculation.
4. Per-Module Notes, References, Important & Weak Topic Flags.
5. Exams, Countdowns, and Urgency Color Logic.
6. Automated "What to Revise" Priority Ordering (Weak -> Important -> Incomplete).
7. SQLite Foreign Key Cascading Deletions.
8. Flask Session-based REST API Endpoints.
9. Analytics & KPI Calculations with Empty State Resilience.
"""

import os
import json
import unittest
from datetime import date, timedelta
from werkzeug.security import generate_password_hash, check_password_hash
from database import Database
from analytics import AnalyticsManager
from app import app


class TestLearnTrackSystem(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.test_db_file = "test_course_tracker.db"
        if os.path.exists(cls.test_db_file):
            os.remove(cls.test_db_file)
        cls.db = Database(sqlite_file=cls.test_db_file, force_sqlite=True)
        cls.analytics = AnalyticsManager(cls.db)

        # Flask Test Client pointing to test database
        import app as app_module
        app_module.db = cls.db
        app_module.analytics = cls.analytics
        app.config["TESTING"] = True
        app.config["SECRET_KEY"] = "test-secret-key-123"
        cls.client = app.test_client()

    @classmethod
    def tearDownClass(cls):
        if hasattr(cls, "db") and cls.db._conn:
            cls.db._conn.close()
        if os.path.exists(cls.test_db_file):
            os.remove(cls.test_db_file)

    # ========================================================
    # 1. User Authentication & Profile
    # ========================================================

    def test_01_user_registration_and_hashing(self):
        """Tests user creation, secure password hashing, and retrieval."""
        pwd_hash = generate_password_hash("secret123")
        uid = self.db.create_user(
            username="alice",
            password_hash=pwd_hash,
            name="Alice Sharma",
            subject="Informatics Practices",
            roll_no="12-IP-001",
            email="alice@school.edu",
            avatar_color="#4F46E5"
        )
        self.assertGreater(uid, 0)

        # Verify password hash is verified by werkzeug
        user = self.db.get_user_by_username("alice")
        self.assertIsNotNone(user)
        self.assertEqual(user["name"], "Alice Sharma")
        self.assertTrue(check_password_hash(user["password_hash"], "secret123"))
        self.assertFalse(check_password_hash(user["password_hash"], "wrongpassword"))

        # Verify search by email
        user_by_email = self.db.get_user_by_username("alice@school.edu")
        self.assertIsNotNone(user_by_email)
        self.assertEqual(user_by_email["user_id"], uid)

    def test_02_user_profile_update(self):
        """Tests updating user profile details."""
        user = self.db.get_user_by_username("alice")
        uid = user["user_id"]

        self.db.update_user_profile(
            user_id=uid,
            name="Alice Sharma (Prefect)",
            subject="Computer Science & IP",
            roll_no="12-IP-001",
            email="alice.updated@school.edu",
            avatar_color="#059669"
        )

        updated = self.db.get_user_by_id(uid)
        self.assertEqual(updated["name"], "Alice Sharma (Prefect)")
        self.assertEqual(updated["subject"], "Computer Science & IP")
        self.assertEqual(updated["avatar_color"], "#059669")

    # ========================================================
    # 2. Strict Per-User Data Isolation
    # ========================================================

    def test_03_per_user_data_isolation(self):
        """Verifies User A and User B cannot view or modify each other's data."""
        # Create User 2 (Bob)
        pwd_hash = generate_password_hash("bobpass456")
        bob_id = self.db.create_user(
            username="bob",
            password_hash=pwd_hash,
            name="Bob Verma",
            subject="Information Technology",
            roll_no="12-IT-002"
        )
        alice = self.db.get_user_by_username("alice")
        alice_id = alice["user_id"]

        # Alice creates a course
        alice_cid = self.db.add_course(
            user_id=alice_id,
            course_name="Data Structures with Python",
            platform="Coursera",
            instructor="Prof. Charles"
        )

        # Bob creates a course
        bob_cid = self.db.add_course(
            user_id=bob_id,
            course_name="Web Dev Bootcamp",
            platform="Udemy",
            instructor="Colt Steele"
        )

        # 1. Verify Alice only sees her own course
        alice_courses = self.db.get_courses(user_id=alice_id)
        alice_names = [c["course_name"] for c in alice_courses]
        self.assertIn("Data Structures with Python", alice_names)
        self.assertNotIn("Web Dev Bootcamp", alice_names)

        # 2. Verify Bob only sees his own course
        bob_courses = self.db.get_courses(user_id=bob_id)
        bob_names = [c["course_name"] for c in bob_courses]
        self.assertIn("Web Dev Bootcamp", bob_names)
        self.assertNotIn("Data Structures with Python", bob_names)

        # 3. Bob attempts to access Alice's course directly -> should return None
        tamper_course = self.db.get_course_by_id(user_id=bob_id, course_id=alice_cid)
        self.assertIsNone(tamper_course)

        # 4. Bob attempts to delete Alice's course -> should delete 0 rows
        deleted_count = self.db.delete_course(user_id=bob_id, course_id=alice_cid)
        self.assertEqual(deleted_count, 0)
        self.assertIsNotNone(self.db.get_course_by_id(user_id=alice_id, course_id=alice_cid))

        # 5. Anti-duplicate course name per-user:
        # Alice cannot add another course with same name
        self.assertTrue(self.db.course_exists(alice_id, "Data Structures with Python"))
        # But Bob can add a course with the same name without collision
        self.assertFalse(self.db.course_exists(bob_id, "Data Structures with Python"))

    # ========================================================
    # 3. Modules & Automatic Course Progress Calculation
    # ========================================================

    def test_04_modules_and_progress_calculation(self):
        """
        Tests:
        - Adding modules to a course
        - Auto-calculating course progress: (completed / total) * 100
        - Auto-updating course status: 0% -> Not Started, 1-99% -> In Progress, 100% -> Completed
        - Preserving manual 'On Hold' status override
        """
        alice = self.db.get_user_by_username("alice")
        uid = alice["user_id"]

        cid = self.db.add_course(user_id=uid, course_name="CBSE IP Masterclass", platform="YouTube")
        course = self.db.get_course_by_id(uid, cid)
        self.assertEqual(course["progress_percent"], 0)
        self.assertEqual(course["status"], "Not Started")

        # Add Module 1
        m1 = self.db.add_module(
            user_id=uid,
            course_id=cid,
            title="Unit 1: Data Handling with Pandas",
            key_points="Series, DataFrames, head(), tail()",
            is_important=1
        )
        # Add Module 2
        m2 = self.db.add_module(
            user_id=uid,
            course_id=cid,
            title="Unit 2: Database Query using SQL",
            key_points="SELECT, WHERE, GROUP BY, HAVING",
            is_weak=1
        )

        # Progress with 0 completed out of 2 = 0%
        c_state1 = self.db.get_course_by_id(uid, cid)
        self.assertEqual(c_state1["total_modules"], 2)
        self.assertEqual(c_state1["completed_modules"], 0)
        self.assertEqual(c_state1["progress_percent"], 0)
        self.assertEqual(c_state1["status"], "Not Started")

        # Toggle Module 1 complete -> 1/2 = 50% ("In Progress")
        res1 = self.db.toggle_module_completion(uid, m1, 1)
        self.assertEqual(res1["course_progress"]["progress_percent"], 50)
        self.assertEqual(res1["course_progress"]["status"], "In Progress")

        # Toggle Module 2 complete -> 2/2 = 100% ("Completed")
        res2 = self.db.toggle_module_completion(uid, m2, 1)
        self.assertEqual(res2["course_progress"]["progress_percent"], 100)
        self.assertEqual(res2["course_progress"]["status"], "Completed")

        # Toggle Module 2 back to incomplete -> 1/2 = 50% ("In Progress")
        res3 = self.db.toggle_module_completion(uid, m2, 0)
        self.assertEqual(res3["course_progress"]["progress_percent"], 50)
        self.assertEqual(res3["course_progress"]["status"], "In Progress")

        # Test 'On Hold' preservation
        self.db.update_course(
            user_id=uid,
            course_id=cid,
            course_name="CBSE IP Masterclass",
            platform="YouTube",
            instructor="",
            start_date="",
            end_date="",
            status="On Hold",
            priority="Medium",
            course_link="",
            notes=""
        )
        # Toggle m2 complete: status should remain 'On Hold' even though progress is 100%
        res4 = self.db.toggle_module_completion(uid, m2, 1)
        self.assertEqual(res4["course_progress"]["progress_percent"], 100)
        self.assertEqual(res4["course_progress"]["status"], "On Hold")

    # ========================================================
    # 4. Per-Module Notes, References, and Flags
    # ========================================================

    def test_05_module_notes_references_and_flags(self):
        """Tests updating module notes, JSON reference links, important and weak flags."""
        alice = self.db.get_user_by_username("alice")
        uid = alice["user_id"]
        courses = self.db.get_courses(uid)
        cid = courses[0]["course_id"]

        m_id = self.db.add_module(
            user_id=uid,
            course_id=cid,
            title="Matplotlib Plotting Fundamentals",
            notes="plt.bar() for bar charts, plt.plot() for line graphs",
            reference_links=[{"label": "Matplotlib Docs", "url": "https://matplotlib.org"}],
            is_important=1,
            is_weak=1,
            key_points="xlabel, ylabel, title, legend, grid"
        )

        mod = self.db.get_module_by_id(uid, m_id)
        self.assertIsNotNone(mod)
        self.assertEqual(mod["is_important"], 1)
        self.assertEqual(mod["is_weak"], 1)
        self.assertEqual(mod["key_points"], "xlabel, ylabel, title, legend, grid")
        self.assertEqual(len(mod["reference_links"]), 1)
        self.assertEqual(mod["reference_links"][0]["label"], "Matplotlib Docs")

    # ========================================================
    # 5. Exams, Countdowns, and Urgency Colors
    # ========================================================

    def test_06_exams_and_countdown_urgency(self):
        """Tests exam scheduling, dynamic countdown calculation, and urgency colors."""
        alice = self.db.get_user_by_username("alice")
        uid = alice["user_id"]
        cid = self.db.get_courses(uid)[0]["course_id"]

        today = date.today()
        d_today = today.strftime("%Y-%m-%d")
        d_tomorrow = (today + timedelta(days=1)).strftime("%Y-%m-%d")
        d_three_days = (today + timedelta(days=3)).strftime("%Y-%m-%d")
        d_ten_days = (today + timedelta(days=10)).strftime("%Y-%m-%d")

        e1 = self.db.add_exam(uid, cid, "Today Exam", d_today, "09:00 AM")
        e2 = self.db.add_exam(uid, cid, "Tomorrow Exam", d_tomorrow, "10:00 AM")
        e3 = self.db.add_exam(uid, cid, "Urgent 3-Day Exam", d_three_days, "02:00 PM")
        e4 = self.db.add_exam(uid, cid, "Future 10-Day Exam", d_ten_days, "11:00 AM")

        exams = self.db.get_exams(uid)
        exam_map = {ex["exam_name"]: ex for ex in exams}

        # Check countdown text and urgency color
        self.assertEqual(exam_map["Today Exam"]["urgency_color"], "red")
        self.assertIn("Today", exam_map["Today Exam"]["countdown_text"])

        self.assertEqual(exam_map["Tomorrow Exam"]["urgency_color"], "red")
        self.assertIn("Tomorrow", exam_map["Tomorrow Exam"]["countdown_text"])

        self.assertEqual(exam_map["Urgent 3-Day Exam"]["urgency_color"], "red")
        self.assertEqual(exam_map["Urgent 3-Day Exam"]["days_left"], 3)

        self.assertEqual(exam_map["Future 10-Day Exam"]["urgency_color"], "green")
        self.assertEqual(exam_map["Future 10-Day Exam"]["days_left"], 10)

    # ========================================================
    # 6. Automated "What to Revise" Priority Ordering
    # ========================================================

    def test_07_automated_revision_checklist_priority(self):
        """
        Tests that exam revision checklist is ordered strictly by priority:
        Priority 1: Weak Topics
        Priority 2: Important Concepts
        Priority 3: Incomplete Modules
        Priority 4: Other Completed Modules
        """
        alice = self.db.get_user_by_username("alice")
        uid = alice["user_id"]

        cid = self.db.add_course(uid, "Full Stack Python Track", "Coursera")

        # 1. Weak module (Priority 1)
        m_weak = self.db.add_module(uid, cid, "Topic A: Complex SQL Joins", is_weak=1)
        # 2. Important module (Priority 2)
        m_imp = self.db.add_module(uid, cid, "Topic B: Pandas GroupBy", is_important=1, is_weak=0)
        # 3. Incomplete regular module (Priority 3)
        m_incomp = self.db.add_module(uid, cid, "Topic C: Matplotlib Subplots", is_important=0, is_weak=0)
        # 4. Completed regular module (Priority 4)
        m_comp = self.db.add_module(uid, cid, "Topic D: Python Basics", is_important=0, is_weak=0)
        self.db.toggle_module_completion(uid, m_comp, 1)

        # Schedule Exam
        exam_date = (date.today() + timedelta(days=5)).strftime("%Y-%m-%d")
        eid = self.db.add_exam(uid, cid, "Final Practical Exam", exam_date, covered_module_ids=[m_weak, m_imp, m_incomp, m_comp])

        # Get automated checklist
        checklist = self.db.get_exam_revision_checklist(uid, eid)
        self.assertEqual(checklist["total_items"], 4)
        self.assertEqual(checklist["revised_items"], 0)
        self.assertEqual(checklist["progress_percent"], 0)

        # Verify ordering: Priority 1 (Weak) -> Priority 2 (Important) -> Priority 3 (Incomplete) -> Priority 4 (Completed)
        items = checklist["items"]
        self.assertEqual(items[0]["module_id"], m_weak)
        self.assertEqual(items[0]["priority_rank"], 1)

        self.assertEqual(items[1]["module_id"], m_imp)
        self.assertEqual(items[1]["priority_rank"], 2)

        self.assertEqual(items[2]["module_id"], m_incomp)
        self.assertEqual(items[2]["priority_rank"], 3)

        self.assertEqual(items[3]["module_id"], m_comp)
        self.assertEqual(items[3]["priority_rank"], 4)

        # Mark Weak Topic as revised
        self.db.toggle_revision_item(uid, eid, m_weak, 1)
        updated_checklist = self.db.get_exam_revision_checklist(uid, eid)
        self.assertEqual(updated_checklist["revised_items"], 1)
        self.assertEqual(updated_checklist["progress_percent"], 25)

    # ========================================================
    # 7. Foreign Key Cascading Deletions
    # ========================================================

    def test_08_cascading_deletes(self):
        """Verifies deleting a course cascades to its modules, logs, deadlines, exams, and revision items."""
        alice = self.db.get_user_by_username("alice")
        uid = alice["user_id"]

        cid = self.db.add_course(uid, "Ephemeral Course", "edX")
        mid = self.db.add_module(uid, cid, "Ephemeral Module")
        lid = self.db.add_study_log(uid, cid, date.today().strftime("%Y-%m-%d"), 2.0, "Testing cascade")
        did = self.db.add_deadline(uid, cid, "Ephemeral Task", date.today().strftime("%Y-%m-%d"))
        eid = self.db.add_exam(uid, cid, "Ephemeral Exam", date.today().strftime("%Y-%m-%d"), covered_module_ids=[mid])
        self.db.toggle_revision_item(uid, eid, mid, 1)

        # Verify items exist
        self.assertIsNotNone(self.db.get_module_by_id(uid, mid))
        self.assertEqual(len(self.db.get_study_logs(uid, cid)), 1)
        self.assertEqual(len(self.db.get_deadlines(uid, cid)), 1)
        self.assertIsNotNone(self.db.get_exam_by_id(uid, eid))

        # Delete Course
        self.db.delete_course(uid, cid)

        # Verify all child rows were deleted by SQLite cascade
        self.assertIsNone(self.db.get_course_by_id(uid, cid))
        self.assertIsNone(self.db.get_module_by_id(uid, mid))
        self.assertEqual(len(self.db.get_study_logs(uid, cid)), 0)
        self.assertEqual(len(self.db.get_deadlines(uid, cid)), 0)
        self.assertIsNone(self.db.get_exam_by_id(uid, eid))

    # ========================================================
    # 8. Flask REST API & Session Flow
    # ========================================================

    def test_09_flask_api_and_session_auth(self):
        """Tests registration, login, session protection, and API data isolation via HTTP client."""
        # 1. Unauthenticated request to protected API -> 401
        res = self.client.get("/api/courses")
        self.assertEqual(res.status_code, 401)

        # 2. Register via API
        reg_payload = {
            "name": "Charlie Patel",
            "username": "charlie",
            "password": "charliepass",
            "subject": "Informatics Practices",
            "roll_no": "12-IP-099",
            "email": "charlie@test.org"
        }
        res_reg = self.client.post("/api/auth/register", json=reg_payload)
        self.assertEqual(res_reg.status_code, 200)
        data_reg = res_reg.get_json()
        self.assertTrue(data_reg["success"])
        self.assertEqual(data_reg["user"]["username"], "charlie")

        # 3. /api/auth/me should return authenticated user
        res_me = self.client.get("/api/auth/me")
        self.assertEqual(res_me.status_code, 200)
        self.assertTrue(res_me.get_json()["authenticated"])

        # 4. Clean empty state for new user: 0 courses
        res_c = self.client.get("/api/courses")
        self.assertEqual(res_c.status_code, 200)
        self.assertEqual(len(res_c.get_json()), 0)

        # 5. Create course via API
        res_add = self.client.post("/api/courses", json={"course_name": "API Python Course", "platform": "Coursera"})
        self.assertEqual(res_add.status_code, 200)
        cid = res_add.get_json()["course_id"]

        # 6. Add Module via API
        res_mod = self.client.post(f"/api/courses/{cid}/modules", json={"title": "API Module 1", "is_weak": True})
        self.assertEqual(res_mod.status_code, 200)
        mid = res_mod.get_json()["module"]["module_id"]

        # 7. Toggle Module via API
        res_toggle = self.client.post(f"/api/modules/{mid}/toggle", json={"is_completed": True})
        self.assertEqual(res_toggle.status_code, 200)
        self.assertEqual(res_toggle.get_json()["course_progress"]["progress_percent"], 100)
        self.assertEqual(res_toggle.get_json()["course_progress"]["status"], "Completed")

        # 8. Logout
        res_logout = self.client.post("/api/auth/logout")
        self.assertEqual(res_logout.status_code, 200)

        # 9. Next call to /api/courses should be 401 Unauthorized
        res_after = self.client.get("/api/courses")
        self.assertEqual(res_after.status_code, 401)

    # ========================================================
    # 9. Analytics & KPI Engine
    # ========================================================

    def test_10_analytics_empty_and_populated_states(self):
        """Verifies AnalyticsManager handles both completely clean accounts and populated accounts without errors."""
        # Empty user test
        pwd_hash = generate_password_hash("danpass")
        dan_id = self.db.create_user(username="dan", password_hash=pwd_hash, name="Dan", subject="IP")

        kpis_empty = self.analytics.get_kpi_summary(dan_id)
        self.assertEqual(kpis_empty["total_courses"], 0)
        self.assertEqual(kpis_empty["total_hours"], 0.0)
        self.assertEqual(kpis_empty["avg_progress"], 0.0)
        self.assertEqual(kpis_empty["pending_deadlines"], 0)
        self.assertEqual(kpis_empty["upcoming_exams"], 0)
        self.assertEqual(kpis_empty["most_used_platform"], "N/A")

        # Populated user test (Alice)
        alice = self.db.get_user_by_username("alice")
        kpis_alice = self.analytics.get_kpi_summary(alice["user_id"])
        self.assertGreaterEqual(kpis_alice["total_courses"], 1)


if __name__ == "__main__":
    unittest.main()
