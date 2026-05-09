import json

PILLAR_KEYWORDS = {
    "Financial":           ["money", "debt", "cash", "income", "salary", "broke", "savings", "invest", "financial", "afford", "rent", "bills"],
    "Social":              ["friend", "lonely", "tribe", "people", "network", "community", "brother", "social", "relationship", "isolat", "alone"],
    "Spiritual":           ["purpose", "meaning", "drift", "lost", "faith", "soul", "direction", "blur", "spiritual", "meditat", "peace", "clarity"],
    "Craft/Career":        ["work", "job", "career", "skill", "craft", "build", "code", "create", "hustle", "business", "grind", "productiv", "focus"],
    "Emotional/Intimacy":  ["partner", "love", "intimacy", "emotion", "feel", "connect", "vulnerable", "trust", "relation", "hurt", "sad", "angry"],
    "Intellectual":        ["learn", "read", "think", "study", "book", "idea", "knowledge", "mind", "understand", "curious", "education"],
    "Legacy":              ["legacy", "impact", "future", "generation", "mission", "vision", "mark", "remember", "long-term", "purpose", "contribute"],
}

STORIES = {
    "Financial": (
        "Marcus Aurelius ruled an empire worth more than anything you can put in a bank, and he slept on the same hard bed as his soldiers. "
        "His wealth was in his discipline, not his treasury. The man who controls his spending controls his fate. "
        "What one financial decision, made today, would the future version of you thank you for?"
    ),
    "Social": (
        "The Spartans didn't build walls around Sparta — they built men. "
        "A warrior without a tribe is just a man with a sword. "
        "Look around your circle. Are these men sharpening you, or are they comfortable with you staying dull?"
    ),
    "Spiritual": (
        "The Stoics called it the 'inner citadel' — a place inside you that no circumstance can reach. "
        "Epictetus was a slave. He had nothing. Yet no man owned his mind. "
        "The fog you're feeling isn't weakness. It's a signal. Your soul is asking for direction. Give it one."
    ),
    "Craft/Career": (
        "Miyamoto Musashi fought 61 duels and never lost — not because he was born gifted, but because he treated every day as a training ground. "
        "He wrote: 'Do nothing that is of no use.' "
        "The work in front of you today is the duel. Show up like it matters, because it does."
    ),
    "Emotional/Intimacy": (
        "Achilles, the greatest warrior of his age, was undone not by a sword but by grief — the loss of the one person who truly knew him. "
        "Strength without the capacity to feel is just armour with nobody inside. "
        "The people in your life deserve your presence, not just your proximity."
    ),
    "Intellectual": (
        "Darwin spent 20 years quietly observing, reading, and thinking before he published a single word. "
        "His greatest weapon wasn't a lab — it was curiosity held long enough to become conviction. "
        "What idea have you been sitting with that's ready to be acted on?"
    ),
    "Legacy": (
        "Cincinnatus was given absolute power over Rome, defeated the enemy in 15 days, then returned to his farm. "
        "He didn't need the throne. He knew who he was building for. "
        "The question isn't what you want to achieve — it's what you want to leave behind."
    ),
}

def detect_pillar(text: str) -> tuple[str, str]:
    text_lower = text.lower()
    scores = {pillar: 0 for pillar in PILLAR_KEYWORDS}
    for pillar, keywords in PILLAR_KEYWORDS.items():
        for kw in keywords:
            if kw in text_lower:
                scores[pillar] += 1
    best = max(scores, key=lambda p: scores[p])
    # if nothing matched, fall back to Social
    if scores[best] == 0:
        best = "Social"
    negative_words = ["struggle", "fail", "can't", "stuck", "lost", "worried", "broke", "scared", "tired", "sad", "angry", "alone", "lonely", "debt", "behind"]
    state = "negative" if any(w in text_lower for w in negative_words) else "neutral"
    return best, state


class ArchitectPipeline:
    def process_journal(self, journal_text: str) -> dict:
        pillar, state = detect_pillar(journal_text)
        momentum = "Paused" if state == "negative" else "Moving"
        story = STORIES.get(pillar, STORIES["Social"])
        return {
            "message": story,
            "pillar": pillar,
            "momentum": momentum,
        }
