"""PATTERN (Structural): Facade - one simple entry point over repositories, pricing, payments and notifications.
Every public method holds the DB lock, so check-then-insert operations are atomic inside this process."""
from datetime import datetime, timedelta

from ..data.database import DatabaseManager, synchronized
from ..data.repositories import (BookingRepository, MovieRepository, ReportQueries, ShowRepository,
                                 TheatreRepository, UserRepository)
from ..domain.models import Booking, BookingStatus, Customer, Movie, Payment, Show, Ticket
from ..errors import (CineBookError, HoldExpiredError, InvalidStateTransition, PaymentFailedError, PermissionDenied,
                      ScheduleConflictError, SeatUnavailableError, ShowStartedError, ValidationError)
from ..patterns.observers import BookingEvent, BookingEventPublisher
from ..patterns.payments import get_creator
from ..patterns.pricing import select_pricing
from ..patterns.reports import REPORTS

MAX_SEATS_PER_BOOKING = 10
HOLD_MINUTES = 5                      # how long selected seats are reserved while the customer pays
TURNAROUND = timedelta(minutes=15)    # cleaning gap required between two shows on one screen


class BookingFacade:
    def __init__(self, db=None, clock=datetime.now, publisher=None, hold_minutes=HOLD_MINUTES):
        self._db = db or DatabaseManager.get_instance()
        self.clock = clock
        self.hold = timedelta(minutes=hold_minutes)
        self.publisher = publisher or BookingEventPublisher()
        self.movies = MovieRepository(self._db)
        self.theatres = TheatreRepository(self._db)
        self.shows = ShowRepository(self._db, self.movies, self.theatres)
        self.users = UserRepository(self._db)
        self.bookings = BookingRepository(self._db, self.users, self.shows, self.theatres)

    @property
    def db(self): return self._db

    # ================= internal helpers =================
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
                raise SeatUnavailableError(f"Seat {label} is already taken")
            seats.append(seat)
        return seats

    @staticmethod
    def _price(show, customer, seats):
        strategy = select_pricing(show, customer)
        return strategy, [Ticket(seat=s, price=strategy.price(show, s)) for s in seats]

    def _release(self, booking):
        """Drop a PENDING hold quietly (no notification): used for abandoned or replaced holds."""
        with self._db.transaction():
            booking.cancel()
            self.bookings.update_status(booking)

    def _expire_stale_holds(self):
        """Lazy expiry: any hold past its deadline becomes EXPIRED and its seats are free again."""
        for booking_id in self.bookings.pending_expired(self.clock()):
            booking = self.bookings.get(booking_id)
            with self._db.transaction():
                booking.expire()
                self.bookings.update_status(booking)
            self.publisher.notify(BookingEvent.EXPIRED, booking)

    def _own_booking(self, booking_id, requester_id, allow_admin=True):
        booking = self.bookings.get(booking_id)
        is_admin = allow_admin and self.users.get(requester_id).role() == "ADMIN"
        if booking.customer.id != requester_id and not is_admin:
            raise PermissionDenied("This booking belongs to another customer")
        return booking

    # ================= browsing =================
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
        self._expire_stale_holds()
        show = self.shows.get(show_id)
        return show.screen.capacity - len(self.bookings.booked_seat_ids(show_id)), show.screen.capacity

    @synchronized
    def seat_map(self, show_id):
        self._expire_stale_holds()
        show = self.shows.get(show_id)
        taken = self.bookings.booked_seat_ids(show_id)
        return [(s.label, s.seat_type.name, s.id not in taken) for s in show.screen.seats]

    @synchronized
    def booking_history(self, customer_id):
        self._expire_stale_holds()
        return self.bookings.for_customer(customer_id)

    @synchronized
    def get_booking(self, booking_id, requester_id):
        self._expire_stale_holds()
        return self._own_booking(booking_id, requester_id)

    @synchronized
    def payment_for(self, booking_id): return self.bookings.payment_for(booking_id)

    # ================= use case: book tickets (hold -> pay) =================
    @synchronized
    def quote(self, customer_id, show_id, seat_labels) -> dict:
        self._expire_stale_holds()
        customer, show = self._customer(customer_id), self._bookable_show(show_id)
        strategy, tickets = self._price(show, customer, self._pick_seats(show, seat_labels))
        return {"pricing": strategy.name,
                "seats": [{"label": t.seat.label, "type": t.seat.seat_type.name, "price": t.price} for t in tickets],
                "total": round(sum(t.price for t in tickets), 2)}

    @synchronized
    def hold_seats(self, customer_id, show_id, seat_labels) -> Booking:
        """Reserve seats for HOLD_MINUTES (booking = PENDING). A new hold replaces the customer's old hold on the show."""
        self._expire_stale_holds()
        customer, show = self._customer(customer_id), self._bookable_show(show_id)
        for old_id in self.bookings.pending_for(customer.id, show.id):
            self._release(self.bookings.get(old_id))
        _strategy, tickets = self._price(show, customer, self._pick_seats(show, seat_labels))
        now = self.clock()
        with self._db.transaction():
            return self.bookings.add(Booking(customer, show, tickets, created_at=now, expires_at=now + self.hold))

    @synchronized
    def pay_booking(self, booking_id, requester_id, method, details) -> Booking:
        self._expire_stale_holds()
        booking = self._own_booking(booking_id, requester_id, allow_admin=False)
        if booking.status is BookingStatus.EXPIRED:
            raise HoldExpiredError("Your seat hold expired. Please select your seats again.")
        if booking.status is not BookingStatus.PENDING:
            raise InvalidStateTransition(f"Booking is already {booking.status.name.lower()}")
        if booking.show.start_time <= self.clock():
            raise ShowStartedError("Show has already started")

        result = get_creator(method).process(booking.total_amount, details)  # unknown method -> ValidationError, nothing written
        with self._db.transaction():
            self.bookings.add_payment(Payment(booking.id, method.upper(), booking.total_amount,
                                              "SUCCESS" if result.success else "FAILED", result.txn_ref))
            if result.success:
                booking.confirm()
                self.bookings.update_status(booking)
        if not result.success:  # attempt is recorded; the hold stays so the customer can retry
            raise PaymentFailedError(result.message)
        self.publisher.notify(BookingEvent.CONFIRMED, booking)
        return booking

    @synchronized
    def book_tickets(self, customer_id, show_id, seat_labels, method, details) -> Booking:
        """One-shot convenience (console UI / API users): hold, then pay; release the hold if payment cannot complete."""
        booking = self.hold_seats(customer_id, show_id, seat_labels)
        try:
            return self.pay_booking(booking.id, customer_id, method, details)
        except CineBookError:
            self._release(booking)
            raise

    @synchronized
    def release_hold(self, booking_id, requester_id) -> Booking:
        """Customer leaves checkout: free the seats immediately, no notification."""
        booking = self._own_booking(booking_id, requester_id, allow_admin=False)
        if booking.status is BookingStatus.PENDING:
            self._release(booking)
        return booking

    # ================= use case: cancel booking =================
    @synchronized
    def cancel_booking(self, booking_id, requester_id) -> Booking:
        self._expire_stale_holds()
        booking = self._own_booking(booking_id, requester_id)
        if booking.show.start_time <= self.clock():
            raise ShowStartedError("Cannot cancel after the show has started")
        payment = self.bookings.payment_for(booking_id)
        paid = payment is not None and payment.status == "SUCCESS"
        with self._db.transaction():
            booking.cancel()  # raises InvalidStateTransition if already cancelled/expired
            self.bookings.update_status(booking)
            if paid:
                self.bookings.refund_payment(booking_id)
        self.publisher.notify(BookingEvent.CANCELLED, booking)
        return booking

    # ================= admin use cases =================
    @synchronized
    def generate_report(self, admin_id, kind: str) -> str:
        self._require_admin(admin_id)
        if kind not in REPORTS:
            raise ValidationError(f"Unknown report '{kind}' (choose: {', '.join(REPORTS)})")
        return REPORTS[kind](ReportQueries(self._db)).generate()

    @synchronized
    def dashboard(self, admin_id) -> dict:
        self._require_admin(admin_id)
        self._expire_stale_holds()
        q = ReportQueries(self._db)
        revenue, occupancy = q.revenue_by_movie(), q.occupancy_by_show()
        sold, capacity = sum(r[3] for r in occupancy), sum(r[2] for r in occupancy)
        return {"revenue": round(sum(r[2] for r in revenue), 2), "tickets_sold": sum(r[1] for r in revenue),
                "occupancy_pct": round(100 * sold / capacity, 1) if capacity else 0.0,
                "shows": len(occupancy), "bookings": q.booking_counts(),
                "revenue_by_movie": [{"title": r[0], "tickets": r[1], "revenue": r[2]} for r in revenue]}

    @synchronized
    def all_bookings(self, admin_id, limit=50):
        self._require_admin(admin_id)
        self._expire_stale_holds()
        return self.bookings.recent(limit)

    @synchronized
    def add_movie(self, admin_id, title, duration_min, genre, language, rating="UA", synopsis="") -> Movie:
        self._require_admin(admin_id)
        with self._db.transaction():
            return self.movies.add(Movie(title.strip(), duration_min, genre.strip(), language.strip(),
                                         rating.strip() or "UA", synopsis.strip()))

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
