from collections import defaultdict
from datetime import datetime, timedelta, timezone

from app.db.session import SessionLocal
from app.models.masked_record import MaskedRecord
from app.models.raw_record import RawRecord
from app.models.sentiment_score import SentimentScore
from app.models.topic import FocusArea, TopicAssignment
from app.models.topic_daily_stat import TopicDailyStat

# ---------------------------------------------------------------------------
# Tunable parameters. Weights are PLACEHOLDERS to review with ESF staff.
# ---------------------------------------------------------------------------
WINDOW_DAYS = 7            # each row summarizes the 7 days ending on stat_date
VELOCITY_PSEUDOCOUNT = 3   # keeps tiny counts from producing extreme velocity
FRICTION_SHRINKAGE = 3     # pulls low-count topics toward the overall average

W_VELOCITY = 0.4
W_ENGAGEMENT = 0.2         # unused until engagement data exists (RSS has none)
W_FRICTION = 0.4


def clamp(value: float, lo: float = 0.0, hi: float = 1.0) -> float:
    return max(lo, min(hi, value))


def mean(values: list[float]) -> float:
    return sum(values) / len(values)


def compute_velocity(current_count: int, previous_count: int) -> float:
    """
    Volume velocity on a 0..1 scale.

      0.0 = activity collapsed compared with the previous window
      0.5 = no change (steady)
      1.0 = activity surged compared with the previous window

    The relative change is computed against (this + last + pseudo-count), so a
    jump from 0 to 1 post is a small move, not a maximum surge. Shifting the
    result to 0..1 means a steady topic sits in the middle instead of being
    floored at zero, which is what made every topic read 0.00 or 1.00 before.
    """
    change = (current_count - previous_count) / (
        current_count + previous_count + VELOCITY_PSEUDOCOUNT
    )
    return 0.5 + 0.5 * clamp(change, -1.0, 1.0)


def combine(velocity, engagement, friction):
    """
    Topic Urgency Score = w1*velocity + w2*engagement + w3*friction.
    Components that are None (not measured) are dropped and the remaining
    weights are renormalized, so a missing signal never counts as zero.
    """
    parts = [
        (W_VELOCITY, velocity),
        (W_ENGAGEMENT, engagement),
        (W_FRICTION, friction),
    ]
    available = [(w, v) for w, v in parts if v is not None]
    if not available:
        return None
    total_weight = sum(w for w, _ in available)
    return sum(w * v for w, v in available) / total_weight


def load_scored_posts(db) -> list[dict]:
    """Every post with its topic and scores, dated by when it was POSTED."""
    rows = (
        db.query(
            RawRecord.source_created_at,
            TopicAssignment.focus_area,
            SentimentScore.friction_index,
            SentimentScore.polarity,
        )
        .join(MaskedRecord, MaskedRecord.raw_record_id == RawRecord.id)
        .join(TopicAssignment, TopicAssignment.masked_record_id == MaskedRecord.id)
        .join(SentimentScore, SentimentScore.masked_record_id == MaskedRecord.id)
        .filter(RawRecord.source_created_at.isnot(None))
        .all()
    )
    return [
        {
            "post_date": created.astimezone(timezone.utc).date(),
            "focus_area": area,
            "friction": friction,
            "polarity": polarity,
        }
        for created, area, friction, polarity in rows
    ]


def posts_in_range(area_days: dict, start, end) -> list[dict]:
    """Posts for one topic between two dates, inclusive."""
    found = []
    for offset in range((end - start).days + 1):
        found.extend(area_days.get(start + timedelta(days=offset), []))
    return found


def run_daily_stats():
    db = SessionLocal()
    try:
        posts = load_scored_posts(db)
        if not posts:
            print("No scored posts found. Run ingestion, masking, classification, and scoring first.")
            return

        # Rescale friction across the whole dataset so the observed min/max
        # map to 0 and 1. Stored scores stay raw; this happens at read time.
        raw = [p["friction"] for p in posts]
        lo, hi = min(raw), max(raw)
        for p in posts:
            p["friction_scaled"] = 0.5 if hi == lo else (p["friction"] - lo) / (hi - lo)
        overall_friction = mean([p["friction_scaled"] for p in posts])

        # Index posts: topic -> date -> [posts]
        by_area_day = defaultdict(lambda: defaultdict(list))
        for p in posts:
            by_area_day[p["focus_area"]][p["post_date"]].append(p)

        existing = {
            (row.stat_date, row.focus_area): row
            for row in db.query(TopicDailyStat).all()
        }

        first_day = min(p["post_date"] for p in posts)
        today = datetime.now(timezone.utc).date()

        day = first_day
        while day <= today:
            win_start = day - timedelta(days=WINDOW_DAYS - 1)
            prev_start = win_start - timedelta(days=WINDOW_DAYS)
            prev_end = win_start - timedelta(days=1)

            # If nothing at all was collected in the previous window, we have
            # no baseline, so velocity is "not measured" rather than "huge".
            prev_total = sum(
                len(posts_in_range(by_area_day[a], prev_start, prev_end))
                for a in FocusArea
            )

            for area in FocusArea:
                current = posts_in_range(by_area_day[area], win_start, day)
                n = len(current)

                if n == 0:
                    # Quiet topics fade to zero urgency.
                    values = dict(
                        post_count=0, avg_friction=None, avg_polarity=None,
                        volume_velocity=None, engagement_weight=None,
                        friction_intensity=None, urgency_score=0.0,
                    )
                else:
                    prev_count = len(posts_in_range(by_area_day[area], prev_start, prev_end))

                    velocity = None
                    if prev_total > 0:
                        velocity = compute_velocity(n, prev_count)

                    scaled_mean = mean([p["friction_scaled"] for p in current])
                    friction_intensity = (
                        n * scaled_mean + FRICTION_SHRINKAGE * overall_friction
                    ) / (n + FRICTION_SHRINKAGE)

                    values = dict(
                        post_count=n,
                        avg_friction=mean([p["friction"] for p in current]),
                        avg_polarity=mean([p["polarity"] for p in current]),
                        volume_velocity=velocity,
                        engagement_weight=None,  # RSS has no engagement data
                        friction_intensity=friction_intensity,
                        urgency_score=combine(velocity, None, friction_intensity),
                    )

                key = (day, area)
                row = existing.get(key)
                if row is None:
                    row = TopicDailyStat(stat_date=day, focus_area=area)
                    db.add(row)
                    existing[key] = row
                for field, value in values.items():
                    setattr(row, field, value)
                row.computed_at = datetime.now(timezone.utc)

            day += timedelta(days=1)

        db.commit()  # safe to rerun: rows are updated in place, never duplicated

        latest = (
            db.query(TopicDailyStat)
            .filter(TopicDailyStat.stat_date == today)
            .order_by(TopicDailyStat.urgency_score.desc())
            .all()
        )
        print(f"Daily stats computed through {today}. Current ranking:")
        for row in latest:
            velocity = "n/a" if row.volume_velocity is None else f"{row.volume_velocity:.2f}"
            print(
                f"  {row.focus_area.name:32} posts={row.post_count:3}  "
                f"velocity={velocity:>4}  urgency={row.urgency_score:.2f}"
            )

    finally:
        db.close()


if __name__ == "__main__":
    run_daily_stats()