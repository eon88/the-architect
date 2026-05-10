import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'web_app'))

os.environ.setdefault("DATABASE_URL", "sqlite:///./test_architect.db")

import pytest
from fastapi.testclient import TestClient
from main import app

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
    assert "token" in data
    assert "user_id" in data
    assert data["email"] == "new_user@example.com"


def test_login_same_email_returns_same_user():
    email = "same_user@example.com"
    res1 = client.post("/auth/login", json={"email": email, "name": "Test"})
    res2 = client.post("/auth/login", json={"email": email, "name": "Test"})
    assert res1.json()["user_id"] == res2.json()["user_id"]


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
    res = client.get("/ritual/morning")
    assert res.status_code == 401


def test_evening_journal_requires_auth():
    res = client.post("/ritual/evening", json={"content": "Test entry"})
    assert res.status_code == 401


def test_pillars_requires_auth():
    res = client.get("/user/pillars")
    assert res.status_code == 401


# ---------------------------------------------------------------------------
# Morning ritual
# ---------------------------------------------------------------------------

def test_morning_ritual_day_one_message():
    token, _ = _login("morning_test@example.com")
    res = client.get("/ritual/morning", headers=auth_headers(token))
    assert res.status_code == 200
    assert "message" in res.json()


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


def test_submit_empty_journal_rejected():
    token, _ = _login("empty_journal@example.com")
    res = client.post(
        "/ritual/evening",
        json={"content": "   "},
        headers=auth_headers(token),
    )
    assert res.status_code == 422


def test_submit_journal_too_long_rejected():
    token, _ = _login("toolong@example.com")
    res = client.post(
        "/ritual/evening",
        json={"content": "x" * 10_001},
        headers=auth_headers(token),
    )
    assert res.status_code == 422


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
    for pillar in res.json():
        assert pillar["status"] in ("Moving", "Paused")
