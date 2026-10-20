"""
analytics.py - Data Analysis & Visualizations Layer
Leverages Pandas for summary aggregations and Matplotlib for charting.
Strictly scoped per-user.
"""

import os
from typing import Dict, Any, Tuple, Optional
import pandas as pd
import matplotlib.pyplot as plt
from matplotlib.figure import Figure
import matplotlib.dates as mdates

# Set clean aesthetic styling
plt.style.use("seaborn-v0_8-whitegrid" if "seaborn-v0_8-whitegrid" in plt.style.available else "default")
PALETTE = ["#2563EB", "#10B981", "#F59E0B", "#EF4444", "#8B5CF6", "#06B6D4"]


class AnalyticsManager:
    def __init__(self, db):
        self.db = db

    # ========================================================
    # Pandas Summary Aggregations (Per-User)
    # ========================================================

    def get_courses_df(self, user_id: int) -> pd.DataFrame:
        """Fetches all courses for the user into a Pandas DataFrame."""
        courses = self.db.get_courses(user_id)
        if not courses:
            return pd.DataFrame(columns=[
                "course_id", "course_name", "platform", "instructor",
                "start_date", "end_date", "status", "progress_percent", "priority", "course_link", "notes"
            ])
        df = pd.DataFrame(courses)
        df["progress_percent"] = pd.to_numeric(df["progress_percent"], errors="coerce").fillna(0)
        return df

    def get_study_logs_df(self, user_id: int) -> pd.DataFrame:
        """Fetches all study logs for the user into a Pandas DataFrame."""
        logs = self.db.get_study_logs(user_id)
        if not logs:
            return pd.DataFrame(columns=[
                "log_id", "course_id", "course_name", "platform", "study_date", "hours_spent", "topic_covered"
            ])
        df = pd.DataFrame(logs)
        df["hours_spent"] = pd.to_numeric(df["hours_spent"], errors="coerce").fillna(0.0)
        df["study_date"] = pd.to_datetime(df["study_date"], errors="coerce")
        return df

    def get_deadlines_df(self, user_id: int) -> pd.DataFrame:
        """Fetches all deadlines for the user into a Pandas DataFrame."""
        deadlines = self.db.get_deadlines(user_id)
        if not deadlines:
            return pd.DataFrame(columns=[
                "deadline_id", "course_id", "course_name", "platform", "task_name", "due_date", "is_done"
            ])
        df = pd.DataFrame(deadlines)
        df["due_date"] = pd.to_datetime(df["due_date"], errors="coerce")
        return df

    def get_kpi_summary(self, user_id: int) -> Dict[str, Any]:
        """Calculates executive KPI metrics across courses, logs, deadlines, and exams."""
        c_df = self.get_courses_df(user_id)
        s_df = self.get_study_logs_df(user_id)
        d_df = self.get_deadlines_df(user_id)

        total_courses = len(c_df)
        completed_courses = len(c_df[c_df["status"] == "Completed"]) if not c_df.empty else 0
        in_progress_courses = len(c_df[c_df["status"] == "In Progress"]) if not c_df.empty else 0
        avg_progress = c_df["progress_percent"].mean() if not c_df.empty else 0.0

        total_hours = s_df["hours_spent"].sum() if not s_df.empty else 0.0
        total_sessions = len(s_df)

        pending_deadlines = len(d_df[d_df["is_done"] == 0]) if not d_df.empty else 0

        # Count upcoming exams (where days_left >= 0)
        exams = self.db.get_exams(user_id)
        upcoming_exams = sum(1 for e in exams if e.get("days_left", -1) >= 0)

        # Most used platform
        most_used_platform = "N/A"
        if not c_df.empty and "platform" in c_df.columns:
            mode_platform = c_df["platform"].mode()
            if not mode_platform.empty:
                most_used_platform = mode_platform.iloc[0]

        return {
            "total_courses": total_courses,
            "completed_courses": completed_courses,
            "in_progress_courses": in_progress_courses,
            "avg_progress": round(avg_progress, 1),
            "total_hours": round(total_hours, 1),
            "total_sessions": total_sessions,
            "pending_deadlines": pending_deadlines,
            "upcoming_exams": upcoming_exams,
            "most_used_platform": most_used_platform
        }

    def get_platform_breakdown_df(self, user_id: int) -> pd.DataFrame:
        """Returns a Pandas DataFrame aggregating metrics by learning platform."""
        c_df = self.get_courses_df(user_id)
        if c_df.empty:
            return pd.DataFrame()
        grouped = c_df.groupby("platform").agg(
            course_count=("course_id", "count"),
            avg_progress=("progress_percent", "mean")
        ).reset_index()
        grouped["avg_progress"] = grouped["avg_progress"].round(1)
        return grouped

    # ========================================================
    # Matplotlib Visualizations (Per-User)
    # ========================================================

    def plot_hours_per_course(self, user_id: int, fig: Figure):
        """Generates a horizontal bar chart of study hours per course."""
        fig.clear()
        ax = fig.add_subplot(111)

        s_df = self.get_study_logs_df(user_id)
        if s_df.empty:
            ax.text(0.5, 0.5, "No study sessions recorded yet.\nStart studying and log your hours!",
                    horizontalalignment='center', verticalalignment='center', transform=ax.transAxes,
                    fontsize=11, color="#64748B")
            ax.set_axis_off()
            fig.tight_layout()
            return

        grouped = s_df.groupby("course_name")["hours_spent"].sum().sort_values(ascending=True)

        bars = ax.barh(grouped.index, grouped.values, color="#3B82F6", edgecolor="#1D4ED8", height=0.6)
        ax.set_title("Total Study Hours per Course", fontsize=13, fontweight="bold", pad=12, color="#1E293B")
        ax.set_xlabel("Hours Spent", fontsize=10, fontweight="600", color="#475569")
        ax.set_ylabel("Course Name", fontsize=10, fontweight="600", color="#475569")

        for bar in bars:
            width = bar.get_width()
            ax.annotate(f"{width:.1f} hrs",
                        xy=(width, bar.get_y() + bar.get_height() / 2),
                        xytext=(5, 0),
                        textcoords="offset points",
                        ha='left', va='center', fontsize=9, fontweight="bold", color="#1E293B")

        ax.grid(axis='x', linestyle='--', alpha=0.6)
        fig.tight_layout()

    def plot_status_pie(self, user_id: int, fig: Figure):
        """Generates a donut/pie chart showing course completion status distribution."""
        fig.clear()
        ax = fig.add_subplot(111)

        c_df = self.get_courses_df(user_id)
        if c_df.empty:
            ax.text(0.5, 0.5, "No courses added yet.\nAdd courses to see status breakdown.",
                    horizontalalignment='center', verticalalignment='center', transform=ax.transAxes,
                    fontsize=11, color="#64748B")
            ax.set_axis_off()
            fig.tight_layout()
            return

        status_counts = c_df["status"].value_counts()
        status_colors = {
            "Completed": "#10B981",
            "In Progress": "#3B82F6",
            "Not Started": "#94A3B8",
            "On Hold": "#F59E0B"
        }
        colors = [status_colors.get(s, "#CBD5E1") for s in status_counts.index]

        wedges, texts, autotexts = ax.pie(
            status_counts.values,
            labels=status_counts.index,
            autopct="%1.1f%%",
            startangle=140,
            colors=colors,
            wedgeprops=dict(width=0.45, edgecolor="white", linewidth=2)
        )

        for text in texts:
            text.set_fontsize(9)
            text.set_fontweight("600")
            text.set_color("#1E293B")
        for autotext in autotexts:
            autotext.set_fontsize(9)
            autotext.set_fontweight("bold")
            autotext.set_color("white")

        ax.set_title("Course Status Distribution", fontsize=13, fontweight="bold", pad=12, color="#1E293B")
        fig.tight_layout()

    def plot_weekly_trend(self, user_id: int, fig: Figure):
        """Generates a daily / weekly study-hour trend line chart."""
        fig.clear()
        ax = fig.add_subplot(111)

        s_df = self.get_study_logs_df(user_id)
        if s_df.empty:
            ax.text(0.5, 0.5, "No study logs available to plot trend.",
                    horizontalalignment='center', verticalalignment='center', transform=ax.transAxes,
                    fontsize=11, color="#64748B")
            ax.set_axis_off()
            fig.tight_layout()
            return

        daily = s_df.dropna(subset=["study_date"]).groupby("study_date")["hours_spent"].sum().reset_index()
        daily = daily.sort_values("study_date")

        ax.plot(daily["study_date"], daily["hours_spent"], marker="o", markersize=6,
                linewidth=2.5, color="#8B5CF6", label="Daily Study Hours")
        ax.fill_between(daily["study_date"], daily["hours_spent"], color="#8B5CF6", alpha=0.15)

        ax.set_title("Study Hours Trend Over Time", fontsize=13, fontweight="bold", pad=12, color="#1E293B")
        ax.set_xlabel("Date", fontsize=10, fontweight="600", color="#475569")
        ax.set_ylabel("Hours Studied", fontsize=10, fontweight="600", color="#475569")

        ax.xaxis.set_major_formatter(mdates.DateFormatter("%b %d"))
        fig.autofmt_xdate(rotation=30)
        ax.grid(True, linestyle="--", alpha=0.6)
        ax.legend(loc="upper left")
        fig.tight_layout()

    def plot_platform_breakdown(self, user_id: int, fig: Figure):
        """Generates a vertical bar chart of courses per platform."""
        fig.clear()
        ax = fig.add_subplot(111)

        c_df = self.get_courses_df(user_id)
        if c_df.empty:
            ax.text(0.5, 0.5, "No courses found to aggregate platforms.",
                    horizontalalignment='center', verticalalignment='center', transform=ax.transAxes,
                    fontsize=11, color="#64748B")
            ax.set_axis_off()
            fig.tight_layout()
            return

        counts = c_df["platform"].value_counts()
        colors = ["#3B82F6", "#10B981", "#F59E0B", "#EF4444", "#8B5CF6"][:len(counts)]

        bars = ax.bar(counts.index, counts.values, color=colors, edgecolor="#334155", width=0.55)
        ax.set_title("Courses Enrolled by Platform", fontsize=13, fontweight="bold", pad=12, color="#1E293B")
        ax.set_xlabel("Platform", fontsize=10, fontweight="600", color="#475569")
        ax.set_ylabel("Number of Courses", fontsize=10, fontweight="600", color="#475569")

        for bar in bars:
            height = bar.get_height()
            ax.annotate(f"{int(height)}",
                        xy=(bar.get_x() + bar.get_width() / 2, height),
                        xytext=(0, 4),
                        textcoords="offset points",
                        ha='center', va='bottom', fontsize=9, fontweight="bold")

        ax.grid(axis='y', linestyle='--', alpha=0.6)
        fig.tight_layout()

    def export_all_charts(self, user_id: int, output_dir: str = "exported_charts") -> list:
        """Renders and saves all 4 charts to PNG images for the user."""
        os.makedirs(output_dir, exist_ok=True)
        saved_paths = []

        charts = [
            ("hours_per_course.png", self.plot_hours_per_course),
            ("status_distribution.png", self.plot_status_pie),
            ("study_trend.png", self.plot_weekly_trend),
            ("platform_breakdown.png", self.plot_platform_breakdown),
        ]

        for filename, plot_fn in charts:
            fig = Figure(figsize=(8, 5), dpi=150)
            plot_fn(user_id, fig)
            filepath = os.path.join(output_dir, filename)
            fig.savefig(filepath, bbox_inches="tight")
            saved_paths.append(filepath)
            plt.close(fig)

        return saved_paths
