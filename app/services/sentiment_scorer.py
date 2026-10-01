import re

import numpy as np
from vaderSentiment.vaderSentiment import SentimentIntensityAnalyzer

from app.db.session import SessionLocal
from app.models.masked_record import MaskedRecord
from app.models.sentiment_score import SentimentScore
from app.services.embeddings import get_embeddings_batch

_vader = SentimentIntensityAnalyzer()

# ---------------------------------------------------------------------------
# Friction Index reference examples
#
# Friction is a spectrum between two poles, each anchored by real posts.
# Design rule: BOTH poles must contain help-seeking posts. If only the
# high-friction pole contains questions, the score learns "asking for help"
# instead of "facing a barrier" and would reward question-shaped posts.
# The only thing separating the poles should be barrier severity.
#
# NOTE: these examples come from posts in our own dataset, so those specific
# posts will score artificially extreme (they're compared partly to
# themselves). Revisit with examples from a held-out set as data grows.
# ---------------------------------------------------------------------------
HIGH_FRICTION_EXAMPLES = [
    "I just wanted to buy fresh fruit and vegetables. I live alone and my "
    "mom couldn't come over, so I had no way to get to the store myself.",
    "Speech therapy for blind child. Unfortunately where we live there are "
    "no specialists who know how to work with blind children, and I don't "
    "know where else to turn.",
    "My guide dog has to retire this week and the vet didn't investigate "
    "the problem properly. I feel completely stuck with no good options.",
    "I have recently been struggling to find work since losing my job for "
    "being disabled, and nobody seems willing to give me a chance.",
]

LOW_FRICTION_EXAMPLES = [
    # Casual / celebratory posts
    "Does anyone elses cat love playing with your cane? Every time I go "
    "out I have to play canes with my cat.",
    "Excited! Getting a Scientific Canute. I'm getting a laptop with a "
    "refreshable braille display this year.",
    "NVDA 2026.2 Released. Featuring magnifier improvements and better "
    "speech dictionaries.",
    # Help-seeking WITHOUT a barrier, so the pole isn't just "announcements"
    "Best accessible smart watch. I'm looking to get a new Apple Watch but "
    "don't want to spend a ton of money. Any other accessible options?",
    "Free accessible apps for university notes? Basically the title!",
    "Looking for an iPhone app to make a 75-ball bingo card accessible to "
    "a blind player.",
]


def compute_friction_poles() -> tuple[np.ndarray, np.ndarray]:
    """Average each pole's example embeddings, re-normalized to unit length."""
    high = np.array(get_embeddings_batch(HIGH_FRICTION_EXAMPLES)).mean(axis=0)
    low = np.array(get_embeddings_batch(LOW_FRICTION_EXAMPLES)).mean(axis=0)
    return high / np.linalg.norm(high), low / np.linalg.norm(low)


def cosine_similarity(a: np.ndarray, b: np.ndarray) -> float:
    return float(np.dot(a, b) / (np.linalg.norm(a) * np.linalg.norm(b)))


def compute_friction_index(
    record_embedding: np.ndarray, high_pole: np.ndarray, low_pole: np.ndarray
) -> float:
    """
    Position between the two poles, 0.0 (low friction) to 1.0 (high friction).
    Using the difference between both similarities (not just similarity to the
    high pole) keeps ambiguous posts near 0.5 instead of conflating
    "clearly low friction" with "unrelated to both".

    Raw scores are stored as-is. Any rescaling to stretch the observed range
    should happen at read time (in the urgency engine), so stored values stay
    honest and adapt automatically as more data arrives.
    """
    sim_high = cosine_similarity(record_embedding, high_pole)
    sim_low = cosine_similarity(record_embedding, low_pole)
    score = (sim_high - sim_low + 1) / 2
    return max(0.0, min(1.0, score))


def compute_polarity(text: str) -> float:
    """
    Average VADER compound score across sentences, range -1 to +1.

    Scoring the whole post at once saturates on long text: a few positive
    words ("thank you", "loves") push the compound score toward +1 even when
    the post describes a real problem. Averaging per sentence stops one polite
    closing line from dominating.
    """
    sentences = [s for s in re.split(r"(?<=[.!?])\s+", text) if s.strip()]
    if not sentences:
        return 0.0
    scores = [_vader.polarity_scores(s)["compound"] for s in sentences]
    return sum(scores) / len(scores)


def run_scoring():
    db = SessionLocal()
    try:
        high_pole, low_pole = compute_friction_poles()

        already_scored_ids = {
            row.masked_record_id
            for row in db.query(SentimentScore.masked_record_id).all()
        }
        records = [
            r for r in db.query(MaskedRecord).all()
            if r.id not in already_scored_ids
        ]

        if not records:
            print("No new records to score.")
            return

        print(f"Scoring {len(records)} records...")
        texts = [r.masked_text for r in records]
        embeddings = get_embeddings_batch(texts)

        scored = 0
        for record, embedding, text in zip(records, embeddings, texts):
            friction = compute_friction_index(
                np.array(embedding), high_pole, low_pole
            )
            polarity = compute_polarity(text)

            db.add(
                SentimentScore(
                    masked_record_id=record.id,
                    polarity=polarity,
                    friction_index=friction,
                )
            )
            db.commit()  # per-row commit, same pattern as the other services
            scored += 1

        print(f"Scoring complete: {scored} records scored")

    finally:
        db.close()


if __name__ == "__main__":
    run_scoring()