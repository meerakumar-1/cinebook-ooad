import unittest
from datetime import datetime, timedelta

try:
    import flask  # noqa: F401
    HAVE_FLASK = True
except ImportError:
    HAVE_FLASK = False

from cinebook.data.database import DatabaseManager
from cinebook.data.seed import DEMO_PASSWORD, seed_demo
from cinebook.services.booking_facade import BookingFacade

NOW = datetime(2026, 11, 12, 10, 0)


class Clock:
    def __init__(self): self.now = NOW
    def __call__(self): return self.now


@unittest.skipUnless(HAVE_FLASK, "Flask not installed")
class ApiTest(unittest.TestCase):
    def setUp(self):
        from cinebook.web.app import create_app
        DatabaseManager.reset_instance()
        self.clock = Clock()
        self.facade = BookingFacade(DatabaseManager.get_instance(":memory:"), clock=self.clock)
        seed_demo(self.facade, now=NOW)
        self.app = create_app(self.facade)
        self.c = self.app.test_client()
        self.upi = {"upi_id": "a@upi"}

    def tearDown(self): DatabaseManager.reset_instance()

    # helpers
    def login(self, email, password=DEMO_PASSWORD):
        r = self.c.post("/api/auth/login", json={"email": email, "password": password})
        return r, {"Authorization": f"Bearer {r.json.get('token')}"}

    def asha(self): return self.login("asha@example.com")[1]
    def rohan(self): return self.login("rohan@example.com")[1]
    def admin(self): return self.login("admin@orion.example")[1]

    def book(self, headers, seats, show_id=1, method="UPI", details=None):
        return self.c.post("/api/bookings", headers=headers,
                           json={"show_id": show_id, "seats": seats, "method": method, "details": details or self.upi})

    def hold(self, headers, seats, show_id=1):
        return self.c.post(f"/api/shows/{show_id}/hold", headers=headers, json={"seats": seats})

    def pay(self, headers, booking_id, method="UPI", details=None):
        return self.c.post(f"/api/bookings/{booking_id}/pay", headers=headers,
                           json={"method": method, "details": details or self.upi})

    # ---- auth ----
    def test_login_ok_and_bad_password(self):
        r, _ = self.login("asha@example.com")
        self.assertEqual((r.status_code, r.json["user"]["role"]), (200, "CUSTOMER"))
        self.assertEqual(self.login("asha@example.com", "wrong")[0].status_code, 401)
        self.assertEqual(self.login("nobody@example.com")[0].status_code, 401)

    def test_protected_routes_need_token(self):
        self.assertEqual(self.c.get("/api/bookings").status_code, 401)
        self.assertEqual(self.c.get("/api/bookings", headers={"Authorization": "Bearer fake"}).status_code, 401)

    def test_register_validation_and_login(self):
        ok = self.c.post("/api/auth/register", json={"name": "Neha", "email": "Neha@Example.com", "password": "longenough"})
        self.assertEqual(ok.status_code, 201)
        self.assertEqual(self.login("neha@example.com", "longenough")[0].status_code, 200)
        dup = self.c.post("/api/auth/register", json={"name": "N", "email": "neha@example.com", "password": "longenough"})
        short = self.c.post("/api/auth/register", json={"name": "N", "email": "x@y.com", "password": "short"})
        self.assertEqual((dup.status_code, short.status_code), (400, 400))

    def test_logout_invalidates_token(self):
        h = self.asha()
        self.assertEqual(self.c.post("/api/auth/logout", headers=h).status_code, 200)
        self.assertEqual(self.c.get("/api/me", headers=h).status_code, 401)

    def test_session_survives_restart_and_expires(self):
        from cinebook.web.app import create_app
        h = self.asha()
        restarted = create_app(self.facade).test_client()  # new app object, same database
        self.assertEqual(restarted.get("/api/me", headers=h).status_code, 200)
        self.clock.now = NOW + timedelta(hours=13)
        self.assertEqual(restarted.get("/api/me", headers=h).status_code, 401)

    def test_login_lockout_after_repeated_failures(self):
        for _ in range(5):
            self.assertEqual(self.login("asha@example.com", "wrong")[0].status_code, 401)
        self.assertEqual(self.login("asha@example.com")[0].status_code, 429)  # even the right password is refused
        self.clock.now = NOW + timedelta(minutes=11)
        self.assertEqual(self.login("asha@example.com")[0].status_code, 200)

    # ---- browsing ----
    def test_public_browsing(self):
        movies = self.c.get("/api/movies").json
        self.assertEqual(len(movies), 6)
        self.assertTrue(all(m["synopsis"] for m in movies))
        shows = self.c.get("/api/movies/1/shows").json
        self.assertGreaterEqual(len(shows), 3)
        self.assertEqual(shows[0]["available_seats"], 40)
        self.assertEqual(shows[0]["tiers"]["PREMIUM"], 375.0)
        self.assertEqual(len(self.c.get("/api/shows/1/seats").json["seats"]), 40)
        self.assertEqual(self.c.get("/api/movies/99/shows").status_code, 404)

    # ---- booking flow ----
    def test_quote_and_one_shot_book(self):
        h = self.asha()
        q = self.c.post("/api/shows/1/quote", headers=h, json={"seats": ["C1", "C2"]}).json
        self.assertEqual((q["total"], q["pricing"]), (637.5, "Student (-15%)"))
        r = self.book(h, ["C1", "C2"])
        self.assertEqual((r.status_code, r.json["status"], r.json["total_amount"]), (201, "CONFIRMED", 637.5))
        self.assertEqual(r.json["payment"]["status"], "SUCCESS")
        self.assertEqual(self.c.get("/api/shows/1/seats").json["show"]["available_seats"], 38)

    def test_hold_pay_flow_with_countdown(self):
        h = self.asha()
        r = self.hold(h, ["A1", "A2"])
        self.assertEqual((r.status_code, r.json["status"], r.json["seconds_left"]), (201, "PENDING", 300))
        self.assertEqual(self.hold(self.rohan(), ["A1"]).status_code, 409)  # held by Asha
        self.clock.now = NOW + timedelta(seconds=90)
        self.assertEqual(self.c.get(f"/api/bookings/{r.json['id']}", headers=h).json["seconds_left"], 210)
        paid = self.pay(h, r.json["id"])
        self.assertEqual((paid.status_code, paid.json["status"]), (200, "CONFIRMED"))
        self.assertNotIn("seconds_left", paid.json)

    def test_hold_expiry_over_http(self):
        h = self.asha()
        bid = self.hold(h, ["A1"]).json["id"]
        self.clock.now = NOW + timedelta(minutes=6)
        self.assertEqual(self.pay(h, bid).status_code, 410)
        self.assertEqual(self.hold(self.rohan(), ["A1"]).status_code, 201)

    def test_failed_payment_allows_retry_then_release(self):
        h = self.rohan()
        bid = self.hold(h, ["B1"]).json["id"]
        bad = self.pay(h, bid, "CARD", {"card_number": "1", "cvv": "1"})
        self.assertEqual(bad.status_code, 402)
        self.assertEqual(self.pay(h, bid).status_code, 200)  # retry with UPI works
        other = self.hold(h, ["B2"]).json["id"]
        rel = self.c.post(f"/api/bookings/{other}/release", headers=h)
        self.assertEqual(rel.json["status"], "CANCELLED")
        self.assertEqual(len(self.c.get("/api/bookings", headers=h).json), 1)  # abandoned hold hidden

    def test_cannot_pay_for_someone_else(self):
        bid = self.hold(self.asha(), ["A1"]).json["id"]
        self.assertEqual(self.pay(self.rohan(), bid).status_code, 403)
        self.assertEqual(self.c.get(f"/api/bookings/{bid}", headers=self.rohan()).status_code, 403)

    def test_double_booking_409_and_failed_one_shot_releases(self):
        self.assertEqual(self.book(self.asha(), ["A1"]).status_code, 201)
        self.assertEqual(self.book(self.rohan(), ["A1"]).status_code, 409)
        bad = self.book(self.rohan(), ["A2"], method="CARD", details={"card_number": "1", "cvv": "1"})
        self.assertEqual(bad.status_code, 402)
        self.assertEqual(self.book(self.rohan(), ["A2"]).status_code, 201)  # seat was released

    def test_bad_input_400(self):
        h = self.asha()
        self.assertEqual(self.c.post("/api/bookings", headers=h, json={"show_id": 1}).status_code, 400)
        self.assertEqual(self.book(h, ["Z9"]).status_code, 400)
        self.assertEqual(self.book(h, ["A1"], method="CASH").status_code, 400)
        self.assertEqual(self.book(h, ["A1"]).status_code, 201)  # the CASH attempt left no stuck hold

    def test_cancel_rules(self):
        booking_id = self.book(self.asha(), ["B1"]).json["id"]
        self.assertEqual(self.c.post(f"/api/bookings/{booking_id}/cancel", headers=self.rohan()).status_code, 403)
        ok = self.c.post(f"/api/bookings/{booking_id}/cancel", headers=self.asha())
        self.assertEqual((ok.status_code, ok.json["status"], ok.json["payment"]["status"]), (200, "CANCELLED", "REFUNDED"))
        self.assertEqual(self.c.post(f"/api/bookings/{booking_id}/cancel", headers=self.asha()).status_code, 409)

    def test_history_and_persistent_notifications(self):
        h = self.asha()
        bid = self.book(h, ["B2"]).json["id"]
        self.c.post(f"/api/bookings/{bid}/cancel", headers=h)
        notes = self.c.get("/api/notifications", headers=h).json
        self.assertEqual([n["event"] for n in notes], ["CANCELLED", "CONFIRMED"])
        self.assertEqual(self.c.get("/api/notifications", headers=self.rohan()).json, [])
        from cinebook.web.app import create_app  # notifications live in the DB, not in memory
        again = create_app(self.facade).test_client()
        self.assertEqual(len(again.get("/api/notifications", headers=h).json), 2)

    def test_admin_cannot_book(self):
        self.assertEqual(self.book(self.admin(), ["A1"]).status_code, 403)

    # ---- admin ----
    def test_reports_stats_and_permissions(self):
        self.book(self.rohan(), ["A1", "A2"])
        self.assertEqual(self.c.get("/api/admin/reports/revenue", headers=self.rohan()).status_code, 403)
        self.assertEqual(self.c.get("/api/admin/stats", headers=self.rohan()).status_code, 403)
        r = self.c.get("/api/admin/reports/revenue", headers=self.admin())
        self.assertIn("Total revenue: Rs.500.00", r.json["text"])
        self.assertEqual(self.c.get("/api/admin/reports/bogus", headers=self.admin()).status_code, 400)
        s = self.c.get("/api/admin/stats", headers=self.admin()).json
        self.assertEqual((s["revenue"], s["tickets_sold"], s["bookings"]["CONFIRMED"]), (500.0, 2, 1))
        self.assertEqual(s["revenue_by_movie"][0]["title"], "Interstellar Returns")

    def test_admin_booking_list_and_cancel_any(self):
        bid = self.book(self.rohan(), ["C1"]).json["id"]
        rows = self.c.get("/api/admin/bookings", headers=self.admin()).json
        self.assertEqual((rows[0]["id"], rows[0]["customer"]["name"]), (bid, "Rohan"))
        self.assertEqual(self.c.post(f"/api/bookings/{bid}/cancel", headers=self.admin()).json["status"], "CANCELLED")
        self.assertEqual(self.c.get("/api/admin/bookings", headers=self.rohan()).status_code, 403)

    def test_admin_add_movie_and_schedule(self):
        a = self.admin()
        m = self.c.post("/api/admin/movies", headers=a, json={"title": "New Film", "duration_min": 100, "genre": "Action",
                                                              "language": "English", "synopsis": "A new story."})
        self.assertEqual((m.status_code, m.json["synopsis"]), (201, "A new story."))
        self.assertEqual(self.c.post("/api/admin/movies", headers=self.rohan(), json={"title": "x", "duration_min": 1, "genre": "g", "language": "l"}).status_code, 403)
        base = {"movie_id": m.json["id"], "screen_id": 1, "base_price": 200}
        clash = self.c.post("/api/admin/shows", headers=a, json={**base, "start_time": "2026-11-13T13:00"})
        self.assertEqual(clash.status_code, 409)
        free = self.c.post("/api/admin/shows", headers=a, json={**base, "start_time": "2026-11-20T22:00"})
        self.assertEqual(free.status_code, 201)
        past = self.c.post("/api/admin/shows", headers=a, json={**base, "start_time": "2026-11-01T22:00"})
        self.assertEqual(past.status_code, 400)
        self.assertEqual(self.c.get("/api/admin/screens", headers=a).json[0]["capacity"], 40)
        long_title = self.c.post("/api/admin/movies", headers=a, json={"title": "x" * 500, "duration_min": 90, "genre": "g", "language": "l"})
        self.assertEqual(long_title.status_code, 400)

    # ---- misc ----
    def test_json_404_frontend_and_security_headers(self):
        r = self.c.get("/api/nope")
        self.assertEqual((r.status_code, "error" in r.json), (404, True))
        index = self.c.get("/")
        self.assertEqual(index.status_code, 200)
        self.assertIn("script-src 'self'", index.headers["Content-Security-Policy"])
        self.assertEqual(index.headers["X-Frame-Options"], "DENY")
        index.close()
        self.assertEqual(self.c.get("/api/movies").headers["Cache-Control"], "no-store")


if __name__ == "__main__":
    unittest.main()
