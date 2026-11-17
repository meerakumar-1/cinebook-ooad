"""Data-access layer. Repositories never commit; the caller wraps writes in db.transaction()."""
from dataclasses import replace
from datetime import datetime

from ..domain.models import (Admin, Booking, BookingStatus, Customer, Movie, Payment,
                             Screen, Seat, SeatType, Show, Theatre, Ticket)
from ..errors import NotFoundError


def _one(row, what):
    if row is None:
        raise NotFoundError(what)
    return row


def _iso(dt):
    return dt.isoformat(timespec="seconds") if dt else None


class MovieRepository:
    def __init__(self, db): self._db = db

    def add(self, m: Movie) -> Movie:
        cur = self._db.connection.execute(
            "INSERT INTO movies(title,duration_min,genre,language,rating,synopsis) VALUES(?,?,?,?,?,?)",
            (m.title, m.duration_min, m.genre, m.language, m.rating, m.synopsis))
        return replace(m, id=cur.lastrowid)

    @staticmethod
    def _to_movie(r):
        return Movie(title=r["title"], duration_min=r["duration_min"], genre=r["genre"], language=r["language"],
                     rating=r["rating"], synopsis=r["synopsis"], id=r["id"])

    def get(self, movie_id: int) -> Movie:
        r = self._db.connection.execute("SELECT * FROM movies WHERE id=?", (movie_id,)).fetchone()
        return self._to_movie(_one(r, f"Movie {movie_id}"))

    def all(self) -> list[Movie]:
        return [self._to_movie(r) for r in self._db.connection.execute("SELECT * FROM movies ORDER BY title")]


class TheatreRepository:
    def __init__(self, db): self._db = db

    def add(self, theatre: Theatre) -> Theatre:
        c = self._db.connection
        theatre.id = c.execute("INSERT INTO theatres(name,city) VALUES(?,?)", (theatre.name, theatre.city)).lastrowid
        for screen in theatre.screens:  # composition => cascade save
            screen.id = c.execute("INSERT INTO screens(theatre_id,name) VALUES(?,?)", (theatre.id, screen.name)).lastrowid
            screen.theatre_id, saved = theatre.id, []
            for s in screen.seats:
                sid = c.execute("INSERT INTO seats(screen_id,row_label,number,seat_type) VALUES(?,?,?,?)",
                                (screen.id, s.row, s.number, s.seat_type.name)).lastrowid
                saved.append(replace(s, id=sid, screen_id=screen.id))
            screen.seats = saved
        return theatre

    @staticmethod
    def _to_seat(r): return Seat(r["row_label"], r["number"], SeatType[r["seat_type"]], r["id"], r["screen_id"])

    def get_screen(self, screen_id: int) -> Screen:
        c = self._db.connection
        r = _one(c.execute("SELECT * FROM screens WHERE id=?", (screen_id,)).fetchone(), f"Screen {screen_id}")
        seats = [self._to_seat(s) for s in c.execute(
            "SELECT * FROM seats WHERE screen_id=? ORDER BY row_label, number", (screen_id,))]
        return Screen(r["name"], seats, r["id"], r["theatre_id"])

    def list_screens(self):
        rows = self._db.connection.execute(
            "SELECT s.id AS id, t.name AS theatre FROM screens s JOIN theatres t ON t.id=s.theatre_id "
            "ORDER BY t.name, s.name").fetchall()
        return [(self.get_screen(r["id"]), r["theatre"]) for r in rows]

    def get_seat(self, seat_id: int) -> Seat:
        r = self._db.connection.execute("SELECT * FROM seats WHERE id=?", (seat_id,)).fetchone()
        return self._to_seat(_one(r, f"Seat {seat_id}"))


class ShowRepository:
    def __init__(self, db, movies: MovieRepository, theatres: TheatreRepository):
        self._db, self._movies, self._theatres = db, movies, theatres

    def add(self, s: Show) -> Show:
        s.id = self._db.connection.execute(
            "INSERT INTO shows(movie_id,screen_id,start_time,base_price) VALUES(?,?,?,?)",
            (s.movie.id, s.screen.id, _iso(s.start_time), s.base_price)).lastrowid
        return s

    def _hydrate(self, r) -> Show:
        return Show(self._movies.get(r["movie_id"]), self._theatres.get_screen(r["screen_id"]),
                    datetime.fromisoformat(r["start_time"]), r["base_price"], r["id"])

    def get(self, show_id: int) -> Show:
        r = self._db.connection.execute("SELECT * FROM shows WHERE id=?", (show_id,)).fetchone()
        return self._hydrate(_one(r, f"Show {show_id}"))

    def by_screen(self, screen_id: int) -> list[Show]:
        rows = self._db.connection.execute("SELECT * FROM shows WHERE screen_id=? ORDER BY start_time", (screen_id,))
        return [self._hydrate(r) for r in rows]

    def by_movie(self, movie_id: int) -> list[Show]:
        rows = self._db.connection.execute("SELECT * FROM shows WHERE movie_id=? ORDER BY start_time", (movie_id,))
        return [self._hydrate(r) for r in rows]


