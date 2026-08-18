from dotenv import load_dotenv

# ============================================================
# LOAD ENVIRONMENT VARIABLES FIRST
# ============================================================

load_dotenv()


# ============================================================
# FASTAPI
# ============================================================

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware


# ============================================================
# API ROUTERS
# ============================================================

from app.api.upload import router as upload_router
from app.api.search import router as search_router
from app.api.rag import router as rag_router
from app.api.meetings import router as meetings_router
from app.api.action_items import router as action_items_router
from app.api.zoom import router as zoom_router


# ============================================================
# ZOOM LOCAL RECORDING WATCHER
# ============================================================

from app.services.zoom_recording_watcher import (
    start_zoom_recording_watcher,
    stop_zoom_recording_watcher,
)


# ============================================================
# APPLICATION
# ============================================================

app = FastAPI(
    title="AI Meeting Assistant"
)


# ============================================================
# CORS
# ============================================================

app.add_middleware(
    CORSMiddleware,

    allow_origins=[
        "http://localhost:5173",
        "http://127.0.0.1:5173",
    ],

    allow_credentials=True,

    allow_methods=[
        "*"
    ],

    allow_headers=[
        "*"
    ],
)


# ============================================================
# API ROUTERS
# ============================================================

app.include_router(
    upload_router
)

app.include_router(
    search_router
)

app.include_router(
    rag_router
)

app.include_router(
    meetings_router
)

app.include_router(
    action_items_router
)

app.include_router(
    zoom_router
)


# ============================================================
# FASTAPI STARTUP
# ============================================================

@app.on_event("startup")
async def startup_event():

    print("\n========================================")
    print("AI MEETING ASSISTANT STARTING")
    print("========================================")

    # Start Zoom local recording watcher
    start_zoom_recording_watcher()

    print(
        "Zoom local recording watcher started."
    )

    print("========================================\n")


# ============================================================
# FASTAPI SHUTDOWN
# ============================================================

@app.on_event("shutdown")
async def shutdown_event():

    print("\n========================================")
    print("AI MEETING ASSISTANT SHUTTING DOWN")
    print("========================================")

    stop_zoom_recording_watcher()

    print(
        "Zoom local recording watcher stopped."
    )

    print("========================================\n")


# ============================================================
# ROOT
# ============================================================

@app.get("/")
def home():

    return {
        "message": "Backend is running",
        "zoom_recording_watcher": "enabled"
    }