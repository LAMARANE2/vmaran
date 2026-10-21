"""M10 — SSE chat streaming (mocked AI, offline)."""
import json

import pytest

from app.ai import services
from app.ai.client import AIServiceError
from app.models import ChatMessage


@pytest.fixture()
def fake_stream(monkeypatch):
    """Replace the streaming service with a scripted generator of deltas."""
    state = {"reply": "رد تجريبي", "chunks": None, "error": None, "calls": []}

    def _stream(tasks, history, question, today, on_text):
        state["calls"].append(
            {"tasks": tasks, "history": history, "question": question, "today": today}
        )
        for chunk in state["chunks"] or [state["reply"]]:
            on_text(chunk)
        if state["error"] is not None:
            raise AIServiceError(state["error"])
        return state["reply"]

    monkeypatch.setattr(services, "chat_reply_stream", _stream)
    return state


def _parse_frames(body: str) -> list[dict]:
    frames = []
    for block in body.split("\n\n"):
        if block.startswith("data: "):
            frames.append(json.loads(block[6:]))
    return frames


def _post_stream(client, question="سؤال"):
    return client.post("/copilot/chat/stream", data={"question": question})


def test_stream_emits_deltas_then_done(auth_client, fake_stream):
    fake_stream["chunks"] = ["لي", "ليلة", "ليلة سعيدة"]
    fake_stream["reply"] = "ليلة سعيدة"
    response = _post_stream(auth_client)
    assert response.status_code == 200
    assert response.headers["Content-Type"].startswith("text/event-stream")

    frames = _parse_frames(response.get_data(as_text=True))
    deltas = [f["text"] for f in frames if f["type"] == "delta"]
    # progressive growth, deduped (same text not repeated)
    assert deltas == ["لي", "ليلة", "ليلة سعيدة"]
    assert frames[-1]["type"] == "done"
    assert frames[-1]["reply"] == "ليلة سعيدة"


def test_stream_persists_question_and_reply(auth_client, fake_stream):
    fake_stream["reply"] = "ابدأ بالتقرير"
    fake_stream["chunks"] = ["ابدأ بالتقرير"]
    response = _post_stream(auth_client, "بماذا أبدأ؟")
    response.get_data()  # drain the stream so the worker completes and commits
    with auth_client.application.app_context():
        rows = ChatMessage.query.order_by(ChatMessage.id).all()
        assert [r.role for r in rows] == ["user", "assistant"]
        assert rows[0].content == "بماذا أبدأ؟"
        assert rows[1].content == "ابدأ بالتقرير"


def test_stream_passes_plain_snapshots_off_request(auth_client, fake_stream):
    """The service receives dicts (session-free) so a worker thread can use them."""
    auth_client.post("/tasks/new", data={"title": "مهمة", "priority": "high", "due_date": ""})
    fake_stream["reply"] = "رد"
    _post_stream(auth_client).get_data()
    call = fake_stream["calls"][-1]
    assert isinstance(call["tasks"][0], dict)
    assert call["tasks"][0]["title"] == "مهمة"
    assert all(isinstance(m, dict) for m in call["history"])


def test_stream_error_frame(auth_client, fake_stream):
    fake_stream["error"] = "boom"
    response = _post_stream(auth_client)
    frames = _parse_frames(response.get_data(as_text=True))
    assert frames[-1]["type"] == "error"
    assert "تعذّر" in frames[-1]["error"]
    # the user's question is kept for a retry, but no assistant row is stored
    with auth_client.application.app_context():
        assert [r.role for r in ChatMessage.query.all()] == ["user"]


def test_stream_rejects_empty_question(auth_client):
    response = _post_stream(auth_client, "   ")
    assert response.status_code == 400


def test_stream_requires_login(client):
    response = client.post("/copilot/chat/stream", data={"question": "س"})
    assert response.status_code == 302
    assert "/auth/login" in response.headers["Location"]


def test_stream_history_isolated_between_users(auth_client, fake_stream):
    fake_stream["reply"] = "رد سري"
    _post_stream(auth_client, "سري").get_data()

    other = auth_client.application.test_client()
    other.post(
        "/auth/register",
        data={"email": "stream@example.com", "password": "passw0rd1", "password2": "passw0rd1"},
    )
    other.post("/copilot/chat/stream", data={"question": "سؤال آخر"}).get_data()
    with auth_client.application.app_context():
        # each user's transcript stays their own
        assert ChatMessage.query.filter_by(content="سري").count() == 1
