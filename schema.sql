-- ========================================================
-- ONLINE COURSE TRACKER: A Student Learning Management System
-- Database Schema for MySQL / SQLite
-- Includes Full Authentication, Module Progress, & Exam Revision
-- ========================================================

-- 1. Users / Student Accounts Table
CREATE TABLE IF NOT EXISTS users (
    user_id INTEGER PRIMARY KEY AUTOINCREMENT,
    username VARCHAR(100) UNIQUE NOT NULL,
    password_hash VARCHAR(255) NOT NULL,
    name VARCHAR(100) NOT NULL,
    subject VARCHAR(100) NOT NULL,
    roll_no VARCHAR(50) DEFAULT '',
    email VARCHAR(150) DEFAULT '',
    avatar_color VARCHAR(20) DEFAULT '#4F46E5',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- 2. Courses Table
CREATE TABLE IF NOT EXISTS courses (
    course_id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER NOT NULL,
    course_name VARCHAR(150) NOT NULL,
    platform VARCHAR(50) NOT NULL,
    instructor VARCHAR(100) DEFAULT '',
    start_date DATE,
    end_date DATE,
    status VARCHAR(20) DEFAULT 'Not Started', -- 'Not Started', 'In Progress', 'Completed', 'On Hold'
    progress_percent INTEGER DEFAULT 0,
    priority VARCHAR(10) DEFAULT 'Medium',    -- 'High', 'Medium', 'Low'
    course_link VARCHAR(255) DEFAULT '',
    notes TEXT DEFAULT '',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (user_id) REFERENCES users(user_id) ON DELETE CASCADE
);

-- 3. Modules Table (Module-based progress calculation)
CREATE TABLE IF NOT EXISTS modules (
    module_id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER NOT NULL,
    course_id INTEGER NOT NULL,
    title VARCHAR(200) NOT NULL,
    position INTEGER DEFAULT 1,
    is_completed INTEGER DEFAULT 0,
    completed_date DATE,
    notes TEXT DEFAULT '',
    reference_links TEXT DEFAULT '[]', -- JSON array of {label, url}
    is_important INTEGER DEFAULT 0,
    is_weak INTEGER DEFAULT 0,
    key_points TEXT DEFAULT '',
    FOREIGN KEY (user_id) REFERENCES users(user_id) ON DELETE CASCADE,
    FOREIGN KEY (course_id) REFERENCES courses(course_id) ON DELETE CASCADE
);

-- 4. Study Log Table (Daily hours spent per course)
CREATE TABLE IF NOT EXISTS study_log (
    log_id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER NOT NULL,
    course_id INTEGER NOT NULL,
    study_date DATE NOT NULL,
    hours_spent DECIMAL(4, 2) NOT NULL,
    topic_covered VARCHAR(200) DEFAULT '',
    FOREIGN KEY (user_id) REFERENCES users(user_id) ON DELETE CASCADE,
    FOREIGN KEY (course_id) REFERENCES courses(course_id) ON DELETE CASCADE
);

-- 5. Deadlines Table (Assignments & Homework Tasks)
CREATE TABLE IF NOT EXISTS deadlines (
    deadline_id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER NOT NULL,
    course_id INTEGER NOT NULL,
    task_name VARCHAR(150) NOT NULL,
    due_date DATE NOT NULL,
    is_done INTEGER DEFAULT 0,
    FOREIGN KEY (user_id) REFERENCES users(user_id) ON DELETE CASCADE,
    FOREIGN KEY (course_id) REFERENCES courses(course_id) ON DELETE CASCADE
);

-- 6. Certificates Table
CREATE TABLE IF NOT EXISTS certificates (
    cert_id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER NOT NULL,
    course_id INTEGER NOT NULL,
    certificate_link VARCHAR(255) NOT NULL,
    issue_date DATE,
    grade VARCHAR(50) DEFAULT '',
    FOREIGN KEY (user_id) REFERENCES users(user_id) ON DELETE CASCADE,
    FOREIGN KEY (course_id) REFERENCES courses(course_id) ON DELETE CASCADE
);

-- 7. Exams Table
CREATE TABLE IF NOT EXISTS exams (
    exam_id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER NOT NULL,
    course_id INTEGER NOT NULL,
    exam_name VARCHAR(150) NOT NULL,
    exam_date DATE NOT NULL,
    exam_time VARCHAR(20) DEFAULT '',
    syllabus_notes TEXT DEFAULT '',
    covered_module_ids TEXT DEFAULT '[]', -- JSON array of covered module IDs
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (user_id) REFERENCES users(user_id) ON DELETE CASCADE,
    FOREIGN KEY (course_id) REFERENCES courses(course_id) ON DELETE CASCADE
);

-- 8. Revision Items Table (Auto-generated priority revision checklist for exams)
CREATE TABLE IF NOT EXISTS revision_items (
    revision_id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER NOT NULL,
    exam_id INTEGER NOT NULL,
    module_id INTEGER NOT NULL,
    is_revised INTEGER DEFAULT 0,
    revised_at TIMESTAMP,
    FOREIGN KEY (user_id) REFERENCES users(user_id) ON DELETE CASCADE,
    FOREIGN KEY (exam_id) REFERENCES exams(exam_id) ON DELETE CASCADE,
    FOREIGN KEY (module_id) REFERENCES modules(module_id) ON DELETE CASCADE,
    UNIQUE(exam_id, module_id)
);
