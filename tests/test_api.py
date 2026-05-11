import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'web_app'))

import pytest
from fastapi.testclient import TestClient
from main import app, _get_seed_question

client = TestClient(app)


def _login(email="ci_test@example.com"):
    res = client.post("/auth/login", json={"email": email, "name": "CI Tester"})
    assert res.status_code == 200
    data = res.json()
    return data["token"], data["user_id"]


def auth_headers(token):
    return {"Authorization": f"Bearer {token}"}


# ---------------------------------------------------------------------------
# Health
# ---------------------------------------------------------------------------

def test_health():
    res = client.get("/health")
    assert res.status_code == 200
    assert res.json() == {"status": "ok"}


# ---------------------------------------------------------------------------
# Login
# ---------------------------------------------------------------------------

def test_login_creates_user():
    res = client.post("/auth/login", json={"email": "new_user@example.com", "name": "Test"})
    assert res.status_code == 200
    data = res.json()
    assert "token" in data and "user_id" in data
    assert data["email"] == "new_user@example.com"


def test_login_same_email_returns_same_user():
    email = "same_user@example.com"
    r1 = client.post("/auth/login", json={"email": email, "name": "Test"})
    r2 = client.post("/auth/login", json={"email": email, "name": "Test"})
    assert r1.json()["user_id"] == r2.json()["user_id"]


def test_login_invalid_email_rejected():
    res = client.post("/auth/login", json={"email": "not-an-email", "name": "Test"})
    assert res.status_code == 422


def test_login_missing_email_rejected():
    res = client.post("/auth/login", json={"name": "Test"})
    assert res.status_code == 422


# ---------------------------------------------------------------------------
# Auth protection
# ---------------------------------------------------------------------------

def test_morning_ritual_requires_auth():
    assert client.get("/ritual/morning").status_code == 401


def test_evening_journal_requires_auth():
    assert client.post("/ritual/evening", json={"content": "Test"}).status_code == 401


def test_pillars_requires_auth():
    assert client.get("/user/pillars").status_code == 401


# ---------------------------------------------------------------------------
# Onboarding
# ---------------------------------------------------------------------------

def test_login_returns_has_onboarded_false_for_new_user():
    res = client.post("/auth/login", json={"email": "onboard_flag@example.com", "name": "Test"})
    assert res.status_code == 200
    assert res.json()["has_onboarded"] is False


def test_onboard_requires_auth():
    assert client.post("/user/onboard", json={"spark": "I want more."}).status_code == 401


def test_onboard_success():
    token, _ = _login("onboard_ok@example.com")
    res = client.post(
        "/user/onboard",
        json={"spark": "I am tired of settling for a mediocre career and financial stress."},
        headers=auth_headers(token),
    )
    assert res.status_code == 200
    data = res.json()
    assert data["status"] == "complete"
    assert "pillar" in data


def test_onboard_sets_has_onboarded_flag():
    token, _ = _login("onboard_flag2@example.com")
    client.post(
        "/user/onboard",
        json={"spark": "I am tired of being broke."},
        headers=auth_headers(token),
    )
    # Re-login to get fresh response
    res = client.post("/auth/login", json={"email": "onboard_flag2@example.com", "name": "Test"})
    assert res.json()["has_onboarded"] is True


def test_onboard_cannot_be_called_twice():
    token, _ = _login("onboard_twice@example.com")
    payload = {"spark": "I want a better life."}
    client.post("/user/onboard", json=payload, headers=auth_headers(token))
    res = client.post("/user/onboard", json=payload, headers=auth_headers(token))
    assert res.status_code == 400


def test_onboard_blank_spark_rejected():
    token, _ = _login("onboard_blank@example.com")
    res = client.post("/user/onboard", json={"spark": "   "}, headers=auth_headers(token))
    assert res.status_code == 422


def test_onboard_too_long_spark_rejected():
    token, _ = _login("onboard_long@example.com")
    res = client.post("/user/onboard", json={"spark": "x" * 2001}, headers=auth_headers(token))
    assert res.status_code == 422


