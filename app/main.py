from fastapi import FastAPI
from app.api.upload import router as upload_router

app = FastAPI(title="AI Meeting Assistant")
app.include_router(upload_router)


@app.get("/")
def home():
    return {"message": "Backend is running"}