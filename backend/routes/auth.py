from fastapi import APIRouter, HTTPException

from database import users_collection
from models import SignupRequest, SigninRequest


router = APIRouter(
    prefix="/api/auth",
    tags=["Authentication"]
)


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

    new_user = {
        "name": user.name,
        "email": user.email,
        "password": user.password
    }

    result = users_collection.insert_one(new_user)

    return {
        "message": "Account created successfully",
        "user": {
            "id": str(result.inserted_id),
            "name": user.name,
            "email": user.email
        }
    }


@router.post("/signin")
def signin(user: SigninRequest):

    existing_user = users_collection.find_one({
        "email": user.email
    })

    if not existing_user:
        raise HTTPException(
            status_code=401,
            detail="Invalid email or password"
        )

    if existing_user["password"] != user.password:
        raise HTTPException(
            status_code=401,
            detail="Invalid email or password"
        )

    return {
        "message": "Login successful",
        "user": {
            "id": str(existing_user["_id"]),
            "name": existing_user["name"],
            "email": existing_user["email"]
        }
    }