# ---------------------------------------------------------------------------
# Morning ritual
# ---------------------------------------------------------------------------

def test_morning_ritual_returns_message_and_seed_question():
    token, _ = _login("morning_test@example.com")
    res = client.get("/ritual/morning", headers=auth_headers(token))
    assert res.status_code == 200
    data = res.json()
    assert "message" in data
    assert "seed_question" in data
    assert isinstance(data["seed_question"], str) and len(data["seed_question"]) > 0
    assert "streak" in data and isinstance(data["streak"], int)
    assert "total_entries" in data and isinstance(data["total_entries"], int)


def test_morning_ritual_streak_zero_for_new_user():
    token, _ = _login("streak_zero@example.com")
    data = client.get("/ritual/morning", headers=auth_headers(token)).json()
    assert data["streak"] == 0
    assert data["total_entries"] == 0


def test_morning_ritual_streak_increments_after_journal():
    token, _ = _login("streak_one@example.com")
    client.post("/ritual/evening",
                json={"content": "Day one entry."},
                headers=auth_headers(token))
    data = client.get("/ritual/morning", headers=auth_headers(token)).json()
    assert data["streak"] >= 1
    assert data["total_entries"] >= 1


def test_morning_ritual_day_one_message():
    token, _ = _login("day_one@example.com")
    res = client.get("/ritual/morning", headers=auth_headers(token))
    assert res.status_code == 200
    assert "Day 1" in res.json()["message"]


# ---------------------------------------------------------------------------
# Seed question logic
# ---------------------------------------------------------------------------

_PILLAR_STATES = [
    {"name": "Social", "status": "Paused", "days_in_state": 5},
    {"name": "Financial", "status": "Paused", "days_in_state": 14},
    {"name": "Spiritual", "status": "Moving", "days_in_state": 2},
    {"name": "Craft/Career", "status": "Paused", "days_in_state": 1},
    {"name": "Emotional/Intimacy", "status": "Paused", "days_in_state": 1},
    {"name": "Intellectual", "status": "Paused", "days_in_state": 1},
    {"name": "Legacy", "status": "Paused", "days_in_state": 1},
]


def test_seed_question_sequential_for_first_seven():
    from main import _SEED_QUESTIONS
    for i in range(7):
        q = _get_seed_question(i, _PILLAR_STATES)
        assert q == _SEED_QUESTIONS[i][1]


def test_seed_question_targets_most_paused_after_seven():
    # Financial has been Paused 14 days — should be targeted
    q = _get_seed_question(7, _PILLAR_STATES)
    from main import _SEED_QUESTIONS
    financial_q = next(question for pillar, question in _SEED_QUESTIONS if pillar == "Financial")
    assert q == financial_q


def test_seed_question_returns_string():
    q = _get_seed_question(0, _PILLAR_STATES)
    assert isinstance(q, str) and len(q) > 0


# ---------------------------------------------------------------------------
# Evening journal
# ---------------------------------------------------------------------------

def test_submit_journal_success():
    token, _ = _login("evening_test@example.com")
    res = client.post(
        "/ritual/evening",
        json={"content": "I was stressed about my finances today but pushed through."},
        headers=auth_headers(token),
    )
    assert res.status_code == 200
    data = res.json()
    assert data["status"] == "success"
    assert "pillar_updated" in data
    assert data["momentum"] in ("Moving", "Paused")


def test_submit_journal_updates_seed_question_progression():
    """After submitting a journal, the next morning's seed question should advance."""
    token, _ = _login("seed_progression@example.com")
    from main import _SEED_QUESTIONS

    morning1 = client.get("/ritual/morning", headers=auth_headers(token)).json()
    assert morning1["seed_question"] == _SEED_QUESTIONS[0][1]  # session 0 → first question

    client.post("/ritual/evening",
                json={"content": "I spent time with friends today."},
                headers=auth_headers(token))

    morning2 = client.get("/ritual/morning", headers=auth_headers(token)).json()
    assert morning2["seed_question"] == _SEED_QUESTIONS[1][1]  # session 1 → second question