class UserRepository:
    def __init__(self, db): self._db = db

    def add(self, u, password_hash: str = ""):
        u.id = self._db.connection.execute(
            "INSERT INTO users(name,email,phone,role,is_student,password_hash) VALUES(?,?,?,?,?,?)",
            (u.name, u.email, getattr(u, "phone", ""), u.role(), int(getattr(u, "is_student", False)),
             password_hash)).lastrowid
        return u

    @staticmethod
    def _hydrate(r):
        if r["role"] == "ADMIN":
            return Admin(r["name"], r["email"], r["id"])
        return Customer(r["name"], r["email"], r["phone"], bool(r["is_student"]), r["id"])

    def get(self, user_id: int):
        r = _one(self._db.connection.execute("SELECT * FROM users WHERE id=?", (user_id,)).fetchone(), f"User {user_id}")
        return self._hydrate(r)

    def credentials_for(self, email: str):
        """Return (user, password_hash) for an email, or raise NotFoundError."""
        r = _one(self._db.connection.execute("SELECT * FROM users WHERE email=?", (email.strip().lower(),)).fetchone(),
                 "User")
        return self._hydrate(r), r["password_hash"]


class BookingRepository:
    def __init__(self, db, users: UserRepository, shows: ShowRepository, theatres: TheatreRepository):
        self._db, self._users, self._shows, self._theatres = db, users, shows, theatres

    def add(self, b: Booking) -> Booking:
        c = self._db.connection
        b.id = c.execute("INSERT INTO bookings(user_id,show_id,status,created_at,expires_at) VALUES(?,?,?,?,?)",
                         (b.customer.id, b.show.id, b.status.name, _iso(b.created_at), _iso(b.expires_at))).lastrowid
        for t in b.tickets:
            t.id = c.execute("INSERT INTO tickets(booking_id,seat_id,price,code) VALUES(?,?,?,?)",
                             (b.id, t.seat.id, t.price, t.code)).lastrowid
        return b

    def update_status(self, b: Booking):
        self._db.connection.execute("UPDATE bookings SET status=? WHERE id=?", (b.status.name, b.id))

    def get(self, booking_id: int) -> Booking:
        c = self._db.connection
        r = _one(c.execute("SELECT * FROM bookings WHERE id=?", (booking_id,)).fetchone(), f"Booking {booking_id}")
        tickets = [Ticket(self._theatres.get_seat(t["seat_id"]), t["price"], t["code"], t["id"])
                   for t in c.execute("SELECT * FROM tickets WHERE booking_id=? ORDER BY id", (booking_id,))]
        return Booking(self._users.get(r["user_id"]), self._shows.get(r["show_id"]), tickets,
                       BookingStatus[r["status"]], datetime.fromisoformat(r["created_at"]),
                       datetime.fromisoformat(r["expires_at"]) if r["expires_at"] else None, r["id"])

    def _ids(self, sql, params=()):
        return [r["id"] for r in self._db.connection.execute(sql, params)]

    def for_customer(self, user_id: int) -> list[Booking]:
        """A customer's bookings, hiding holds that were abandoned before any payment was made."""
        ids = self._ids(
            "SELECT b.id AS id FROM bookings b WHERE b.user_id=? AND (b.status IN ('CONFIRMED','PENDING') "
            "OR EXISTS (SELECT 1 FROM payments p WHERE p.booking_id=b.id AND p.status IN ('SUCCESS','REFUNDED'))) "
            "ORDER BY b.id", (user_id,))
        return [self.get(i) for i in ids]

    def recent(self, limit: int = 50) -> list[Booking]:
        return [self.get(i) for i in self._ids("SELECT id FROM bookings ORDER BY id DESC LIMIT ?", (limit,))]

    def pending_expired(self, now: datetime) -> list[int]:
        return self._ids("SELECT id FROM bookings WHERE status='PENDING' AND expires_at IS NOT NULL AND expires_at <= ?",
                         (_iso(now),))

    def pending_for(self, user_id: int, show_id: int) -> list[int]:
        return self._ids("SELECT id FROM bookings WHERE status='PENDING' AND user_id=? AND show_id=?", (user_id, show_id))

    def booked_seat_ids(self, show_id: int) -> set[int]:
        rows = self._db.connection.execute(
            "SELECT t.seat_id FROM tickets t JOIN bookings b ON b.id=t.booking_id "
            "WHERE b.show_id=? AND b.status IN ('PENDING','CONFIRMED')", (show_id,))
        return {r["seat_id"] for r in rows}

    # ---- payments (one row per attempt) ----
    def add_payment(self, p: Payment) -> Payment:
        p.id = self._db.connection.execute(
            "INSERT INTO payments(booking_id,method,amount,status,txn_ref) VALUES(?,?,?,?,?)",
            (p.booking_id, p.method, p.amount, p.status, p.txn_ref)).lastrowid
        return p

    def payment_for(self, booking_id: int) -> Payment | None:
        r = self._db.connection.execute("SELECT * FROM payments WHERE booking_id=? ORDER BY id DESC LIMIT 1",
                                        (booking_id,)).fetchone()
        return Payment(r["booking_id"], r["method"], r["amount"], r["status"], r["txn_ref"], r["id"]) if r else None

    def refund_payment(self, booking_id: int):
        self._db.connection.execute("UPDATE payments SET status='REFUNDED' WHERE booking_id=? AND status='SUCCESS'",
                                    (booking_id,))


