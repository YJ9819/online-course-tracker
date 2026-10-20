"""
database.py - Database Layer for Online Course Tracker
Supports SQLite with foreign keys and MySQL compatibility.
Features:
  - User authentication and per-user data isolation across all tables
  - Module-based automatic progress tracking
  - Notes, links, key points, important/weak flags per module
  - Exam management with countdowns, reminders, and priority revision lists
  - Parameterized queries to prevent SQL injection
"""

import os
import json
import sqlite3
from datetime import datetime, date
from typing import List, Dict, Any, Optional

try:
    import mysql.connector
    from mysql.connector import Error as MySQLError
    MYSQL_AVAILABLE = True
except ImportError:
    MYSQL_AVAILABLE = False
    MySQLError = Exception


class Database:
    def __init__(
        self,
        host: str = "localhost",
        user: str = "root",
        password: str = "",
        database: str = "course_tracker_db",
        sqlite_file: str = "course_tracker.db",
        force_sqlite: bool = False
    ):
        self.host = os.getenv("DB_HOST", host)
        self.user = os.getenv("DB_USER", user)
        self.password = os.getenv("DB_PASSWORD", password)
        self.database = os.getenv("DB_NAME", database)
        self.sqlite_file = sqlite_file
        self.force_sqlite = force_sqlite
        
        self.is_sqlite = False
        self.engine_name = "Unknown"
        self._init_connection()
        self._migrate_schema()
        self._create_tables()

    def _init_connection(self):
        """Attempts to connect to MySQL; falls back to SQLite seamlessly."""
        if not self.force_sqlite and MYSQL_AVAILABLE:
            try:
                server_conn = mysql.connector.connect(
                    host=self.host,
                    user=self.user,
                    password=self.password,
                    connect_timeout=2
                )
                cursor = server_conn.cursor()
                cursor.execute(f"CREATE DATABASE IF NOT EXISTS `{self.database}`")
                cursor.close()
                server_conn.close()

                self._conn = mysql.connector.connect(
                    host=self.host,
                    user=self.user,
                    password=self.password,
                    database=self.database
                )
                self.is_sqlite = False
                self.engine_name = f"MySQL ({self.database}@{self.host})"
                print(f"[INFO] Successfully connected to {self.engine_name}")
                return
            except Exception as e:
                print(f"[WARN] MySQL connection failed ({e}). Falling back to SQLite.")

        # SQLite backend with foreign keys enabled
        self.is_sqlite = True
        self.engine_name = f"SQLite ({self.sqlite_file})"
        self._conn = sqlite3.connect(self.sqlite_file, check_same_thread=False)
        self._conn.row_factory = sqlite3.Row
        with self._conn:
            self._conn.execute("PRAGMA foreign_keys = ON;")
        print(f"[INFO] Using {self.engine_name}")

    def get_connection(self):
        """Returns active database connection with foreign keys enabled."""
        if self.is_sqlite:
            return self._conn
        else:
            try:
                if not self._conn.is_connected():
                    self._conn.reconnect(attempts=2, delay=1)
            except Exception:
                self._init_connection()
            return self._conn

    def _format_query(self, query: str) -> str:
        """Adapts %s placeholders to ? when running on SQLite."""
        if self.is_sqlite:
            return query.replace("%s", "?")
        return query

    def execute_query(self, query: str, params: tuple = ()) -> int:
        """Executes INSERT, UPDATE, DELETE queries. Returns lastrowid or affected rows."""
        conn = self.get_connection()
        formatted_sql = self._format_query(query)
        cursor = conn.cursor()
        try:
            cursor.execute(formatted_sql, params)
            if not self.is_sqlite:
                conn.commit()
            else:
                self._conn.commit()
            clean_query = query.strip().upper()
            if clean_query.startswith("INSERT"):
                return cursor.lastrowid if cursor.lastrowid else cursor.rowcount
            return cursor.rowcount
        finally:
            cursor.close()

    def fetch_all(self, query: str, params: tuple = ()) -> List[Dict[str, Any]]:
        """Executes SELECT queries and returns rows as list of dictionaries."""
        conn = self.get_connection()
        formatted_sql = self._format_query(query)
        
        if self.is_sqlite:
            cursor = conn.cursor()
            try:
                cursor.execute(formatted_sql, params)
                rows = cursor.fetchall()
                return [dict(row) for row in rows]
            finally:
                cursor.close()
        else:
            cursor = conn.cursor(dictionary=True)
            try:
                cursor.execute(formatted_sql, params)
                return cursor.fetchall()
            finally:
                cursor.close()

    def fetch_one(self, query: str, params: tuple = ()) -> Optional[Dict[str, Any]]:
        """Fetches a single record as a dictionary."""
        rows = self.fetch_all(query, params)
        return rows[0] if rows else None

    def _migrate_schema(self):
        """
        Safely checks if old schema (without user_id) exists.
        If detected, migrates or resets so all tables have strict user_id foreign keys.
        """
        try:
            conn = self.get_connection()
            cursor = conn.cursor()
            if self.is_sqlite:
                cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='courses'")
                if cursor.fetchone():
                    cursor.execute("PRAGMA table_info(courses)")
                    cols = [row[1] for row in cursor.fetchall()]
                    if "user_id" not in cols:
                        print("[INFO] Upgrading database to multi-user isolated schema...")
                        tables_to_drop = [
                            "revision_items", "exams", "modules", "certificates", 
                            "deadlines", "study_log", "courses", "users"
                        ]
                        for t in tables_to_drop:
                            cursor.execute(f"DROP TABLE IF EXISTS {t}")
                        self._conn.commit()
            cursor.close()
        except Exception as e:
            print(f"[WARN] Schema migration check notice: {e}")

    def reset_database(self):
        """Completely resets all tables for clean zero-start testing."""
        conn = self.get_connection()
        cursor = conn.cursor()
        tables = ["revision_items", "exams", "modules", "certificates", "deadlines", "study_log", "courses", "users"]
        for t in tables:
            cursor.execute(f"DROP TABLE IF EXISTS {t}")
        if self.is_sqlite:
            self._conn.commit()
        else:
            conn.commit()
        cursor.close()
        self._create_tables()

    def _create_tables(self):
        """Creates the full normalized multi-user schema."""
        if self.is_sqlite:
            queries = [
                """
                CREATE TABLE IF NOT EXISTS users (
                    user_id INTEGER PRIMARY KEY AUTOINCREMENT,
                    username TEXT UNIQUE NOT NULL,
                    password_hash TEXT NOT NULL,
                    name TEXT NOT NULL,
                    subject TEXT NOT NULL,
                    roll_no TEXT DEFAULT '',
                    email TEXT DEFAULT '',
                    avatar_color TEXT DEFAULT '#4F46E5',
                    created_at TEXT DEFAULT (datetime('now', 'localtime'))
                );
                """,
                """
                CREATE TABLE IF NOT EXISTS courses (
                    course_id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id INTEGER NOT NULL,
                    course_name TEXT NOT NULL,
                    platform TEXT NOT NULL,
                    instructor TEXT DEFAULT '',
                    start_date TEXT DEFAULT '',
                    end_date TEXT DEFAULT '',
                    status TEXT DEFAULT 'Not Started',
                    progress_percent INTEGER DEFAULT 0,
                    priority TEXT DEFAULT 'Medium',
                    course_link TEXT DEFAULT '',
                    notes TEXT DEFAULT '',
                    created_at TEXT DEFAULT (datetime('now', 'localtime')),
                    FOREIGN KEY (user_id) REFERENCES users (user_id) ON DELETE CASCADE
                );
                """,
                """
                CREATE TABLE IF NOT EXISTS modules (
                    module_id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id INTEGER NOT NULL,
                    course_id INTEGER NOT NULL,
                    title TEXT NOT NULL,
                    position INTEGER DEFAULT 1,
                    is_completed INTEGER DEFAULT 0,
                    completed_date TEXT DEFAULT '',
                    notes TEXT DEFAULT '',
                    reference_links TEXT DEFAULT '[]',
                    is_important INTEGER DEFAULT 0,
                    is_weak INTEGER DEFAULT 0,
                    key_points TEXT DEFAULT '',
                    FOREIGN KEY (user_id) REFERENCES users (user_id) ON DELETE CASCADE,
                    FOREIGN KEY (course_id) REFERENCES courses (course_id) ON DELETE CASCADE
                );
                """,
                """
                CREATE TABLE IF NOT EXISTS study_log (
                    log_id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id INTEGER NOT NULL,
                    course_id INTEGER NOT NULL,
                    study_date TEXT NOT NULL,
                    hours_spent REAL NOT NULL,
                    topic_covered TEXT DEFAULT '',
                    FOREIGN KEY (user_id) REFERENCES users (user_id) ON DELETE CASCADE,
                    FOREIGN KEY (course_id) REFERENCES courses (course_id) ON DELETE CASCADE
                );
                """,
                """
                CREATE TABLE IF NOT EXISTS deadlines (
                    deadline_id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id INTEGER NOT NULL,
                    course_id INTEGER NOT NULL,
                    task_name TEXT NOT NULL,
                    due_date TEXT NOT NULL,
                    is_done INTEGER DEFAULT 0,
                    FOREIGN KEY (user_id) REFERENCES users (user_id) ON DELETE CASCADE,
                    FOREIGN KEY (course_id) REFERENCES courses (course_id) ON DELETE CASCADE
                );
                """,
                """
                CREATE TABLE IF NOT EXISTS certificates (
                    cert_id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id INTEGER NOT NULL,
                    course_id INTEGER NOT NULL,
                    certificate_link TEXT NOT NULL,
                    issue_date TEXT DEFAULT '',
                    grade TEXT DEFAULT '',
                    FOREIGN KEY (user_id) REFERENCES users (user_id) ON DELETE CASCADE,
                    FOREIGN KEY (course_id) REFERENCES courses (course_id) ON DELETE CASCADE
                );
                """,
                """
                CREATE TABLE IF NOT EXISTS exams (
                    exam_id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id INTEGER NOT NULL,
                    course_id INTEGER NOT NULL,
                    exam_name TEXT NOT NULL,
                    exam_date TEXT NOT NULL,
                    exam_time TEXT DEFAULT '',
                    syllabus_notes TEXT DEFAULT '',
                    covered_module_ids TEXT DEFAULT '[]',
                    created_at TEXT DEFAULT (datetime('now', 'localtime')),
                    FOREIGN KEY (user_id) REFERENCES users (user_id) ON DELETE CASCADE,
                    FOREIGN KEY (course_id) REFERENCES courses (course_id) ON DELETE CASCADE
                );
                """,
                """
                CREATE TABLE IF NOT EXISTS revision_items (
                    revision_id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id INTEGER NOT NULL,
                    exam_id INTEGER NOT NULL,
                    module_id INTEGER NOT NULL,
                    is_revised INTEGER DEFAULT 0,
                    revised_at TEXT DEFAULT '',
                    FOREIGN KEY (user_id) REFERENCES users (user_id) ON DELETE CASCADE,
                    FOREIGN KEY (exam_id) REFERENCES exams (exam_id) ON DELETE CASCADE,
                    FOREIGN KEY (module_id) REFERENCES modules (module_id) ON DELETE CASCADE,
                    UNIQUE(exam_id, module_id)
                );
                """
            ]
        else:
            queries = [
                """
                CREATE TABLE IF NOT EXISTS users (
                    user_id INT AUTO_INCREMENT PRIMARY KEY,
                    username VARCHAR(100) UNIQUE NOT NULL,
                    password_hash VARCHAR(255) NOT NULL,
                    name VARCHAR(100) NOT NULL,
                    subject VARCHAR(100) NOT NULL,
                    roll_no VARCHAR(50) DEFAULT '',
                    email VARCHAR(150) DEFAULT '',
                    avatar_color VARCHAR(20) DEFAULT '#4F46E5',
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                );
                """,
                """
                CREATE TABLE IF NOT EXISTS courses (
                    course_id INT AUTO_INCREMENT PRIMARY KEY,
                    user_id INT NOT NULL,
                    course_name VARCHAR(150) NOT NULL,
                    platform VARCHAR(50) NOT NULL,
                    instructor VARCHAR(100) DEFAULT '',
                    start_date DATE,
                    end_date DATE,
                    status VARCHAR(20) DEFAULT 'Not Started',
                    progress_percent INT DEFAULT 0,
                    priority VARCHAR(10) DEFAULT 'Medium',
                    course_link VARCHAR(255) DEFAULT '',
                    notes TEXT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (user_id) REFERENCES users(user_id) ON DELETE CASCADE
                );
                """,
                """
                CREATE TABLE IF NOT EXISTS modules (
                    module_id INT AUTO_INCREMENT PRIMARY KEY,
                    user_id INT NOT NULL,
                    course_id INT NOT NULL,
                    title VARCHAR(200) NOT NULL,
                    position INT DEFAULT 1,
                    is_completed INT DEFAULT 0,
                    completed_date DATE,
                    notes TEXT,
                    reference_links TEXT,
                    is_important INT DEFAULT 0,
                    is_weak INT DEFAULT 0,
                    key_points TEXT,
                    FOREIGN KEY (user_id) REFERENCES users(user_id) ON DELETE CASCADE,
                    FOREIGN KEY (course_id) REFERENCES courses(course_id) ON DELETE CASCADE
                );
                """,
                """
                CREATE TABLE IF NOT EXISTS study_log (
                    log_id INT AUTO_INCREMENT PRIMARY KEY,
                    user_id INT NOT NULL,
                    course_id INT NOT NULL,
                    study_date DATE NOT NULL,
                    hours_spent DECIMAL(4, 2) NOT NULL,
                    topic_covered VARCHAR(200) DEFAULT '',
                    FOREIGN KEY (user_id) REFERENCES users(user_id) ON DELETE CASCADE,
                    FOREIGN KEY (course_id) REFERENCES courses(course_id) ON DELETE CASCADE
                );
                """,
                """
                CREATE TABLE IF NOT EXISTS deadlines (
                    deadline_id INT AUTO_INCREMENT PRIMARY KEY,
                    user_id INT NOT NULL,
                    course_id INT NOT NULL,
                    task_name VARCHAR(150) NOT NULL,
                    due_date DATE NOT NULL,
                    is_done INT DEFAULT 0,
                    FOREIGN KEY (user_id) REFERENCES users(user_id) ON DELETE CASCADE,
                    FOREIGN KEY (course_id) REFERENCES courses(course_id) ON DELETE CASCADE
                );
                """,
                """
                CREATE TABLE IF NOT EXISTS certificates (
                    cert_id INT AUTO_INCREMENT PRIMARY KEY,
                    user_id INT NOT NULL,
                    course_id INT NOT NULL,
                    certificate_link VARCHAR(255) NOT NULL,
                    issue_date DATE,
                    grade VARCHAR(50) DEFAULT '',
                    FOREIGN KEY (user_id) REFERENCES users(user_id) ON DELETE CASCADE,
                    FOREIGN KEY (course_id) REFERENCES courses(course_id) ON DELETE CASCADE
                );
                """,
                """
                CREATE TABLE IF NOT EXISTS exams (
                    exam_id INT AUTO_INCREMENT PRIMARY KEY,
                    user_id INT NOT NULL,
                    course_id INT NOT NULL,
                    exam_name VARCHAR(150) NOT NULL,
                    exam_date DATE NOT NULL,
                    exam_time VARCHAR(20) DEFAULT '',
                    syllabus_notes TEXT,
                    covered_module_ids TEXT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (user_id) REFERENCES users(user_id) ON DELETE CASCADE,
                    FOREIGN KEY (course_id) REFERENCES courses(course_id) ON DELETE CASCADE
                );
                """,
                """
                CREATE TABLE IF NOT EXISTS revision_items (
                    revision_id INT AUTO_INCREMENT PRIMARY KEY,
                    user_id INT NOT NULL,
                    exam_id INT NOT NULL,
                    module_id INT NOT NULL,
                    is_revised INT DEFAULT 0,
                    revised_at TIMESTAMP,
                    FOREIGN KEY (user_id) REFERENCES users(user_id) ON DELETE CASCADE,
                    FOREIGN KEY (exam_id) REFERENCES exams(exam_id) ON DELETE CASCADE,
                    FOREIGN KEY (module_id) REFERENCES modules(module_id) ON DELETE CASCADE,
                    UNIQUE(exam_id, module_id)
                );
                """
            ]

        conn = self.get_connection()
        cursor = conn.cursor()
        try:
            for q in queries:
                cursor.execute(q)
            if self.is_sqlite:
                self._conn.commit()
            else:
                conn.commit()
        finally:
            cursor.close()

    # ========================================================
    # 1. User Authentication & Profile
    # ========================================================

    def create_user(
        self,
        username: str,
        password_hash: str,
        name: str,
        subject: str,
        roll_no: str = "",
        email: str = "",
        avatar_color: str = "#4F46E5"
    ) -> int:
        query = """
            INSERT INTO users (username, password_hash, name, subject, roll_no, email, avatar_color)
            VALUES (%s, %s, %s, %s, %s, %s, %s)
        """
        return self.execute_query(query, (username.strip().lower(), password_hash, name.strip(), subject.strip(), roll_no.strip(), email.strip().lower(), avatar_color))

    def get_user_by_username(self, username_or_email: str) -> Optional[Dict[str, Any]]:
        val = username_or_email.strip().lower()
        query = "SELECT * FROM users WHERE username = %s OR (email != '' AND email = %s) LIMIT 1"
        return self.fetch_one(query, (val, val))

    def get_user_by_id(self, user_id: int) -> Optional[Dict[str, Any]]:
        return self.fetch_one("SELECT * FROM users WHERE user_id = %s", (user_id,))

    def update_user_profile(
        self,
        user_id: int,
        name: str,
        subject: str,
        roll_no: str = "",
        email: str = "",
        avatar_color: str = "#4F46E5"
    ) -> int:
        query = """
            UPDATE users SET 
                name = %s,
                subject = %s,
                roll_no = %s,
                email = %s,
                avatar_color = %s
            WHERE user_id = %s
        """
        return self.execute_query(query, (name.strip(), subject.strip(), roll_no.strip(), email.strip().lower(), avatar_color, user_id))

    # ========================================================
    # 2. Courses Management (Per-User)
    # ========================================================

    def course_exists(self, user_id: int, course_name: str, exclude_id: Optional[int] = None) -> bool:
        """Prevents accidental duplicate course names for the same user."""
        query = "SELECT course_id FROM courses WHERE user_id = %s AND LOWER(course_name) = LOWER(%s)"
        params = [user_id, course_name.strip()]
        if exclude_id:
            query += " AND course_id != %s"
            params.append(exclude_id)
        return bool(self.fetch_one(query, tuple(params)))

    def add_course(
        self,
        user_id: int,
        course_name: str,
        platform: str,
        instructor: str = "",
        start_date: str = "",
        end_date: str = "",
        status: str = "Not Started",
        progress_percent: int = 0,
        priority: str = "Medium",
        course_link: str = "",
        notes: str = ""
    ) -> int:
        query = """
            INSERT INTO courses 
            (user_id, course_name, platform, instructor, start_date, end_date, status, progress_percent, priority, course_link, notes)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
        """
        return self.execute_query(
            query,
            (user_id, course_name.strip(), platform.strip(), instructor.strip(), start_date, end_date, status, progress_percent, priority, course_link.strip(), notes.strip())
        )

    def get_courses(
        self,
        user_id: int,
        search: str = "",
        status_filter: str = "",
        platform_filter: str = ""
    ) -> List[Dict[str, Any]]:
        query = "SELECT * FROM courses WHERE user_id = %s"
        params = [user_id]

        if search:
            query += " AND (course_name LIKE %s OR instructor LIKE %s)"
            params.extend([f"%{search}%", f"%{search}%"])
        if status_filter and status_filter != "All":
            query += " AND status = %s"
            params.append(status_filter)
        if platform_filter and platform_filter != "All":
            query += " AND platform = %s"
            params.append(platform_filter)

        query += " ORDER BY course_id DESC"
        courses = self.fetch_all(query, tuple(params))

        # Include module count metrics for each course
        for c in courses:
            cid = c["course_id"]
            m_stats = self.fetch_one(
                "SELECT COUNT(*) AS total_modules, SUM(CASE WHEN is_completed = 1 THEN 1 ELSE 0 END) AS completed_modules FROM modules WHERE user_id = %s AND course_id = %s",
                (user_id, cid)
            )
            c["total_modules"] = m_stats["total_modules"] if m_stats else 0
            c["completed_modules"] = m_stats["completed_modules"] if m_stats and m_stats["completed_modules"] else 0
        return courses

    def get_course_by_id(self, user_id: int, course_id: int) -> Optional[Dict[str, Any]]:
        course = self.fetch_one("SELECT * FROM courses WHERE user_id = %s AND course_id = %s", (user_id, course_id))
        if course:
            m_stats = self.fetch_one(
                "SELECT COUNT(*) AS total_modules, SUM(CASE WHEN is_completed = 1 THEN 1 ELSE 0 END) AS completed_modules FROM modules WHERE user_id = %s AND course_id = %s",
                (user_id, course_id)
            )
            course["total_modules"] = m_stats["total_modules"] if m_stats else 0
            course["completed_modules"] = m_stats["completed_modules"] if m_stats and m_stats["completed_modules"] else 0
        return course

    def update_course(
        self,
        user_id: int,
        course_id: int,
        course_name: str,
        platform: str,
        instructor: str,
        start_date: str,
        end_date: str,
        status: str,
        priority: str,
        course_link: str,
        notes: str
    ) -> int:
        query = """
            UPDATE courses SET 
                course_name = %s,
                platform = %s,
                instructor = %s,
                start_date = %s,
                end_date = %s,
                status = %s,
                priority = %s,
                course_link = %s,
                notes = %s
            WHERE user_id = %s AND course_id = %s
        """
        res = self.execute_query(
            query,
            (course_name.strip(), platform.strip(), instructor.strip(), start_date, end_date, status, priority, course_link.strip(), notes.strip(), user_id, course_id)
        )
        self.recalculate_course_progress(user_id, course_id)
        return res

    def delete_course(self, user_id: int, course_id: int) -> int:
        """Deletes course with cascade (removes modules, logs, deadlines, exams)."""
        return self.execute_query("DELETE FROM courses WHERE user_id = %s AND course_id = %s", (user_id, course_id))

    def recalculate_course_progress(self, user_id: int, course_id: int) -> Dict[str, Any]:
        """
        Recalculates progress = (completed_modules / total_modules) * 100.
        Updates status automatically:
          0% -> 'Not Started'
          1% - 99% -> 'In Progress'
          100% -> 'Completed'
          Preserves 'On Hold' as a manual user override.
        """
        course = self.fetch_one("SELECT status FROM courses WHERE user_id = %s AND course_id = %s", (user_id, course_id))
        if not course:
            return {"progress_percent": 0, "status": "Not Started"}

        current_status = course.get("status", "Not Started")
        stats = self.fetch_one(
            "SELECT COUNT(*) AS total, SUM(CASE WHEN is_completed = 1 THEN 1 ELSE 0 END) AS completed FROM modules WHERE user_id = %s AND course_id = %s",
            (user_id, course_id)
        )
        total = stats["total"] if stats else 0
        completed = stats["completed"] if stats and stats["completed"] else 0

        progress_pct = round((completed / total) * 100) if total > 0 else 0

        if current_status == "On Hold":
            new_status = "On Hold"
        else:
            if progress_pct == 0:
                new_status = "Not Started"
            elif progress_pct == 100:
                new_status = "Completed"
            else:
                new_status = "In Progress"

        self.execute_query(
            "UPDATE courses SET progress_percent = %s, status = %s WHERE user_id = %s AND course_id = %s",
            (progress_pct, new_status, user_id, course_id)
        )
        return {"progress_percent": progress_pct, "status": new_status, "total_modules": total, "completed_modules": completed}

    # ========================================================
    # 3. Modules & Notes/References Management
    # ========================================================

    def add_module(
        self,
        user_id: int,
        course_id: int,
        title: str,
        position: Optional[int] = None,
        notes: str = "",
        reference_links: str = "[]",
        is_important: int = 0,
        is_weak: int = 0,
        key_points: str = ""
    ) -> int:
        if position is None:
            max_pos = self.fetch_one(
                "SELECT COALESCE(MAX(position), 0) AS max_p FROM modules WHERE user_id = %s AND course_id = %s",
                (user_id, course_id)
            )
            position = (max_pos["max_p"] if max_pos else 0) + 1

        if isinstance(reference_links, (list, dict)):
            reference_links = json.dumps(reference_links)

        query = """
            INSERT INTO modules 
            (user_id, course_id, title, position, is_completed, completed_date, notes, reference_links, is_important, is_weak, key_points)
            VALUES (%s, %s, %s, %s, 0, '', %s, %s, %s, %s, %s)
        """
        mid = self.execute_query(
            query,
            (user_id, course_id, title.strip(), position, notes.strip(), reference_links, is_important, is_weak, key_points.strip())
        )
        self.recalculate_course_progress(user_id, course_id)
        return mid

    def get_course_modules(self, user_id: int, course_id: int) -> List[Dict[str, Any]]:
        query = """
            SELECT * FROM modules 
            WHERE user_id = %s AND course_id = %s 
            ORDER BY position ASC, module_id ASC
        """
        modules = self.fetch_all(query, (user_id, course_id))
        for m in modules:
            try:
                m["reference_links"] = json.loads(m.get("reference_links") or "[]")
            except Exception:
                m["reference_links"] = []
        return modules

    def get_module_by_id(self, user_id: int, module_id: int) -> Optional[Dict[str, Any]]:
        m = self.fetch_one("SELECT * FROM modules WHERE user_id = %s AND module_id = %s", (user_id, module_id))
        if m:
            try:
                m["reference_links"] = json.loads(m.get("reference_links") or "[]")
            except Exception:
                m["reference_links"] = []
        return m

    def update_module(
        self,
        user_id: int,
        module_id: int,
        title: str,
        notes: str = "",
        reference_links: str = "[]",
        is_important: int = 0,
        is_weak: int = 0,
        key_points: str = ""
    ) -> int:
        if isinstance(reference_links, list):
            reference_links = json.dumps(reference_links)

        query = """
            UPDATE modules SET 
                title = %s,
                notes = %s,
                reference_links = %s,
                is_important = %s,
                is_weak = %s,
                key_points = %s
            WHERE user_id = %s AND module_id = %s
        """
        return self.execute_query(
            query,
            (title.strip(), notes.strip(), reference_links, is_important, is_weak, key_points.strip(), user_id, module_id)
        )

    def toggle_module_completion(self, user_id: int, module_id: int, is_completed: int) -> Dict[str, Any]:
        """Toggles module completed/undo state and recalculates course progress."""
        completed_date = date.today().strftime("%Y-%m-%d") if is_completed else ""
        query = "UPDATE modules SET is_completed = %s, completed_date = %s WHERE user_id = %s AND module_id = %s"
        self.execute_query(query, (is_completed, completed_date, user_id, module_id))

        mod = self.get_module_by_id(user_id, module_id)
        if mod:
            progress_info = self.recalculate_course_progress(user_id, mod["course_id"])
            return {"module": mod, "course_progress": progress_info}
        return {"module": None, "course_progress": None}

    def delete_module(self, user_id: int, module_id: int) -> int:
        mod = self.get_module_by_id(user_id, module_id)
        if not mod:
            return 0
        cid = mod["course_id"]
        res = self.execute_query("DELETE FROM modules WHERE user_id = %s AND module_id = %s", (user_id, module_id))
        self.recalculate_course_progress(user_id, cid)
        return res

    # ========================================================
    # 4. Daily Study Log Operations (Per-User)
    # ========================================================

    def study_log_exists(self, user_id: int, course_id: int, study_date: str, topic_covered: str) -> bool:
        """Anti-duplicate check for rapid double-clicks on saving study sessions."""
        query = """
            SELECT log_id FROM study_log 
            WHERE user_id = %s AND course_id = %s AND study_date = %s AND LOWER(topic_covered) = LOWER(%s)
        """
        return bool(self.fetch_one(query, (user_id, course_id, study_date, topic_covered.strip())))

    def add_study_log(self, user_id: int, course_id: int, study_date: str, hours_spent: float, topic_covered: str = "") -> int:
        query = """
            INSERT INTO study_log (user_id, course_id, study_date, hours_spent, topic_covered)
            VALUES (%s, %s, %s, %s, %s)
        """
        return self.execute_query(query, (user_id, course_id, study_date, hours_spent, topic_covered.strip()))

    def get_study_logs(self, user_id: int, course_id: Optional[int] = None) -> List[Dict[str, Any]]:
        query = """
            SELECT s.log_id, s.course_id, c.course_name, c.platform, s.study_date, s.hours_spent, s.topic_covered
            FROM study_log s
            JOIN courses c ON s.course_id = c.course_id
            WHERE s.user_id = %s
        """
        params = [user_id]
        if course_id:
            query += " AND s.course_id = %s"
            params.append(course_id)
        query += " ORDER BY s.study_date DESC, s.log_id DESC"
        return self.fetch_all(query, tuple(params))

    def delete_study_log(self, user_id: int, log_id: int) -> int:
        return self.execute_query("DELETE FROM study_log WHERE user_id = %s AND log_id = %s", (user_id, log_id))

    # ========================================================
    # 5. Deadlines & Tasks Operations (Per-User)
    # ========================================================

    def deadline_exists(self, user_id: int, course_id: int, task_name: str, due_date: str) -> bool:
        query = """
            SELECT deadline_id FROM deadlines 
            WHERE user_id = %s AND course_id = %s AND LOWER(task_name) = LOWER(%s) AND due_date = %s
        """
        return bool(self.fetch_one(query, (user_id, course_id, task_name.strip(), due_date)))

    def add_deadline(self, user_id: int, course_id: int, task_name: str, due_date: str, is_done: int = 0) -> int:
        query = """
            INSERT INTO deadlines (user_id, course_id, task_name, due_date, is_done)
            VALUES (%s, %s, %s, %s, %s)
        """
        return self.execute_query(query, (user_id, course_id, task_name.strip(), due_date, is_done))

    def get_deadlines(self, user_id: int, course_id: Optional[int] = None, include_completed: bool = True) -> List[Dict[str, Any]]:
        query = """
            SELECT d.deadline_id, d.course_id, c.course_name, c.platform, d.task_name, d.due_date, d.is_done
            FROM deadlines d
            JOIN courses c ON d.course_id = c.course_id
            WHERE d.user_id = %s
        """
        params = [user_id]
        if course_id:
            query += " AND d.course_id = %s"
            params.append(course_id)
        if not include_completed:
            query += " AND d.is_done = 0"
        query += " ORDER BY d.is_done ASC, d.due_date ASC"
        return self.fetch_all(query, tuple(params))

    def toggle_deadline(self, user_id: int, deadline_id: int, is_done: int) -> int:
        return self.execute_query(
            "UPDATE deadlines SET is_done = %s WHERE user_id = %s AND deadline_id = %s",
            (is_done, user_id, deadline_id)
        )

    def delete_deadline(self, user_id: int, deadline_id: int) -> int:
        return self.execute_query("DELETE FROM deadlines WHERE user_id = %s AND deadline_id = %s", (user_id, deadline_id))

    # ========================================================
    # 6. Certificates Operations (Per-User)
    # ========================================================

    def add_certificate(self, user_id: int, course_id: int, certificate_link: str, issue_date: str = "", grade: str = "") -> int:
        query = """
            INSERT INTO certificates (user_id, course_id, certificate_link, issue_date, grade)
            VALUES (%s, %s, %s, %s, %s)
        """
        return self.execute_query(query, (user_id, course_id, certificate_link.strip(), issue_date, grade.strip()))

    def get_certificates(self, user_id: int) -> List[Dict[str, Any]]:
        query = """
            SELECT cert.cert_id, cert.course_id, c.course_name, c.platform, cert.certificate_link, cert.issue_date, cert.grade
            FROM certificates cert
            JOIN courses c ON cert.course_id = c.course_id
            WHERE cert.user_id = %s
            ORDER BY cert.cert_id DESC
        """
        return self.fetch_all(query, (user_id,))

    def delete_certificate(self, user_id: int, cert_id: int) -> int:
        return self.execute_query("DELETE FROM certificates WHERE user_id = %s AND cert_id = %s", (user_id, cert_id))

    # ========================================================
    # 7. Exams & Priority Revision Lists (Per-User)
    # ========================================================

    def add_exam(
        self,
        user_id: int,
        course_id: int,
        exam_name: str,
        exam_date: str,
        exam_time: str = "",
        syllabus_notes: str = "",
        covered_module_ids: str = "[]"
    ) -> int:
        if isinstance(covered_module_ids, list):
            covered_module_ids = json.dumps(covered_module_ids)

        query = """
            INSERT INTO exams (user_id, course_id, exam_name, exam_date, exam_time, syllabus_notes, covered_module_ids)
            VALUES (%s, %s, %s, %s, %s, %s, %s)
        """
        return self.execute_query(
            query,
            (user_id, course_id, exam_name.strip(), exam_date, exam_time.strip(), syllabus_notes.strip(), covered_module_ids)
        )

    def get_exams(self, user_id: int) -> List[Dict[str, Any]]:
        query = """
            SELECT e.exam_id, e.course_id, c.course_name, c.platform, e.exam_name, e.exam_date, e.exam_time, e.syllabus_notes, e.covered_module_ids
            FROM exams e
            JOIN courses c ON e.course_id = c.course_id
            WHERE e.user_id = %s
            ORDER BY e.exam_date ASC
        """
        exams = self.fetch_all(query, (user_id,))
        today = date.today()

        for ex in exams:
            try:
                ex_date = datetime.strptime(str(ex["exam_date"])[:10], "%Y-%m-%d").date()
                delta = (ex_date - today).days
                ex["days_left"] = delta
                if delta < 0:
                    ex["countdown_text"] = "Exam passed"
                    ex["urgency_color"] = "gray"
                elif delta == 0:
                    ex["countdown_text"] = "🚨 Today!"
                    ex["urgency_color"] = "red"
                elif delta == 1:
                    ex["countdown_text"] = "🔥 Tomorrow"
                    ex["urgency_color"] = "red"
                elif delta <= 3:
                    ex["countdown_text"] = f"⏰ In {delta} days"
                    ex["urgency_color"] = "red"
                elif delta <= 7:
                    ex["countdown_text"] = f"In {delta} days"
                    ex["urgency_color"] = "amber"
                else:
                    ex["countdown_text"] = f"In {delta} days"
                    ex["urgency_color"] = "green"
            except Exception:
                ex["days_left"] = 999
                ex["countdown_text"] = "Scheduled"
                ex["urgency_color"] = "blue"

            # Revision stats for this exam
            rev_stats = self.fetch_one(
                "SELECT COUNT(*) AS total, SUM(CASE WHEN is_revised = 1 THEN 1 ELSE 0 END) AS done FROM revision_items WHERE user_id = %s AND exam_id = %s",
                (user_id, ex["exam_id"])
            )
            ex["revision_total"] = rev_stats["total"] if rev_stats else 0
            ex["revision_done"] = rev_stats["done"] if rev_stats and rev_stats["done"] else 0
        return exams

    def get_exam_by_id(self, user_id: int, exam_id: int) -> Optional[Dict[str, Any]]:
        query = """
            SELECT e.*, c.course_name, c.platform
            FROM exams e
            JOIN courses c ON e.course_id = c.course_id
            WHERE e.user_id = %s AND e.exam_id = %s
        """
        exam = self.fetch_one(query, (user_id, exam_id))
        if exam:
            try:
                exam["covered_module_ids"] = json.loads(exam.get("covered_module_ids") or "[]")
            except Exception:
                exam["covered_module_ids"] = []
        return exam

    def update_exam(
        self,
        user_id: int,
        exam_id: int,
        course_id: int,
        exam_name: str,
        exam_date: str,
        exam_time: str = "",
        syllabus_notes: str = "",
        covered_module_ids: str = "[]"
    ) -> int:
        if isinstance(covered_module_ids, list):
            covered_module_ids = json.dumps(covered_module_ids)

        query = """
            UPDATE exams SET 
                course_id = %s,
                exam_name = %s,
                exam_date = %s,
                exam_time = %s,
                syllabus_notes = %s,
                covered_module_ids = %s
            WHERE user_id = %s AND exam_id = %s
        """
        return self.execute_query(
            query,
            (course_id, exam_name.strip(), exam_date, exam_time.strip(), syllabus_notes.strip(), covered_module_ids, user_id, exam_id)
        )

    def delete_exam(self, user_id: int, exam_id: int) -> int:
        return self.execute_query("DELETE FROM exams WHERE user_id = %s AND exam_id = %s", (user_id, exam_id))

    def get_exam_revision_checklist(self, user_id: int, exam_id: int) -> Dict[str, Any]:
        """
        Builds the automated 'What to revise' list ordered by priority:
          Priority 1: Weak Topics (highest priority)
          Priority 2: Important Topics
          Priority 3: Incomplete Modules
          Priority 4: Other covered modules
        """
        exam = self.get_exam_by_id(user_id, exam_id)
        if not exam:
            return {"exam": None, "items": [], "total_items": 0, "revised_items": 0, "progress_percent": 0}

        cid = exam["course_id"]
        all_modules = self.get_course_modules(user_id, cid)

        # Filter by covered modules if specified
        covered_ids = exam.get("covered_module_ids") or []
        if covered_ids and len(covered_ids) > 0:
            target_modules = [m for m in all_modules if m["module_id"] in covered_ids]
        else:
            target_modules = all_modules

        # Sync/Ensure revision_items records exist for each module
        existing_rev_rows = self.fetch_all(
            "SELECT module_id, is_revised, revised_at FROM revision_items WHERE user_id = %s AND exam_id = %s",
            (user_id, exam_id)
        )
        rev_lookup = {r["module_id"]: r for r in existing_rev_rows}

        for m in target_modules:
            mid = m["module_id"]
            if mid not in rev_lookup:
                self.execute_query(
                    "INSERT OR IGNORE INTO revision_items (user_id, exam_id, module_id, is_revised) VALUES (%s, %s, %s, 0)",
                    (user_id, exam_id, mid)
                )

        # Re-fetch revision records
        synced_rev_rows = self.fetch_all(
            "SELECT module_id, is_revised, revised_at FROM revision_items WHERE user_id = %s AND exam_id = %s",
            (user_id, exam_id)
        )
        rev_map = {r["module_id"]: r["is_revised"] for r in synced_rev_rows}

        # Build prioritized items list
        items = []
        for m in target_modules:
            mid = m["module_id"]
            is_revised = rev_map.get(mid, 0)
            
            # Determine priority rank
            if m.get("is_weak"):
                priority_rank = 1
                reason = "⚠️ Weak Topic"
            elif m.get("is_important"):
                priority_rank = 2
                reason = "⭐ Important Concept"
            elif not m.get("is_completed"):
                priority_rank = 3
                reason = "⏳ Incomplete Module"
            else:
                priority_rank = 4
                reason = "Completed"

            items.append({
                "module_id": mid,
                "title": m["title"],
                "is_completed": m["is_completed"],
                "is_important": m.get("is_important", 0),
                "is_weak": m.get("is_weak", 0),
                "key_points": m.get("key_points", ""),
                "notes": m.get("notes", ""),
                "priority_rank": priority_rank,
                "reason": reason,
                "is_revised": is_revised
            })

        # Sort: Incomplete revised first? No, sort by priority_rank ASC (weak first), then title
        items.sort(key=lambda x: (x["priority_rank"], x["title"]))

        total = len(items)
        done = sum(1 for it in items if it["is_revised"])
        pct = round((done / total) * 100) if total > 0 else 0

        return {
            "exam": exam,
            "items": items,
            "total_items": total,
            "revised_items": done,
            "progress_percent": pct
        }

    def toggle_revision_item(self, user_id: int, exam_id: int, module_id: int, is_revised: int) -> int:
        revised_at = datetime.now().strftime("%Y-%m-%d %H:%M:%S") if is_revised else ""
        query = """
            INSERT INTO revision_items (user_id, exam_id, module_id, is_revised, revised_at)
            VALUES (%s, %s, %s, %s, %s)
            ON CONFLICT(exam_id, module_id) DO UPDATE SET is_revised = %s, revised_at = %s
        """
        return self.execute_query(query, (user_id, exam_id, module_id, is_revised, revised_at, is_revised, revised_at))
