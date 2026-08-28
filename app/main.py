from dotenv import load_dotenv

load_dotenv()

import logging

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
)

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.slack import router as slack_router
from app.api.upload import router as upload_router
from app.api.search import router as search_router
from app.api.rag import router as rag_router
from app.api.meetings import router as meetings_router
from app.api.action_items import router as action_items_router

from app.services.slack_listener import (
    stop_slack_listener,
    create_slack_listener_task,
    cancel_slack_listener_task,
)


# ============================================================
# FASTAPI APP
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

    allow_methods=["*"],

    allow_headers=["*"],
)


# ============================================================
# API ROUTERS
# ============================================================

app.include_router(upload_router)
app.include_router(search_router)
app.include_router(rag_router)
app.include_router(meetings_router)
app.include_router(action_items_router)
app.include_router(slack_router)

# ============================================================
# STARTUP
# ============================================================

@app.on_event("startup")
async def startup_event():

    print("\n========================================")
    print("AI MEETING ASSISTANT STARTING")
    print("========================================")

    # IMPORTANT: schedule as a background task, do NOT await it here.
    # start_slack_listener() -> socket_handler.start_async() sleeps
    # forever by design (it's meant to keep a standalone process alive).
    # Awaiting it directly would block FastAPI/Uvicorn startup forever.
    create_slack_listener_task()

    print("Slack Socket Mode listener started.")
    print("========================================\n")


# ============================================================
# SHUTDOWN
# ============================================================

@app.on_event("shutdown")
async def shutdown_event():

    print("\n========================================")
    print("AI MEETING ASSISTANT SHUTTING DOWN")
    print("========================================")

    await stop_slack_listener()
    await cancel_slack_listener_task()

    print("Slack Socket Mode listener stopped.")
    print("========================================\n")


# ============================================================
# ROOT
# ============================================================

@app.get("/")
async def home():

    return {
        "message": "Backend is running",
        "slack_socket_mode": "enabled"
    }