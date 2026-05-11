import json
import logging
import re
import urllib.request
import urllib.error
from config import GEMINI_API_KEY
from prompts import (
    PROFILER_PROMPT, PATTERN_TRACKER_PROMPT, STRATEGIST_PROMPT,
    STORYTELLER_PROMPT, MENTOR_PROMPT, AUDITOR_PROMPT,
    EXTRACTOR_PROMPT, WEEKLY_REVIEW_PROMPT, MONTHLY_REVIEW_PROMPT,
)
from context import UserContext

logger = logging.getLogger(__name__)

GEMINI_MODEL = "gemini-2.5-flash"
_GEMINI_BASE = (
    f"https://generativelanguage.googleapis.com/v1beta/models/{GEMINI_MODEL}:generateContent"
)

# ---------------------------------------------------------------------------
# Mock fallback
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

_PILLAR_PATTERNS: dict[str, re.Pattern] = {
    pillar: re.compile(r'\b(' + '|'.join(re.escape(k) for k in keywords) + r')\b')
    for pillar, keywords in _PILLAR_KEYWORDS.items()
}

_MENTOR_DIRECTIVES: dict[str, str] = {
    "Financial":          "Open your banking app right now and move whatever you can — even a small amount — into savings before you close this.",
    "Social":             "Text one person you have been meaning to reach out to before you put your phone down.",
    "Spiritual":          "Before you sleep tonight, sit in silence for five minutes — no phone, no music, nothing.",
    "Craft/Career":       "Block two uninterrupted hours in your calendar this week for deep work on your craft and protect them like a non-negotiable appointment.",
    "Emotional/Intimacy": "Have one real conversation today — not small talk, not logistics, something that actually matters to both of you.",
    "Intellectual":       "Pick up the book or article you have been meaning to read and commit to 20 pages before tonight.",
    "Legacy":             "Write down one action you could take this week that will still matter in ten years.",
}

_STORIES: dict[str, str] = {
    "Financial": "Marcus Aurelius ruled the known world but lived simply. He proved that true security comes from the strength of the mind, not the size of the treasury.",
    "Spiritual": "The Stoics taught that when you are lost in the storm, you don't fight the wind — you adjust your sails. Clarity comes from action, not from thinking.",
    "Craft/Career": "The Japanese concept of Kaizen teaches that greatness is not a leap, but a thousand tiny steps of improvement. Every hour of mastery is a brick in your fortress.",
    "Emotional/Intimacy": "Achilles was the greatest warrior of his age, yet it was grief — raw, unfiltered emotion — that revealed his true depth. Strength and feeling are not opposites.",
    "Intellectual": "Da Vinci filled 13,000 pages of notebooks not because he was told to, but because curiosity was his weapon. The sharpest minds never stop asking why.",
    "Legacy": "Frederick Douglass escaped slavery with nothing but will and words. Decades later, those words rewrote the laws of a nation. Your actions today are the seeds of tomorrow's world.",
    "Social": "The Spartans didn't seek comfort — they sought strength in their phalanx. A man alone is a target. A man with a tribe is a force.",
}


def _detect_pillar(text: str) -> str:
    text_lower = text.lower()
    for pillar, pattern in _PILLAR_PATTERNS.items():
        if pattern.search(text_lower):
            return pillar
    return "Social"


def _extract_journal_section(text: str) -> str:
    """Pull out the raw journal text from a context-enriched input string."""
    marker = "=== TODAY'S JOURNAL ENTRY ==="
    if marker in text:
        return text.split(marker, 1)[1].strip()
    return text


