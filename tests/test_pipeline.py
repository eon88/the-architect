import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'web_app'))

import json
import pytest
from pipeline import ArchitectPipeline, call_llm, _detect_pillar, _extract_journal_section
from prompts import (PROFILER_PROMPT, PATTERN_TRACKER_PROMPT, STRATEGIST_PROMPT,
                     STORYTELLER_PROMPT, MENTOR_PROMPT, AUDITOR_PROMPT, EXTRACTOR_PROMPT)
from context import UserContext


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def make_context(**kwargs) -> UserContext:
    defaults = dict(
        entry_count=3,
        recent_entries=["I was stressed about debt.", "Had a decent day."],
        pillar_states=[
            {"name": "Financial", "status": "Paused", "days_in_state": 10},
            {"name": "Social", "status": "Moving", "days_in_state": 2},
            {"name": "Spiritual", "status": "Paused", "days_in_state": 5},
            {"name": "Craft/Career", "status": "Paused", "days_in_state": 1},
            {"name": "Emotional/Intimacy", "status": "Paused", "days_in_state": 1},
            {"name": "Intellectual", "status": "Paused", "days_in_state": 1},
            {"name": "Legacy", "status": "Paused", "days_in_state": 1},
        ],
        user_facts=["works in software engineering", "has credit card debt"],
    )
    defaults.update(kwargs)
    return UserContext(**defaults)


# ---------------------------------------------------------------------------
# _extract_journal_section
# ---------------------------------------------------------------------------

def test_extract_journal_section_with_marker():
    text = "=== USER CONTEXT ===\nsome stuff\n\n=== TODAY'S JOURNAL ENTRY ===\nActual journal"
    assert _extract_journal_section(text) == "Actual journal"


def test_extract_journal_section_without_marker():
    text = "Just a plain journal entry"
    assert _extract_journal_section(text) == "Just a plain journal entry"


# ---------------------------------------------------------------------------
# _detect_pillar
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("text,expected", [
    ("I'm really stressed about my credit card debt", "Financial"),
    ("I feel lost and have no sense of purpose", "Spiritual"),
    ("I've been grinding on my coding project all week", "Craft/Career"),
    ("My relationship fell apart and I'm heartbroken", "Emotional/Intimacy"),
    ("I read three books this month and feel alive", "Intellectual"),
    ("I want to leave something behind that matters", "Legacy"),
    ("I feel so alone and disconnected from my friends", "Social"),
    ("today was fine", "Social"),  # fallback
])
def test_detect_pillar(text, expected):
    assert _detect_pillar(text) == expected


# ---------------------------------------------------------------------------
# UserContext.format()
# ---------------------------------------------------------------------------

def test_context_format_contains_facts():
    ctx = make_context(user_facts=["works in tech", "has a dog"])
    formatted = ctx.format()
    assert "works in tech" in formatted
    assert "has a dog" in formatted


def test_context_format_contains_pillar_states():
    ctx = make_context()
    formatted = ctx.format()
    assert "Financial" in formatted
    assert "Paused" in formatted


def test_context_format_no_facts_shows_placeholder():
    ctx = make_context(user_facts=[])
    formatted = ctx.format()
    assert "none yet" in formatted.lower()


# ---------------------------------------------------------------------------
# call_llm — mock (no API key set in test env)
# ---------------------------------------------------------------------------

def test_call_llm_pattern_tracker_returns_valid_json():
    profile = json.dumps({"pillar": "Financial", "state": "negative", "core_issue": "Debt"})
    result = call_llm(PATTERN_TRACKER_PROMPT, profile, json_mode=True)
    parsed = json.loads(result)
    assert "trend" in parsed
    assert "neglected_pillar" in parsed
    assert "repeat_theme" in parsed


def test_call_llm_pattern_tracker_returns_strings():
    profile = json.dumps({"pillar": "Social", "state": "neutral", "core_issue": "Isolation"})
    result = call_llm(PATTERN_TRACKER_PROMPT, profile, json_mode=True)
    parsed = json.loads(result)
    for key in ("trend", "neglected_pillar", "repeat_theme"):
        assert isinstance(parsed[key], str) and len(parsed[key]) > 0


