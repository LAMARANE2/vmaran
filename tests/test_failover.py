"""M8 — endpoint failover in the single call path (mocked SDK, offline)."""
from types import SimpleNamespace

import pytest

from app import create_app
from app.ai import client as ai_client
from app.ai.client import AIServiceError, complete_json
from app.config import Config

SCHEMA = {
    "type": "object",
    "properties": {"ok": {"type": "boolean"}},
    "required": ["ok"],
    "additionalProperties": False,
}


def _response(payload: str = '{"ok": true}'):
    return SimpleNamespace(output_text=payload, usage=None)


class _FakeResponses:
    """Records calls and replays a scripted outcome (exception or response)."""

    def __init__(self, outcome):
        self.outcome = outcome
        self.calls = []

    def create(self, **kwargs):
        self.calls.append(kwargs)
        if isinstance(self.outcome, Exception):
            raise self.outcome
        return self.outcome


def _fake_openai(monkeypatch, primary, fallback=None):
    """Patch OpenAI() so the Nth construction yields the given fake responses object."""
    built = []

    def _factory(**kwargs):
        outcome = primary if not built else fallback
        responses = _FakeResponses(outcome)
        built.append({"kwargs": kwargs, "responses": responses})
        return SimpleNamespace(responses=responses)

    monkeypatch.setattr(ai_client, "OpenAI", _factory)
    return built


def _call(app, role="main", model="primary-model"):
    with app.app_context():
        return complete_json(name="t", system="s", user="u", schema=SCHEMA, model=model, role=role)


def _fallback_app(**overrides):
    class C(Config):
        TESTING = True
        OPENAI_API_KEY = "primary-key"
        OPENAI_BASE_URL = "http://primary.test/v1"
        AI_FALLBACK_BASE_URL = "https://api.openai.com/v1"
        AI_FALLBACK_API_KEY = "fallback-key"
        AI_MODEL_MAIN = "primary-model"
        AI_MODEL_FAST = "primary-fast"
        AI_FALLBACK_MODEL_MAIN = "fallback-main"
        AI_FALLBACK_MODEL_FAST = "fallback-fast"

    for key, value in overrides.items():
        setattr(C, key, value)
    return create_app(C)


def test_primary_success_never_touches_fallback(monkeypatch):
    app = _fallback_app()
    built = _fake_openai(monkeypatch, _response())
    assert _call(app) == {"ok": True}
    assert len(built) == 1  # fallback client never constructed
    assert built[0]["kwargs"]["base_url"] == "http://primary.test/v1"


def test_failover_uses_fallback_model_for_role(monkeypatch):
    app = _fallback_app()
    built = _fake_openai(monkeypatch, RuntimeError("router down"), _response())
    assert _call(app, role="main", model="primary-model") == {"ok": True}
    assert len(built) == 2
    # fallback client points at the fallback endpoint with the fallback key
    assert built[1]["kwargs"]["base_url"] == "https://api.openai.com/v1"
    assert built[1]["kwargs"]["api_key"] == "fallback-key"
    # fallback used the main-role model name
    assert built[1]["responses"].calls[0]["model"] == "fallback-main"


def test_failover_uses_fast_model_when_role_is_fast(monkeypatch):
    app = _fallback_app()
    built = _fake_openai(monkeypatch, RuntimeError("router down"), _response())
    assert _call(app, role="fast", model="primary-fast") == {"ok": True}
    assert built[1]["responses"].calls[0]["model"] == "fallback-fast"


def test_both_endpoints_fail_raises(monkeypatch):
    app = _fallback_app()
    _fake_openai(monkeypatch, RuntimeError("down"), RuntimeError("also down"))
    with pytest.raises(AIServiceError):
        _call(app)


def test_fallback_disabled_without_api_key(monkeypatch):
    app = _fallback_app(AI_FALLBACK_API_KEY="")
    built = _fake_openai(monkeypatch, RuntimeError("router down"), _response())
    with pytest.raises(AIServiceError):
        _call(app)
    assert len(built) == 1  # no fallback attempt


def test_fallback_disabled_when_base_url_empty_and_key_empty(monkeypatch):
    app = _fallback_app(AI_FALLBACK_BASE_URL="", AI_FALLBACK_API_KEY="")
    built = _fake_openai(monkeypatch, RuntimeError("router down"), _response())
    with pytest.raises(AIServiceError):
        _call(app)
    assert len(built) == 1


def test_missing_primary_key_raises_before_any_call(monkeypatch):
    app = _fallback_app(OPENAI_API_KEY="")
    built = _fake_openai(monkeypatch, _response())
    with pytest.raises(AIServiceError):
        _call(app)
    assert built == []


def test_invalid_json_from_primary_fails_over(monkeypatch):
    app = _fallback_app()
    built = _fake_openai(monkeypatch, _response("not json"), _response('{"ok": true}'))
    assert _call(app) == {"ok": True}
    assert len(built) == 2