def _mock_llm(system_prompt: str, user_input: str) -> str:
    first_line = system_prompt.strip().splitlines()[0] if system_prompt else ""
    journal = _extract_journal_section(user_input)
    try:
        if "Pattern Tracker" in first_line:
            try:
                data = json.loads(user_input.split("\n")[1]) if user_input.strip().startswith("===") else json.loads(user_input)
            except Exception:
                data = {}
            pillar = data.get("pillar", "Social")
            return json.dumps({
                "trend": f"{pillar} has been the recurring theme across recent entries.",
                "neglected_pillar": "Spiritual",
                "repeat_theme": f"Avoidance of taking concrete action on {pillar.lower()} rather than just reflecting on it.",
            })
        if "Profiler" in first_line:
            pillar = _detect_pillar(journal)
            state = "negative" if pillar in ("Financial", "Spiritual", "Emotional/Intimacy") else "neutral"
            return json.dumps({
                "pillar": pillar,
                "state": state,
                "core_issue": f"User is working through {pillar.lower()} challenges",
                "fact": "Extracted from journal entry",
            })
        if "Strategist" in first_line:
            data = json.loads(user_input) if user_input.strip().startswith("{") else {}
            momentum = "Paused" if data.get("state") == "negative" else "Moving"
            return json.dumps({
                "priority_pillar": data.get("pillar", "Social"),
                "momentum": momentum,
                "strategic_goal": f"Address {data.get('core_issue', 'current challenges')}",
            })
        if "Storyteller" in first_line:
            try:
                strategy = json.loads(user_input) if user_input.strip().startswith("{") else {}
            except json.JSONDecodeError:
                strategy = {}
            pillar = strategy.get("priority_pillar", "Social")
            return _STORIES.get(pillar, "The greatest battles are won before they are fought — through discipline and resolve.")
        if "Mentor" in first_line:
            try:
                lines = [l for l in user_input.splitlines() if l.strip().startswith("{")]
                data = json.loads(lines[0]) if lines else {}
            except Exception:
                data = {}
            pillar = data.get("priority_pillar", "Social")
            return _MENTOR_DIRECTIVES.get(pillar, "Do the one thing you have been putting off — today, not tomorrow.")
        if "Auditor" in first_line:
            return f"Listen. {user_input} Stop worrying about the noise and focus on the work. That's how you win."
        if "Memory Keeper" in first_line:
            return json.dumps({"new_facts": []})
        if "Manager" in first_line:
            return json.dumps({
                "moved": ["You showed up and wrote this week."],
                "stalled": ["Several pillars remain untouched — no entries, no movement."],
                "pattern": "You are engaging with the process. The question is whether engagement is translating into real action outside these walls.",
                "directive": "Pick one paused pillar and take one concrete action on it before this week ends.",
            })
        if "Architect" in first_line:
            return json.dumps({
                "pillars_moved": ["Craft/Career — consistent engagement with daily work."],
                "pillars_neglected": ["Spiritual — no entries, no reflection, no movement."],
                "blind_spot": "You treat busyness as progress. Every entry is about what you did — almost none are about who you are becoming. Activity is not the same as direction.",
                "architectural_decision": "Dedicate the first 20 minutes of every Sunday to answering one question in writing: is where I am heading still where I want to go?",
            })
    except (json.JSONDecodeError, KeyError) as e:
        logger.error("Mock LLM error: %s", e)
    return "Focus on what you can control today. Everything else is noise."


# ---------------------------------------------------------------------------
# Gemini REST call
# ---------------------------------------------------------------------------

def _call_gemini(system_prompt: str, user_input: str, json_mode: bool = False) -> str:
    url = f"{_GEMINI_BASE}?key={GEMINI_API_KEY}"
    body: dict = {
        "system_instruction": {"parts": [{"text": system_prompt}]},
        "contents": [{"role": "user", "parts": [{"text": user_input}]}],
    }
    if json_mode:
        body["generationConfig"] = {"responseMimeType": "application/json"}

    req = urllib.request.Request(
        url,
        data=json.dumps(body).encode(),
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=30) as resp:
        data = json.loads(resp.read())

    return data["candidates"][0]["content"]["parts"][0]["text"]


def call_llm(system_prompt: str, user_input: str, json_mode: bool = False) -> str:
    if not GEMINI_API_KEY:
        logger.debug("No GEMINI_API_KEY — using mock LLM.")
        return _mock_llm(system_prompt, user_input)

    try:
        result = _call_gemini(system_prompt, user_input, json_mode=json_mode)
        logger.debug("Gemini response received (json_mode=%s)", json_mode)
        return result
    except urllib.error.HTTPError as e:
        body = e.read().decode()
        logger.error("Gemini HTTP %d: %s — falling back to mock", e.code, body)
    except Exception as e:
        logger.error("Gemini call failed: %s — falling back to mock", e)

    return _mock_llm(system_prompt, user_input)


# ---------------------------------------------------------------------------
# Input builders — assemble context-enriched strings for each pipeline stage
# ---------------------------------------------------------------------------

def _profiler_input(journal_text: str, ctx: UserContext | None) -> str:
    if not ctx:
        return journal_text
    return f"{ctx.format()}\n\n=== TODAY'S JOURNAL ENTRY ===\n{journal_text}"


def _pattern_tracker_input(profile: dict, ctx: UserContext | None) -> str:
    lines = [f"=== TODAY'S PROFILE ===\n{json.dumps(profile)}"]
    if ctx and ctx.pillar_states:
        lines.append("\n=== PILLAR STATES ===")
        for p in sorted(ctx.pillar_states, key=lambda x: x["days_in_state"], reverse=True):
            lines.append(f"- {p['name']}: {p['status']} for {p['days_in_state']} days")
    if ctx and ctx.recent_entries:
        lines.append("\n=== RECENT ENTRIES ===")
        for i, entry in enumerate(ctx.recent_entries[:3]):
            lines.append(f"Entry {i + 1}: {entry[:300]}")
    return "\n".join(lines)


