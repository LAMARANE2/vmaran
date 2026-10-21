"""M4 — AI core: everything is mocked (offline); one opt-in live test at the end."""
import os

import pytest

from app import create_app
from app.ai import services
from app.config import Config
from app.models import Tag, Task


@pytest.fixture()
def fake_ai(monkeypatch):
    """Replace the single call path with canned structured output."""
    state = {"response": {"tasks": []}, "calls": []}

    def _complete(**kwargs):
        state["calls"].append(kwargs)
        return state["response"]

    monkeypatch.setattr(services, "complete_json", _complete)
    return state


def test_parse_endpoint_returns_preview(auth_client, fake_ai):
    fake_ai["response"] = {
        "tasks": [
            {
                "title": "مراجعة التقرير",
                "description": "قبل إرساله",
                "due_date": "2026-11-01",
                "priority": "high",
            }
        ]
    }
    response = auth_client.post("/copilot/parse", data={"text": "غداً راجع التقرير"})
    assert response.status_code == 200
    tasks = response.get_json()["tasks"]
    assert tasks[0]["title"] == "مراجعة التقرير"
    assert tasks[0]["priority"] == "high"
    # contract: main model + strict schema, single call path
    call = fake_ai["calls"][0]
    assert call["model"] == auth_client.application.config["AI_MODEL_MAIN"]
    assert call["schema"]["additionalProperties"] is False
    # nothing written to the DB during preview
    with auth_client.application.app_context():
        assert Task.query.count() == 0


def test_parse_endpoint_requires_text(auth_client):
    response = auth_client.post("/copilot/parse", data={"text": "   "})
    assert response.status_code == 400


def test_parse_apply_creates_tasks_and_sanitizes(auth_client):
    payload = {
        "tasks": [
            {"title": "مهمة صحيحة", "priority": "urgent", "due_date": "2026-11-02",
             "description": "وصف"},
            {"title": "", "priority": "low"},          # dropped: no title
            {"title": "أولوية فاسدة", "priority": "ZZZ", "due_date": "not-a-date"},
            "not-a-dict",                               # dropped
        ]
    }
    response = auth_client.post("/copilot/parse/apply", json=payload)
    assert response.status_code == 200
    assert response.get_json() == {"created": 2}
    with auth_client.application.app_context():
        tasks = {t.title: t for t in Task.query.all()}
        assert tasks["مهمة صحيحة"].priority == "urgent"
        assert tasks["مهمة صحيحة"].due_date.isoformat() == "2026-11-02"
        assert tasks["أولوية فاسدة"].priority == "medium"  # sanitized default
        assert tasks["أولوية فاسدة"].due_date is None


def test_create_task_enriches_priority_estimate_tags(auth_client, fake_ai):
    fake_ai["response"] = {
        "priority": "urgent",
        "estimated_hours": 3.5,
        "tags": ["تقارير", "مبيعات", "تقارير", "،多余"],
    }
    auth_client.post(
        "/tasks/new", data={"title": "أرسل التقرير", "priority": "medium"}
    )
    with auth_client.application.app_context():
        task = Task.query.one()
        assert task.priority == "urgent"          # G7
        assert task.estimated_hours == 3.5        # G7
        assert [t.name for t in task.tags][:2] == ["تقارير", "مبيعات"]  # G8 dedup+cap
        # fast model for enrich
        assert fake_ai["calls"][0]["model"] == auth_client.application.config["AI_MODEL_FAST"]


def test_enrich_never_overwrites_explicit_choice(auth_client, fake_ai):
    fake_ai["response"] = {"priority": "urgent", "estimated_hours": 8, "tags": ["x"]}
    auth_client.post("/tasks/new", data={"title": "مهمة أخفضها يدوياً", "priority": "low"})
    with auth_client.application.app_context():
        task = Task.query.one()
        assert task.priority == "low"       # explicit user choice wins
        assert task.estimated_hours == 8    # missing values still filled


def test_ai_failure_keeps_platform_working(auth_client):
    """G13: no API key → task created with defaults, no exception anywhere."""
    response = auth_client.post(
        "/tasks/new",
        data={"title": "مهمة بلا ذكاء", "priority": "medium"},
        follow_redirects=True,
    )
    assert response.status_code == 200
    assert "مهمة بلا ذكاء" in response.get_data(as_text=True)
    with auth_client.application.app_context():
        task = Task.query.one()
        assert task.priority == "medium"
        assert task.estimated_hours is None
        assert task.tags == []


def test_parse_endpoint_fails_gracefully_without_key(auth_client):
    response = auth_client.post("/copilot/parse", data={"text": "غداً المهمة"})
    assert response.status_code == 502
    assert "تعذّر" in response.get_json()["error"]
    # board still serves
    assert auth_client.get("/tasks/").status_code == 200


@pytest.mark.live
def test_live_parse_with_real_key():
    """Run explicitly: `pytest -m live` with OPENAI_API_KEY set (network required)."""
    if not os.environ.get("OPENAI_API_KEY"):
        pytest.skip("OPENAI_API_KEY not set")
    app = create_app(Config)
    with app.app_context():
        tasks = services.parse_tasks("غداً راسل أحمد بخصوص التقرير وأنشئ عرضاً الأسبوع القادم")
    assert tasks
    assert tasks[0]["title"]
    assert isinstance(Tag, type)  # models imported cleanly
