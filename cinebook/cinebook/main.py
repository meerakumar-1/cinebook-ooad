"""Entry point.
  python main.py web [--reset] [--port 5000]   full web application (REST API + browser UI + SQLite)
  python main.py demo                           scripted console walkthrough (in-memory DB)
  python main.py                                interactive console (alternative presentation layer)
"""
import os
import sys

from cinebook.data.database import DatabaseManager
from cinebook.data.seed import seed_demo
from cinebook.presentation.cli import interactive, run_demo
from cinebook.services.booking_facade import BookingFacade

DB_FILE = "cinebook.db"


def main(argv):
    mode = argv[1] if len(argv) > 1 else "cli"
    if mode == "web" and "--reset" in argv and os.path.exists(DB_FILE):
        os.remove(DB_FILE)
    db = DatabaseManager.get_instance(":memory:" if mode == "demo" else DB_FILE)
    facade = BookingFacade(db)
    if not facade.list_movies():
        seed_demo(facade)

    if mode == "demo":
        run_demo(facade)
    elif mode == "web":
        from cinebook.web.app import create_app
        port = int(argv[argv.index("--port") + 1]) if "--port" in argv else 5000
        print(f"CineBook running on http://localhost:{port}  (demo login: asha@example.com / demo1234)")
        create_app(facade).run(host="0.0.0.0", port=port, threaded=True)
    else:
        interactive(facade)


if __name__ == "__main__":
    main(sys.argv)
