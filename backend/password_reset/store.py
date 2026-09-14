"""Persistence for password reset tokens.

A reset token is a bearer credential: whoever holds it can set the account's
password. So the raw token only ever exists in the email sent to the user and
in the reset request they send back. What is stored is its SHA-256 hash, which
is enough to recognise a presented token but useless to anyone who reads the
collection.

Tokens are single-use and short-lived. Issuing a new token for an account
retires any earlier unused one, so only the most recent email works. Consuming
a token is one atomic find-and-update, so two requests racing with the same
token cannot both succeed.
"""

import hashlib
import secrets
from datetime import datetime, timedelta, timezone

from database import password_reset_tokens_collection


# 32 bytes from the OS CSPRNG, URL-safe base64: 43 characters, 256 bits.
TOKEN_BYTES = 32


def ensure_indexes():
    """Create the indexes the token paths rely on. Safe to run repeatedly."""

    password_reset_tokens_collection.create_index(
        "token_hash", unique=True, name="token_hash_unique"
    )

    password_reset_tokens_collection.create_index("user_id", name="user_id")

    # MongoDB removes each document once expires_at has passed. The expiry
    # check in consume_reset_token() is what actually enforces the lifetime;
    # the TTL monitor runs about once a minute and only tidies up.
    password_reset_tokens_collection.create_index(
        "expires_at", expireAfterSeconds=0, name="expires_at_ttl"
    )


def hash_token(token: str) -> str:
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


def create_reset_token(user_id: str, *, lifetime_minutes: int, now: datetime = None) -> str:
    """Issue a new reset token for the user and return the raw token.

    Any earlier token for this user that has not been used is retired first.
    """

    now = now or datetime.now(timezone.utc)

    password_reset_tokens_collection.update_many(
        {"user_id": user_id, "used_at": None},
        {"$set": {"used_at": now, "retired": True}},
    )

    token = secrets.token_urlsafe(TOKEN_BYTES)

    password_reset_tokens_collection.insert_one({
        "user_id": user_id,
        "token_hash": hash_token(token),
        "created_at": now,
        "expires_at": now + timedelta(minutes=lifetime_minutes),
        "used_at": None,
    })

    return token


def consume_reset_token(token: str, *, now: datetime = None):
    """Mark a valid token as used and return its document, or None.

    None covers every way a token can be unusable -- unknown, already used,
    retired by a newer token, or expired -- so a caller cannot tell them apart
    and neither can anyone probing the endpoint.
    """

    if not isinstance(token, str) or not token:
        return None

    now = now or datetime.now(timezone.utc)

    return password_reset_tokens_collection.find_one_and_update(
        {
            "token_hash": hash_token(token),
            "used_at": None,
            "expires_at": {"$gt": now},
        },
        {"$set": {"used_at": now}},
    )
