"""Password hashing and verification.

bcrypt is used with a per-password salt generated at hash time, so the salt
travels inside the stored hash and no separate column is needed.
"""

import bcrypt


# bcrypt only consumes the first 72 bytes of input. Newer releases raise on
# longer input rather than silently truncating, so the limit is enforced here
# to keep behaviour identical across bcrypt versions.
MAX_PASSWORD_BYTES = 72


class PasswordTooLongError(ValueError):
    """Raised when a password exceeds what bcrypt can process."""


def hash_password(password: str) -> str:
    """Return a bcrypt hash (salt included) for the given plaintext password."""

    encoded = password.encode("utf-8")

    if len(encoded) > MAX_PASSWORD_BYTES:
        raise PasswordTooLongError(
            f"Password must be at most {MAX_PASSWORD_BYTES} bytes."
        )

    return bcrypt.hashpw(encoded, bcrypt.gensalt()).decode("utf-8")


def verify_password(password: str, password_hash: str) -> bool:
    """Check a plaintext password against a stored bcrypt hash.

    Returns False rather than raising for any unusable stored value. Accounts
    created before hashing existed hold plaintext in that field, which is not a
    valid bcrypt hash; those logins fail closed instead of erroring, and the
    account has to be created again.
    """

    if not password or not password_hash:
        return False

    encoded = password.encode("utf-8")

    if len(encoded) > MAX_PASSWORD_BYTES:
        return False

    try:
        return bcrypt.checkpw(encoded, password_hash.encode("utf-8"))

    except (ValueError, TypeError):
        return False
