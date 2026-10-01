# app/api/topics.py
from collections import defaultdict
from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.models.topic import FocusArea
from app.models.topic_daily_stat import TopicDailyStat

router = APIRouter(prefix="/api/topics", tags=["topics"])

DISPLAY_NAMES = {
    FocusArea.COMMUNITY_IDENTITY_SOCIAL: "Community and social life",
    FocusArea.ASSISTIVE_TECH_DIGITAL_ACCESS: "Assistive tech and digital access",
    FocusArea.ORIENTATION_MOBILITY: "Orientation and mobility",
    FocusArea.DAILY_LIVING_UNCATEGORIZED: "Daily living",
    FocusArea.HEALTHCARE_VISION_DIAGNOSIS: "Healthcare and vision diagnosis",
}

MIN_POSTS_TO_RANK = 3      # below this, a topic is shown but not ranked
STALE_AFTER_DAYS = 2       # warn if the pipeline hasn't run recently

# Daily trend: today's urgency vs the average of the previous few days.
TREND_LOOKBACK_DAYS = 3    # how many earlier days form the baseline
MIN_BASELINE_DAYS = 2      # need at least this many usable earlier days
TREND_THRESHOLD = 0.03     # change needed to call a topic rising or falling


class TopicOut(BaseModel):
    focus_area: str
    display_name: str
    rank: int | None
    ranked: bool
    urgency_score: float
    post_count: int
    trend: str  # "rising" | "steady" | "falling" | "limited data"
    volume_velocity: float | None
    friction_intensity: float | None
    summary: str


class CurrentTopicsOut(BaseModel):
    as_of: str | None
    last_updated: datetime | None
    is_stale: bool
    min_posts_to_rank: int
    topics: list[TopicOut]


def compute_trend(current: TopicDailyStat, history: list[TopicDailyStat]) -> str:
    if current.post_count < MIN_POSTS_TO_RANK:
        return "limited data"

    usable = [
        h.urgency_score
        for h in history
        if h.post_count >= MIN_POSTS_TO_RANK and h.urgency_score is not None
    ]
    if len(usable) < MIN_BASELINE_DAYS:
        return "limited data"

    baseline = sum(usable) / len(usable)
    delta = (current.urgency_score or 0.0) - baseline
    if delta > TREND_THRESHOLD:
        return "rising"
    if delta < -TREND_THRESHOLD:
        return "falling"
    return "steady"


@router.get("/current", response_model=CurrentTopicsOut)
def current_topics(db: Session = Depends(get_db)):
    as_of = db.query(func.max(TopicDailyStat.stat_date)).scalar()
    if as_of is None:
        return CurrentTopicsOut(
            as_of=None, last_updated=None, is_stale=True,
            min_posts_to_rank=MIN_POSTS_TO_RANK, topics=[],
        )

    last_updated = db.query(func.max(TopicDailyStat.computed_at)).scalar()
    is_stale = (datetime.now(timezone.utc) - last_updated) > timedelta(days=STALE_AFTER_DAYS)

    rows = db.query(TopicDailyStat).filter(TopicDailyStat.stat_date == as_of).all()

    history = defaultdict(list)
    earlier = (
        db.query(TopicDailyStat)
        .filter(
            TopicDailyStat.stat_date >= as_of - timedelta(days=TREND_LOOKBACK_DAYS),
            TopicDailyStat.stat_date < as_of,
        )
        .all()
    )
    for r in earlier:
        history[r.focus_area].append(r)

    rankable = sorted(
        (r for r in rows if r.post_count >= MIN_POSTS_TO_RANK),
        key=lambda r: r.urgency_score or 0.0,
        reverse=True,
    )
    limited = sorted(
        (r for r in rows if r.post_count < MIN_POSTS_TO_RANK),
        key=lambda r: r.post_count,
        reverse=True,
    )

    topics = []
    for index, row in enumerate(rankable + limited):
        name = DISPLAY_NAMES[row.focus_area]
        is_ranked = row.post_count >= MIN_POSTS_TO_RANK
        rank = index + 1 if is_ranked else None
        score = row.urgency_score or 0.0
        trend = compute_trend(row, history[row.focus_area])
        trend_phrase = "trend not yet available" if trend == "limited data" else trend

        if is_ranked:
            summary = (
                f"{name}: urgency {score:.2f}, ranked {rank} of {len(rankable)}, "
                f"{trend_phrase}, based on {row.post_count} posts in the past week."
            )
        else:
            plural = "post" if row.post_count == 1 else "posts"
            summary = (
                f"{name}: limited data. Only {row.post_count} {plural} in the past "
                f"week, which is not enough to rank this topic."
            )

        topics.append(
            TopicOut(
                focus_area=row.focus_area.value,
                display_name=name,
                rank=rank,
                ranked=is_ranked,
                urgency_score=round(score, 2),
                post_count=row.post_count,
                trend=trend,
                volume_velocity=None if row.volume_velocity is None else round(row.volume_velocity, 2),
                friction_intensity=None if row.friction_intensity is None else round(row.friction_intensity, 2),
                summary=summary,
            )
        )

    return CurrentTopicsOut(
        as_of=as_of.isoformat(),
        last_updated=last_updated,
        is_stale=is_stale,
        min_posts_to_rank=MIN_POSTS_TO_RANK,
        topics=topics,
    )