def _strategist_input(profile: dict, ctx: UserContext | None, trends: dict | None = None) -> str:
    base = f"=== PROFILE FROM TODAY'S ENTRY ===\n{json.dumps(profile)}"
    if trends:
        base += f"\n\n=== PATTERN ANALYSIS ===\n{json.dumps(trends)}"
    if not ctx or not ctx.pillar_states:
        return base
    trend_lines = ["", "=== PILLAR TREND DATA ==="]
    for p in sorted(ctx.pillar_states, key=lambda x: x["days_in_state"], reverse=True):
        trend_lines.append(f"- {p['name']}: {p['status']} for {p['days_in_state']} days")
    if ctx.user_facts:
        trend_lines.append("\n=== USER FACTS ===")
        for f in ctx.user_facts:
            trend_lines.append(f"- {f}")
    return base + "\n".join(trend_lines)


def _mentor_input(strategy: dict, story: str, ctx: UserContext | None) -> str:
    lines = [
        f"=== STRATEGIC PRIORITY ===\n{json.dumps(strategy)}",
        f"\n=== TODAY'S HERO STORY ===\n{story}",
    ]
    if ctx and ctx.user_facts:
        lines.append("\n=== WHO THIS PERSON IS ===")
        for f in ctx.user_facts:
            lines.append(f"- {f}")
    return "\n".join(lines)


def _storyteller_input(strategy: dict, ctx: UserContext | None) -> str:
    base = f"=== STRATEGIC PRIORITY ===\n{json.dumps(strategy)}"
    if not ctx or not ctx.user_facts:
        return base
    fact_lines = ["\n\n=== WHO THIS PERSON IS ==="]
    for f in ctx.user_facts:
        fact_lines.append(f"- {f}")
    return base + "\n".join(fact_lines)


def _weekly_review_input(entries: list[dict], ctx: UserContext) -> str:
    lines = ["=== WEEKLY REVIEW CONTEXT ==="]
    lines.append(f"Total sessions to date: {ctx.entry_count}")

    if ctx.user_facts:
        lines.append("\nUser facts:")
        for f in ctx.user_facts:
            lines.append(f"- {f}")

    if ctx.pillar_states:
        lines.append("\nPillar states:")
        for p in sorted(ctx.pillar_states, key=lambda x: x["days_in_state"], reverse=True):
            lines.append(f"- {p['name']}: {p['status']} ({p['days_in_state']} days)")

    lines.append(f"\n=== JOURNAL ENTRIES THIS WEEK ({len(entries)} entries) ===")
    for e in entries:
        lines.append(f"\n[{e['date']}]:\n{e['content']}")

    return "\n".join(lines)


def _monthly_review_input(entries: list[dict], ctx: UserContext) -> str:
    lines = ["=== MONTHLY REVIEW CONTEXT ==="]
    lines.append(f"Total sessions to date: {ctx.entry_count}")

    if ctx.user_facts:
        lines.append("\nUser facts:")
        for f in ctx.user_facts:
            lines.append(f"- {f}")

    if ctx.pillar_states:
        lines.append("\nPillar states (30-day snapshot):")
        for p in sorted(ctx.pillar_states, key=lambda x: x["days_in_state"], reverse=True):
            lines.append(f"- {p['name']}: {p['status']} ({p['days_in_state']} days in this state)")

    lines.append(f"\n=== JOURNAL ENTRIES THIS MONTH ({len(entries)} entries) ===")
    for e in entries:
        lines.append(f"\n[{e['date']}]:\n{e['content']}")

    return "\n".join(lines)


def _extractor_input(journal_text: str, existing_facts: list[str]) -> str:
    facts_section = "\n".join(f"- {f}" for f in existing_facts) if existing_facts else "None yet."
    return (
        f"=== EXISTING USER FACTS ===\n{facts_section}"
        f"\n\n=== TODAY'S JOURNAL ENTRY ===\n{journal_text}"
    )


# ---------------------------------------------------------------------------
# Pipeline
# ---------------------------------------------------------------------------

