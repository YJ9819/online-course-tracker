"""
main.py - Main Launcher for Online Course Tracker
Modes:
    python main.py              # Launches Modern SaaS Web Dashboard (Default)
    python main.py --cli        # Launches Menu-Driven Terminal CLI (CBSE IP Viva mode)
    python main.py --gui        # Launches Tkinter Desktop GUI
"""

import sys
import argparse
from database import Database
from analytics import AnalyticsManager


def main():
    parser = argparse.ArgumentParser(description="Online Course Tracker - Student Learning Management System")
    parser.add_argument("--web", action="store_true", help="Launch Modern SaaS Web Dashboard (Default)")
    parser.add_argument("--gui", action="store_true", help="Launch Tkinter Desktop GUI")
    parser.add_argument("--cli", action="store_true", help="Launch interactive menu-driven console CLI")
    parser.add_argument("--sqlite", action="store_true", help="Force SQLite database instead of attempting MySQL")
    parser.add_argument("--port", type=int, default=5000, help="Port for web dashboard (default: 5000)")
    parser.add_argument("--no-browser", action="store_true", help="Do not automatically open browser on web launch")
    args = parser.parse_args()

    print("=" * 60)
    print("🎓 Online Course Tracker: Student LMS")
    print("   Informatics Practices (IP) Project")
    print("=" * 60)

    # Initialize Database Layer
    db = Database(force_sqlite=args.sqlite)

    if args.cli:
        print("[INFO] Starting Menu-Driven Terminal Interface...")
        from cli import launch_cli
        launch_cli(db)
    elif args.gui:
        print("[INFO] Launching Desktop Tkinter GUI...")
        try:
            from gui import launch_gui
            launch_gui(db)
        except Exception as e:
            print(f"[ERROR] Could not start GUI ({e}). Falling back to Web Dashboard...")
            from app import run_web
            run_web(port=args.port, open_browser=not args.no_browser)
    else:
        # Default: Modern Web Dashboard
        print(f"[INFO] Launching Modern SaaS Web Interface on http://127.0.0.1:{args.port} ...")
        from app import run_web
        run_web(port=args.port, open_browser=not args.no_browser)


if __name__ == "__main__":
    main()
