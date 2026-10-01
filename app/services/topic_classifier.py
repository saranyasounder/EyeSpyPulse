import numpy as np

from app.db.session import SessionLocal
from app.models.masked_record import MaskedRecord
from app.models.topic import TopicAssignment, FocusArea
from app.services.embeddings import get_embedding, get_embeddings_batch

# Real example posts pulled from exploratory clustering (app/services/explore_clusters.py
# output), grouped into our 5 finalized focus areas. Using actual post text — not written
# descriptions — because embedding similarity works best comparing like-with-like: real
# conversational Reddit posts to other real conversational Reddit posts, not to
# encyclopedia-style summaries.
FOCUS_AREA_EXAMPLES = {
    FocusArea.ASSISTIVE_TECH_DIGITAL_ACCESS: [
        "Switching from a Smart Phone. I'm looking into being able to switch from a smart "
        "phone. My iPhone 14 is getting old and I want something more accessible.",
        "NVDA 2026.2 Released. It's here: NVDA 2026.2 is out! Featuring: Magnifier full "
        "screen, colour filtering, zoom, focus tracking.",
        "Accessible course to learn Google Sheets and Google Docs on Mac OS with voice "
        "over? Hi everyone, hope you're doing well, looking for resources to learn "
        "productivity software with a screen reader.",
        "Linux and its screen reader. Hi everyone, how's it going? Does anyone have "
        "experience with Orca or know of any groups using Linux with a screen reader?",
    ],
    FocusArea.ORIENTATION_MOBILITY: [
        "Is this normal guide dog behavior? I have recently been having some issues with "
        "my guide dog and I wanted to check in with others who have service animals.",
        "Where to buy a cane in Australia. To my fellow Australians, how do you replace "
        "your cane? I know vision Australia have some options.",
        "QQ on service dogs. Can you have a dog you already own become a guide dog with "
        "Seeing Eye? Like if one is low vision already.",
    ],
    FocusArea.COMMUNITY_IDENTITY_SOCIAL: [
        "Question about partial sight, blindness, and representation. I'm a person with "
        "blindness and only a little light perception, and I've been thinking about how "
        "we talk about our conditions publicly.",
        "Community. Do y'all know the other blind folks in your area? Have other blind "
        "friends? Especially those who lost your sight later in life.",
        "Has AI video transcription killed Be My Eyes? I'm a sighted person. I used to "
        "get a Be My Eyes call every 1 to 2 months, wondering if the community still "
        "needs this kind of support.",
    ],
    FocusArea.HEALTHCARE_VISION_DIAGNOSIS: [
        # No real examples exist in our current dataset yet — this category hasn't
        # populated from r/Blind's recent posts. Using a written description as a
        # placeholder until real examples become available; revisit once healthcare-
        # related posts appear (or once a health-focused source is added).
        "I was recently diagnosed with a degenerative eye condition and my doctor "
        "explained the treatment options and prognosis during my appointment. The "
        "surgery is scheduled for next month and I'm trying to understand what to expect "
        "from the vision loss process and ongoing medical care.",
    ],
    FocusArea.DAILY_LIVING_UNCATEGORIZED: [
        "How to follow crochet patterns and designs without seeing? To my fellow "
        "crocheter, what are your ways or tips in creating patterns?",
        "Blind accessible form of highlighting. Hello r/Blind. I am making a document "
        "and have a blind coworker. They use a screen reader and I want to find a way "
        "to highlight text for them.",
        "Introducing myself. Hello everyone! I am brand new here and still figuring out "
        "how everything works. I am looking forward to being part of this community.",
    ],
}


def compute_focus_area_embeddings() -> dict[FocusArea, np.ndarray]:
    """
    Compute one reference embedding per focus area by averaging the
    embeddings of several real example posts in that category.
    """
    embeddings = {}
    for area, examples in FOCUS_AREA_EXAMPLES.items():
        example_embeddings = np.array(get_embeddings_batch(examples))
        # Average the example embeddings into a single reference vector,
        # then re-normalize (averaging unit vectors doesn't preserve unit length)
        mean_embedding = example_embeddings.mean(axis=0)
        mean_embedding = mean_embedding / np.linalg.norm(mean_embedding)
        embeddings[area] = mean_embedding
    return embeddings


def cosine_similarity(a: np.ndarray, b: np.ndarray) -> float:
    return float(np.dot(a, b) / (np.linalg.norm(a) * np.linalg.norm(b)))


def classify_record(
    record_embedding: np.ndarray,
    focus_area_embeddings: dict[FocusArea, np.ndarray],
) -> tuple[FocusArea, float]:
    scores = {
        area: cosine_similarity(record_embedding, area_embedding)
        for area, area_embedding in focus_area_embeddings.items()
    }
    best_area = max(scores, key=scores.get)
    return best_area, scores[best_area]


def run_classification(reclassify_all: bool = False):
    db = SessionLocal()
    try:
        focus_area_embeddings = compute_focus_area_embeddings()

        if reclassify_all:
            # Wipe existing assignments so we can re-run with the improved
            # reference vectors instead of only classifying new records
            deleted = db.query(TopicAssignment).delete()
            db.commit()
            print(f"Cleared {deleted} existing assignments for reclassification.")
            records = db.query(MaskedRecord).all()
        else:
            already_assigned_ids = {
                row.masked_record_id for row in db.query(TopicAssignment.masked_record_id).all()
            }
            records = [
                r for r in db.query(MaskedRecord).all()
                if r.id not in already_assigned_ids
            ]

        if not records:
            print("No records to classify.")
            return

        print(f"Classifying {len(records)} records...")
        texts = [r.masked_text for r in records]
        embeddings = get_embeddings_batch(texts)

        classified = 0
        for record, embedding in zip(records, embeddings):
            embedding_np = np.array(embedding)
            best_area, similarity = classify_record(embedding_np, focus_area_embeddings)

            assignment = TopicAssignment(
                masked_record_id=record.id,
                focus_area=best_area,
                focus_area_similarity=similarity,
                sub_cluster_id=None,
                embedding=embedding,
            )
            db.add(assignment)
            db.commit()
            classified += 1

        print(f"Classification complete: {classified} records classified")

    finally:
        db.close()


if __name__ == "__main__":
    run_classification(reclassify_all=True)