"""Domain layer: entities and their behaviour. No SQL, no I/O here."""
from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum

from ..errors import InvalidStateTransition, ValidationError


class SeatType(Enum):
    REGULAR = 1.0
    PREMIUM = 1.5
    RECLINER = 2.0

    @property
    def multiplier(self) -> float:
        return self.value


class BookingStatus(Enum):
    PENDING = "PENDING"
    CONFIRMED = "CONFIRMED"
    CANCELLED = "CANCELLED"
    EXPIRED = "EXPIRED"


# ---------- value-like entities (frozen => immutable, safe to share) ----------
@dataclass(frozen=True)
class Movie:
    title: str
    duration_min: int
    genre: str
    language: str
    rating: str = "UA"
    id: int | None = None

    def __post_init__(self):
        if not self.title.strip():
            raise ValidationError("Movie title is required")
        if self.duration_min <= 0:
            raise ValidationError("Duration must be positive")


@dataclass(frozen=True)
class Seat:
    row: str
    number: int
    seat_type: SeatType = SeatType.REGULAR
    id: int | None = None
    screen_id: int | None = None

    @property
    def label(self) -> str:
        return f"{self.row}{self.number}"


# ---------- aggregation / composition ----------
@dataclass
class Screen:
    name: str
    seats: list[Seat] = field(default_factory=list)  # composition: seats die with screen
    id: int | None = None
    theatre_id: int | None = None

    @property
    def capacity(self) -> int:
        return len(self.seats)

    def seat_by_label(self, label: str) -> Seat:
        for s in self.seats:
            if s.label == label.upper():
                return s
        raise ValidationError(f"Seat {label} does not exist on {self.name}")


@dataclass
class Theatre:
    name: str
    city: str
    screens: list[Screen] = field(default_factory=list)  # composition
    id: int | None = None


@dataclass
class Show:
    movie: Movie  # aggregation: a Movie exists independently of its Shows
    screen: Screen
    start_time: datetime
    base_price: float
    id: int | None = None

    @property
    def end_time(self) -> datetime:
        return self.start_time + timedelta(minutes=self.movie.duration_min)


# ---------- generalization: User <- Customer / Admin ----------
class User:
    def __init__(self, name: str, email: str, id: int | None = None):
        if "@" not in email:
            raise ValidationError("Invalid email")
        self.id, self.name, self._email = id, name, email.strip().lower()

    @property
    def email(self) -> str:
        return self._email

    def role(self) -> str:  # overridden => polymorphism
        return "USER"


class Customer(User):
    def __init__(self, name, email, phone="", is_student=False, id=None):
        super().__init__(name, email, id)
        self.phone, self.is_student = phone, is_student

    def role(self) -> str:
        return "CUSTOMER"


class Admin(User):
    def role(self) -> str:
        return "ADMIN"


# ---------- booking aggregate ----------
@dataclass
class Ticket:
    seat: Seat
    price: float
    code: str = field(default_factory=lambda: uuid.uuid4().hex[:8].upper())
    id: int | None = None


@dataclass
class Payment:
    booking_id: int
    method: str
    amount: float
    status: str  # SUCCESS | FAILED | REFUNDED
    txn_ref: str
    id: int | None = None


class Booking:
    """Aggregate root. Status can only change through confirm/cancel/expire (information hiding)."""

    _ALLOWED = {
        BookingStatus.PENDING: {BookingStatus.CONFIRMED, BookingStatus.CANCELLED, BookingStatus.EXPIRED},
        BookingStatus.CONFIRMED: {BookingStatus.CANCELLED},
        BookingStatus.CANCELLED: set(),
        BookingStatus.EXPIRED: set(),
    }

    def __init__(self, customer: Customer, show: Show, tickets: list[Ticket],
                 status: BookingStatus = BookingStatus.PENDING,
                 created_at: datetime | None = None, id: int | None = None):
        self.customer, self.show, self.tickets, self.id = customer, show, tickets, id
        self.created_at = created_at or datetime.now()
        self._status = status

    @property
    def status(self) -> BookingStatus:
        return self._status

    @property
    def total_amount(self) -> float:
        return round(sum(t.price for t in self.tickets), 2)

    def confirm(self): self._move(BookingStatus.CONFIRMED)
    def cancel(self): self._move(BookingStatus.CANCELLED)
    def expire(self): self._move(BookingStatus.EXPIRED)

    def _move(self, new: BookingStatus):
        if new not in self._ALLOWED[self._status]:
            raise InvalidStateTransition(f"{self._status.name} -> {new.name} not allowed")
        self._status = new