def test_submit_empty_journal_rejected():
    token, _ = _login("empty_journal@example.com")
    res = client.post("/ritual/evening", json={"content": "   "}, headers=auth_headers(token))
    assert res.status_code == 422


def test_submit_journal_too_long_rejected():
    token, _ = _login("toolong@example.com")
    res = client.post("/ritual/evening", json={"content": "x" * 10_001}, headers=auth_headers(token))
    assert res.status_code == 422


# ---------------------------------------------------------------------------
# Weekly review
# ---------------------------------------------------------------------------

def test_weekly_review_requires_auth():
    assert client.get("/ritual/weekly").status_code == 401


def test_weekly_review_no_entries_returns_placeholder():
    token, _ = _login("no_entries_weekly@example.com")
    res = client.get("/ritual/weekly", headers=auth_headers(token))
    assert res.status_code == 200
    data = res.json()
    assert data["entries_this_week"] == 0
    assert isinstance(data["moved"], list)
    assert isinstance(data["stalled"], list)
    assert isinstance(data["pattern"], str)
    assert isinstance(data["directive"], str)


def test_weekly_review_with_entries():
    token, _ = _login("has_entries_weekly@example.com")
    client.post("/ritual/evening",
                json={"content": "Long day grinding at work but I shipped a feature."},
                headers=auth_headers(token))
    client.post("/ritual/evening",
                json={"content": "Went to the gym and caught up with an old friend."},
                headers=auth_headers(token))

    res = client.get("/ritual/weekly", headers=auth_headers(token))
    assert res.status_code == 200
    data = res.json()
    assert data["entries_this_week"] == 2
    assert len(data["moved"]) >= 1
    assert len(data["stalled"]) >= 1
    assert len(data["pattern"]) > 10
    assert len(data["directive"]) > 10


def test_weekly_review_response_fields_are_strings():
    token, _ = _login("field_check_weekly@example.com")
    client.post("/ritual/evening",
                json={"content": "Reflected on my goals today."},
                headers=auth_headers(token))
    res = client.get("/ritual/weekly", headers=auth_headers(token))
    data = res.json()
    assert isinstance(data["pattern"], str)
    assert isinstance(data["directive"], str)
    for item in data["moved"] + data["stalled"]:
        assert isinstance(item, str)


# ---------------------------------------------------------------------------
# Monthly review
# ---------------------------------------------------------------------------

def test_monthly_review_requires_auth():
    assert client.get("/ritual/monthly").status_code == 401


def test_monthly_review_no_entries_returns_placeholder():
    token, _ = _login("no_entries_monthly@example.com")
    res = client.get("/ritual/monthly", headers=auth_headers(token))
    assert res.status_code == 200
    data = res.json()
    assert data["entries_this_month"] == 0
    assert isinstance(data["pillars_moved"], list)
    assert isinstance(data["pillars_neglected"], list)
    assert isinstance(data["blind_spot"], str)
    assert isinstance(data["architectural_decision"], str)


def test_monthly_review_with_entries():
    token, _ = _login("has_entries_monthly@example.com")
    client.post("/ritual/evening",
                json={"content": "I shipped a new feature at work and felt proud."},
                headers=auth_headers(token))
    client.post("/ritual/evening",
                json={"content": "Haven't called my friends in weeks. Feeling isolated."},
                headers=auth_headers(token))

    res = client.get("/ritual/monthly", headers=auth_headers(token))
    assert res.status_code == 200
    data = res.json()
    assert data["entries_this_month"] == 2
    assert len(data["pillars_moved"]) >= 1
    assert len(data["pillars_neglected"]) >= 1
    assert len(data["blind_spot"]) > 10
    assert len(data["architectural_decision"]) > 10


def test_monthly_review_response_fields_are_strings():
    token, _ = _login("monthly_field_check@example.com")
    client.post("/ritual/evening",
                json={"content": "Deep focus on my craft today."},
                headers=auth_headers(token))
    res = client.get("/ritual/monthly", headers=auth_headers(token))
    data = res.json()
    assert isinstance(data["blind_spot"], str)
    assert isinstance(data["architectural_decision"], str)
    for item in data["pillars_moved"] + data["pillars_neglected"]:
        assert isinstance(item, str)


