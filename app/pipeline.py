# app/pipeline.py
from app.ingestion.reddit_rss import run_ingestion
from app.services.pii_masker import run_masking
from app.services.topic_classifier import run_classification
from app.services.sentiment_scorer import run_scoring
from app.services.urgency_engine import run_daily_stats

# Order matters: masking runs before everything downstream, so no later
# stage ever touches unmasked text.
STEPS = [
    ("Ingest RSS feeds", run_ingestion),
    ("Mask PII and PHI", lambda: run_masking(batch_size=1000)),
    ("Classify topics", lambda: run_classification(reclassify_all=False)),
    ("Score sentiment and friction", run_scoring),
    ("Compute topic urgency", run_daily_stats),
]


def run_pipeline():
    for name, step in STEPS:
        print(f"\n=== {name} ===")
        try:
            step()
        except Exception:
            print(f"Pipeline stopped: '{name}' failed.")
            raise
    print("\nPipeline finished.")


if __name__ == "__main__":
    run_pipeline()