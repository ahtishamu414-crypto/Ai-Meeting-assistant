from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.upload import router as upload_router
from app.api.search import router as search_router
from app.api.rag import router as rag_router
from app.api.meetings import router as meetings_router
from app.api.action_items import router as action_items_router


app = FastAPI(title="AI Meeting Assistant")


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


# ============================================================
# ROOT
# ============================================================

@app.get("/")
def home():
    return {"message": "Backend is running"}