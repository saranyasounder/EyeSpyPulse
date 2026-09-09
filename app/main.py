from fastapi import FastAPI

from app.api import records

app = FastAPI(
    title="ES-Pulse API",
    description="Anonymized NLP pipeline for BVI community insights",
    version="0.1.0",
)

app.include_router(records.router, prefix="/records", tags=["records"])


@app.get("/health")
def health_check():
    """Simple liveness check — confirms the API process is up."""
    return {"status": "ok"}