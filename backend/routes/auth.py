from datetime import datetime, timezone

from bson import ObjectId
from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException

from auth.deps import get_current_user
from auth.jwt_handler import create_access_token, token_expires_in_seconds
from auth.security import PasswordTooLongError, hash_password, verify_password
from config import PASSWORD_RESET_TOKEN_MINUTES
from database import users_collection
from models import (
    ForgotPasswordRequest,
    ResetPasswordRequest,
    SigninRequest,
    SignupRequest,
)
from password_reset.mailer import send_reset_email
from password_reset.store import consume_reset_token, create_reset_token


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


# Returned for every well-formed forgot-password request, whether or not the
# address belongs to an account, so the endpoint cannot be used to discover
# which emails are registered.
FORGOT_PASSWORD_MESSAGE = (
    "If an account exists with this email address, password reset "
    "instructions have been sent."
)

INVALID_RESET_TOKEN_MESSAGE = (
    "This password reset link is invalid or has expired. "
    "Please request a new one."
)

# Applies to passwords chosen through the reset flow. The upper bound is
# bcrypt's, enforced by hash_password().
MIN_PASSWORD_LENGTH = 8


@router.post("/forgot-password")
def forgot_password(
    payload: ForgotPasswordRequest,
    background_tasks: BackgroundTasks
):
    """Start a password reset. Always answers with the same message.

    The email is sent as a background task after the response, so the time
    taken to answer does not reveal whether an account was found either.
    """

    existing_user = users_collection.find_one({
        "email": payload.email
    })

    if existing_user:
        token = create_reset_token(
            str(existing_user["_id"]),
            lifetime_minutes=PASSWORD_RESET_TOKEN_MINUTES
        )

        background_tasks.add_task(
            send_reset_email,
            existing_user["email"],
            existing_user.get("name", ""),
            token
        )

    return {
        "message": FORGOT_PASSWORD_MESSAGE
    }


@router.post("/reset-password")
def reset_password(payload: ResetPasswordRequest):
    """Set a new password using a token from a reset email."""

    # The password is checked before the token is consumed, so a password
    # that is rejected does not use up the link.
    if len(payload.new_password) < MIN_PASSWORD_LENGTH:
        raise HTTPException(
            status_code=400,
            detail=f"Password must be at least {MIN_PASSWORD_LENGTH} characters."
        )

    try:
        password_hash = hash_password(payload.new_password)

    except PasswordTooLongError as error:
        raise HTTPException(
            status_code=400,
            detail=str(error)
        ) from None

    token_document = consume_reset_token(payload.token)

    if not token_document:
        raise HTTPException(
            status_code=400,
            detail=INVALID_RESET_TOKEN_MESSAGE
        )

    result = users_collection.update_one(
        {"_id": ObjectId(token_document["user_id"])},
        {"$set": {
            "password_hash": password_hash,
            "password_changed_at": datetime.now(timezone.utc)
        }}
    )

    # The account was deleted after the token was issued.
    if result.matched_count == 0:
        raise HTTPException(
            status_code=400,
            detail=INVALID_RESET_TOKEN_MESSAGE
        )

    return {
        "message": "Your password has been reset. You can now sign in with your new password."
    }


@router.get("/me")
def me(current_user: dict = Depends(get_current_user)):
    """Resolve the caller from their token. Used by the client to check a
    stored token is still valid before relying on it.
    """

    return {
        "user": _public_user(current_user)
    }
