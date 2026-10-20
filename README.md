# LearnTrack Pro • Online Course Tracker & Student LMS

> **Academic Level:** CBSE Class 12 Informatics Practices (IP) / University Capstone Project  
> **Tech Stack:** Python 3.10+, Flask, Tailwind CSS, Lucide Icons, Chart.js, Pandas, Matplotlib, SQLite3 / MySQL  
> **Architecture:** Secure Multi-User SaaS Web Application + Interactive Terminal CLI (Viva Mode)

---

## 1. Project Title & Overview

**LearnTrack Pro: A Student Learning Management & Revision Optimization System** is a full-featured, data-driven web application designed to help students track, monitor, and optimize their online learning progress across multiple platforms (Coursera, Udemy, NPTEL, YouTube, edX, etc.).

Unlike conventional trackers, **LearnTrack Pro** implements:
1. **Real User Authentication & Strict Data Isolation:** Every student registers with hashed passwords; sessions are cryptographically signed; users cannot view or manipulate other students' data.
2. **Module-Based Curriculum & Automatic Progress:** Course progress is never guessed or set via a manual slider; it is dynamically calculated as $\frac{\text{Completed Modules}}{\text{Total Modules}} \times 100$.
3. **Deep Topic Annotations:** Per-module notes, clickable reference links, concept summaries, and topic flags (`is_important`, `is_weak`).
4. **Target Exams & Automated Priority Revision:** Algorithmic revision checklist that orders syllabus topics strictly by need: **Weak Topics (Priority 1)** $\rightarrow$ **Important Concepts (Priority 2)** $\rightarrow$ **Incomplete Modules (Priority 3)** $\rightarrow$ **Completed Modules (Priority 4)**.
5. **Dynamic Countdowns & In-App Reminders:** Exam countdowns with real-time urgency color-coding (Red: $\le 3$ days, Amber: $4-7$ days, Green: $> 7$ days).
6. **Zero Pre-Filled Data:** Clean empty states for new user accounts without hardcoded demo clutter.
7. **Dual Database Engine:** Zero-config SQLite3 default with transparent auto-fallback and MySQL connectivity for school lab viva demonstrations.

---

## 2. System Architecture & Relational Schema

The database consists of **8 normalized relational tables** in 3rd Normal Form (3NF) linked by Foreign Keys with cascading deletions (`ON DELETE CASCADE`).

### Entity-Relationship Diagram (ERD)

```text
       +-------------------------------------------------------------+
       |                            USERS                            |
       +-------------------------------------------------------------+
       | PK user_id (INT)                                            |
       |    username (VARCHAR, UNIQUE)                               |
       |    password_hash (VARCHAR - Werkzeug Security)              |
       |    name, subject, roll_no, email, avatar_color, created_at  |
       +------------------------------+------------------------------+
                                      | 1:N (Cascades)
       +------------------------------+------------------------------+
       |                                                             |
       v                                                             v
+-------------------------------+                             +-------------------------------+
|            COURSES            |                             |             EXAMS             |
+-------------------------------+                             +-------------------------------+
| PK course_id (INT)            |                             | PK exam_id (INT)              |
| FK user_id -> users(user_id)  |                             | FK user_id -> users(user_id)  |
|    course_name, platform      |                             | FK course_id -> courses(...)  |
|    instructor, start_date     |                             |    exam_name, exam_date       |
|    end_date, status, priority |                             |    exam_time, syllabus_notes  |
|    progress_percent (AUTO)    |                             |    covered_module_ids (JSON)  |
|    course_link, notes         |                             +---------------+---------------+
+---------------+---------------+                                             |
                |                                                             |
    +-----------+-----------+-------------------+                             |
    | 1:N                   | 1:N               | 1:N                         | 1:N
    v                       v                   v                             v
+------------------+ +-----------------+ +-------------------+     +-------------------------+
|     MODULES      | |    STUDY_LOG    | |     DEADLINES     |     |     REVISION_ITEMS      |
+------------------+ +-----------------+ +-------------------+     +-------------------------+
| PK module_id     | | PK log_id       | | PK deadline_id    |     | PK revision_id          |
| FK user_id       | | FK user_id      | | FK user_id        |     | FK user_id              |
| FK course_id     | | FK course_id    | | FK course_id      |     | FK exam_id              |
|    title         | |    study_date   | |    task_name      |     | FK module_id            |
|    position      | |    hours_spent  | |    due_date       |     |    is_revised (0 or 1)  |
|    is_completed  | |    topic_covered| |    is_done        |     |    revised_at           |
|    completed_date| +-----------------+ +-------------------+     | UNIQUE(exam_id, module) |
|    notes         |                                               +-------------------------+
|    reference_links (JSON)                                                   ^
|    is_important (0 or 1)                                                    |
|    is_weak (0 or 1) --------------------------------------------------------+
|    key_points    |
+------------------+
        |
        | 1:N
        v
+-------------------+
|   CERTIFICATES    |
+-------------------+
| PK cert_id        |
| FK user_id        |
| FK course_id      |
| certificate_link  |
| issue_date, grade |
+-------------------+
```