class ArchitectPipeline:

    def process_journal(self, journal_text: str, ctx: UserContext | None = None) -> dict:
        logger.info("Processing journal (length=%d, has_context=%s)", len(journal_text), ctx is not None)

        # Stage 1: Profiler — what is this entry about?
        try:
            profile_json = call_llm(PROFILER_PROMPT, _profiler_input(journal_text, ctx), json_mode=True)
            profile = json.loads(profile_json)
        except Exception as e:
            logger.error("Profiler failed: %s", e)
            profile = {"pillar": "Social", "state": "neutral", "core_issue": "General reflection"}

        # Stage 2: Pattern Tracker — what trends are forming across entries?
        try:
            trends_json = call_llm(PATTERN_TRACKER_PROMPT, _pattern_tracker_input(profile, ctx), json_mode=True)
            trends = json.loads(trends_json)
        except Exception as e:
            logger.error("Pattern Tracker failed: %s", e)
            trends = None

        # Stage 3: Strategist — what should tomorrow focus on?
        try:
            strategy_json = call_llm(STRATEGIST_PROMPT, _strategist_input(profile, ctx, trends), json_mode=True)
            strategy = json.loads(strategy_json)
        except Exception as e:
            logger.error("Strategist failed: %s", e)
            strategy = {"priority_pillar": profile.get("pillar", "Social"), "momentum": "Paused"}

        # Stage 4: Storyteller — write the morning hero story
        try:
            story = call_llm(STORYTELLER_PROMPT, _storyteller_input(strategy, ctx))
        except Exception as e:
            logger.error("Storyteller failed: %s", e)
            story = "Discipline is the bridge between goals and accomplishment."

        # Stage 5: Auditor — sharpen the tone
        try:
            final_message = call_llm(AUDITOR_PROMPT, story)
        except Exception as e:
            logger.error("Auditor failed: %s", e)
            final_message = story

        # Stage 6: Mentor — one direct instruction
        try:
            directive = call_llm(MENTOR_PROMPT, _mentor_input(strategy, final_message, ctx))
        except Exception as e:
            logger.error("Mentor failed: %s", e)
            directive = "Do the one thing you have been putting off — today, not tomorrow."

        return {
            "message": final_message,
            "directive": directive.strip(),
            "pillar": profile.get("pillar", "Social"),
            "momentum": strategy.get("momentum", "Paused"),
        }

    def generate_weekly_review(self, entries: list[dict], ctx: UserContext) -> dict:
        logger.info("Generating weekly review (entries=%d)", len(entries))
        try:
            result_json = call_llm(
                WEEKLY_REVIEW_PROMPT,
                _weekly_review_input(entries, ctx),
                json_mode=True,
            )
            data = json.loads(result_json)
            return {
                "moved":     [str(x)[:300] for x in data.get("moved", []) if x],
                "stalled":   [str(x)[:300] for x in data.get("stalled", []) if x],
                "pattern":   str(data.get("pattern", ""))[:1000],
                "directive": str(data.get("directive", ""))[:300],
            }
        except Exception as e:
            logger.error("Weekly review generation failed: %s", e)
            return {
                "moved":     ["You showed up this week."],
                "stalled":   ["Not enough data to assess all pillars yet."],
                "pattern":   "Keep journaling — the patterns will emerge with more entries.",
                "directive": "Write your evening journal every day this week without missing.",
            }

    def generate_monthly_review(self, entries: list[dict], ctx: UserContext) -> dict:
        logger.info("Generating monthly review (entries=%d)", len(entries))
        try:
            result_json = call_llm(
                MONTHLY_REVIEW_PROMPT,
                _monthly_review_input(entries, ctx),
                json_mode=True,
            )
            data = json.loads(result_json)
            return {
                "pillars_moved":          [str(x)[:300] for x in data.get("pillars_moved", []) if x],
                "pillars_neglected":      [str(x)[:300] for x in data.get("pillars_neglected", []) if x],
                "blind_spot":             str(data.get("blind_spot", ""))[:1000],
                "architectural_decision": str(data.get("architectural_decision", ""))[:500],
            }
        except Exception as e:
            logger.error("Monthly review generation failed: %s", e)
            return {
                "pillars_moved":          ["Keep journaling — momentum will become visible with more entries."],
                "pillars_neglected":      ["Not enough data to assess neglect yet."],
                "blind_spot":             "The system needs more journal entries before it can identify your blind spots.",
                "architectural_decision": "Write every evening this week without exception.",
            }

    def extract_facts(self, journal_text: str, existing_facts: list[str]) -> list[str]:
        logger.info("Running fact extraction (existing_facts=%d)", len(existing_facts))
        try:
            result_json = call_llm(
                EXTRACTOR_PROMPT,
                _extractor_input(journal_text, existing_facts),
                json_mode=True,
            )
            data = json.loads(result_json)
            facts = data.get("new_facts", [])
            # Sanitise: strings only, max 500 chars each
            return [str(f)[:500] for f in facts if f and isinstance(f, str)]
        except Exception as e:
            logger.error("Fact extraction failed: %s", e)
            return []
