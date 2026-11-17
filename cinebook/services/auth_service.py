"""Authentication: registration, login, bearer-token sessions stored (hashed) in the database."""
import hashlib
import secrets
from collections import defaultdict
from datetime import datetime, timedelta

from ..data.database import synchronized
from ..domain.models import Customer
from ..errors import AuthenticationRequired, NotFoundError, TooManyAttempts, ValidationError
from ..security import hash_password, verify_password

MIN_PASSWORD_LENGTH = 8


class AuthService:
    TOKEN_TTL = timedelta(hours=12)
    MAX_FAILURES = 5
    LOCK_WINDOW = timedelta(minutes=10)

    def __init__(self, db, users, sessions, clock=datetime.now):
        self._db, self._users, self._sessions, self._clock = db, users, sessions, clock
        self._failures = defaultdict(list)  # email -> timestamps of recent failed logins

    @synchronized
    def register(self, name, email, password, phone="", is_student=False):
        if not name.strip():
            raise ValidationError("Name is required")
        if len(password) < MIN_PASSWORD_LENGTH:
            raise ValidationError(f"Password must be at least {MIN_PASSWORD_LENGTH} characters")
        customer = Customer(name.strip(), email, phone.strip(), bool(is_student))  # validates email
        try:
            self._users.credentials_for(customer.email)
        except NotFoundError:
            pass
        else:
            raise ValidationError("Email is already registered")
        with self._db.transaction():
            self._users.add(customer, hash_password(password))
        return self._issue_token(customer), customer

    @synchronized
    def login(self, email, password):
        email = email.strip().lower()
        self._check_not_locked(email)
        try:
            user, stored = self._users.credentials_for(email)
            valid = verify_password(password, stored)
        except NotFoundError:
            valid = False
        if not valid:
            self._failures[email].append(self._clock())
            raise AuthenticationRequired("Invalid email or password")
        self._failures.pop(email, None)
        return self._issue_token(user), user

    @synchronized
    def user_for_token(self, token):
        entry = self._sessions.get(self._digest(token))
        if not entry or entry[1] <= self._clock():
            raise AuthenticationRequired("Please sign in again")
        return self._users.get(entry[0])

    @synchronized
    def logout(self, token):
        with self._db.transaction():
            self._sessions.delete(self._digest(token))

    # ---- internals ----
    def _check_not_locked(self, email):
        now = self._clock()
        recent = [t for t in self._failures[email] if now - t < self.LOCK_WINDOW]
        self._failures[email] = recent
        if len(recent) >= self.MAX_FAILURES:
            raise TooManyAttempts("Too many failed sign-in attempts. Try again in a few minutes.")

    @staticmethod
    def _digest(token): return hashlib.sha256(token.encode()).hexdigest()

    def _issue_token(self, user):
        token = secrets.token_urlsafe(32)
        with self._db.transaction():
            self._sessions.purge_expired(self._clock())
            self._sessions.add(self._digest(token), user.id, self._clock() + self.TOKEN_TTL)
        return token
