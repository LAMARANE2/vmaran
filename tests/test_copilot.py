"""M5 — Copilot: digest / weekly plan / reschedule (all mocked offline)."""
from datetime import date, timedelta

import pytest

from app.ai import services
from app.models import Task

TODAY = date.today()


@pytest.fixture()
def fake_ai(monkeypatch):
    state = {"response": {}, "calls": []}

    def _complete(**kwargs):
        state["calls"].append(kwargs)
        return state["response"]

    monkeypatch.setattr(services, "complete_json", _complete)
    return state


def seed(client, **overrides):
    data = {
        "title": "مهمة",
        "priority": "medium",
        "due_date": "",
        **overrides,
    }
    client.post("/tasks/new", data=data)


# ---- L3 digest --------------------------------------------------------------
def test_digest_page_renders_summary(auth_client, fake_ai):
    seed(auth_client, title="مهمة اليوم")
    fake_ai["response"] = {"summary": "يوم متوسط الحجم؛ ركّز على مهمة اليوم."}
    response = auth_client.get("/copilot/digest")
    assert response.status_code == 200
    body = response.get_data(as_text=True)
    assert "يوم متوسط الحجم" in body
    assert fake_ai["calls"][-1]["name"] == "daily_digest"
    assert fake_ai["calls"][-1]["model"] == auth_client.application.config["AI_MODEL_MAIN"]


def test_digest_handles_ai_failure(auth_client):
    seed(auth_client, title="مهمة")
    response = auth_client.get("/copilot/digest")
    assert response.status_code == 200
    assert "تعذّر توليد الملخص" in response.get_data(as_text=True)


def test_digest_without_tasks_shows_empty_state(auth_client):
    response = auth_client.get("/copilot/digest")
    assert response.status_code == 200
    assert "لا توجد مهام لتلخيصها" in response.get_data(as_text=True)


# ---- L4 weekly plan ---------------------------------------------------------
def test_plan_page_previews_ai_dates(auth_client, fake_ai):
    seed(auth_client, title="مهمة أ")
    with auth_client.application.app_context():
        task_id = Task.query.one().id
    fake_ai["response"] = {"items": [{"task_id": task_id, "day_offset": 3}]}
    response = auth_client.get("/copilot/plan")
    assert response.status_code == 200
    expected = (TODAY + timedelta(days=3)).isoformat()
    assert expected in response.get_data(as_text=True)


def test_plan_drops_unknown_ids(auth_client, fake_ai):
    seed(auth_client, title="مهمة")
    fake_ai["response"] = {"items": [{"task_id": 9999, "day_offset": 2}]}
    response = auth_client.get("/copilot/plan")
    assert response.status_code == 200
    assert "تعذّر توليد الخطة" in response.get_data(as_text=True)


def test_plan_apply_persists_dates(auth_client):
    seed(auth_client, title="مهمة للتطبيق")
    with auth_client.application.app_context():
        task_id = Task.query.one().id
    target = (TODAY + timedelta(days=5)).isoformat()
    response = auth_client.post(
        "/copilot/plan/apply",
        data={"task_id": str(task_id), "due_date": target},
        follow_redirects=True,
    )
    assert response.status_code == 200
    assert "تم تحديث تواريخ 1 مهمة" in response.get_data(as_text=True)
    with auth_client.application.app_context():
        assert Task.query.one().due_date.isoformat() == target


def test_plan_apply_ignores_other_users(auth_client):
    seed(auth_client, title="مهمة محمية")
    with auth_client.application.app_context():
        task_id = Task.query.one().id

    other = auth_client.application.test_client()
    other.post(
        "/auth/register",
        data={"email": "other2@example.com", "password": "passw0rd1", "password2": "passw0rd1"},
    )
    target = (TODAY + timedelta(days=4)).isoformat()
    other.post("/copilot/plan/apply", data={"task_id": str(task_id), "due_date": target})
    with auth_client.application.app_context():
        assert Task.query.one().due_date is None  # untouched


# ---- L5 reschedule ----------------------------------------------------------
def test_reschedule_moves_overdue_tasks(auth_client, fake_ai):
    seed(auth_client, title="متأخرة جداً", due_date=(TODAY - timedelta(days=3)).isoformat())
    with auth_client.application.app_context():
        task_id = Task.query.one().id
    new_date = (TODAY + timedelta(days=1)).isoformat()
    fake_ai["response"] = {"items": [{"task_id": task_id, "new_due_date": new_date}]}

    response = auth_client.post("/copilot/reschedule", follow_redirects=True)
    assert response.status_code == 200
    assert "تمت إعادة جدولة 1" in response.get_data(as_text=True)
    with auth_client.application.app_context():
        assert Task.query.one().due_date.isoformat() == new_date


def test_reschedule_rejects_past_dates(auth_client, fake_ai):
    seed(auth_client, title="متأخرة", due_date=(TODAY - timedelta(days=2)).isoformat())
    with auth_client.application.app_context():
        task_id = Task.query.one().id
    fake_ai["response"] = {
        "items": [{"task_id": task_id, "new_due_date": (TODAY - timedelta(days=1)).isoformat()}]
    }
    response = auth_client.post("/copilot/reschedule", follow_redirects=True)
    assert response.status_code == 200
    assert "تعذّر إعادة الجدولة" in response.get_data(as_text=True)


def test_reschedule_without_overdue_is_noop(auth_client):
    seed(auth_client, title="مهمة سليمة", due_date=(TODAY + timedelta(days=10)).isoformat())
    response = auth_client.post("/copilot/reschedule", follow_redirects=True)
    assert "لا توجد مهام متأخرة" in response.get_data(as_text=True)
