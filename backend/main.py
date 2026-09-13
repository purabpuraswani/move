from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from pymongo.errors import PyMongoError

from agents.store import ensure_indexes as ensure_guidance_indexes
from assessments.store import ensure_indexes
from config import CORS_ORIGINS
from exercise_assessment.store import ensure_indexes as ensure_exercise_result_indexes
from behaviour_log.store import ensure_indexes as ensure_behaviour_log_indexes
from food_log.store import ensure_indexes as ensure_food_log_indexes
from reports.store import ensure_indexes as ensure_report_indexes
from routes.assessments import router as assessments_router
from routes.exercise_results import router as exercise_results_router
from routes.behaviour_log import router as behaviour_log_router
from routes.food_log import router as food_log_router
from routes.guidance import router as guidance_router
from routes.profile import router as profile_router
from routes.reports import router as reports_router
from routes.workflow import router as workflow_router
from routes.dashboard import router as dashboard_router
from routes.auth import router as auth_router
from user_state.store import ensure_indexes as ensure_user_state_indexes


LOCAL_CORS_ORIGINS = (
    "http://localhost:5173",
    "http://localhost:5174",
    "http://127.0.0.1:5173",
    "http://127.0.0.1:5174",
)


@asynccontextmanager
async def lifespan(_app: FastAPI):
    """Prepare the database on startup.

    Index creation is the first thing that actually talks to MongoDB, so a
    wrong or unreachable MONGODB_URI shows up here with a clear message. It is
    not fatal: the API still starts so its own routes can report the problem,
    rather than the process dying with a stack trace and no endpoint to ask.
    """

    try:
        ensure_indexes()
        ensure_report_indexes()
        ensure_guidance_indexes()
        ensure_exercise_result_indexes()
        ensure_food_log_indexes()
        ensure_behaviour_log_indexes()
        ensure_user_state_indexes()

    except PyMongoError as error:
        print(
            "MoveWell AI: could not prepare database indexes.\n"
            f"  {type(error).__name__}: {error}\n"
            "  Check MONGODB_URI in backend/.env and that the database is "
            "reachable. The API has started, but requests that need the "
            "database will fail until this is fixed."
        )

    yield


app = FastAPI(
    title="MoveWell AI API",
    version="1.0.0",
    lifespan=lifespan
)


# Cross-origin access is limited to the origins named in CORS_ORIGINS, which
# includes the local Vite development ports. The broad method and header
# settings allow browser preflight requests for authenticated API calls.
app.add_middleware(
    CORSMiddleware,
    allow_origins=sorted(set(CORS_ORIGINS).union(LOCAL_CORS_ORIGINS)),
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


app.include_router(auth_router)
app.include_router(profile_router)
app.include_router(assessments_router)
app.include_router(exercise_results_router)
app.include_router(food_log_router)
app.include_router(behaviour_log_router)
app.include_router(reports_router)
app.include_router(guidance_router)
app.include_router(workflow_router)
app.include_router(dashboard_router)

@app.get("/")
def root():
    return {
        "message": "MoveWell AI API is running"
    }
