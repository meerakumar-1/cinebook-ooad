"""Demo data. Show times are relative to 'now' so the demo never goes stale."""
from datetime import datetime, timedelta

from ..domain.models import Admin, Customer, Movie, Screen, Seat, SeatType, Show, Theatre
from ..security import hash_password

DEMO_PASSWORD = "demo1234"  # demo accounts only
ROW_TYPES = {"A": SeatType.REGULAR, "B": SeatType.REGULAR, "C": SeatType.PREMIUM,
             "D": SeatType.PREMIUM, "E": SeatType.RECLINER}
SEATS_PER_ROW = 8
SLOTS = [(11, 250.0), (14, 250.0), (18, 300.0), (21, 300.0)]  # (start hour, base price)
SLOT_MINUTES = [0, 30, 0, 30]

MOVIES = [
    Movie("Interstellar Returns", 165, "Sci-Fi", "English", "UA",
          "A retired astronaut is pulled back into the void when a signal from a lost colony reaches Earth."),
    Movie("Kantara Legacy", 148, "Drama", "Kannada", "UA",
          "A village guardian spirit, a land dispute and a family secret collide in this folklore-rooted drama."),
    Movie("Laugh Riot", 122, "Comedy", "Hindi", "U",
          "Four mismatched roommates accidentally become the managers of a failing wedding-planning agency."),
    Movie("Midnight Heist", 134, "Thriller", "English", "A",
          "One night, one vault, and a crew that has exactly 90 minutes before the city wakes up."),
    Movie("Monsoon Melodies", 128, "Romance", "Tamil", "U",
          "Two street musicians keep missing each other across a rain-soaked Chennai, one song at a time."),
    Movie("Iron Horizon", 141, "Action", "Telugu", "UA",
          "A railway engineer must stop a runaway freight train carrying something far more dangerous than cargo."),
]


def _screen(name):
    return Screen(name, [Seat(r, n, t) for r, t in ROW_TYPES.items() for n in range(1, SEATS_PER_ROW + 1)])


def seed_demo(facade, now=None):
    now = now or datetime.now()
    with facade.db.transaction():
        theatre = facade.theatres.add(Theatre("Orion Cinemas", "Bengaluru", [_screen("Screen 1"), _screen("Screen 2")]))
        movies = [facade.movies.add(m) for m in MOVIES]
        for si, screen in enumerate(theatre.screens):
            for day in (1, 2, 3):
                for slot, (hour, price) in enumerate(SLOTS):
                    start = (now + timedelta(days=day)).replace(hour=hour, minute=SLOT_MINUTES[slot], second=0, microsecond=0)
                    facade.shows.add(Show(movies[(si * 2 + slot + day - 1) % len(movies)], screen, start, price))
        pw = hash_password(DEMO_PASSWORD)
        facade.users.add(Customer("Asha", "asha@example.com", "9876500001", is_student=True), pw)
        facade.users.add(Customer("Rohan", "rohan@example.com", "9876500002"), pw)
        facade.users.add(Admin("Manager", "admin@orion.example"), pw)
