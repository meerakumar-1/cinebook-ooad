"""Authentication: registration, login, bearer-token sessions (in memory, expire after 12 h)."""
import secrets
from datetime import datetime, timedelta

from ..data.database import synchronized
from ..domain.models import Customer
from ..errors import AuthenticationRequired, NotFoundError, ValidationError
from ..security import hash_password, verify_password

MIN_PASSWORD_LENGTH = 8


class AuthService:
    TOKEN_TTL = timedelta(hours=12)

    def __init__(self, db, users, clock=datetime.now):
        self._db, self._users, self._clock = db, users, clock
        self._tokens: dict[str, tuple[int, datetime]] = {}

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
        try:
            user, stored = self._users.credentials_for(email)
        except NotFoundError:
            raise AuthenticationRequired("Invalid email or password")
        if not verify_password(password, stored):
            raise AuthenticationRequired("Invalid email or password")
        return self._issue_token(user), user

    @synchronized
    def user_for_token(self, token):
        entry = self._tokens.get(token)
        if not entry or entry[1] < self._clock():
            self._tokens.pop(token, None)
            raise AuthenticationRequired("Please sign in again")
        return self._users.get(entry[0])

    def logout(self, token):
        self._tokens.pop(token, None)

    def _issue_token(self, user):
        token = secrets.token_urlsafe(32)
        self._tokens[token] = (user.id, self._clock() + self.TOKEN_TTL)
        return token
