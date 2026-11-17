"""Application factory: wires the layers together and serves the front end."""
from pathlib import Path
from types import SimpleNamespace

from flask import Flask, jsonify, request, send_from_directory
from werkzeug.exceptions import HTTPException

from ..data.database import DatabaseManager
from ..data.repositories import NotificationRepository, SessionRepository
from ..errors import (AuthenticationRequired, CineBookError, InvalidStateTransition, NotFoundError,
                      HoldExpiredError, PaymentFailedError, PermissionDenied, ScheduleConflictError,
                      SeatUnavailableError, ShowStartedError, TooManyAttempts, ValidationError)
from ..patterns.observers import AuditLogger, EmailNotifier, InAppNotifier, SMSNotifier
from ..services.auth_service import AuthService
from ..services.booking_facade import BookingFacade
from . import api

STATIC_DIR = Path(__file__).with_name("static")

HTTP_STATUS = {
    ValidationError: 400, AuthenticationRequired: 401, PaymentFailedError: 402, PermissionDenied: 403,
    NotFoundError: 404, SeatUnavailableError: 409, InvalidStateTransition: 409, ShowStartedError: 409,
    ScheduleConflictError: 409, HoldExpiredError: 410, TooManyAttempts: 429,
}


def create_app(facade: BookingFacade | None = None, db_path: str = "cinebook.db") -> Flask:
    app = Flask(__name__, static_folder=str(STATIC_DIR), static_url_path="/static")
    facade = facade or BookingFacade(DatabaseManager.get_instance(db_path))

    notifier = InAppNotifier(facade.db, NotificationRepository(facade.db), facade.clock)
    for observer in (notifier, EmailNotifier(), SMSNotifier(), AuditLogger()):
        facade.publisher.subscribe(observer)  # Observer pattern: add/remove without touching the facade
    app.extensions["cinebook"] = SimpleNamespace(
        facade=facade, notifier=notifier, auth=AuthService(facade.db, facade.users, SessionRepository(facade.db), facade.clock))
    app.register_blueprint(api.bp)

    @app.get("/")
    def index():
        return send_from_directory(STATIC_DIR, "index.html")

    @app.after_request
    def security_headers(resp):
        resp.headers["X-Content-Type-Options"] = "nosniff"
        resp.headers["X-Frame-Options"] = "DENY"
        resp.headers["Referrer-Policy"] = "same-origin"
        resp.headers["Content-Security-Policy"] = (
            "default-src 'self'; img-src 'self' data:; style-src 'self'; script-src 'self'; "
            "base-uri 'none'; form-action 'self'; frame-ancestors 'none'")
        if request.path.startswith("/api"):
            resp.headers["Cache-Control"] = "no-store"
        return resp

    @app.errorhandler(CineBookError)
    def domain_error(e):
        status = next((code for cls, code in HTTP_STATUS.items() if isinstance(e, cls)), 400)
        return jsonify(error=str(e), type=type(e).__name__), status

    @app.errorhandler(HTTPException)
    def http_error(e):
        if request.path.startswith("/api"):
            return jsonify(error=e.description, type=e.name), e.code
        return e

    return app
