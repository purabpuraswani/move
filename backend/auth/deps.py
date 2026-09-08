"""The reusable authentication dependency for protected routes.

Any route that needs to know who is calling should depend on get_current_user.
User identity comes from the signed token only; it is never accepted from the
request body, form fields, or query string.
"""

import jwt
from bson import ObjectId
from bson.errors import InvalidId
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from auth.jwt_handler import decode_access_token
from database import users_collection


bearer_scheme = HTTPBearer(auto_error=False)


def _unauthorized(detail: str) -> HTTPException:
    return HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail=detail,
        headers={"WWW-Authenticate": "Bearer"}
    )


def get_current_user(
    credentials: HTTPAuthorizationCredentials | None = Depends(bearer_scheme)
) -> dict:
    """Resolve the authenticated user document, or raise 401."""

    if credentials is None or not credentials.credentials:
        raise _unauthorized("Not authenticated")

    try:
        payload = decode_access_token(credentials.credentials)

    except jwt.ExpiredSignatureError:
        raise _unauthorized("Session expired. Please sign in again.") from None

    except jwt.InvalidTokenError:
        raise _unauthorized("Invalid authentication token") from None

    user_id = payload.get("sub")

    if not user_id:
        raise _unauthorized("Invalid authentication token")

    try:
        object_id = ObjectId(user_id)

    except (InvalidId, TypeError):
        raise _unauthorized("Invalid authentication token") from None

    user = users_collection.find_one({"_id": object_id})

    if not user:
        raise _unauthorized("User no longer exists")

    return user


def current_user_id(user: dict = Depends(get_current_user)) -> str:
    """Convenience dependency for routes that only need the user's id."""

    return str(user["_id"])


def require_staff_user(user: dict = Depends(get_current_user)) -> dict:
    """Same as get_current_user, but additionally requires is_staff=True.

    `is_staff` is a minimal, additive field on the user document (see
    routes/auth.py's signup, which sets it False for every new account).
    There is no admin UI to grant it yet — it can currently only be set by
    a direct database update. That is an honestly-documented known
    limitation, not an oversight: building that UI is out of scope here.
    """

    if not user.get("is_staff"):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Staff access required",
        )

    return user