---

## 3. Key Features & Mathematical Formulas

### A. Dynamic Course Progress Calculation
Course progress is automatically recomputed on every module completion or deletion:

$$\text{progress\_percent} = \begin{cases} 
0, & \text{if } \text{total\_modules} = 0 \\ 
\operatorname{round}\left(\frac{\text{completed\_modules}}{\text{total\_modules}} \times 100\right), & \text{if } \text{total\_modules} > 0 
\end{cases}$$

**Status State Machine:**
- $\text{progress} = 0\% \implies \textbf{Not Started}$
- $1\% \le \text{progress} \le 99\% \implies \textbf{In Progress}$
- $\text{progress} = 100\% \implies \textbf{Completed}$
- **Manual Override:** If the user sets status to $\textbf{On Hold}$, the pause state is preserved regardless of completion percentage until changed.

### B. Automated "What to Revise" Priority Algorithm
When an exam is scheduled, the system inspects all covered course modules and algorithmically arranges the revision checklist into 4 tiers:

1. **Tier 1 (Priority Rank 1 — Highest):** Weak Topics ($\text{is\_weak} = 1$). Flagged by the student as challenging; reviewed first to solidify concepts.
2. **Tier 2 (Priority Rank 2):** Important Concepts ($\text{is\_important} = 1, \text{is\_weak} = 0$). High-weightage core syllabus topics.
3. **Tier 3 (Priority Rank 3):** Incomplete Modules ($\text{is\_completed} = 0, \text{is\_weak} = 0, \text{is\_important} = 0$). Topics not yet finished in the course.
4. **Tier 4 (Priority Rank 4):** Completed Topics ($\text{is\_completed} = 1$). Completed regular modules for quick brush-up.

### C. Exam Countdown & Urgency Thresholds
Let $\Delta = \text{exam\_date} - \text{today}$.
- $\Delta < 0 \implies \text{Exam passed (Gray)}$
- $\Delta = 0 \implies \text{"🚨 Today!" (Red, pulsing reminder)}$
- $\Delta = 1 \implies \text{"🔥 Tomorrow" (Red urgent)}$
- $2 \le \Delta \le 3 \implies \text{"⏰ In } \Delta \text{ days" (Red urgent)}$
- $4 \le \Delta \le 7 \implies \text{"In } \Delta \text{ days" (Amber warning)}$
- $\Delta > 7 \implies \text{"In } \Delta \text{ days" (Green scheduled)}$

---

## 4. Installation & Setup

### Prerequisites
- Python 3.10, 3.11, or 3.12
- Virtual environment tool (`venv`)

### 1. Clone & Set Up Virtual Environment
```bash
cd /Users/yugjain/aad/online-course-tracker

# Create virtual environment (if not already created)
python3 -m venv venv

# Activate virtual environment
# On macOS / Linux:
source venv/bin/activate
# On Windows:
# venv\Scripts\activate
```

### 2. Install Required Packages
```bash
pip install -r requirements.txt
```

### 3. Launch Modes

#### Mode 1: Modern SaaS Web Dashboard (Recommended)
```bash
python main.py
# Or:
python app.py
```
Open your browser at `http://127.0.0.1:5000`. You will be greeted with the authentication overlay. Create a new account with your username and password to begin with a clean workspace.

#### Mode 2: Interactive Console CLI (CBSE IP Viva Mode)
```bash
python main.py --cli
```
Launches the menu-driven terminal interface featuring student login, tabular course listings, module checklists, study logs, priority revision lists, Pandas reports, and Matplotlib chart exports.

#### Mode 3: Desktop Tkinter GUI
```bash
python main.py --gui
```

---

## 5. Automated Verification & Test Suite

Run the comprehensive unit test suite to verify all database operations, password hashing, per-user isolation, module progress calculation, exams, revision checklist sorting, and REST API routes:

```bash
venv/bin/python -m unittest test_system.py -v
```

### Test Suite Coverage:
- `test_01_user_registration_and_hashing`: Verifies `werkzeug.security` password hashing (`scrypt`/`pbkdf2`) and duplicate username blocking.
- `test_02_user_profile_update`: Tests student name, stream, roll number, and avatar color customization.
- `test_03_per_user_data_isolation`: Proves that User A cannot view, query, or delete User B's courses or data.
- `test_04_modules_and_progress_calculation`: Validates module addition, completion toggling, auto-updating progress %, and 'On Hold' preservation.
- `test_05_module_notes_references_and_flags`: Tests JSON reference link storage and important/weak flags.
- `test_06_exams_and_countdown_urgency`: Tests dynamic countdown days calculation and urgency color classification.
- `test_07_automated_revision_checklist_priority`: Verifies the 4-tier priority revision ordering (Weak topics first).
- `test_08_cascading_deletes`: Proves that deleting a course cascades and deletes modules, logs, deadlines, exams, and revision items.
- `test_09_flask_api_and_session_auth`: Verifies HTTP endpoints, 401 Unauthorized handling, login session cookies, and logout.
- `test_10_analytics_empty_and_populated_states`: Proves Pandas aggregations and KPIs run without errors on both empty and populated accounts.

