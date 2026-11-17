"""PATTERN (Behavioral): Observer - booking events fan out to notifiers without coupling the facade to them."""
import logging
from datetime import datetime
from abc import ABC, abstractmethod
from enum import Enum

log = logging.getLogger("cinebook")


class BookingEvent(Enum):
    CONFIRMED = "CONFIRMED"
    CANCELLED = "CANCELLED"
    EXPIRED = "EXPIRED"


class BookingObserver(ABC):
    @abstractmethod
    def update(self, event: BookingEvent, booking) -> None: ...


class BookingEventPublisher:  # the Subject
    def __init__(self): self._observers: list[BookingObserver] = []
    def subscribe(self, o: BookingObserver): self._observers.append(o)
    def unsubscribe(self, o: BookingObserver): self._observers.remove(o)

    def notify(self, event: BookingEvent, booking) -> None:
        for o in list(self._observers):
            o.update(event, booking)


class EmailNotifier(BookingObserver):
    def __init__(self): self.outbox: list[str] = []
    def update(self, event, booking):
        seats = ", ".join(t.seat.label for t in booking.tickets)
        msg = f"[EMAIL to {booking.customer.email}] Booking #{booking.id} {event.value}: {booking.show.movie.title}, seats {seats}"
        self.outbox.append(msg); log.info(msg)


class SMSNotifier(BookingObserver):
    def __init__(self): self.sent: list[str] = []
    def update(self, event, booking):
        if not booking.customer.phone:
            return
        msg = f"[SMS to {booking.customer.phone}] Booking #{booking.id} {event.value}"
        self.sent.append(msg); log.info(msg)


class AuditLogger(BookingObserver):
    def __init__(self): self.entries: list[str] = []
    def update(self, event, booking):
        self.entries.append(f"booking={booking.id} event={event.value} total={booking.total_amount}")


class InAppNotifier(BookingObserver):
    """Stores a per-customer notification feed in the database (survives restarts); the web UI reads it."""
    TEXT = {BookingEvent.CONFIRMED: "confirmed", BookingEvent.CANCELLED: "cancelled"}

    def __init__(self, db, repository, clock=datetime.now):
        self._db, self._repo, self._clock = db, repository, clock

    def update(self, event, booking):
        if event not in self.TEXT:  # expired holds are not worth a customer notification
            return
        seats = ", ".join(t.seat.label for t in booking.tickets)
        message = f"Booking #{booking.id} {self.TEXT[event]}: {booking.show.movie.title} (seats {seats})"
        with self._db.transaction():
            self._repo.add(booking.customer.id, booking.id, event.value, message, self._clock())

    def for_user(self, user_id: int) -> list[dict]:
        with self._db.lock:
            return self._repo.for_user(user_id)
