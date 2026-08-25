from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from routes.profile import router as profile_router
from routes.auth import router as auth_router


app = FastAPI(
    title="MoveWell AI API",
    version="1.0.0"
)


app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:5173"
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


app.include_router(auth_router)
app.include_router(profile_router)

@app.get("/")
def root():
    return {
        "message": "MoveWell AI API is running"
    }