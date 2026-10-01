import pytest

from app.services.pii_masker import mask_text, strip_reddit_html


def run(text: str) -> str:
    masked, _entities = mask_text(strip_reddit_html(text))
    return masked


def known_gap(reason: str):
    """A gap I have already seen on real data. Shows up as 'xfail', not a failure."""
    return pytest.mark.xfail(reason=reason, strict=False)


# (id, text, strings that must NOT survive masking)
MUST_MASK = [
    ("name_intro", "Hey guys! I'm Jojo. I'm looking into switching phones.", ["Jojo"]),
    ("name_full", "My name is Priya Raman and I use JAWS at work.", ["Priya", "Raman"]),
    ("name_call_me", "Call me Marcus, I've been blind since birth.", ["Marcus"]),
    ("name_family", "My mom, Linda, drives me to appointments every week.", ["Linda"]),
    ("email", "You can reach me at jane.doe@example.com anytime.", ["jane.doe@example.com"]),
    ("phone_dashes", "Call me at 555-123-4567 after 5.", ["555-123-4567"]),
    ("phone_parens", "Text me at (555) 867-5309 please.", ["867-5309"]),
    ("phone_intl", "My number is +1 555 123 4567.", ["123 4567"]),
    ("ssn_with_context", "My social security number is 219-09-9999.", ["219-09-9999"]),
    ("location_city_state", "I live in Portland, Oregon and the buses are not accessible.", ["Portland", "Oregon"]),
    ("url", "Details are here: https://www.example.com/profiles/jsmith", ["example.com", "jsmith"]),
    ("reddit_handle", "Thanks to u/BlindTechGuy for the tip!", ["BlindTechGuy"]),
    ("reddit_handle_slash", "Shout out to /u/screenreader_sam for the help.", ["screenreader_sam"]),
    ("at_handle", "Follow me @jsmith_blind for updates.", ["jsmith_blind"]),
    ("own_condition", "I was diagnosed with glaucoma last year.", ["glaucoma"]),
    (
        "rss_footer",
        '<!-- SC_OFF --><div class="md"><p>Hi, I\'m Dana and I need help with my new cane.</p></div>'
        '<!-- SC_ON --> &#32; submitted by &#32; <a href="https://www.reddit.com/user/dana_k_92"> '
        '/u/dana_k_92 </a> <span><a href="https://www.reddit.com/r/Blind/comments/abc/help/">[link]</a></span>',
        ["Dana", "dana_k_92"],
    ),
    pytest.param(
        "rare_condition", "I was diagnosed with stargardts at 20.", ["stargardts"],
        marks=known_gap("not in the 8-word stub vocabulary; needs a real clinical vocabulary"),
        id="rare_condition",
    ),
    pytest.param(
        "school", "My son is at GMU and having a hard time making friends.", ["GMU"],
        marks=known_gap("organizations are not in the entity list"),
        id="school",
    ),
]


@pytest.mark.parametrize(
    "case_id, text, forbidden",
    [c if isinstance(c, tuple) else c.values for c in MUST_MASK],
    ids=[c[0] if isinstance(c, tuple) else c.id for c in MUST_MASK],
)
def test_personal_information_is_removed(case_id, text, forbidden):
    masked = run(text)
    leaked = [s for s in forbidden if s.lower() in masked.lower()]
    assert not leaked, f"LEAK: {leaked} still present in: {masked!r}"


# (id, text, strings that MUST still be there: over-masking destroys the signal)
MUST_KEEP = [
    ("timeline", "I'm going blind next year according to my surgeon.", ["next year"]),
    ("screen_reader_news", "NVDA 2026.2 is out with a new magnifier.", ["NVDA", "magnifier"]),
    ("products", "Does VoiceOver work well with Google Docs on a Mac?", ["VoiceOver", "Google Docs"]),
    ("braille", "I use an iPhone with VoiceOver and a braille display.", ["iPhone", "VoiceOver", "braille"]),
    ("family_condition", "My mother has diabetes but I don't.", ["diabetes"]),
    ("negated_condition", "Patient denies hypertension.", ["hypertension"]),
    pytest.param(
        "linux_orca", "Does anyone have experience with Orca on Linux?", ["Orca", "Linux"],
        marks=known_gap("Orca is read as a person and Linux as a location"),
        id="linux_orca",
    ),
    pytest.param(
        "guide_dog_school", "Can my own dog become a guide dog with Seeing Eye?", ["Seeing Eye"],
        marks=known_gap("'Seeing Eye' is read as a person"),
        id="guide_dog_school",
    ),
]


@pytest.mark.parametrize(
    "case_id, text, required",
    [c if isinstance(c, tuple) else c.values for c in MUST_KEEP],
    ids=[c[0] if isinstance(c, tuple) else c.id for c in MUST_KEEP],
)
def test_useful_content_is_kept(case_id, text, required):
    masked = run(text)
    lost = [s for s in required if s.lower() not in masked.lower()]
    assert not lost, f"OVER-MASKED: {lost} missing from: {masked!r}"