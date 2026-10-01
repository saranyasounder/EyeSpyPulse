# app/main.py
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.topics import router as topics_router

app = FastAPI(title="ES-Pulse API")

# The React dev server runs on a different port, so the browser needs
# permission to call this API. Read-only: GET is the only method allowed.
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://localhost:3000"],
    allow_methods=["GET"],
    allow_headers=["*"],
)

app.include_router(topics_router)


@app.get("/health")
def health():
    return {"status": "ok"}