import re
import html

from presidio_analyzer import AnalyzerEngine
from presidio_anonymizer import AnonymizerEngine

from app.db.session import SessionLocal
from app.models.raw_record import RawRecord
from app.models.masked_record import MaskedRecord

# --- SETUP (runs once when this file is imported) ---
# Presidio's analyzer loads a spaCy model under the hood to detect PII,
# and that load is slow. We create ONE analyzer and ONE anonymizer here,
# at import time, so every row reuses the same loaded model instead of
# reloading it 25+ times per batch.
_analyzer = AnalyzerEngine()
_anonymizer = AnonymizerEngine()

# We only ask Presidio to look for these specific PII types.
# Presidio supports many more (like DATE_TIME), but we deliberately
# leave those out — a phrase like "going blind next year" is useful
# for topic/sentiment analysis, and DATE_TIME would strip "next year"
# even though it's not actually identifying anyone.
ENTITY_TYPES = [
    "PERSON",
    "LOCATION",
    "EMAIL_ADDRESS",
    "PHONE_NUMBER",
    "URL",
    "US_SSN",
]


def strip_reddit_html(raw_text: str) -> str:
    """Remove Reddit RSS markup noise before PII analysis."""
    # Reddit's RSS feed encodes special characters as HTML entities
    # (e.g. &amp; instead of &). This converts them back to normal text.
    text = html.unescape(raw_text)

    # Reddit's RSS always appends a "submitted by ... [link] [comments]"
    # footer to every entry. We cut everything from "submitted by" onward
    # so it doesn't get treated as part of the actual post content.
    text = re.split(r"submitted by", text)[0]

    # Reddit wraps content in HTML comment markers like <!-- SC_OFF -->
    # and real HTML tags like <div>, <p>, <a>. Strip both so PII detection
    # runs on plain readable text, not markup.
    text = re.sub(r"<!--.*?-->", "", text, flags=re.DOTALL)
    text = re.sub(r"<[^>]+>", " ", text)

    # Stripping tags leaves behind extra/irregular whitespace
    # (double spaces, stray newlines) — collapse it all down to
    # single spaces and trim the ends.
    text = re.sub(r"\s+", " ", text).strip()

    return text


def mask_text(clean_text: str) -> tuple[str, list[str]]:
    """Run Presidio analysis + anonymization on cleaned text."""
    # Step 1: ANALYZE — Presidio scans the text and returns a list of
    # "hits": spans of text it believes are PII, each tagged with a type
    # (PERSON, EMAIL_ADDRESS, etc.) and a confidence score. Nothing is
    # modified yet at this stage — it's just detection.
    results = _analyzer.analyze(
        text=clean_text,
        entities=ENTITY_TYPES,
        language="en",
    )

    # Step 2: ANONYMIZE — takes the original text plus the list of hits
    # from step 1, and actually replaces each hit with a placeholder
    # (Presidio's default is something like "<PERSON>").
    anonymized = _anonymizer.anonymize(
        text=clean_text,
        analyzer_results=results,
    )

    # Build a simple summary of *which types* of PII were found in this
    # text (not the PII itself) — useful for later stats/auditing without
    # storing anything sensitive, e.g. "this record had PERSON + EMAIL".
    entity_types_found = sorted({r.entity_type for r in results})

    return anonymized.text, entity_types_found


def run_masking(batch_size: int = 25):
    db = SessionLocal()
    masked_count = 0

    try:
        # Pull only rows that haven't been masked yet. This is what makes
        # the script safe to re-run repeatedly — it always picks up where
        # it left off instead of reprocessing everything each time.
        unprocessed = (
            db.query(RawRecord)
            .filter(RawRecord.is_processed == "pending")
            .limit(batch_size)
            .all()
        )

        for record in unprocessed:
            # Clean the HTML noise first, then run PII detection +
            # anonymization on the cleaned text.
            clean_text = strip_reddit_html(record.raw_text)
            masked_text, entity_types = mask_text(clean_text)

            # Store the masked result as a NEW row in a separate table
            # (MaskedRecord), linked back to the original raw_records row
            # by ID. This keeps raw (unmasked) and masked text physically
            # separate — which matters for your retention rules, since the
            # raw table has a 7-30 day expiry but masked data can be kept
            # longer as de-identified aggregate data.
            masked_row = MaskedRecord(
                raw_record_id=record.id,
                masked_text=masked_text,
                entity_types_found=", ".join(entity_types) if entity_types else None,
            )
            db.add(masked_row)

            # Flip the original row's status so it won't be picked up
            # again on the next run.
            record.is_processed = "masked"

            # Commit after EACH row (not once at the end of the loop).
            # This means if something crashes halfway through a batch,
            # everything processed so far is already safely saved —
            # you won't lose completed work or need to redo it.
            db.commit()
            masked_count += 1

    finally:
        # Always close the DB connection, even if something above raised
        # an exception.
        db.close()

    print(f"Masking complete: {masked_count} records processed")


if __name__ == "__main__":
    run_masking()