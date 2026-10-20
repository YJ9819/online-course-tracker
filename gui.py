"""
gui.py - Modern Tkinter Desktop Graphical User Interface
Features:
  - Custom styled ttk widgets & cards
  - Tabbed interface (Dashboard/Courses, Study Log, Deadlines, Certificates & Notes, Analytics)
  - Embedded Matplotlib charts with interactive controls
  - Full CRUD operations with modal dialogs
  - Quick Seed Demo Data support
"""

import sys
import webbrowser
from datetime import datetime, date
import tkinter as tk
from tkinter import ttk, messagebox, simpledialog

import matplotlib
matplotlib.use("TkAgg")
from matplotlib.figure import Figure
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg, NavigationToolbar2Tk

from database import Database
from analytics import AnalyticsManager


class CourseTrackerGUI:
    def __init__(self, root: tk.Tk, db: Database):
        self.root = root
        self.db = db
        self.analytics = AnalyticsManager(db)

        self.root.title("Online Course Tracker - Student LMS")
        self.root.geometry("1120x760")
        self.root.minsize(980, 650)

        # Apply Modern Styling
        self._setup_styles()

        # Build Main Layout
        self._build_header()
        self._build_kpi_cards()
        self._build_notebook()

        # Initial Data Refresh
        self.refresh_all_data()

    def _setup_styles(self):
        """Configures clean modern styles for ttk widgets."""
        self.style = ttk.Style()
        try:
            self.style.theme_use("clam")
        except Exception:
            pass

        # Color Palette
        self.c_primary = "#2563EB"
        self.c_primary_dark = "#1D4ED8"
        self.c_bg = "#F8FAFC"
        self.c_card = "#FFFFFF"
        self.c_text = "#0F172A"
        self.c_text_muted = "#64748B"
        self.c_border = "#E2E8F0"
        self.c_success = "#10B981"
        self.c_warning = "#F59E0B"
        self.c_danger = "#EF4444"

        self.root.configure(bg=self.c_bg)

        # Style configurations
        self.style.configure(".", font=("Helvetica", 10), background=self.c_bg, foreground=self.c_text)
        self.style.configure("TFrame", background=self.c_bg)
        self.style.configure("Card.TFrame", background=self.c_card, relief="ridge", borderwidth=1)
        self.style.configure("Header.TFrame", background="#1E293B")

        self.style.configure("HeaderTitle.TLabel", font=("Helvetica", 16, "bold"), background="#1E293B", foreground="#F8FAFC")
        self.style.configure("HeaderSubtitle.TLabel", font=("Helvetica", 9), background="#1E293B", foreground="#94A3B8")
        self.style.configure("HeaderBadge.TLabel", font=("Helvetica", 9, "bold"), background="#334155", foreground="#38BDF8", padding=4)

        # KPI Styles
        self.style.configure("KPITitle.TLabel", font=("Helvetica", 9, "bold"), foreground=self.c_text_muted, background=self.c_card)
        self.style.configure("KPIValue.TLabel", font=("Helvetica", 18, "bold"), foreground=self.c_primary, background=self.c_card)

        # Buttons
        self.style.configure("Primary.TButton", font=("Helvetica", 10, "bold"), background=self.c_primary, foreground="white", borderwidth=0, padding=6)
        self.style.map("Primary.TButton", background=[("active", self.c_primary_dark)])

        self.style.configure("Success.TButton", font=("Helvetica", 10, "bold"), background=self.c_success, foreground="white", padding=6)
        self.style.configure("Danger.TButton", font=("Helvetica", 10, "bold"), background=self.c_danger, foreground="white", padding=6)
        self.style.configure("Secondary.TButton", font=("Helvetica", 10), padding=6)

        # Notebook Tabs
        self.style.configure("TNotebook", background=self.c_bg, tabmargins=[10, 5, 2, 0])
        self.style.configure("TNotebook.Tab", font=("Helvetica", 10, "bold"), padding=[14, 8], background="#E2E8F0", foreground="#334155")
        self.style.map("TNotebook.Tab",
                       background=[("selected", self.c_card)],
                       foreground=[("selected", self.c_primary)])

        # Treeview styling
        self.style.configure("Treeview", font=("Helvetica", 9), rowheight=26, background=self.c_card, fieldbackground=self.c_card, bordercolor=self.c_border)
        self.style.configure("Treeview.Heading", font=("Helvetica", 10, "bold"), background="#F1F5F9", foreground="#1E293B", relief="flat")
        self.style.map("Treeview.Heading", background=[("active", "#E2E8F0")])

    def _build_header(self):
        """Top Application Banner with Database status & Action buttons."""
        header = ttk.Frame(self.root, style="Header.TFrame", padding=(20, 12))
        header.pack(fill=tk.X)

        titles_frame = ttk.Frame(header, style="Header.TFrame")
        titles_frame.pack(side=tk.LEFT)

        title_lbl = ttk.Label(titles_frame, text="🎓 Online Course Tracker", style="HeaderTitle.TLabel")
        title_lbl.pack(anchor="w")

        sub_lbl = ttk.Label(titles_frame, text="Student Learning Management System • Informatics Practices (IP)", style="HeaderSubtitle.TLabel")
        sub_lbl.pack(anchor="w")

        # Right-side controls
        actions_frame = ttk.Frame(header, style="Header.TFrame")
        actions_frame.pack(side=tk.RIGHT)

        db_badge = ttk.Label(actions_frame, text=f"⚡ DB: {self.db.engine_name}", style="HeaderBadge.TLabel")
        db_badge.pack(side=tk.LEFT, padx=10)

        seed_btn = ttk.Button(actions_frame, text="🌱 Load Demo Data", style="Secondary.TButton", command=self.seed_demo_data)
        seed_btn.pack(side=tk.LEFT, padx=4)

        refresh_btn = ttk.Button(actions_frame, text="🔄 Refresh All", style="Secondary.TButton", command=self.refresh_all_data)
        refresh_btn.pack(side=tk.LEFT, padx=4)

    def _build_kpi_cards(self):
        """Ribbon displaying executive summary KPI metric cards."""
        ribbon = ttk.Frame(self.root, padding=(16, 10))
        ribbon.pack(fill=tk.X)

        self.kpi_labels = {}
        metrics = [
            ("total_courses", "📚 Enrolled Courses", "0"),
            ("total_hours", "⏱️ Study Hours Logged", "0.0 hrs"),
            ("avg_progress", "📈 Average Progress", "0%"),
            ("pending_deadlines", "⏰ Pending Deadlines", "0"),
            ("most_used_platform", "🌐 Top Platform", "N/A")
        ]

        for i, (key, title, default_val) in enumerate(metrics):
            card = ttk.Frame(ribbon, style="Card.TFrame", padding=(12, 8))
            card.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=5)

            t_lbl = ttk.Label(card, text=title, style="KPITitle.TLabel")
            t_lbl.pack(anchor="w")

            v_lbl = ttk.Label(card, text=default_val, style="KPIValue.TLabel")
            v_lbl.pack(anchor="w", pady=(4, 0))

            self.kpi_labels[key] = v_lbl

    def _build_notebook(self):
        """Constructs tabbed views for all system modules."""
        self.notebook = ttk.Notebook(self.root)
        self.notebook.pack(fill=tk.BOTH, expand=True, padx=16, pady=(0, 12))

        # Tabs
        self.tab_courses = ttk.Frame(self.notebook, padding=12)
        self.tab_study_log = ttk.Frame(self.notebook, padding=12)
        self.tab_deadlines = ttk.Frame(self.notebook, padding=12)
        self.tab_certs_notes = ttk.Frame(self.notebook, padding=12)
        self.tab_analytics = ttk.Frame(self.notebook, padding=12)

        self.notebook.add(self.tab_courses, text="  Courses Management  ")
        self.notebook.add(self.tab_study_log, text="  Study Hours Log  ")
        self.notebook.add(self.tab_deadlines, text="  Deadlines & Tasks  ")
        self.notebook.add(self.tab_certs_notes, text="  Certificates & Notes  ")
        self.notebook.add(self.tab_analytics, text="  Analytics & Visualizations  ")

        # Build each tab's UI
        self._init_courses_tab()
        self._init_study_log_tab()
        self._init_deadlines_tab()
        self._init_certs_notes_tab()
        self._init_analytics_tab()

    # ========================================================
    # TAB 1: Courses Management
    # ========================================================

    def _init_courses_tab(self):
        tab = self.tab_courses

        # Filter & Action Toolbar
        toolbar = ttk.Frame(tab)
        toolbar.pack(fill=tk.X, pady=(0, 10))

        ttk.Label(toolbar, text="Search:").pack(side=tk.LEFT, padx=(0, 4))
        self.course_search_var = tk.StringVar()
        self.course_search_var.trace("w", lambda *args: self.load_courses())
        search_entry = ttk.Entry(toolbar, textvariable=self.course_search_var, width=18)
        search_entry.pack(side=tk.LEFT, padx=(0, 12))

        ttk.Label(toolbar, text="Status:").pack(side=tk.LEFT, padx=(0, 4))
        self.course_status_filter = ttk.Combobox(toolbar, values=["All", "In Progress", "Completed", "Not Started", "On Hold"], state="readonly", width=12)
        self.course_status_filter.set("All")
        self.course_status_filter.bind("<<ComboboxSelected>>", lambda e: self.load_courses())
        self.course_status_filter.pack(side=tk.LEFT, padx=(0, 12))

        ttk.Label(toolbar, text="Platform:").pack(side=tk.LEFT, padx=(0, 4))
        self.course_platform_filter = ttk.Combobox(toolbar, values=["All", "Coursera", "Udemy", "NPTEL", "YouTube", "edX", "Other"], state="readonly", width=11)
        self.course_platform_filter.set("All")
        self.course_platform_filter.bind("<<ComboboxSelected>>", lambda e: self.load_courses())
        self.course_platform_filter.pack(side=tk.LEFT, padx=(0, 12))

        # Action Buttons
        btn_add = ttk.Button(toolbar, text="➕ Add Course", style="Primary.TButton", command=self.open_add_course_modal)
        btn_add.pack(side=tk.RIGHT, padx=3)

        btn_edit = ttk.Button(toolbar, text="✏️ Edit", style="Secondary.TButton", command=self.open_edit_course_modal)
        btn_edit.pack(side=tk.RIGHT, padx=3)

        btn_prog = ttk.Button(toolbar, text="📊 Update Progress", style="Secondary.TButton", command=self.open_update_progress_modal)
        btn_prog.pack(side=tk.RIGHT, padx=3)

        btn_del = ttk.Button(toolbar, text="🗑️ Delete", style="Danger.TButton", command=self.delete_selected_course)
        btn_del.pack(side=tk.RIGHT, padx=3)

        btn_open = ttk.Button(toolbar, text="🌐 Open Link", style="Secondary.TButton", command=self.open_course_link)
        btn_open.pack(side=tk.RIGHT, padx=3)

        # Courses Treeview Table
        table_frame = ttk.Frame(tab)
        table_frame.pack(fill=tk.BOTH, expand=True)

        cols = ("id", "name", "platform", "instructor", "status", "progress", "priority", "start_date", "end_date")
        self.course_tree = ttk.Treeview(table_frame, columns=cols, show="headings", selectmode="browse")

        self.course_tree.heading("id", text="ID")
        self.course_tree.heading("name", text="Course Name")
        self.course_tree.heading("platform", text="Platform")
        self.course_tree.heading("instructor", text="Instructor")
        self.course_tree.heading("status", text="Status")
        self.course_tree.heading("progress", text="Progress")
        self.course_tree.heading("priority", text="Priority")
        self.course_tree.heading("start_date", text="Start Date")
        self.course_tree.heading("end_date", text="Target End Date")

        self.course_tree.column("id", width=45, anchor="center")
        self.course_tree.column("name", width=240, anchor="w")
        self.course_tree.column("platform", width=95, anchor="center")
        self.course_tree.column("instructor", width=130, anchor="w")
        self.course_tree.column("status", width=95, anchor="center")
        self.course_tree.column("progress", width=80, anchor="center")
        self.course_tree.column("priority", width=70, anchor="center")
        self.course_tree.column("start_date", width=85, anchor="center")
        self.course_tree.column("end_date", width=95, anchor="center")

        scroll = ttk.Scrollbar(table_frame, orient=tk.VERTICAL, command=self.course_tree.yview)
        self.course_tree.configure(yscroll=scroll.set)

        self.course_tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scroll.pack(side=tk.RIGHT, fill=tk.Y)

    def load_courses(self):
        """Fetches courses according to search and filter criteria."""
        for item in self.course_tree.get_children():
            self.course_tree.delete(item)

        search = self.course_search_var.get().strip()
        status = self.course_status_filter.get()
        platform = self.course_platform_filter.get()

        courses = self.db.get_courses(search=search, status_filter=status, platform_filter=platform)
        for c in courses:
            prog_str = f"{c.get('progress_percent', 0)}%"
            self.course_tree.insert("", tk.END, values=(
                c["course_id"],
                c["course_name"],
                c["platform"],
                c.get("instructor", ""),
                c.get("status", "Not Started"),
                prog_str,
                c.get("priority", "Medium"),
                c.get("start_date", "") or "-",
                c.get("end_date", "") or "-"
            ))

    def _get_selected_course_id(self) -> int:
        selected = self.course_tree.selection()
        if not selected:
            messagebox.showwarning("Selection Required", "Please select a course from the table first.")
            return None
        return int(self.course_tree.item(selected[0], "values")[0])

    def open_add_course_modal(self):
        self._course_form_modal(title="Add New Course")

    def open_edit_course_modal(self):
        cid = self._get_selected_course_id()
        if cid:
            course = self.db.get_course_by_id(cid)
            if course:
                self._course_form_modal(title="Edit Course", course=course)

    def _course_form_modal(self, title: str, course: dict = None):
        modal = tk.Toplevel(self.root)
        modal.title(title)
        modal.geometry("500x520")
        modal.transient(self.root)
        modal.grab_set()

        frame = ttk.Frame(modal, padding=20)
        frame.pack(fill=tk.BOTH, expand=True)

        fields = [
            ("Course Name *", "name", tk.StringVar(value=course["course_name"] if course else "")),
            ("Platform *", "platform", tk.StringVar(value=course["platform"] if course else "Coursera")),
            ("Instructor", "instructor", tk.StringVar(value=course.get("instructor", "") if course else "")),
            ("Start Date (YYYY-MM-DD)", "start_date", tk.StringVar(value=course.get("start_date", "") or "" if course else date.today().strftime("%Y-%m-%d"))),
            ("End Date (YYYY-MM-DD)", "end_date", tk.StringVar(value=course.get("end_date", "") or "" if course else "")),
            ("Priority", "priority", tk.StringVar(value=course.get("priority", "Medium") if course else "Medium")),
            ("Course Link / URL", "link", tk.StringVar(value=course.get("course_link", "") or "" if course else "")),
        ]

        entries = {}
        for row, (label, key, var) in enumerate(fields):
            ttk.Label(frame, text=label, font=("Helvetica", 9, "bold")).grid(row=row, column=0, sticky="w", pady=4)
            if key == "platform":
                ent = ttk.Combobox(frame, textvariable=var, values=["Coursera", "Udemy", "NPTEL", "YouTube", "edX", "Codecademy", "Other"])
            elif key == "priority":
                ent = ttk.Combobox(frame, textvariable=var, values=["High", "Medium", "Low"], state="readonly")
            else:
                ent = ttk.Entry(frame, textvariable=var, width=32)
            ent.grid(row=row, column=1, sticky="ew", pady=4, padx=(8, 0))
            entries[key] = var

        # Notes field
        ttk.Label(frame, text="Notes / Syllabus", font=("Helvetica", 9, "bold")).grid(row=len(fields), column=0, sticky="nw", pady=6)
        notes_txt = tk.Text(frame, height=4, width=30, font=("Helvetica", 9))
        notes_txt.grid(row=len(fields), column=1, sticky="ew", pady=6, padx=(8, 0))
        if course and course.get("notes"):
            notes_txt.insert("1.0", course["notes"])

        def save():
            name = entries["name"].get().strip()
            platform = entries["platform"].get().strip()
            if not name or not platform:
                messagebox.showerror("Validation Error", "Course Name and Platform are mandatory.", parent=modal)
                return

            notes = notes_txt.get("1.0", tk.END).strip()
            if course:
                self.db.update_course(
                    course_id=course["course_id"],
                    course_name=name,
                    platform=platform,
                    instructor=entries["instructor"].get().strip(),
                    start_date=entries["start_date"].get().strip(),
                    end_date=entries["end_date"].get().strip(),
                    status=course.get("status", "Not Started"),
                    progress_percent=course.get("progress_percent", 0),
                    priority=entries["priority"].get().strip(),
                    course_link=entries["link"].get().strip(),
                    notes=notes
                )
            else:
                self.db.add_course(
                    course_name=name,
                    platform=platform,
                    instructor=entries["instructor"].get().strip(),
                    start_date=entries["start_date"].get().strip(),
                    end_date=entries["end_date"].get().strip(),
                    status="Not Started",
                    progress_percent=0,
                    priority=entries["priority"].get().strip(),
                    course_link=entries["link"].get().strip(),
                    notes=notes
                )
            modal.destroy()
            self.refresh_all_data()

        btn_frame = ttk.Frame(frame)
        btn_frame.grid(row=len(fields)+1, column=0, columnspan=2, pady=16)
        ttk.Button(btn_frame, text="Save Course", style="Primary.TButton", command=save).pack(side=tk.LEFT, padx=6)
        ttk.Button(btn_frame, text="Cancel", style="Secondary.TButton", command=modal.destroy).pack(side=tk.LEFT, padx=6)

    def open_update_progress_modal(self):
        cid = self._get_selected_course_id()
        if not cid:
            return
        course = self.db.get_course_by_id(cid)
        if not course:
            return

        modal = tk.Toplevel(self.root)
        modal.title(f"Update Progress: {course['course_name'][:30]}")
        modal.geometry("420x220")
        modal.transient(self.root)
        modal.grab_set()

        frame = ttk.Frame(modal, padding=20)
        frame.pack(fill=tk.BOTH, expand=True)

        current_val = course.get("progress_percent", 0)
        slider_var = tk.IntVar(value=current_val)

        ttk.Label(frame, text=course["course_name"], font=("Helvetica", 11, "bold")).pack(anchor="w")
        ttk.Label(frame, text=f"Platform: {course['platform']} • Current Status: {course.get('status')}").pack(anchor="w", pady=(0, 10))

        val_label = ttk.Label(frame, text=f"Progress: {current_val}%", font=("Helvetica", 12, "bold"), foreground=self.c_primary)
        val_label.pack(pady=4)

        def on_slider_move(val):
            val_int = int(float(val))
            val_label.config(text=f"Progress: {val_int}%")

        slider = ttk.Scale(frame, from_=0, to=100, orient=tk.HORIZONTAL, variable=slider_var, command=on_slider_move)
        slider.pack(fill=tk.X, padx=10, pady=8)

        def save():
            new_pct = slider_var.get()
            self.db.update_course_progress(cid, new_pct)
            modal.destroy()
            self.refresh_all_data()

        btn_box = ttk.Frame(frame)
        btn_box.pack(pady=10)
        ttk.Button(btn_box, text="Save Progress", style="Primary.TButton", command=save).pack(side=tk.LEFT, padx=6)
        ttk.Button(btn_box, text="Cancel", style="Secondary.TButton", command=modal.destroy).pack(side=tk.LEFT, padx=6)

    def delete_selected_course(self):
        cid = self._get_selected_course_id()
        if not cid:
            return
        course = self.db.get_course_by_id(cid)
        if messagebox.askyesno("Confirm Delete", f"Are you sure you want to delete course:\n'{course['course_name']}'?\n\nThis will also remove associated study logs and deadlines."):
            self.db.delete_course(cid)
            self.refresh_all_data()

    def open_course_link(self):
        cid = self._get_selected_course_id()
        if not cid:
            return
        course = self.db.get_course_by_id(cid)
        link = course.get("course_link")
        if link:
            webbrowser.open(link)
        else:
            messagebox.showinfo("No Link", "No URL/link has been saved for this course.")

    # ========================================================
    # TAB 2: Study Hours Log
    # ========================================================

    def _init_study_log_tab(self):
        tab = self.tab_study_log

        # Top Log Input Card
        log_box = ttk.Frame(tab, style="Card.TFrame", padding=14)
        log_box.pack(fill=tk.X, pady=(0, 10))

        ttk.Label(log_box, text="➕ Log Daily Study Session", font=("Helvetica", 11, "bold"), background=self.c_card).grid(row=0, column=0, columnspan=6, sticky="w", pady=(0, 8))

        ttk.Label(log_box, text="Course *:", background=self.c_card).grid(row=1, column=0, sticky="w", padx=4)
        self.log_course_cb = ttk.Combobox(log_box, width=28, state="readonly")
        self.log_course_cb.grid(row=1, column=1, sticky="w", padx=4)

        ttk.Label(log_box, text="Date (YYYY-MM-DD):", background=self.c_card).grid(row=1, column=2, sticky="w", padx=4)
        self.log_date_var = tk.StringVar(value=date.today().strftime("%Y-%m-%d"))
        ttk.Entry(log_box, textvariable=self.log_date_var, width=12).grid(row=1, column=3, sticky="w", padx=4)

        ttk.Label(log_box, text="Hours Spent *:", background=self.c_card).grid(row=1, column=4, sticky="w", padx=4)
        self.log_hours_var = tk.StringVar(value="1.5")
        ttk.Entry(log_box, textvariable=self.log_hours_var, width=8).grid(row=1, column=5, sticky="w", padx=4)

        ttk.Label(log_box, text="Topic / Concepts Covered:", background=self.c_card).grid(row=2, column=0, sticky="w", padx=4, pady=8)
        self.log_topic_var = tk.StringVar()
        ttk.Entry(log_box, textvariable=self.log_topic_var, width=48).grid(row=2, column=1, columnspan=3, sticky="w", padx=4, pady=8)

        btn_add_log = ttk.Button(log_box, text="Record Session", style="Primary.TButton", command=self.add_study_session)
        btn_add_log.grid(row=2, column=4, columnspan=2, sticky="e", padx=4, pady=8)

        # Log History Table
        history_frame = ttk.Frame(tab)
        history_frame.pack(fill=tk.BOTH, expand=True)

        cols = ("id", "course_name", "platform", "date", "hours", "topic")
        self.log_tree = ttk.Treeview(history_frame, columns=cols, show="headings", selectmode="browse")

        self.log_tree.heading("id", text="Log ID")
        self.log_tree.heading("course_name", text="Course Name")
        self.log_tree.heading("platform", text="Platform")
        self.log_tree.heading("date", text="Study Date")
        self.log_tree.heading("hours", text="Hours Spent")
        self.log_tree.heading("topic", text="Topic / Work Done")

        self.log_tree.column("id", width=55, anchor="center")
        self.log_tree.column("course_name", width=260, anchor="w")
        self.log_tree.column("platform", width=100, anchor="center")
        self.log_tree.column("date", width=100, anchor="center")
        self.log_tree.column("hours", width=90, anchor="center")
        self.log_tree.column("topic", width=340, anchor="w")

        scroll = ttk.Scrollbar(history_frame, orient=tk.VERTICAL, command=self.log_tree.yview)
        self.log_tree.configure(yscroll=scroll.set)

        self.log_tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scroll.pack(side=tk.RIGHT, fill=tk.Y)

        # Bottom Bar for Study Log
        b_bar = ttk.Frame(tab)
        b_bar.pack(fill=tk.X, pady=(6, 0))

        self.log_summary_lbl = ttk.Label(b_bar, text="Total Study Sessions: 0 • Total Hours: 0.0 hrs", font=("Helvetica", 9, "bold"))
        self.log_summary_lbl.pack(side=tk.LEFT)

        btn_del_log = ttk.Button(b_bar, text="🗑️ Delete Selected Log", style="Danger.TButton", command=self.delete_study_session)
        btn_del_log.pack(side=tk.RIGHT)

    def load_study_log_dropdown(self):
        courses = self.db.get_courses()
        self.course_lookup = {f"{c['course_name']} ({c['platform']})": c["course_id"] for c in courses}
        course_names = list(self.course_lookup.keys())
        self.log_course_cb["values"] = course_names
        if course_names and not self.log_course_cb.get():
            self.log_course_cb.set(course_names[0])

    def load_study_logs(self):
        for item in self.log_tree.get_children():
            self.log_tree.delete(item)

        logs = self.db.get_study_logs()
        total_hours = 0.0
        for log in logs:
            h = float(log.get("hours_spent", 0.0))
            total_hours += h
            self.log_tree.insert("", tk.END, values=(
                log["log_id"],
                log["course_name"],
                log["platform"],
                log["study_date"],
                f"{h:.1f} hrs",
                log.get("topic_covered", "") or "-"
            ))

        self.log_summary_lbl.config(text=f"Total Study Sessions: {len(logs)} • Total Hours Logged: {total_hours:.1f} hrs")

    def add_study_session(self):
        selected_text = self.log_course_cb.get()
        if not selected_text or selected_text not in self.course_lookup:
            messagebox.showwarning("Validation Error", "Please select a valid course.")
            return

        cid = self.course_lookup[selected_text]
        s_date = self.log_date_var.get().strip()
        hours_str = self.log_hours_var.get().strip()
        topic = self.log_topic_var.get().strip()

        try:
            hours = float(hours_str)
            if hours <= 0:
                raise ValueError
        except ValueError:
            messagebox.showerror("Validation Error", "Hours spent must be a positive number (e.g., 2.5).")
            return

        self.db.add_study_log(course_id=cid, study_date=s_date, hours_spent=hours, topic_covered=topic)
        self.log_topic_var.set("")
        self.refresh_all_data()
        messagebox.showinfo("Success", f"Logged {hours} hrs for {selected_text.split('(')[0].strip()}!")

    def delete_study_session(self):
        selected = self.log_tree.selection()
        if not selected:
            messagebox.showwarning("Selection Required", "Please select a log entry to delete.")
            return
        log_id = int(self.log_tree.item(selected[0], "values")[0])
        if messagebox.askyesno("Confirm Delete", "Are you sure you want to delete this study session record?"):
            self.db.delete_study_log(log_id)
            self.refresh_all_data()

    # ========================================================
    # TAB 3: Deadlines & Tasks
    # ========================================================

    def _init_deadlines_tab(self):
        tab = self.tab_deadlines

        # Deadline Alert Banner
        self.deadline_alert_lbl = ttk.Label(tab, text="", font=("Helvetica", 10, "bold"), background="#FEF3C7", foreground="#B45309", padding=8, relief="solid", borderwidth=1)
        self.deadline_alert_lbl.pack(fill=tk.X, pady=(0, 10))

        # Add Deadline Input Card
        add_box = ttk.Frame(tab, style="Card.TFrame", padding=14)
        add_box.pack(fill=tk.X, pady=(0, 10))

        ttk.Label(add_box, text="➕ Add Upcoming Assignment or Exam", font=("Helvetica", 11, "bold"), background=self.c_card).grid(row=0, column=0, columnspan=5, sticky="w", pady=(0, 8))

        ttk.Label(add_box, text="Course *:", background=self.c_card).grid(row=1, column=0, sticky="w", padx=4)
        self.dl_course_cb = ttk.Combobox(add_box, width=28, state="readonly")
        self.dl_course_cb.grid(row=1, column=1, sticky="w", padx=4)

        ttk.Label(add_box, text="Task / Exam Name *:", background=self.c_card).grid(row=1, column=2, sticky="w", padx=4)
        self.dl_task_var = tk.StringVar()
        ttk.Entry(add_box, textvariable=self.dl_task_var, width=26).grid(row=1, column=3, sticky="w", padx=4)

        ttk.Label(add_box, text="Due Date (YYYY-MM-DD) *:", background=self.c_card).grid(row=1, column=4, sticky="w", padx=4)
        self.dl_due_var = tk.StringVar(value=date.today().strftime("%Y-%m-%d"))
        ttk.Entry(add_box, textvariable=self.dl_due_var, width=12).grid(row=1, column=5, sticky="w", padx=4)

        btn_add_dl = ttk.Button(add_box, text="Add Deadline", style="Primary.TButton", command=self.add_deadline)
        btn_add_dl.grid(row=1, column=6, sticky="e", padx=(8, 0))

        # Deadlines Table
        table_frame = ttk.Frame(tab)
        table_frame.pack(fill=tk.BOTH, expand=True)

        cols = ("id", "status", "task", "course", "platform", "due_date", "days_left")
        self.dl_tree = ttk.Treeview(table_frame, columns=cols, show="headings", selectmode="browse")

        self.dl_tree.heading("id", text="ID")
        self.dl_tree.heading("status", text="Done?")
        self.dl_tree.heading("task", text="Task / Exam Name")
        self.dl_tree.heading("course", text="Course Name")
        self.dl_tree.heading("platform", text="Platform")
        self.dl_tree.heading("due_date", text="Due Date")
        self.dl_tree.heading("days_left", text="Urgency / Days Left")

        self.dl_tree.column("id", width=45, anchor="center")
        self.dl_tree.column("status", width=65, anchor="center")
        self.dl_tree.column("task", width=250, anchor="w")
        self.dl_tree.column("course", width=220, anchor="w")
        self.dl_tree.column("platform", width=95, anchor="center")
        self.dl_tree.column("due_date", width=100, anchor="center")
        self.dl_tree.column("days_left", width=140, anchor="center")

        scroll = ttk.Scrollbar(table_frame, orient=tk.VERTICAL, command=self.dl_tree.yview)
        self.dl_tree.configure(yscroll=scroll.set)

        self.dl_tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scroll.pack(side=tk.RIGHT, fill=tk.Y)

        # Bottom Bar
        b_bar = ttk.Frame(tab)
        b_bar.pack(fill=tk.X, pady=(6, 0))

        btn_toggle = ttk.Button(b_bar, text="✅ Mark Completed / Incomplete", style="Success.TButton", command=self.toggle_deadline)
        btn_toggle.pack(side=tk.LEFT)

        btn_del_dl = ttk.Button(b_bar, text="🗑️ Delete Deadline", style="Danger.TButton", command=self.delete_deadline)
        btn_del_dl.pack(side=tk.RIGHT)

    def load_deadlines_dropdown(self):
        courses = self.db.get_courses()
        self.dl_lookup = {f"{c['course_name']} ({c['platform']})": c["course_id"] for c in courses}
        course_names = list(self.dl_lookup.keys())
        self.dl_course_cb["values"] = course_names
        if course_names and not self.dl_course_cb.get():
            self.dl_course_cb.set(course_names[0])

    def load_deadlines(self):
        for item in self.dl_tree.get_children():
            self.dl_tree.delete(item)

        deadlines = self.db.get_deadlines(include_completed=True)
        today = date.today()

        urgent_count = 0
        for d in deadlines:
            is_done = bool(d.get("is_done", 0))
            status_symbol = "✅ Done" if is_done else "⏳ Pending"

            # Calculate days left
            try:
                due = datetime.strptime(str(d["due_date"])[:10], "%Y-%m-%d").date()
                delta = (due - today).days
                if is_done:
                    urgency_text = "Completed"
                elif delta < 0:
                    urgency_text = f"⚠️ OVERDUE by {abs(delta)} days"
                    urgent_count += 1
                elif delta == 0:
                    urgency_text = "🔥 DUE TODAY!"
                    urgent_count += 1
                elif delta <= 3:
                    urgency_text = f"⏰ Due in {delta} days (Soon)"
                    urgent_count += 1
                else:
                    urgency_text = f"{delta} days remaining"
            except Exception:
                urgency_text = "N/A"

            self.dl_tree.insert("", tk.END, values=(
                d["deadline_id"],
                status_symbol,
                d["task_name"],
                d["course_name"],
                d["platform"],
                d["due_date"],
                urgency_text
            ))

        if urgent_count > 0:
            self.deadline_alert_lbl.config(
                text=f"⚠️ ATTENTION: You have {urgent_count} urgent or overdue deadlines! Review the table below.",
                background="#FEE2E2", foreground="#991B1B"
            )
        else:
            self.deadline_alert_lbl.config(
                text="🎉 All caught up! No urgent or overdue deadlines in the immediate queue.",
                background="#DCFCE7", foreground="#166534"
            )

    def add_deadline(self):
        selected_text = self.dl_course_cb.get()
        task = self.dl_task_var.get().strip()
        due = self.dl_due_var.get().strip()

        if not selected_text or selected_text not in self.dl_lookup or not task or not due:
            messagebox.showwarning("Validation Error", "All fields are required to create a deadline.")
            return

        cid = self.dl_lookup[selected_text]
        self.db.add_deadline(course_id=cid, task_name=task, due_date=due, is_done=0)
        self.dl_task_var.set("")
        self.refresh_all_data()

    def toggle_deadline(self):
        selected = self.dl_tree.selection()
        if not selected:
            messagebox.showwarning("Selection Required", "Please select a task from the list.")
            return
        row = self.dl_tree.item(selected[0], "values")
        dl_id = int(row[0])
        current_status = row[1]
        new_status = 0 if "Done" in current_status else 1
        self.db.toggle_deadline(dl_id, new_status)
        self.refresh_all_data()

    def delete_deadline(self):
        selected = self.dl_tree.selection()
        if not selected:
            messagebox.showwarning("Selection Required", "Please select a deadline to delete.")
            return
        dl_id = int(self.dl_tree.item(selected[0], "values")[0])
        if messagebox.askyesno("Confirm Delete", "Delete this deadline?"):
            self.db.delete_deadline(dl_id)
            self.refresh_all_data()

    # ========================================================
    # TAB 4: Certificates & Notes
    # ========================================================

    def _init_certs_notes_tab(self):
        tab = self.tab_certs_notes

        paned = ttk.PanedWindow(tab, orient=tk.HORIZONTAL)
        paned.pack(fill=tk.BOTH, expand=True)

        # Left: Certificates
        cert_frame = ttk.Frame(paned, padding=8)
        paned.add(cert_frame, weight=1)

        ttk.Label(cert_frame, text="📜 Course Certificates", font=("Helvetica", 12, "bold")).pack(anchor="w", pady=(0, 6))

        c_bar = ttk.Frame(cert_frame)
        c_bar.pack(fill=tk.X, pady=(0, 6))
        ttk.Button(c_bar, text="➕ Add Certificate", style="Primary.TButton", command=self.open_add_cert_modal).pack(side=tk.LEFT, padx=2)
        ttk.Button(c_bar, text="🌐 Open Link", style="Secondary.TButton", command=self.open_cert_link).pack(side=tk.LEFT, padx=2)
        ttk.Button(c_bar, text="🗑️ Delete", style="Danger.TButton", command=self.delete_cert).pack(side=tk.RIGHT, padx=2)

        cols = ("id", "course", "platform", "date", "grade")
        self.cert_tree = ttk.Treeview(cert_frame, columns=cols, show="headings", selectmode="browse")
        self.cert_tree.heading("id", text="ID")
        self.cert_tree.heading("course", text="Course")
        self.cert_tree.heading("platform", text="Platform")
        self.cert_tree.heading("date", text="Issue Date")
        self.cert_tree.heading("grade", text="Grade / Distinction")

        self.cert_tree.column("id", width=35, anchor="center")
        self.cert_tree.column("course", width=160, anchor="w")
        self.cert_tree.column("platform", width=80, anchor="center")
        self.cert_tree.column("date", width=85, anchor="center")
        self.cert_tree.column("grade", width=110, anchor="center")

        self.cert_tree.pack(fill=tk.BOTH, expand=True)

        # Right: Course Notes Viewer & Editor
        notes_frame = ttk.Frame(paned, padding=8)
        paned.add(notes_frame, weight=1)

        ttk.Label(notes_frame, text="📝 Study Notes & Syllabus Tracker", font=("Helvetica", 12, "bold")).pack(anchor="w", pady=(0, 6))

        sel_box = ttk.Frame(notes_frame)
        sel_box.pack(fill=tk.X, pady=(0, 6))
        ttk.Label(sel_box, text="Select Course:").pack(side=tk.LEFT, padx=(0, 4))
        self.notes_course_cb = ttk.Combobox(sel_box, width=28, state="readonly")
        self.notes_course_cb.pack(side=tk.LEFT, padx=(0, 8))
        self.notes_course_cb.bind("<<ComboboxSelected>>", self.on_notes_course_selected)

        ttk.Button(sel_box, text="💾 Save Notes", style="Primary.TButton", command=self.save_course_notes).pack(side=tk.RIGHT)

        self.course_notes_text = tk.Text(notes_frame, font=("Courier", 10), wrap="word", relief="solid", borderwidth=1)
        self.course_notes_text.pack(fill=tk.BOTH, expand=True)

    def load_certs_and_notes(self):
        # Load Certificates
        for item in self.cert_tree.get_children():
            self.cert_tree.delete(item)

        certs = self.db.get_certificates()
        for c in certs:
            self.cert_tree.insert("", tk.END, values=(
                c["cert_id"],
                c["course_name"],
                c["platform"],
                c.get("issue_date", "") or "-",
                c.get("grade", "") or "Completed"
            ))

        # Load Notes Dropdown
        courses = self.db.get_courses()
        self.notes_lookup = {f"{c['course_name']} ({c['platform']})": c for c in courses}
        names = list(self.notes_lookup.keys())
        self.notes_course_cb["values"] = names
        if names and not self.notes_course_cb.get():
            self.notes_course_cb.set(names[0])
            self.on_notes_course_selected(None)

    def on_notes_course_selected(self, event):
        sel = self.notes_course_cb.get()
        if sel in self.notes_lookup:
            course = self.notes_lookup[sel]
            self.course_notes_text.delete("1.0", tk.END)
            self.course_notes_text.insert("1.0", course.get("notes", "") or "")

    def save_course_notes(self):
        sel = self.notes_course_cb.get()
        if sel not in self.notes_lookup:
            messagebox.showwarning("Warning", "Please select a course first.")
            return
        course = self.notes_lookup[sel]
        cid = course["course_id"]
        notes = self.course_notes_text.get("1.0", tk.END).strip()
        self.db.update_course(
            course_id=cid,
            course_name=course["course_name"],
            platform=course["platform"],
            instructor=course.get("instructor", ""),
            start_date=course.get("start_date", ""),
            end_date=course.get("end_date", ""),
            status=course.get("status", "Not Started"),
            progress_percent=course.get("progress_percent", 0),
            priority=course.get("priority", "Medium"),
            course_link=course.get("course_link", ""),
            notes=notes
        )
        messagebox.showinfo("Saved", "Course notes updated successfully!")

    def open_add_cert_modal(self):
        modal = tk.Toplevel(self.root)
        modal.title("Add Certificate Link")
        modal.geometry("450x300")
        modal.transient(self.root)
        modal.grab_set()

        frame = ttk.Frame(modal, padding=20)
        frame.pack(fill=tk.BOTH, expand=True)

        courses = self.db.get_courses()
        course_map = {f"{c['course_name']} ({c['platform']})": c["course_id"] for c in courses}

        ttk.Label(frame, text="Course *:", font=("Helvetica", 9, "bold")).grid(row=0, column=0, sticky="w", pady=6)
        c_cb = ttk.Combobox(frame, values=list(course_map.keys()), width=26, state="readonly")
        c_cb.grid(row=0, column=1, sticky="w", pady=6)
        if course_map:
            c_cb.set(list(course_map.keys())[0])

        ttk.Label(frame, text="Certificate URL/File *:", font=("Helvetica", 9, "bold")).grid(row=1, column=0, sticky="w", pady=6)
        url_var = tk.StringVar()
        ttk.Entry(frame, textvariable=url_var, width=28).grid(row=1, column=1, sticky="w", pady=6)

        ttk.Label(frame, text="Issue Date:", font=("Helvetica", 9, "bold")).grid(row=2, column=0, sticky="w", pady=6)
        date_var = tk.StringVar(value=date.today().strftime("%Y-%m-%d"))
        ttk.Entry(frame, textvariable=date_var, width=15).grid(row=2, column=1, sticky="w", pady=6)

        ttk.Label(frame, text="Grade / Distinction:", font=("Helvetica", 9, "bold")).grid(row=3, column=0, sticky="w", pady=6)
        grade_var = tk.StringVar(value="Certificate of Completion")
        ttk.Entry(frame, textvariable=grade_var, width=28).grid(row=3, column=1, sticky="w", pady=6)

        def save():
            c_txt = c_cb.get()
            url = url_var.get().strip()
            if not c_txt or not url:
                messagebox.showerror("Error", "Course and Certificate Link are required.", parent=modal)
                return
            self.db.add_certificate(course_map[c_txt], url, date_var.get().strip(), grade_var.get().strip())
            modal.destroy()
            self.refresh_all_data()

        b_box = ttk.Frame(frame)
        b_box.grid(row=4, column=0, columnspan=2, pady=16)
        ttk.Button(b_box, text="Add Certificate", style="Primary.TButton", command=save).pack(side=tk.LEFT, padx=6)
        ttk.Button(b_box, text="Cancel", style="Secondary.TButton", command=modal.destroy).pack(side=tk.LEFT, padx=6)

    def open_cert_link(self):
        selected = self.cert_tree.selection()
        if not selected:
            messagebox.showwarning("Selection Required", "Please select a certificate to view.")
            return
        cert_id = int(self.cert_tree.item(selected[0], "values")[0])
        certs = self.db.get_certificates()
        for c in certs:
            if c["cert_id"] == cert_id:
                link = c.get("certificate_link")
                if link:
                    webbrowser.open(link)
                return

    def delete_cert(self):
        selected = self.cert_tree.selection()
        if not selected:
            messagebox.showwarning("Selection Required", "Please select a certificate to delete.")
            return
        cert_id = int(self.cert_tree.item(selected[0], "values")[0])
        if messagebox.askyesno("Confirm Delete", "Remove this certificate link?"):
            self.db.delete_certificate(cert_id)
            self.refresh_all_data()

    # ========================================================
    # TAB 5: Analytics & Visualizations
    # ========================================================

    def _init_analytics_tab(self):
        tab = self.tab_analytics

        # Controls Toolbar
        c_bar = ttk.Frame(tab)
        c_bar.pack(fill=tk.X, pady=(0, 10))

        ttk.Label(c_bar, text="Select Chart Type:", font=("Helvetica", 10, "bold")).pack(side=tk.LEFT, padx=(0, 6))

        self.chart_type_cb = ttk.Combobox(
            c_bar,
            values=[
                "Total Study Hours per Course",
                "Course Status Distribution",
                "Study Hours Trend Over Time",
                "Courses Enrolled by Platform"
            ],
            state="readonly",
            width=28
        )
        self.chart_type_cb.set("Total Study Hours per Course")
        self.chart_type_cb.bind("<<ComboboxSelected>>", lambda e: self.render_current_chart())
        self.chart_type_cb.pack(side=tk.LEFT, padx=(0, 12))

        ttk.Button(c_bar, text="🔄 Refresh Chart", style="Secondary.TButton", command=self.render_current_chart).pack(side=tk.LEFT, padx=4)
        ttk.Button(c_bar, text="💾 Export All Charts to PNG", style="Primary.TButton", command=self.export_charts).pack(side=tk.RIGHT, padx=4)

        # Matplotlib Canvas Container
        self.chart_container = ttk.Frame(tab, style="Card.TFrame", padding=6)
        self.chart_container.pack(fill=tk.BOTH, expand=True)

        self.fig = Figure(figsize=(7, 4.5), dpi=100)
        self.canvas = FigureCanvasTkAgg(self.fig, master=self.chart_container)
        self.canvas_widget = self.canvas.get_tk_widget()
        self.canvas_widget.pack(fill=tk.BOTH, expand=True)

        self.toolbar = NavigationToolbar2Tk(self.canvas, self.chart_container)
        self.toolbar.update()

    def render_current_chart(self):
        chart_type = self.chart_type_cb.get()
        if chart_type == "Total Study Hours per Course":
            self.analytics.plot_hours_per_course(self.fig)
        elif chart_type == "Course Status Distribution":
            self.analytics.plot_status_pie(self.fig)
        elif chart_type == "Study Hours Trend Over Time":
            self.analytics.plot_weekly_trend(self.fig)
        elif chart_type == "Courses Enrolled by Platform":
            self.analytics.plot_platform_breakdown(self.fig)

        self.canvas.draw()

    def export_charts(self):
        try:
            saved_paths = self.analytics.export_all_charts("exported_charts")
            msg = "Successfully exported 4 high-resolution charts:\n\n" + "\n".join(saved_paths)
            messagebox.showinfo("Export Successful", msg)
        except Exception as e:
            messagebox.showerror("Export Failed", f"Error exporting charts: {e}")

    # ========================================================
    # Global Refresh & Demo Data
    # ========================================================

    def refresh_all_data(self):
        """Refreshes KPI metrics, tables, dropdowns, and charts."""
        # Refresh KPI cards
        kpis = self.analytics.get_kpi_summary()
        self.kpi_labels["total_courses"].config(text=str(kpis["total_courses"]))
        self.kpi_labels["total_hours"].config(text=f"{kpis['total_hours']} hrs")
        self.kpi_labels["avg_progress"].config(text=f"{kpis['avg_progress']}%")
        self.kpi_labels["pending_deadlines"].config(text=str(kpis["pending_deadlines"]))
        self.kpi_labels["most_used_platform"].config(text=str(kpis["most_used_platform"]))

        # Refresh individual views
        self.load_courses()
        self.load_study_log_dropdown()
        self.load_study_logs()
        self.load_deadlines_dropdown()
        self.load_deadlines()
        self.load_certs_and_notes()
        self.render_current_chart()

    def seed_demo_data(self):
        if messagebox.askyesno("Load Demo Data", "This will load sample courses, study logs, and deadlines for testing. Continue?"):
            self.db.seed_demo_data()
            self.refresh_all_data()
            messagebox.showinfo("Success", "Demo data loaded successfully!")


def launch_gui(db: Database):
    root = tk.Tk()
    app = CourseTrackerGUI(root, db)
    root.mainloop()


if __name__ == "__main__":
    db = Database()
    launch_gui(db)
