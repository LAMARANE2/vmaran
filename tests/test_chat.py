"""L6 — free assistant chat (mocked offline)."""
from datetime import date, timedelta

import pytest

from app.ai import services
from app.models import ChatMessage, Task


@pytest.fixture()
def fake_ai(monkeypatch):
    state = {"response": {}, "calls": []}

    def _complete(**kwargs):
        state["calls"].append(kwargs)
        return state["response"]

    monkeypatch.setattr(services, "complete_json", _complete)
    return state


def seed(client, **overrides):
    data = {"title": "مهمة", "priority": "medium", "due_date": "", **overrides}
    client.post("/tasks/new", data=data)


def test_chat_page_empty_state(auth_client):
    response = auth_client.get("/copilot/chat")
    assert response.status_code == 200
    assert "المساعد الذكي" in response.get_data(as_text=True)


def test_chat_stores_question_and_answer(auth_client, fake_ai):
    seed(auth_client, title="أرسل التقرير", priority="urgent")
    fake_ai["response"] = {"reply": "ابدأ بإرسال التقرير لأنه عاجل."}
    response = auth_client.post(
        "/copilot/chat", data={"question": "بماذا أبدأ؟"}, follow_redirects=True
    )
    assert response.status_code == 200
    body = response.get_data(as_text=True)
    assert "بماذا أبدأ؟" in body
    assert "ابدأ بإرسال التقرير" in body
    with auth_client.application.app_context():
        roles = [m.role for m in ChatMessage.query.order_by(ChatMessage.id).all()]
        assert roles == ["user", "assistant"]
    # grounded in real data + main model
    call = fake_ai["calls"][-1]
    assert call["name"] == "assistant_chat"
    assert call["model"] == auth_client.application.config["AI_MODEL_MAIN"]
    assert "أرسل التقرير" in call["user"]


def test_chat_failure_keeps_question_and_flashes(auth_client):
    seed(auth_client, title="مهمة")
    response = auth_client.post(
        "/copilot/chat", data={"question": "سؤال بلا مفتاح"}, follow_redirects=True
    )
    assert response.status_code == 200
    assert "تعذّر الحصول على رد" in response.get_data(as_text=True)
    with auth_client.application.app_context():
        # only the user's question is stored; no assistant row
        assert [m.role for m in ChatMessage.query.all()] == ["user"]


def test_chat_rejects_empty_question(auth_client):
    response = auth_client.post("/copilot/chat", data={"question": "   "}, follow_redirects=True)
    assert "اكتب سؤالك" in response.get_data(as_text=True)


def test_chat_clear_removes_history(auth_client, fake_ai):
    seed(auth_client, title="مهمة")
    fake_ai["response"] = {"reply": "رد"}
    auth_client.post("/copilot/chat", data={"question": "س1"})
    auth_client.post("/copilot/chat/clear", follow_redirects=True)
    with auth_client.application.app_context():
        assert ChatMessage.query.count() == 0


def test_chat_history_isolated_between_users(auth_client, fake_ai):
    seed(auth_client, title="مهمة")
    fake_ai["response"] = {"reply": "رد خاص"}
    auth_client.post("/copilot/chat", data={"question": "سري"})

    other = auth_client.application.test_client()
    other.post(
        "/auth/register",
        data={"email": "chat@example.com", "password": "passw0rd1", "password2": "passw0rd1"},
    )
    assert "سري" not in other.get("/copilot/chat").get_data(as_text=True)


def test_chat_requires_login(client):
    response = client.get("/copilot/chat")
    assert response.status_code == 302
    assert "/auth/login" in response.headers["Location"]


def test_overdue_tasks_are_grounded_in_prompt(auth_client, fake_ai):
    seed(auth_client, title="متأخرة", due_date=(date.today() - timedelta(days=1)).isoformat())
    fake_ai["response"] = {"reply": "لديك مهمة متأخرة."}
    auth_client.post("/copilot/chat", data={"question": "حالتي؟"})
    assert "متأخرة: 1" in fake_ai["calls"][-1]["user"]
    with auth_client.application.app_context():
        assert Task.query.count() == 1
