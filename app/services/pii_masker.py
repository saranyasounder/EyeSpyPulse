import re
import html

import spacy
import medspacy
from medspacy.ner import TargetRule

from presidio_analyzer import AnalyzerEngine, RecognizerResult, Pattern, PatternRecognizer
from presidio_anonymizer import AnonymizerEngine

from app.db.session import SessionLocal
from app.models.raw_record import RawRecord
from app.models.masked_record import MaskedRecord

# ============================================================
# Layer 1: Presidio -- general PII (names, locations, contact info)
# ============================================================

_analyzer = AnalyzerEngine()
_anonymizer = AnonymizerEngine()

ENTITY_TYPES = [
    "PERSON",
    "LOCATION",
    "EMAIL_ADDRESS",
    "PHONE_NUMBER",
    "URL",
    "US_SSN",
]

# Reddit usernames (u/name, /u/name) and @handles. Presidio has no built-in
# recognizer for these. The lookbehinds stop this from matching the domain
# part of an email address (e.g. jane.doe@example.com).
_handle_recognizer = PatternRecognizer(
    supported_entity="SOCIAL_HANDLE",
    patterns=[
        Pattern("reddit_user", r"(?<![\w/])/?u/[A-Za-z0-9_-]{3,20}\b", 0.85),
        Pattern("at_handle", r"(?<![\w.])@[A-Za-z0-9_]{2,30}\b", 0.7),
    ],
)
_analyzer.registry.add_recognizer(_handle_recognizer)
ENTITY_TYPES.append("SOCIAL_HANDLE")


_intl_phone_recognizer = PatternRecognizer(
    supported_entity="PHONE_NUMBER",
    patterns=[
        Pattern(
            "intl_phone_spaced",
            r"(?<!\d)\+\d{1,2}[\s.-]\d{3}[\s.-]\d{3}[\s.-]\d{4}(?!\d)",
            0.6,
        ),
    ],
)
_analyzer.registry.add_recognizer(_intl_phone_recognizer)

ENTITY_THRESHOLDS = {
    "PHONE_NUMBER": 0.35,
}
DEFAULT_THRESHOLD = 0.6


def _passes_threshold(result: RecognizerResult) -> bool:
    threshold = ENTITY_THRESHOLDS.get(result.entity_type, DEFAULT_THRESHOLD)
    return result.score >= threshold


# ============================================================
# Layer 2: MedSpaCy -- medical conditions, context-aware
# ============================================================

_base_nlp = spacy.load("en_core_web_lg")
_med_nlp = medspacy.load(
    _base_nlp,
    medspacy_enable=["medspacy_target_matcher", "medspacy_context"],
)

MEDICAL_CONDITION_RULES = [
    TargetRule(literal="diabetes", category="MEDICAL_CONDITION"),
    TargetRule(literal="glaucoma", category="MEDICAL_CONDITION"),
    TargetRule(literal="hypertension", category="MEDICAL_CONDITION"),
    TargetRule(literal="macular degeneration", category="MEDICAL_CONDITION"),
    TargetRule(literal="cataracts", category="MEDICAL_CONDITION"),
    TargetRule(literal="retinopathy", category="MEDICAL_CONDITION"),
    TargetRule(literal="retinitis pigmentosa", category="MEDICAL_CONDITION"),
    TargetRule(literal="optic neuropathy", category="MEDICAL_CONDITION"),
]

_target_matcher = _med_nlp.get_pipe("medspacy_target_matcher")
_target_matcher.add(MEDICAL_CONDITION_RULES)


def _detect_medical_conditions(clean_text: str) -> list[tuple[int, int]]:
    """
    Run MedSpaCy over the text and return character spans for medical
    conditions that genuinely apply to the speaker.

    Excludes conditions attributed to family members (ent._.is_family) and
    negated conditions (ent._.is_negated) -- "my mother has diabetes" and
    "patient denies hypertension" should not be redacted.
    """
    doc = _med_nlp(clean_text)
    spans = []
    for ent in doc.ents:
        if ent.label_ != "MEDICAL_CONDITION":
            continue
        is_family = getattr(ent._, "is_family", False)
        is_negated = getattr(ent._, "is_negated", False)
        if is_family or is_negated:
            continue
        spans.append((ent.start_char, ent.end_char))
    return spans


# ============================================================
# Shared preprocessing
# ============================================================

def strip_reddit_html(raw_text: str) -> str:
    """Remove Reddit RSS markup noise before any PII/PHI analysis."""
    text = html.unescape(raw_text)
    text = re.split(r"submitted by", text)[0]
    text = re.sub(r"<!--.*?-->", "", text, flags=re.DOTALL)
    text = re.sub(r"<[^>]+>", " ", text)
    text = re.sub(r"\s+", " ", text).strip()
    return text


# ============================================================
# Combined two-layer masking
# ============================================================

def mask_text(clean_text: str) -> tuple[str, list[str]]:
    """
    Two-layer masking pipeline:
      1. Presidio detects and redacts general PII (names, locations,
         emails, phones, URLs, SSNs, social handles) -- masked unconditionally.
      2. MedSpaCy detects medical conditions and redacts only those that
         apply to the speaker (not family, not negated).
    """
    raw_results = _analyzer.analyze(
        text=clean_text,
        entities=ENTITY_TYPES,
        language="en",
    )
    filtered_results = [r for r in raw_results if _passes_threshold(r)]
    entity_types_found = {r.entity_type for r in filtered_results}

    medical_spans = _detect_medical_conditions(clean_text)
    if medical_spans:
        entity_types_found.add("MEDICAL_CONDITION")
        for start, end in medical_spans:
            filtered_results.append(
                RecognizerResult(
                    entity_type="MEDICAL_CONDITION",
                    start=start,
                    end=end,
                    score=1.0,
                )
            )

    anonymized = _anonymizer.anonymize(
        text=clean_text,
        analyzer_results=filtered_results,
    )

    return anonymized.text, sorted(entity_types_found)


# ============================================================
# DB integration
# ============================================================

def run_masking(batch_size: int = 25):
    db = SessionLocal()
    masked_count = 0

    try:
        unprocessed = (
            db.query(RawRecord)
            .filter(RawRecord.is_processed == "pending")
            .limit(batch_size)
            .all()
        )

        for record in unprocessed:
            clean_text = strip_reddit_html(record.raw_text)
            masked_text, entity_types = mask_text(clean_text)

            masked_row = MaskedRecord(
                raw_record_id=record.id,
                masked_text=masked_text,
                entity_types_found=", ".join(entity_types) if entity_types else None,
            )
            db.add(masked_row)

            record.is_processed = "masked"
            db.commit()
            masked_count += 1

    finally:
        db.close()

    print(f"Masking complete: {masked_count} records processed")


if __name__ == "__main__":
    run_masking()