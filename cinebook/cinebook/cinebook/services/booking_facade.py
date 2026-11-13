"""PATTERN (Structural): Facade - one simple entry point over repositories, pricing, payments and notifications."""
from datetime import datetime

from ..data.database import DatabaseManager
from ..data.repositories import (BookingRepository, MovieRepository, ReportQueries, ShowRepository,
                                 TheatreRepository, UserRepository)
from ..domain.models import Booking, Customer, Payment, Ticket
from ..errors import (PaymentFailedError, PermissionDenied, SeatUnavailableError, ShowStartedError, ValidationError)
from ..patterns.observers import BookingEvent, BookingEventPublisher
from ..patterns.payments import get_creator
from ..patterns.pricing import select_pricing
from ..patterns.reports import REPORTS

MAX_SEATS_PER_BOOKING = 10


class BookingFacade:
    def __init__(self, db=None, clock=datetime.now, publisher=None):
        self._db = db or DatabaseManager.get_instance()
        self._clock = clock
        self.publisher = publisher or BookingEventPublisher()
        self.movies = MovieRepository(self._db)
        self.theatres = TheatreRepository(self._db)
        self.shows = ShowRepository(self._db, self.movies, self.theatres)
        self.users = UserRepository(self._db)
        self.bookings = BookingRepository(self._db, self.users, self.shows, self.theatres)

    # ---- browsing ----
    def list_movies(self): return self.movies.all()
    def list_shows(self, movie_id): return [s for s in self.shows.by_movie(movie_id) if s.start_time > self._clock()]

    def seat_map(self, show_id):
        show = self.shows.get(show_id)
        taken = self.bookings.booked_seat_ids(show_id)
        return [(s.label, s.seat_type.name, s.id not in taken) for s in show.screen.seats]

    def booking_history(self, customer_id): return self.bookings.for_customer(customer_id)

    # ---- use case: book tickets ----
    def book_tickets(self, customer_id, show_id, seat_labels, method, details) -> Booking:
        customer = self.users.get(customer_id)
        if not isinstance(customer, Customer):
            raise PermissionDenied("Only customers can book tickets")
        show = self.shows.get(show_id)
        if show.start_time <= self._clock():
            raise ShowStartedError("Show has already started")
        labels = list(dict.fromkeys(l.upper() for l in seat_labels))
        if not labels or len(labels) > MAX_SEATS_PER_BOOKING:
            raise ValidationError(f"Choose between 1 and {MAX_SEATS_PER_BOOKING} seats")

        taken = self.bookings.booked_seat_ids(show.id)
        seats = []
        for label in labels:
            seat = show.screen.seat_by_label(label)
            if seat.id in taken:
                raise SeatUnavailableError(f"Seat {label} is already booked")
            seats.append(seat)

        strategy = select_pricing(show, customer)
        tickets = [Ticket(seat=s, price=strategy.price(show, s)) for s in seats]

        with self._db.transaction():
            booking = self.bookings.add(Booking(customer, show, tickets, created_at=self._clock()))
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
    def cancel_booking(self, booking_id) -> Booking:
        booking = self.bookings.get(booking_id)
        if booking.show.start_time <= self._clock():
            raise ShowStartedError("Cannot cancel after the show has started")
        paid = self.bookings.payment_for(booking_id).status == "SUCCESS"
        with self._db.transaction():
            booking.cancel()  # raises InvalidStateTransition if already cancelled/expired
            self.bookings.update_status(booking)
            if paid:
                self.bookings.set_payment_status(booking_id, "REFUNDED")
        self.publisher.notify(BookingEvent.CANCELLED, booking)
        return booking

    # ---- use case: admin reports ----
    def generate_report(self, admin_id, kind: str) -> str:
        if self.users.get(admin_id).role() != "ADMIN":
            raise PermissionDenied("Admin access required")
        if kind not in REPORTS:
            raise ValidationError(f"Unknown report '{kind}' (choose: {', '.join(REPORTS)})")
        return REPORTS[kind](ReportQueries(self._db)).generate()