def test_call_llm_mentor_returns_string():
    strategy = json.dumps({"priority_pillar": "Financial", "momentum": "Paused"})
    result = call_llm(MENTOR_PROMPT, strategy)
    assert isinstance(result, str) and len(result) > 10


def test_call_llm_mentor_covers_all_pillars():
    pillars = ["Financial", "Spiritual", "Craft/Career", "Emotional/Intimacy",
               "Intellectual", "Legacy", "Social"]
    for pillar in pillars:
        strategy = json.dumps({"priority_pillar": pillar, "momentum": "Paused"})
        result = call_llm(MENTOR_PROMPT, strategy)
        assert isinstance(result, str) and len(result) > 5, f"No directive for pillar: {pillar}"


def test_call_llm_profiler_returns_valid_json():
    result = call_llm(PROFILER_PROMPT, "I'm drowning in debt", json_mode=True)
    parsed = json.loads(result)
    assert "pillar" in parsed
    assert "state" in parsed
    assert "core_issue" in parsed


def test_call_llm_profiler_with_context_enriched_input():
    ctx = make_context()
    enriched = f"{ctx.format()}\n\n=== TODAY'S JOURNAL ENTRY ===\nI can't pay my bills."
    result = call_llm(PROFILER_PROMPT, enriched, json_mode=True)
    parsed = json.loads(result)
    assert parsed["pillar"] == "Financial"


def test_call_llm_strategist_returns_valid_json():
    profile = json.dumps({"pillar": "Financial", "state": "negative", "core_issue": "Debt"})
    result = call_llm(STRATEGIST_PROMPT, profile, json_mode=True)
    parsed = json.loads(result)
    assert "priority_pillar" in parsed
    assert "momentum" in parsed


def test_call_llm_strategist_negative_state_sets_paused():
    profile = json.dumps({"pillar": "Spiritual", "state": "negative", "core_issue": "Lost"})
    result = call_llm(STRATEGIST_PROMPT, profile, json_mode=True)
    parsed = json.loads(result)
    assert parsed["momentum"] == "Paused"


def test_call_llm_strategist_positive_state_sets_moving():
    profile = json.dumps({"pillar": "Craft/Career", "state": "positive", "core_issue": "Growth"})
    result = call_llm(STRATEGIST_PROMPT, profile, json_mode=True)
    parsed = json.loads(result)
    assert parsed["momentum"] == "Moving"


def test_call_llm_storyteller_returns_string():
    strategy = json.dumps({"priority_pillar": "Financial", "momentum": "Paused"})
    result = call_llm(STORYTELLER_PROMPT, strategy)
    assert isinstance(result, str) and len(result) > 10


def test_call_llm_storyteller_covers_all_pillars():
    pillars = ["Financial", "Spiritual", "Craft/Career", "Emotional/Intimacy",
               "Intellectual", "Legacy", "Social"]
    for pillar in pillars:
        strategy = json.dumps({"priority_pillar": pillar, "momentum": "Paused"})
        result = call_llm(STORYTELLER_PROMPT, strategy)
        assert isinstance(result, str) and len(result) > 5, f"No story for pillar: {pillar}"


def test_call_llm_extractor_returns_valid_json():
    result = call_llm(EXTRACTOR_PROMPT, "=== EXISTING USER FACTS ===\nNone yet.\n\n=== TODAY'S JOURNAL ENTRY ===\nI work as a nurse.", json_mode=True)
    parsed = json.loads(result)
    assert "new_facts" in parsed
    assert isinstance(parsed["new_facts"], list)


# ---------------------------------------------------------------------------
# ArchitectPipeline.process_journal
# ---------------------------------------------------------------------------

def test_process_journal_returns_required_keys():
    p = ArchitectPipeline()
    result = p.process_journal("I'm struggling with money")
    assert "message" in result and "pillar" in result and "momentum" in result
    assert "directive" in result and isinstance(result["directive"], str) and len(result["directive"]) > 0


def test_process_journal_with_context():
    p = ArchitectPipeline()
    ctx = make_context()
    result = p.process_journal("I can't stop thinking about my debt.", ctx)
    assert result["pillar"] in {"Financial", "Social", "Spiritual", "Craft/Career",
                                "Emotional/Intimacy", "Intellectual", "Legacy"}
    assert result["momentum"] in ("Moving", "Paused")


