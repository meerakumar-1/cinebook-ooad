"""Entry point:  python main.py demo   |   python main.py   (interactive, persists to cinebook.db)"""
import sys

from cinebook.data.database import DatabaseManager
from cinebook.data.seed import seed_demo
from cinebook.presentation.cli import interactive, run_demo
from cinebook.services.booking_facade import BookingFacade

if __name__ == "__main__":
    demo = len(sys.argv) > 1 and sys.argv[1] == "demo"
    facade = BookingFacade(DatabaseManager.get_instance(":memory:" if demo else "cinebook.db"))
    if not facade.list_movies():
        seed_demo(facade)
    run_demo(facade) if demo else interactive(facade)
