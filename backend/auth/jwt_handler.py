"""Creating and decoding JWT access tokens."""

from datetime import datetime, timedelta, timezone

import jwt

from config import JWT_ALGORITHM, JWT_EXPIRES_MINUTES, JWT_SECRET


def create_access_token(user_id: str) -> str:
    """Issue a signed access token identifying a single user."""

    issued_at = datetime.now(timezone.utc)

    payload = {
        "sub": str(user_id),
        "iat": issued_at,
        "exp": issued_at + timedelta(minutes=JWT_EXPIRES_MINUTES)
    }

    return jwt.encode(payload, JWT_SECRET, algorithm=JWT_ALGORITHM)


def decode_access_token(token: str) -> dict:
    """Return the token payload, or raise a jwt exception if it is not valid.

    Callers are expected to translate jwt.ExpiredSignatureError and
    jwt.InvalidTokenError into HTTP responses.
    """

    return jwt.decode(token, JWT_SECRET, algorithms=[JWT_ALGORITHM])


def token_expires_in_seconds() -> int:
    """Lifetime of a newly issued token, for clients that want to pre-empt expiry."""

    return JWT_EXPIRES_MINUTES * 60