class NotificationRepository:
    def __init__(self, db): self._db = db

    def add(self, user_id, booking_id, event, message, created_at):
        self._db.connection.execute(
            "INSERT INTO notifications(user_id,booking_id,event,message,created_at) VALUES(?,?,?,?,?)",
            (user_id, booking_id, event, message, _iso(created_at)))

    def for_user(self, user_id, limit=50):
        return [{"event": r["event"], "booking_id": r["booking_id"], "message": r["message"], "at": r["created_at"]}
                for r in self._db.connection.execute(
                    "SELECT * FROM notifications WHERE user_id=? ORDER BY id DESC LIMIT ?", (user_id, limit))]


class SessionRepository:
    def __init__(self, db): self._db = db

    def add(self, token_hash, user_id, expires_at):
        self._db.connection.execute("INSERT INTO sessions(token_hash,user_id,expires_at) VALUES(?,?,?)",
                                    (token_hash, user_id, _iso(expires_at)))

    def get(self, token_hash):
        r = self._db.connection.execute("SELECT * FROM sessions WHERE token_hash=?", (token_hash,)).fetchone()
        return (r["user_id"], datetime.fromisoformat(r["expires_at"])) if r else None

    def delete(self, token_hash):
        self._db.connection.execute("DELETE FROM sessions WHERE token_hash=?", (token_hash,))

    def purge_expired(self, now):
        self._db.connection.execute("DELETE FROM sessions WHERE expires_at <= ?", (_iso(now),))


class ReportQueries:
    """Read-only aggregate queries (used by report generators and the admin dashboard)."""
    def __init__(self, db): self._db = db

    def revenue_by_movie(self):
        return [tuple(r) for r in self._db.connection.execute(
            "SELECT m.title, COUNT(t.id), ROUND(SUM(t.price),2) FROM bookings b "
            "JOIN shows s ON s.id=b.show_id JOIN movies m ON m.id=s.movie_id JOIN tickets t ON t.booking_id=b.id "
            "WHERE b.status='CONFIRMED' GROUP BY m.id ORDER BY 3 DESC")]

    def occupancy_by_show(self):
        return [tuple(r) for r in self._db.connection.execute(
            "SELECT m.title, s.start_time, (SELECT COUNT(*) FROM seats WHERE screen_id=s.screen_id) AS cap, "
            "COUNT(t.id) AS sold FROM shows s JOIN movies m ON m.id=s.movie_id "
            "LEFT JOIN bookings b ON b.show_id=s.id AND b.status='CONFIRMED' "
            "LEFT JOIN tickets t ON t.booking_id=b.id GROUP BY s.id ORDER BY s.start_time")]

    def booking_counts(self) -> dict:
        counts = {s.name: 0 for s in BookingStatus}
        for r in self._db.connection.execute("SELECT status, COUNT(*) AS n FROM bookings GROUP BY status"):
            counts[r["status"]] = r["n"]
        return counts
