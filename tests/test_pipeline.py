import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'web_app'))

import json
import pytest
from pipeline import ArchitectPipeline, call_llm, _detect_pillar
from prompts import PROFILER_PROMPT, STRATEGIST_PROMPT, STORYTELLER_PROMPT, AUDITOR_PROMPT


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
# call_llm — profiler
# ---------------------------------------------------------------------------

def test_call_llm_profiler_returns_valid_json():
    result = call_llm(PROFILER_PROMPT, "I'm drowning in debt")
    parsed = json.loads(result)
    assert "pillar" in parsed
    assert "state" in parsed
    assert "core_issue" in parsed


def test_call_llm_profiler_detects_financial():
    result = call_llm(PROFILER_PROMPT, "I can't pay my bills this month")
    parsed = json.loads(result)
    assert parsed["pillar"] == "Financial"


# ---------------------------------------------------------------------------
# call_llm — strategist
# ---------------------------------------------------------------------------

def test_call_llm_strategist_returns_valid_json():
    profile = json.dumps({"pillar": "Financial", "state": "negative", "core_issue": "Debt"})
    result = call_llm(STRATEGIST_PROMPT, profile)
    parsed = json.loads(result)
    assert "priority_pillar" in parsed
    assert "momentum" in parsed


def test_call_llm_strategist_negative_state_sets_paused():
    profile = json.dumps({"pillar": "Spiritual", "state": "negative", "core_issue": "Lost"})
    result = call_llm(STRATEGIST_PROMPT, profile)
    parsed = json.loads(result)
    assert parsed["momentum"] == "Paused"


def test_call_llm_strategist_positive_state_sets_moving():
    profile = json.dumps({"pillar": "Craft/Career", "state": "positive", "core_issue": "Growth"})
    result = call_llm(STRATEGIST_PROMPT, profile)
    parsed = json.loads(result)
    assert parsed["momentum"] == "Moving"


# ---------------------------------------------------------------------------
# call_llm — storyteller
# ---------------------------------------------------------------------------

def test_call_llm_storyteller_returns_string():
    strategy = json.dumps({"priority_pillar": "Financial", "momentum": "Paused"})
    result = call_llm(STORYTELLER_PROMPT, strategy)
    assert isinstance(result, str)
    assert len(result) > 10


def test_call_llm_storyteller_covers_all_pillars():
    pillars = ["Financial", "Spiritual", "Craft/Career", "Emotional/Intimacy",
               "Intellectual", "Legacy", "Social"]
    for pillar in pillars:
        strategy = json.dumps({"priority_pillar": pillar, "momentum": "Paused"})
        result = call_llm(STORYTELLER_PROMPT, strategy)
        assert isinstance(result, str) and len(result) > 5, f"No story for pillar: {pillar}"


# ---------------------------------------------------------------------------
# ArchitectPipeline.process_journal
# ---------------------------------------------------------------------------

def test_process_journal_returns_required_keys():
    pipeline = ArchitectPipeline()
    result = pipeline.process_journal("I'm struggling with money and can't focus")
    assert "message" in result
    assert "pillar" in result
    assert "momentum" in result


def test_process_journal_empty_string_does_not_crash():
    pipeline = ArchitectPipeline()
    result = pipeline.process_journal("")
    assert isinstance(result.get("message"), str)


def test_process_journal_momentum_is_valid():
    pipeline = ArchitectPipeline()
    result = pipeline.process_journal("I feel lost and disconnected from everything")
    assert result["momentum"] in ("Moving", "Paused")


def test_process_journal_pillar_is_known():
    known_pillars = {"Social", "Financial", "Spiritual", "Craft/Career",
                     "Emotional/Intimacy", "Intellectual", "Legacy"}
    pipeline = ArchitectPipeline()
    result = pipeline.process_journal("Working on my craft every single day")
    assert result["pillar"] in known_pillars
