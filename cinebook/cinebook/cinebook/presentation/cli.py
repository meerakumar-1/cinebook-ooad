"""Presentation layer: console UI. Talks ONLY to BookingFacade."""
from ..errors import CineBookError
from ..patterns.observers import AuditLogger, EmailNotifier, SMSNotifier


def attach_default_observers(facade):
    email, sms, audit = EmailNotifier(), SMSNotifier(), AuditLogger()
    for o in (email, sms, audit):
        facade.publisher.subscribe(o)
    return email, sms, audit


def show_seat_map(facade, show_id):
    rows = {}
    for label, _t, free in facade.seat_map(show_id):
        rows.setdefault(label[0], []).append(f"{label}{'' if free else '*'}".ljust(4))
    print("  (* = taken)")
    for r, cells in rows.items():
        print("  " + " ".join(cells))


def run_demo(facade):
    email, sms, audit = attach_default_observers(facade)
    print("== Movies ==")
    for m in facade.list_movies():
        print(f"  {m.id}. {m.title} [{m.genre}, {m.language}, {m.duration_min} min]")
    movie = facade.list_movies()[0]
    show = facade.list_shows(movie.id)[0]
    print(f"\n== Seat map for show #{show.id} ({movie.title}, {show.start_time:%a %d %b %H:%M}) ==")
    show_seat_map(facade, show.id)

    print("\n== Asha (student) books C1,C2 by UPI ==")
    b1 = facade.book_tickets(1, show.id, ["C1", "C2"], "UPI", {"upi_id": "asha@upi"})
    print(f"  Booking #{b1.id} {b1.status.name}, total Rs.{b1.total_amount}")

    print("\n== Rohan tries a taken seat (C1) ==")
    try:
        facade.book_tickets(2, show.id, ["C1"], "UPI", {"upi_id": "rohan@upi"})
    except CineBookError as e:
        print(f"  Rejected: {e}")

    print("\n== Rohan pays with an invalid card ==")
    try:
        facade.book_tickets(2, show.id, ["D1"], "CARD", {"card_number": "123", "cvv": "12"})
    except CineBookError as e:
        print(f"  Rejected: {e}")

    print("\n== Rohan books D1 with wallet, then cancels ==")
    b2 = facade.book_tickets(2, show.id, ["D1"], "WALLET", {"balance": 1000})
    print(f"  Booking #{b2.id} {b2.status.name}, total Rs.{b2.total_amount}")
    b2 = facade.cancel_booking(b2.id)
    print(f"  Booking #{b2.id} now {b2.status.name}")

    print("\n== Notifications (Observer) ==")
    for line in email.outbox + sms.sent:
        print("  " + line)

    print("\n== Admin reports (Template Method) ==")
    print(facade.generate_report(3, "revenue"))
    print()
    print(facade.generate_report(3, "occupancy"))


def interactive(facade):
    attach_default_observers(facade)
    uid = int(input("Login as user id (1,2 = customers, 3 = admin): "))
    user = facade.users.get(uid)
    print(f"Welcome {user.name} ({user.role()})")
    menu = "\n1 Movies  2 Shows  3 Seat map  4 Book  5 My bookings  6 Cancel  7 Report  0 Exit"
    while True:
        print(menu)
        try:
            c = input("> ").strip()
            if c == "0": return
            elif c == "1":
                for m in facade.list_movies(): print(f"  {m.id}. {m.title} ({m.language}, {m.duration_min} min)")
            elif c == "2":
                for s in facade.list_shows(int(input("movie id: "))):
                    print(f"  show {s.id}: {s.start_time:%a %d %b %H:%M} {s.screen.name} base Rs.{s.base_price}")
            elif c == "3": show_seat_map(facade, int(input("show id: ")))
            elif c == "4":
                sid = int(input("show id: "))
                seats = input("seats (e.g. A1,A2): ").replace(" ", "").split(",")
                method = input("method (UPI/CARD/WALLET): ")
                details = {"UPI": lambda: {"upi_id": input("upi id: ")},
                           "CARD": lambda: {"card_number": input("card no: "), "cvv": input("cvv: ")},
                           "WALLET": lambda: {"balance": float(input("wallet balance: "))}}[method.upper()]()
                b = facade.book_tickets(uid, sid, seats, method, details)
                print(f"  Booked #{b.id}, total Rs.{b.total_amount}")
            elif c == "5":
                for b in facade.booking_history(uid):
                    print(f"  #{b.id} {b.show.movie.title} {[t.seat.label for t in b.tickets]} {b.status.name} Rs.{b.total_amount}")
            elif c == "6": facade.cancel_booking(int(input("booking id: "))); print("  Cancelled")
            elif c == "7": print(facade.generate_report(uid, input("revenue/occupancy: ")))
        except (CineBookError, ValueError, KeyError) as e:
            print(f"  ! {e}")
