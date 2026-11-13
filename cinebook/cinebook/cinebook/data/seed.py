"""Demo data. Show times are relative to 'now' so the demo never goes stale."""
from datetime import datetime, timedelta

from ..domain.models import Admin, Customer, Movie, Screen, Seat, SeatType, Show, Theatre

ROW_TYPES = {"A": SeatType.REGULAR, "B": SeatType.REGULAR, "C": SeatType.PREMIUM, "D": SeatType.RECLINER}


def _screen(name):
    return Screen(name, [Seat(r, n, t) for r, t in ROW_TYPES.items() for n in range(1, 7)])


def seed_demo(facade, now=None):
    now = now or datetime.now()
    day = lambda d, h: (now + timedelta(days=d)).replace(hour=h, minute=0, second=0, microsecond=0)
    with facade._db.transaction():
        th = facade.theatres.add(Theatre("Orion Cinemas", "Bengaluru", [_screen("Screen 1"), _screen("Screen 2")]))
        movies = [facade.movies.add(m) for m in (
            Movie("Interstellar Returns", 165, "Sci-Fi", "English", "UA"),
            Movie("Kantara Legacy", 148, "Drama", "Kannada", "UA"),
            Movie("Laugh Riot", 122, "Comedy", "Hindi", "U"))]
        for i, m in enumerate(movies):
            facade.shows.add(Show(m, th.screens[i % 2], day(1, 12 + 3 * i), 250.0))
            facade.shows.add(Show(m, th.screens[(i + 1) % 2], day(2, 16 + 3 * i), 280.0))
        facade.users.add(Customer("Asha", "asha@example.com", "9876500001", is_student=True))
        facade.users.add(Customer("Rohan", "rohan@example.com", "9876500002"))
        facade.users.add(Admin("Manager", "admin@orion.example"))
