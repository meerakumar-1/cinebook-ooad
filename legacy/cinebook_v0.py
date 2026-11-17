"""BASELINE ("before") version: everything in one god class. Kept ONLY to show the refactoring.
Pitfalls on purpose: god class, public data, if/elif payment, duplicated pricing, no state rules."""
from datetime import datetime


class CinemaSystem:
    def __init__(self):
        self.movies, self.shows, self.users, self.bookings = [], [], [], []   # public data members
        self.seats_taken = {}                                                 # show_id -> set(labels)

    def book(self, user, show_id, seats, method, info):
        show = [s for s in self.shows if s["id"] == show_id][0]
        total = 0
        for s in seats:
            if s in self.seats_taken.setdefault(show_id, set()):
                print("taken"); return None
            price = show["price"]
            if s[0] == "C": price = price * 1.5                              # duplicated pricing logic
            if s[0] == "D": price = price * 2
            if user["student"]: price = price * 0.85
            elif datetime.fromisoformat(show["time"]).weekday() >= 5: price = price * 1.2
            total += price
        if method == "upi":                                                   # if/elif chain per payment type
            ok = "@" in info
        elif method == "card":
            ok = len(info) == 16
        elif method == "wallet":
            ok = info >= total
        else:
            ok = False
        if not ok:
            print("payment failed"); return None
        self.seats_taken[show_id].update(seats)
        b = {"id": len(self.bookings) + 1, "user": user, "show": show_id, "seats": seats, "status": "ok", "total": total}
        self.bookings.append(b)
        print("EMAIL sent to", user["email"])                                 # notification hard-wired
        return b

    def cancel(self, booking_id):
        for b in self.bookings:
            b["status"] = "cancelled"                                         # bug: cancels EVERY booking, no state check
            self.seats_taken[b["show"]] -= set(b["seats"])

    def revenue_report(self):                                                 # reporting mixed into same class
        return sum(b["total"] for b in self.bookings if b["status"] == "ok")
