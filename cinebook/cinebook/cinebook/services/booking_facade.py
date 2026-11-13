"""PATTERN (Structural): Facade - one simple entry point over repositories, pricing, payments and notifications.
Every public method holds the DB lock, so seat check + insert is atomic inside this process."""
from datetime import datetime, timedelta

from ..data.database import DatabaseManager, synchronized
from ..data.repositories import (BookingRepository, MovieRepository, ReportQueries, ShowRepository,
                                 TheatreRepository, UserRepository)
from ..domain.models import Booking, Customer, Movie, Payment, Show, Ticket
from ..errors import (PaymentFailedError, PermissionDenied, ScheduleConflictError, SeatUnavailableError,
                      ShowStartedError, ValidationError)
from ..patterns.observers import BookingEvent, BookingEventPublisher
from ..patterns.payments import get_creator
from ..patterns.pricing import select_pricing
from ..patterns.reports import REPORTS

MAX_SEATS_PER_BOOKING = 10
TURNAROUND = timedelta(minutes=15)  # cleaning gap required between two shows on one screen


class BookingFacade:
    def __init__(self, db=None, clock=datetime.now, publisher=None):
        self._db = db or DatabaseManager.get_instance()
        self.clock = clock
        self.publisher = publisher or BookingEventPublisher()
        self.movies = MovieRepository(self._db)
        self.theatres = TheatreRepository(self._db)
        self.shows = ShowRepository(self._db, self.movies, self.theatres)
        self.users = UserRepository(self._db)
        self.bookings = BookingRepository(self._db, self.users, self.shows, self.theatres)

    @property
    def db(self): return self._db

    # ---- internal helpers ----
    def _require_admin(self, user_id):
        if self.users.get(user_id).role() != "ADMIN":
            raise PermissionDenied("Admin access required")

    def _customer(self, customer_id):
        customer = self.users.get(customer_id)
        if not isinstance(customer, Customer):
            raise PermissionDenied("Only customers can book tickets")
        return customer

    def _bookable_show(self, show_id):
        show = self.shows.get(show_id)
        if show.start_time <= self.clock():
            raise ShowStartedError("Show has already started")
        return show

    def _pick_seats(self, show, labels):
        labels = list(dict.fromkeys(str(l).strip().upper() for l in labels))
        if not labels or len(labels) > MAX_SEATS_PER_BOOKING:
            raise ValidationError(f"Choose between 1 and {MAX_SEATS_PER_BOOKING} seats")
        taken = self.bookings.booked_seat_ids(show.id)
        seats = []
        for label in labels:
            seat = show.screen.seat_by_label(label)
            if seat.id in taken:
                raise SeatUnavailableError(f"Seat {label} is already booked")
            seats.append(seat)
        return seats

    @staticmethod
    def _price(show, customer, seats):
        strategy = select_pricing(show, customer)
        return strategy, [Ticket(seat=s, price=strategy.price(show, s)) for s in seats]

    # ---- browsing ----
    @synchronized
    def list_movies(self): return self.movies.all()

    @synchronized
    def list_shows(self, movie_id):
        self.movies.get(movie_id)  # NotFoundError for unknown movie
        return [s for s in self.shows.by_movie(movie_id) if s.start_time > self.clock()]

    @synchronized
    def get_show(self, show_id): return self.shows.get(show_id)

    @synchronized
    def availability(self, show_id):
        show = self.shows.get(show_id)
        return show.screen.capacity - len(self.bookings.booked_seat_ids(show_id)), show.screen.capacity

    @synchronized
    def seat_map(self, show_id):
        show = self.shows.get(show_id)
        taken = self.bookings.booked_seat_ids(show_id)
        return [(s.label, s.seat_type.name, s.id not in taken) for s in show.screen.seats]

    @synchronized
    def booking_history(self, customer_id): return self.bookings.for_customer(customer_id)

    @synchronized
    def payment_for(self, booking_id): return self.bookings.payment_for(booking_id)

    # ---- price preview ----
    @synchronized
    def quote(self, customer_id, show_id, seat_labels) -> dict:
        customer, show = self._customer(customer_id), self._bookable_show(show_id)
        strategy, tickets = self._price(show, customer, self._pick_seats(show, seat_labels))
        return {"pricing": strategy.name,
                "seats": [{"label": t.seat.label, "type": t.seat.seat_type.name, "price": t.price} for t in tickets],
                "total": round(sum(t.price for t in tickets), 2)}

    # ---- use case: book tickets ----
    @synchronized
    def book_tickets(self, customer_id, show_id, seat_labels, method, details) -> Booking:
        customer, show = self._customer(customer_id), self._bookable_show(show_id)
        _strategy, tickets = self._price(show, customer, self._pick_seats(show, seat_labels))

        with self._db.transaction():
            booking = self.bookings.add(Booking(customer, show, tickets, created_at=self.clock()))
            result = get_creator(method).process(booking.total_amount, details)
            self.bookings.add_payment(Payment(booking.id, method.upper(), booking.total_amount,
                                              "SUCCESS" if result.success else "FAILED", result.txn_ref))
            booking.confirm() if result.success else booking.cancel()
            self.bookings.update_status(booking)

        if not result.success:  # failed attempt is stored (audit) but seats are released
            raise PaymentFailedError(result.message)
        self.publisher.notify(BookingEvent.CONFIRMED, booking)
        return booking

    # ---- use case: cancel booking ----
    @synchronized
    def cancel_booking(self, booking_id, requester_id) -> Booking:
        booking = self.bookings.get(booking_id)
        if self.users.get(requester_id).role() != "ADMIN" and booking.customer.id != requester_id:
            raise PermissionDenied("You can only cancel your own bookings")
        if booking.show.start_time <= self.clock():
            raise ShowStartedError("Cannot cancel after the show has started")
        paid = self.bookings.payment_for(booking_id).status == "SUCCESS"
        with self._db.transaction():
            booking.cancel()  # raises InvalidStateTransition if already cancelled/expired
            self.bookings.update_status(booking)
            if paid:
                self.bookings.set_payment_status(booking_id, "REFUNDED")
        self.publisher.notify(BookingEvent.CANCELLED, booking)
        return booking

    # ---- admin use cases ----
    @synchronized
    def generate_report(self, admin_id, kind: str) -> str:
        self._require_admin(admin_id)
        if kind not in REPORTS:
            raise ValidationError(f"Unknown report '{kind}' (choose: {', '.join(REPORTS)})")
        return REPORTS[kind](ReportQueries(self._db)).generate()

    @synchronized
    def add_movie(self, admin_id, title, duration_min, genre, language, rating="UA") -> Movie:
        self._require_admin(admin_id)
        with self._db.transaction():
            return self.movies.add(Movie(title.strip(), duration_min, genre.strip(), language.strip(), rating.strip() or "UA"))

    @synchronized
    def list_screens(self, admin_id):
        self._require_admin(admin_id)
        return self.theatres.list_screens()

    @synchronized
    def schedule_show(self, admin_id, movie_id, screen_id, start_time: datetime, base_price: float) -> Show:
        self._require_admin(admin_id)
        movie, screen = self.movies.get(movie_id), self.theatres.get_screen(screen_id)
        if start_time <= self.clock():
            raise ValidationError("Show must start in the future")
        if base_price <= 0:
            raise ValidationError("Base price must be positive")
        end = start_time + timedelta(minutes=movie.duration_min)
        for other in self.shows.by_screen(screen_id):
            if start_time < other.end_time + TURNAROUND and other.start_time < end + TURNAROUND:
                raise ScheduleConflictError(
                    f"{screen.name} is busy ({other.movie.title}, {other.start_time:%d %b %H:%M}-{other.end_time:%H:%M})")
        with self._db.transaction():
            return self.shows.add(Show(movie, screen, start_time, float(base_price)))
