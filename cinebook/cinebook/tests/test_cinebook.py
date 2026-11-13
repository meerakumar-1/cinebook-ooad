import unittest
from datetime import datetime

from cinebook.data.database import DatabaseManager
from cinebook.data.seed import seed_demo
from cinebook.domain.models import (Booking, BookingStatus, Customer, Movie, Screen, Seat, SeatType, Show)
from cinebook.errors import (InvalidStateTransition, PaymentFailedError, PermissionDenied, SeatUnavailableError,
                             ShowStartedError, ValidationError)
from cinebook.patterns.observers import EmailNotifier
from cinebook.patterns.payments import CardCreator, UPICreator, WalletCreator, get_creator
from cinebook.patterns.pricing import (StandardPricing, StudentDiscountPricing, WeekendPricing, select_pricing)
from cinebook.services.booking_facade import BookingFacade

NOW = datetime(2026, 11, 12, 10, 0)  # Thursday


class Base(unittest.TestCase):
    def setUp(self):
        DatabaseManager.reset_instance()
        self.f = BookingFacade(DatabaseManager.get_instance(":memory:"), clock=lambda: NOW)
        seed_demo(self.f, now=NOW)
        self.email = EmailNotifier()
        self.f.publisher.subscribe(self.email)
        self.show = self.f.list_shows(1)[0]
        self.upi = {"upi_id": "a@upi"}

    def tearDown(self): DatabaseManager.reset_instance()


class TestSingleton(unittest.TestCase):
    def test_same_instance(self):
        DatabaseManager.reset_instance()
        self.assertIs(DatabaseManager.get_instance(":memory:"), DatabaseManager.get_instance(":memory:"))
        DatabaseManager.reset_instance()


class TestDomain(unittest.TestCase):
    def _booking(self):
        screen = Screen("S", [Seat("A", 1)])
        show = Show(Movie("M", 100, "g", "en"), screen, NOW, 100)
        return Booking(Customer("c", "c@x.com"), show, [])

    def test_state_machine(self):
        b = self._booking(); b.confirm(); b.cancel()
        self.assertEqual(b.status, BookingStatus.CANCELLED)
        with self.assertRaises(InvalidStateTransition): b.confirm()

    def test_validation(self):
        with self.assertRaises(ValidationError): Movie("", 10, "g", "en")
        with self.assertRaises(ValidationError): Customer("x", "no-at-sign")


class TestPricing(Base):
    def test_strategies(self):
        s = Show(Movie("M", 100, "g", "en"), Screen("S"), datetime(2026, 11, 14, 18), 200)  # Saturday
        prem = Seat("C", 1, SeatType.PREMIUM)
        self.assertEqual(StandardPricing().price(s, prem), 300.0)
        self.assertEqual(WeekendPricing().price(s, prem), 360.0)
        self.assertEqual(StudentDiscountPricing().price(s, prem), 255.0)
        self.assertIsInstance(select_pricing(s, Customer("a", "a@x.com")), WeekendPricing)
        self.assertIsInstance(select_pricing(s, Customer("a", "a@x.com", is_student=True)), StudentDiscountPricing)


class TestPayments(unittest.TestCase):
    def test_factory(self):
        self.assertIsInstance(get_creator("upi"), UPICreator)
        self.assertIsInstance(get_creator("CARD"), CardCreator)
        self.assertIsInstance(get_creator("wallet"), WalletCreator)
        with self.assertRaises(ValidationError): get_creator("cash")

    def test_processors(self):
        self.assertTrue(get_creator("UPI").process(10, {"upi_id": "a@b"}).success)
        self.assertFalse(get_creator("UPI").process(10, {"upi_id": "ab"}).success)
        self.assertFalse(get_creator("WALLET").process(100, {"balance": 50}).success)


class TestBookingFlow(Base):
    def test_book_confirms_and_notifies(self):
        b = self.f.book_tickets(2, self.show.id, ["A1", "A2"], "UPI", self.upi)
        self.assertEqual(b.status, BookingStatus.CONFIRMED)
        self.assertEqual(b.total_amount, 500.0)
        self.assertEqual(len(self.email.outbox), 1)

    def test_double_booking_blocked(self):
        self.f.book_tickets(2, self.show.id, ["A1"], "UPI", self.upi)
        with self.assertRaises(SeatUnavailableError):
            self.f.book_tickets(1, self.show.id, ["A1"], "UPI", self.upi)

    def test_failed_payment_releases_seats(self):
        with self.assertRaises(PaymentFailedError):
            self.f.book_tickets(2, self.show.id, ["A1"], "UPI", {"upi_id": "bad"})
        self.assertTrue(dict((l, free) for l, _, free in self.f.seat_map(self.show.id))["A1"])
        self.f.book_tickets(2, self.show.id, ["A1"], "UPI", self.upi)  # now succeeds

    def test_cancel_refunds_and_frees_seat(self):
        b = self.f.book_tickets(2, self.show.id, ["B1"], "UPI", self.upi)
        self.f.cancel_booking(b.id, 2)
        self.assertEqual(self.f.bookings.payment_for(b.id).status, "REFUNDED")
        self.assertTrue(dict((l, free) for l, _, free in self.f.seat_map(self.show.id))["B1"])
        with self.assertRaises(InvalidStateTransition): self.f.cancel_booking(b.id, 2)

    def test_started_show_rejected(self):
        late = BookingFacade(self.f._db, clock=lambda: self.show.start_time)
        with self.assertRaises(ShowStartedError):
            late.book_tickets(2, self.show.id, ["A1"], "UPI", self.upi)

    def test_seat_limits_and_unknown_seat(self):
        with self.assertRaises(ValidationError): self.f.book_tickets(2, self.show.id, ["Z9"], "UPI", self.upi)
        with self.assertRaises(ValidationError): self.f.book_tickets(2, self.show.id, [], "UPI", self.upi)

    def test_admin_cannot_book(self):
        with self.assertRaises(PermissionDenied): self.f.book_tickets(3, self.show.id, ["A1"], "UPI", self.upi)


class TestReports(Base):
    def test_reports_and_permissions(self):
        self.f.book_tickets(2, self.show.id, ["A1", "A2"], "UPI", self.upi)
        self.assertIn("Total revenue: Rs.500.00", self.f.generate_report(3, "revenue"))
        self.assertIn("OCCUPANCY", self.f.generate_report(3, "occupancy"))
        with self.assertRaises(PermissionDenied): self.f.generate_report(2, "revenue")


if __name__ == "__main__":
    unittest.main()