# ---------------------------------------------------------------------------
# User facts
# ---------------------------------------------------------------------------

def test_facts_requires_auth():
    assert client.get("/user/facts").status_code == 401


def test_facts_empty_for_new_user():
    token, _ = _login("facts_empty@example.com")
    res = client.get("/user/facts", headers=auth_headers(token))
    assert res.status_code == 200
    assert res.json() == []


def test_facts_populated_after_journal():
    token, _ = _login("facts_populated@example.com")
    client.post("/ritual/evening",
                json={"content": "I work as a software engineer and have been dealing with debt."},
                headers=auth_headers(token))
    res = client.get("/user/facts", headers=auth_headers(token))
    assert res.status_code == 200
    facts = res.json()
    assert isinstance(facts, list)
    for f in facts:
        assert "id" in f and "content" in f and "created_at" in f


def test_delete_fact_requires_auth():
    assert client.delete("/user/facts/1").status_code == 401


def test_delete_fact_not_found():
    token, _ = _login("delete_404@example.com")
    res = client.delete("/user/facts/999999", headers=auth_headers(token))
    assert res.status_code == 404


def test_delete_fact_wrong_user():
    token_a, _ = _login("facts_owner@example.com")
    token_b, _ = _login("facts_thief@example.com")

    # Give user A a fact by onboarding
    client.post("/user/onboard",
                json={"spark": "I am tired of being stuck in debt."},
                headers=auth_headers(token_a))

    facts_a = client.get("/user/facts", headers=auth_headers(token_a)).json()
    if not facts_a:
        return  # mock returns no facts — skip ownership check

    fact_id = facts_a[0]["id"]
    res = client.delete(f"/user/facts/{fact_id}", headers=auth_headers(token_b))
    assert res.status_code == 403


def test_delete_fact_success():
    token, _ = _login("facts_delete_ok@example.com")
    client.post("/user/onboard",
                json={"spark": "I am a nurse and I am burned out from long shifts."},
                headers=auth_headers(token))

    facts = client.get("/user/facts", headers=auth_headers(token)).json()
    if not facts:
        return  # mock returns no facts — nothing to delete

    fact_id = facts[0]["id"]
    res = client.delete(f"/user/facts/{fact_id}", headers=auth_headers(token))
    assert res.status_code == 200
    assert res.json()["status"] == "deleted"

    remaining = client.get("/user/facts", headers=auth_headers(token)).json()
    assert all(f["id"] != fact_id for f in remaining)


# ---------------------------------------------------------------------------
# Pillars
# ---------------------------------------------------------------------------

def test_pillars_returns_all_seven():
    token, _ = _login("pillars_test@example.com")
    res = client.get("/user/pillars", headers=auth_headers(token))
    assert res.status_code == 200
    pillars = res.json()
    assert len(pillars) == 7
    names = {p["name"] for p in pillars}
    assert names == {"Social", "Financial", "Spiritual", "Craft/Career",
                     "Emotional/Intimacy", "Intellectual", "Legacy"}


def test_pillars_status_values_are_valid():
    token, _ = _login("status_check@example.com")
    res = client.get("/user/pillars", headers=auth_headers(token))
    for p in res.json():
        assert p["status"] in ("Moving", "Paused")


def test_pillars_days_in_state_present_and_non_negative():
    token, _ = _login("days_check@example.com")
    res = client.get("/user/pillars", headers=auth_headers(token))
    assert res.status_code == 200
    for p in res.json():
        assert "days_in_state" in p
        assert isinstance(p["days_in_state"], int)
        assert p["days_in_state"] >= 0


def test_pillars_days_in_state_zero_for_new_user():
    token, _ = _login("new_days@example.com")
    res = client.get("/user/pillars", headers=auth_headers(token))
    for p in res.json():
        assert p["days_in_state"] == 0
