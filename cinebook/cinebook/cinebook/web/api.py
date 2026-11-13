"""Controller layer: HTTP/JSON <-> BookingFacade / AuthService. No business rules live here."""
from datetime import datetime

from flask import Blueprint, current_app, jsonify, request

from ..errors import AuthenticationRequired, ValidationError
from .serializers import booking_dto, movie_dto, seat_dto, show_dto, user_dto

bp = Blueprint("api", __name__, url_prefix="/api")


# ---------- helpers ----------
def _ctx(): return current_app.extensions["cinebook"]


def _token():
    header = request.headers.get("Authorization", "")
    if not header.startswith("Bearer "):
        raise AuthenticationRequired("Please sign in")
    return header[7:]


def _user(): return _ctx().auth.user_for_token(_token())


def _body(*required):
    data = request.get_json(silent=True)
    if not isinstance(data, dict):
        raise ValidationError("A JSON object body is required")
    missing = [k for k in required if k not in data or data[k] in (None, "")]
    if missing:
        raise ValidationError("Missing field(s): " + ", ".join(missing))
    return data


def _num(value, name, cast=int):
    try:
        return cast(value)
    except (TypeError, ValueError):
        raise ValidationError(f"{name} must be a number")


# ---------- auth ----------
@bp.post("/auth/register")
def register():
    d = _body("name", "email", "password")
    token, user = _ctx().auth.register(str(d["name"]), str(d["email"]), str(d["password"]),
                                       str(d.get("phone", "")), bool(d.get("is_student", False)))
    return jsonify(token=token, user=user_dto(user)), 201


@bp.post("/auth/login")
def login():
    d = _body("email", "password")
    token, user = _ctx().auth.login(str(d["email"]), str(d["password"]))
    return jsonify(token=token, user=user_dto(user))


@bp.post("/auth/logout")
def logout():
    _ctx().auth.logout(_token())
    return jsonify(ok=True)


@bp.get("/me")
def me(): return jsonify(user_dto(_user()))


# ---------- browsing (public) ----------
@bp.get("/movies")
def movies(): return jsonify([movie_dto(m) for m in _ctx().facade.list_movies()])


@bp.get("/movies/<int:movie_id>/shows")
def shows(movie_id):
    f = _ctx().facade
    return jsonify([show_dto(s, f.availability(s.id)[0]) for s in f.list_shows(movie_id)])


@bp.get("/shows/<int:show_id>/seats")
def seats(show_id):
    f = _ctx().facade
    show = f.get_show(show_id)
    return jsonify(show=show_dto(show, f.availability(show_id)[0]),
                   seats=[seat_dto(*row) for row in f.seat_map(show_id)])


# ---------- customer ----------
@bp.post("/shows/<int:show_id>/quote")
def quote(show_id):
    user, d = _user(), _body("seats")
    if not isinstance(d["seats"], list):
        raise ValidationError("seats must be a list")
    return jsonify(_ctx().facade.quote(user.id, show_id, d["seats"]))


@bp.post("/bookings")
def create_booking():
    user, d = _user(), _body("show_id", "seats", "method", "details")
    if not isinstance(d["seats"], list) or not isinstance(d["details"], dict):
        raise ValidationError("seats must be a list and details an object")
    f = _ctx().facade
    booking = f.book_tickets(user.id, _num(d["show_id"], "show_id"), d["seats"], str(d["method"]), d["details"])
    return jsonify(booking_dto(booking, f.payment_for(booking.id))), 201


@bp.get("/bookings")
def my_bookings():
    user, f = _user(), _ctx().facade
    return jsonify([booking_dto(b, f.payment_for(b.id)) for b in reversed(f.booking_history(user.id))])


@bp.post("/bookings/<int:booking_id>/cancel")
def cancel(booking_id):
    user, f = _user(), _ctx().facade
    booking = f.cancel_booking(booking_id, user.id)
    return jsonify(booking_dto(booking, f.payment_for(booking.id)))


@bp.get("/notifications")
def notifications(): return jsonify(_ctx().notifier.for_user(_user().id))


# ---------- admin ----------
@bp.get("/admin/reports/<kind>")
def report(kind): return jsonify(kind=kind, text=_ctx().facade.generate_report(_user().id, kind))


@bp.get("/admin/screens")
def screens():
    return jsonify([{"id": s.id, "name": s.name, "capacity": s.capacity, "theatre": theatre}
                    for s, theatre in _ctx().facade.list_screens(_user().id)])


@bp.post("/admin/movies")
def add_movie():
    user, d = _user(), _body("title", "duration_min", "genre", "language")
    movie = _ctx().facade.add_movie(user.id, str(d["title"]), _num(d["duration_min"], "duration_min"),
                                    str(d["genre"]), str(d["language"]), str(d.get("rating") or "UA"))
    return jsonify(movie_dto(movie)), 201


@bp.post("/admin/shows")
def schedule_show():
    user, d = _user(), _body("movie_id", "screen_id", "start_time", "base_price")
    try:
        start = datetime.fromisoformat(str(d["start_time"]))
    except ValueError:
        raise ValidationError("start_time must look like 2026-12-01T18:30")
    show = _ctx().facade.schedule_show(user.id, _num(d["movie_id"], "movie_id"), _num(d["screen_id"], "screen_id"),
                                       start, _num(d["base_price"], "base_price", float))
    return jsonify(show_dto(show)), 201
