from fastapi import APIRouter, Depends, HTTPException

from auth.deps import get_current_user
from auth.jwt_handler import create_access_token, token_expires_in_seconds
from auth.security import PasswordTooLongError, hash_password, verify_password
from database import users_collection
from models import SigninRequest, SignupRequest


router = APIRouter(
    prefix="/api/auth",
    tags=["Authentication"]
)


def _public_user(user_document) -> dict:
    """Shape a user document for the client. Never includes the password hash."""

    return {
        "id": str(user_document["_id"]),
        "name": user_document["name"],
        "email": user_document["email"]
    }


def _auth_response(message: str, user_document) -> dict:

    user = _public_user(user_document)

    return {
        "message": message,
        "token": create_access_token(user["id"]),
        "token_type": "bearer",
        "expires_in": token_expires_in_seconds(),
        "user": user
    }


@router.post("/signup")
def signup(user: SignupRequest):

    existing_user = users_collection.find_one({
        "email": user.email
    })

    if existing_user:
        raise HTTPException(
            status_code=400,
            detail="Email already registered"
        )

    try:
        password_hash = hash_password(user.password)

    except PasswordTooLongError as error:
        raise HTTPException(
            status_code=400,
            detail=str(error)
        ) from None

    new_user = {
        "name": user.name,
        "email": user.email,
        "password_hash": password_hash,
        # Additive, Phase 6: every new account starts as a non-staff user.
        # There is no admin UI yet to promote one — see auth/deps.py's
        # require_staff_user docstring for that honestly-documented
        # limitation. Existing user documents are unaffected: a document
        # from before this field existed is just treated as not staff by
        # require_staff_user's `user.get("is_staff")` check.
        "is_staff": False
    }

    result = users_collection.insert_one(new_user)

    return _auth_response(
        "Account created successfully",
        {**new_user, "_id": result.inserted_id}
    )


@router.post("/signin")
def signin(user: SigninRequest):

    existing_user = users_collection.find_one({
        "email": user.email
    })

    # The same message is returned whether the email or the password was wrong,
    # so the response cannot be used to discover which emails are registered.
    if not existing_user:
        raise HTTPException(
            status_code=401,
            detail="Invalid email or password"
        )

    if not verify_password(
        user.password,
        existing_user.get("password_hash", "")
    ):
        raise HTTPException(
            status_code=401,
            detail="Invalid email or password"
        )

    return _auth_response(
        "Login successful",
        existing_user
    )


@router.get("/me")
def me(current_user: dict = Depends(get_current_user)):
    """Resolve the caller from their token. Used by the client to check a
    stored token is still valid before relying on it.
    """

    return {
        "user": _public_user(current_user)
    }
