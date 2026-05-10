import json
import logging
import re
from prompts import PROFILER_PROMPT, STRATEGIST_PROMPT, STORYTELLER_PROMPT, AUDITOR_PROMPT

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Mock LLM — replace call_llm() body with a real API call (Claude, Gemma, etc.)
# when an LLM API key is available. The pipeline orchestration stays the same.
# ---------------------------------------------------------------------------

_PILLAR_KEYWORDS: dict[str, list[str]] = {
    "Financial": ["money", "debt", "cash", "financial", "bank", "broke", "savings", "income", "bills", "rent"],
    "Spiritual": ["drift", "purpose", "blur", "lost", "meaning", "faith", "prayer", "soul", "peace", "direction"],
    "Craft/Career": ["work", "career", "job", "coding", "skill", "master", "craft", "business", "project", "build"],
    "Emotional/Intimacy": ["relationship", "partner", "lonely", "love", "connection", "heartbreak", "heartbroken", "intimacy", "feelings", "hurt", "sad"],
    "Intellectual": ["read", "learn", "study", "book", "idea", "think", "understand", "knowledge", "curious", "philosophy"],
    "Legacy": ["future", "impact", "legacy", "mark", "purpose", "children", "family", "contribute", "world", "remember", "leave", "behind", "matters"],
    "Social": ["friend", "social", "tribe", "people", "alone", "community", "network", "isolation", "group", "disconnect"],
}

# Pre-compiled word-boundary patterns to avoid substring false positives (e.g. "broke" in "heartbroken")
_PILLAR_PATTERNS: dict[str, re.Pattern] = {
    pillar: re.compile(r'\b(' + '|'.join(re.escape(k) for k in keywords) + r')\b')
    for pillar, keywords in _PILLAR_KEYWORDS.items()
}

_STORIES: dict[str, str] = {
    "Financial": (
        "Marcus Aurelius ruled the known world but lived simply. He proved that true security "
        "comes from the strength of the mind, not the size of the treasury."
    ),
    "Spiritual": (
        "The Stoics taught that when you are lost in the storm, you don't fight the wind — "
        "you adjust your sails. Clarity comes from action, not from thinking."
    ),
    "Craft/Career": (
        "The Japanese concept of Kaizen teaches that greatness is not a leap, but a thousand "
        "tiny steps of improvement. Every hour of mastery is a brick in your fortress."
    ),
    "Emotional/Intimacy": (
        "Achilles was the greatest warrior of his age, yet it was grief — raw, unfiltered emotion "
        "— that revealed his true depth. Strength and feeling are not opposites."
    ),
    "Intellectual": (
        "Da Vinci filled 13,000 pages of notebooks not because he was told to, but because "
        "curiosity was his weapon. The sharpest minds are the ones that never stop asking why."
    ),
    "Legacy": (
        "Frederick Douglass escaped slavery with nothing but will and words. Decades later, "
        "those words rewrote the laws of a nation. Your actions today are the seeds of tomorrow's world."
    ),
    "Social": (
        "The Spartans didn't seek comfort — they sought strength in their phalanx. "
        "A man alone is a target. A man with a tribe is a force."
    ),
}


def _detect_pillar(text: str) -> str:
    text_lower = text.lower()
    for pillar, pattern in _PILLAR_PATTERNS.items():
        if pattern.search(text_lower):
            return pillar
    return "Social"


def call_llm(system_prompt: str, user_input: str) -> str:
    """
    Stub LLM. Replace this function body with a real API call.
    The surrounding pipeline logic does not need to change.
    """
    # Use the opening line to identify persona — avoids false matches when one
    # prompt references another (e.g. Strategist prompt mentions "Profiler").
    first_line = system_prompt.strip().splitlines()[0] if system_prompt else ""

    try:
        if "Profiler" in first_line:
            pillar = _detect_pillar(user_input)
            state = "negative" if pillar in ("Financial", "Spiritual", "Emotional/Intimacy") else "neutral"
            return json.dumps({
                "pillar": pillar,
                "state": state,
                "core_issue": f"User is working through {pillar.lower()} challenges",
                "fact": "Extracted from journal entry",
            })

        if "Strategist" in first_line:
            data = json.loads(user_input)
            momentum = "Paused" if data.get("state") == "negative" else "Moving"
            return json.dumps({
                "priority_pillar": data.get("pillar", "Social"),
                "momentum": momentum,
                "strategic_goal": f"Address {data.get('core_issue', 'current challenges')}",
            })

        if "Storyteller" in first_line:
            strategy = json.loads(user_input)
            pillar = strategy.get("priority_pillar", "Social")
            return _STORIES.get(pillar, "The greatest battles are won before they are fought — through discipline and resolve.")

        if "Auditor" in first_line:
            return f"Listen. {user_input} Stop worrying about the noise and focus on the work. That's how you win."

    except (json.JSONDecodeError, KeyError) as e:
        logger.error("LLM stub error for prompt type: %s", e)

    return "Focus on what you can control today. Everything else is noise."


class ArchitectPipeline:
    def process_journal(self, journal_text: str) -> dict:
        logger.info("Processing journal entry (length=%d)", len(journal_text))

        try:
            profile_json = call_llm(PROFILER_PROMPT, journal_text)
            profile = json.loads(profile_json)
        except (json.JSONDecodeError, Exception) as e:
            logger.error("Profiler stage failed: %s", e)
            profile = {"pillar": "Social", "state": "neutral", "core_issue": "General reflection"}

        try:
            strategy_json = call_llm(STRATEGIST_PROMPT, json.dumps(profile))
            strategy = json.loads(strategy_json)
        except (json.JSONDecodeError, Exception) as e:
            logger.error("Strategist stage failed: %s", e)
            strategy = {"priority_pillar": profile.get("pillar", "Social"), "momentum": "Paused"}

        try:
            story = call_llm(STORYTELLER_PROMPT, json.dumps(strategy))
        except Exception as e:
            logger.error("Storyteller stage failed: %s", e)
            story = "Discipline is the bridge between goals and accomplishment."

        try:
            final_message = call_llm(AUDITOR_PROMPT, story)
        except Exception as e:
            logger.error("Auditor stage failed: %s", e)
            final_message = story

        return {
            "message": final_message,
            "pillar": profile.get("pillar", "Social"),
            "momentum": strategy.get("momentum", "Paused"),
        }