---

## 6. CBSE Class 12 IP / College Viva Examination Guide

Below are the most frequently asked viva questions regarding this project, along with expert technical answers:

### Q1: Why did you use a relational database with 8 tables instead of storing everything in one table or a CSV file?
> **Answer:** Storing all information in a single table or CSV violates database normalization principles, leading to data redundancy, insertion anomalies, update anomalies, and deletion anomalies. By designing 8 normalized tables in 3NF (3rd Normal Form) linked by Foreign Keys, every entity (`users`, `courses`, `modules`, `study_log`, `deadlines`, `certificates`, `exams`, `revision_items`) represents an atomic relation. This ensures data integrity, saves storage, and allows `ON DELETE CASCADE` so deleting a user or course cleanly removes child records without orphaned data.

### Q2: How does the system calculate course progress without a manual slider?
> **Answer:** Manual sliders introduce human error and arbitrary progress numbers. In our system, progress is strictly module-driven:
> $$\text{Progress } \% = \operatorname{round}\left(\frac{\text{Completed Modules}}{\text{Total Modules}} \times 100\right)$$
> Every time a student checks off or unchecks a module, the backend executes an aggregation query (`COUNT(*)` and `SUM(CASE WHEN is_completed = 1 THEN 1 ELSE 0 END)`), updates the course record, and synchronizes status between 'Not Started', 'In Progress', and 'Completed'.

### Q3: How do you enforce security and prevent User B from seeing User A's data?
> **Answer:**
> 1. Passwords are never stored in plaintext. We use `werkzeug.security.generate_password_hash` which generates a salted cryptographic hash. During login, `check_password_hash` verifies the hash.
> 2. Authenticated sessions are managed via Flask's cryptographically signed cookie session (`session['user_id']`).
> 3. Every single SQL query includes `WHERE user_id = %s`. Even if a user attempts to fetch `/api/courses/42`, the backend executes `SELECT * FROM courses WHERE user_id = %s AND course_id = 42`. If course 42 belongs to another user, it returns a 404/401 response.

### Q4: Explain the automated revision algorithm for exams.
> **Answer:** Before an exam, students often waste time reviewing topics they already know. Our algorithm queries all covered modules for the exam, joins them with student self-assessment flags, and assigns a Priority Rank:
> - **Rank 1 (Weak Topics):** Modules where `is_weak = 1`.
> - **Rank 2 (Important Concepts):** Modules where `is_important = 1`.
> - **Rank 3 (Incomplete Modules):** Modules where `is_completed = 0`.
> - **Rank 4 (Completed Concepts):** Modules already finished.
> The SQL query sorts by `(priority_rank ASC, title ASC)`, presenting the student with an optimized study checklist.

### Q5: What is the role of Pandas and Matplotlib in this project?
> **Answer:**
> - **Pandas (`pandas`):** Used in `analytics.py` for high-performance summary aggregations. Methods like `.groupby('course_name')['hours_spent'].sum()` and `.value_counts()` compute total hours studied per course and platform distribution. It also gracefully handles empty datasets using `.empty` checks and fillna values.
> - **Matplotlib (`matplotlib.pyplot`):** Used for generating publication-quality static visualizations (horizontal bar charts, donut charts, time-series line plots) that can be embedded into student project reports and exported to PNG files via `export_all_charts()`. On the web front, Chart.js provides dynamic, client-side rendering.

---

## 7. Project Directory Structure

```text
online-course-tracker/
│
├── app.py                   # Flask REST API server with session authentication
├── database.py              # SQLite/MySQL database layer with user-scoped CRUD
├── analytics.py             # Pandas aggregations and Matplotlib visualization engine
├── schema.sql               # Normalized 8-table relational database schema
├── main.py                  # Multi-mode launcher (Web, CLI, GUI)
├── cli.py                   # Terminal CLI for CBSE IP viva examination
├── gui.py                   # Tkinter desktop GUI
├── test_system.py           # Comprehensive automated unit & integration test suite
├── requirements.txt         # Production Python dependencies
├── course_tracker.db        # Clean SQLite database (auto-created on first run)
├── templates/
│   └── index.html           # Modern SaaS web dashboard (Tailwind + Lucide + Chart.js)
└── exported_charts/         # Target directory for Matplotlib PNG exports
```
