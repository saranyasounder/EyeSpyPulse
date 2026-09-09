"""
PII Masker (Module A)

Strips personally identifiable information from raw community text
before it's used for topic modeling, sentiment analysis, or sent to
any external LLM (per the ES-Pulse Reddit RSS Pilot Plan).

Approach: hybrid NER + regex.
- spaCy NER catches names, locations, and organizations in natural
  language context (e.g. "I live in Springfield" -> location).
- Regex catches structured PII that NER often misses: emails, phone
  numbers, URLs with usernames, @handles, and Reddit-style u/username
  mentions.

This module is intentionally source-agnostic — it operates on plain
text and returns plain text, so it can be reused for Reddit, Google
Search Console, or any future source without modification.
"""

import re
from dataclasses import dataclass, field

import spacy

# Load once at import time — loading the model is expensive, so we
# don't want to do it per-call.
_nlp = spacy.load("en_core_web_sm")

# spaCy entity labels we treat as PII and mask.
# GPE = geopolitical entity (cities, countries, states)
# LOC = non-GPE locations (mountain ranges, bodies of water, etc.)
# PERSON = names
# ORG = organizations (can leak identifying info, e.g. small employer)
PII_ENTITY_LABELS = {"PERSON", "GPE", "LOC", "ORG"}

# Regex patterns for structured PII that NER commonly misses.
# Order matters: more specific patterns should run before general ones.
REGEX_PATTERNS = {
    "EMAIL": re.compile(r"[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}"),
    "PHONE": re.compile(
        r"(\+?\d{1,2}[\s.-]?)?\(?\d{3}\)?[\s.-]?\d{3}[\s.-]?\d{4}"
    ),
    "REDDIT_USER": re.compile(r"/?u/[A-Za-z0-9_-]+"),
    "SUBREDDIT": re.compile(r"/?r/[A-Za-z0-9_-]+"),
    "HANDLE": re.compile(r"@[A-Za-z0-9_]+"),
    "URL": re.compile(r"https?://\S+"),
}


@dataclass
class MaskResult:
    """Result of masking a piece of text."""

    masked_text: str
    entities_found: dict[str, int] = field(default_factory=dict)

    def total_redactions(self) -> int:
        return sum(self.entities_found.values())


def _apply_regex_masks(text: str, counts: dict[str, int]) -> str:
    """Apply all regex-based PII patterns, tracking counts per type."""
    for label, pattern in REGEX_PATTERNS.items():
        matches = pattern.findall(text)
        if matches:
            counts[label] = counts.get(label, 0) + len(matches)
            text = pattern.sub(f"[{label}_REDACTED]", text)
    return text


def _apply_ner_masks(text: str, counts: dict[str, int]) -> str:
    """Apply spaCy NER-based masking for names, locations, orgs."""
    doc = _nlp(text)

    # Collect spans to replace. We build the new string from the end
    # backward so earlier character offsets don't shift as we edit.
    spans_to_mask = [
        (ent.start_char, ent.end_char, ent.label_)
        for ent in doc.ents
        if ent.label_ in PII_ENTITY_LABELS
    ]

    for start, end, label in sorted(spans_to_mask, key=lambda s: s[0], reverse=True):
        counts[label] = counts.get(label, 0) + 1
        text = text[:start] + f"[{label}_REDACTED]" + text[end:]

    return text


def mask_text(raw_text: str) -> MaskResult:
    """
    Strip PII from a block of text using regex first, then NER.

    Regex runs first because it's cheap and catches high-confidence,
    structured patterns (emails, handles) that would otherwise
    confuse or slow down the NER pass. NER then catches everything
    contextual — names and locations mentioned in plain prose.
    """
    counts: dict[str, int] = {}

    text = _apply_regex_masks(raw_text, counts)
    text = _apply_ner_masks(text, counts)

    return MaskResult(masked_text=text, entities_found=counts)