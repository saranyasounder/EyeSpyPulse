from app.services.pii_masker import strip_reddit_html, mask_text

TEST_CASES = [
    "Hey guys! I'm Jojo. I'm looking into switching phones.",
    "My name is Sarah and I live in Chicago.",
    "You can reach me at john.doe@example.com or call 555-123-4567.",
    "Check out this link: https://example.com/resource",
    "I met with Dr. Smith in Boston last week about my diagnosis.",
    "Hi, I'm going blind next year according to my surgeon.",
]

for text in TEST_CASES:
    masked, entities = mask_text(text)
    print(f"ORIGINAL: {text}")
    print(f"MASKED:   {masked}")
    print(f"ENTITIES: {entities}")
    print("-" * 60)