def test_process_journal_empty_string_does_not_crash():
    p = ArchitectPipeline()
    result = p.process_journal("")
    assert isinstance(result.get("message"), str)


def test_process_journal_momentum_is_valid():
    p = ArchitectPipeline()
    result = p.process_journal("I feel lost and disconnected from everything")
    assert result["momentum"] in ("Moving", "Paused")


def test_process_journal_pillar_is_known():
    known = {"Social", "Financial", "Spiritual", "Craft/Career",
             "Emotional/Intimacy", "Intellectual", "Legacy"}
    p = ArchitectPipeline()
    result = p.process_journal("Working on my craft every single day")
    assert result["pillar"] in known


# ---------------------------------------------------------------------------
# ArchitectPipeline.extract_facts
# ---------------------------------------------------------------------------

def test_extract_facts_returns_list():
    p = ArchitectPipeline()
    result = p.extract_facts("I work as a nurse and go to the gym daily.", [])
    assert isinstance(result, list)


def test_extract_facts_no_crash_on_empty_entry():
    p = ArchitectPipeline()
    result = p.extract_facts("", ["works in tech"])
    assert isinstance(result, list)


def test_generate_weekly_review_returns_required_keys():
    p = ArchitectPipeline()
    ctx = make_context()
    entries = [
        {"date": "Monday 05 May", "content": "Stressed about bills."},
        {"date": "Tuesday 06 May", "content": "Had a good workout."},
    ]
    result = p.generate_weekly_review(entries, ctx)
    assert "moved" in result
    assert "stalled" in result
    assert "pattern" in result
    assert "directive" in result


def test_generate_weekly_review_no_crash_empty_entries():
    p = ArchitectPipeline()
    ctx = make_context(entry_count=0, recent_entries=[], user_facts=[])
    result = p.generate_weekly_review([], ctx)
    assert isinstance(result["directive"], str)


def test_generate_weekly_review_lists_are_lists():
    p = ArchitectPipeline()
    ctx = make_context()
    result = p.generate_weekly_review(
        [{"date": "Monday", "content": "I worked on my project all day."}], ctx
    )
    assert isinstance(result["moved"], list)
    assert isinstance(result["stalled"], list)


def test_extract_facts_strings_only():
    p = ArchitectPipeline()
    result = p.extract_facts("I am a carpenter building my own house.", [])
    for fact in result:
        assert isinstance(fact, str)
        assert len(fact) <= 500


# ---------------------------------------------------------------------------
# ArchitectPipeline.generate_monthly_review
# ---------------------------------------------------------------------------

def test_generate_monthly_review_returns_required_keys():
    p = ArchitectPipeline()
    ctx = make_context()
    entries = [
        {"date": "Monday 05 May", "content": "I grinded on work all month."},
        {"date": "Tuesday 13 May", "content": "Haven't seen friends in weeks."},
    ]
    result = p.generate_monthly_review(entries, ctx)
    assert "pillars_moved" in result
    assert "pillars_neglected" in result
    assert "blind_spot" in result
    assert "architectural_decision" in result


def test_generate_monthly_review_no_crash_empty_entries():
    p = ArchitectPipeline()
    ctx = make_context(entry_count=0, recent_entries=[], user_facts=[])
    result = p.generate_monthly_review([], ctx)
    assert isinstance(result["architectural_decision"], str)


def test_generate_monthly_review_lists_are_lists():
    p = ArchitectPipeline()
    ctx = make_context()
    result = p.generate_monthly_review(
        [{"date": "Monday", "content": "I worked on my project all month."}], ctx
    )
    assert isinstance(result["pillars_moved"], list)
    assert isinstance(result["pillars_neglected"], list)


def test_generate_monthly_review_strings_are_strings():
    p = ArchitectPipeline()
    ctx = make_context()
    result = p.generate_monthly_review(
        [{"date": "Monday", "content": "Focused month."}], ctx
    )
    assert isinstance(result["blind_spot"], str)
    assert isinstance(result["architectural_decision"], str)
