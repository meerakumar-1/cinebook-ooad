"""View side of the JSON API: domain objects -> plain dicts. No business logic here."""
from ..domain.models import BookingStatus, SeatType


def user_dto(u):
    return {"id": u.id, "name": u.name, "email": u.email, "role": u.role(),
            "phone": getattr(u, "phone", ""), "is_student": getattr(u, "is_student", False)}


def movie_dto(m):
    return {"id": m.id, "title": m.title, "duration_min": m.duration_min, "genre": m.genre,
            "language": m.language, "rating": m.rating, "synopsis": m.synopsis}


def show_dto(s, free=None):
    d = {"id": s.id, "movie": movie_dto(s.movie),
         "screen": {"id": s.screen.id, "name": s.screen.name, "capacity": s.screen.capacity},
         "start_time": s.start_time.isoformat(timespec="minutes"),
         "end_time": s.end_time.isoformat(timespec="minutes"), "base_price": s.base_price,
         "tiers": {t.name: round(s.base_price * t.multiplier, 2) for t in SeatType}}
    if free is not None:
        d["available_seats"] = free
    return d


def seat_dto(label, seat_type, available):
    return {"label": label, "row": label[0], "number": int(label[1:]), "type": seat_type, "available": available}


def booking_dto(b, payment=None, now=None):
    d = {"id": b.id, "status": b.status.name, "total_amount": b.total_amount,
         "created_at": b.created_at.isoformat(timespec="seconds"),
         "customer": {"id": b.customer.id, "name": b.customer.name, "email": b.customer.email},
         "show": show_dto(b.show),
         "tickets": [{"seat": t.seat.label, "type": t.seat.seat_type.name, "price": t.price, "code": t.code}
                     for t in b.tickets]}
    if payment:
        d["payment"] = {"method": payment.method, "status": payment.status, "txn_ref": payment.txn_ref}
    if b.status is BookingStatus.PENDING and b.expires_at and now:
        # remaining time is computed on the server, so the browser's clock/timezone never matters
        d["seconds_left"] = max(0, int((b.expires_at - now).total_seconds()))
    return d
