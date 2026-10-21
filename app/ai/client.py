"""Single OpenAI call path — shared by every AI service (Architecture rule 1).

Resilience (Protocol 5): if a secondary OpenAI-compatible endpoint is configured
(`AI_FALLBACK_BASE_URL`), a failed primary call is retried once against it using the
role-appropriate fallback model. Failover is opt-in and silent to callers.

Privacy: prompts/completions are never logged; only name/model/latency/tokens.
"""
import json
import logging
import time

from flask import current_app
from openai import OpenAI

log = logging.getLogger(__name__)

_ROLE_CONFIG = {
    "main": ("AI_MODEL_MAIN", "AI_FALLBACK_MODEL_MAIN"),
    "fast": ("AI_MODEL_FAST", "AI_FALLBACK_MODEL_FAST"),
}


class AIServiceError(Exception):
    """The model call failed or returned unusable output."""


def _build_client(*, api_key: str, base_url: str) -> OpenAI:
    return OpenAI(
        api_key=api_key,
        base_url=(base_url or "").strip() or None,
        timeout=current_app.config.get("AI_TIMEOUT", 20),
        max_retries=current_app.config.get("AI_MAX_RETRIES", 1),
    )


def _client(key: str, *, api_key: str, base_url: str) -> OpenAI:
    """Cache one client per endpoint slot (primary / fallback) on the app."""
    client = current_app.extensions.get(key)
    if client is None:
        client = _build_client(api_key=api_key, base_url=base_url)
        current_app.extensions[key] = client
    return client


def _request(client: OpenAI, *, model: str, name: str, system: str, user: str, schema: dict):
    return client.responses.create(
        model=model,
        input=[
            {"role": "system", "content": system},
            {"role": "user", "content": user},
        ],
        text={
            "format": {
                "type": "json_schema",
                "name": name,
                "strict": True,
                "schema": schema,
            }
        },
    )


def _parse(response) -> dict:
    try:
        payload = json.loads(response.output_text)
    except (json.JSONDecodeError, TypeError) as exc:
        raise AIServiceError("model returned invalid JSON") from exc
    if not isinstance(payload, dict):
        raise AIServiceError("model returned a non-object payload")
    return payload


def _extract_partial_string(raw: str, key: str) -> str | None:
    """Best-effort: pull the (possibly incomplete) string value of `key` from raw JSON.

    Returns None while the value has not started arriving yet. Never raises — a
    partial JSON stream is expected mid-flight.
    """
    marker = f'"{key}"'
    idx = raw.find(marker)
    if idx == -1:
        return None
    colon = raw.find(":", idx + len(marker))
    if colon == -1:
        return None
    start = raw.find('"', colon + 1)
    if start == -1:
        return None
    out: list[str] = []
    escaped = False
    for ch in raw[start + 1 :]:
        if escaped:
            # Re-decode the common JSON escapes so the preview matches the final text.
            out.append({"n": "\n", "t": "\t", "r": "\r"}.get(ch, ch))
            escaped = False
        elif ch == "\\":
            escaped = True
        elif ch == '"':
            return "".join(out)
        else:
            out.append(ch)
    return "".join(out)  # unterminated → partial value so far


def complete_json(
    *, name: str, system: str, user: str, schema: dict, model: str, role: str = "main"
) -> dict:
    """Responses API + strict structured output → parsed dict.

    Tries the primary endpoint first; on any failure, retries once against the
    configured fallback endpoint (if any) with the fallback model for `role`.

    Raises AIServiceError only when every available endpoint fails.
    """
    api_key = current_app.config.get("OPENAI_API_KEY") or ""
    if not api_key:
        raise AIServiceError("OPENAI_API_KEY is not configured")

    primary = _client(
        "openai_client", api_key=api_key, base_url=current_app.config.get("OPENAI_BASE_URL", "")
    )

    started = time.perf_counter()
    primary_error = None
    try:
        response = _request(
            primary, model=model, name=name, system=system, user=user, schema=schema
        )
        payload = _parse(response)
    except Exception as exc:  # noqa: BLE001 — transport, HTTP, and schema errors all fail over
        primary_error = exc
        log.warning("ai primary failed | name=%s model=%s error=%s", name, model, exc)
    else:
        usage = getattr(response, "usage", None)
        log.info(
            "ai call ok | name=%s model=%s endpoint=primary ms=%d in=%s out=%s",
            name,
            model,
            int((time.perf_counter() - started) * 1000),
            getattr(usage, "input_tokens", "?"),
            getattr(usage, "output_tokens", "?"),
        )
        return payload

    fallback = _fallback_endpoint(role)
    if fallback is None:
        raise AIServiceError(f"model call failed: {primary_error}") from primary_error

    fb_client, fb_model = fallback
    fb_started = time.perf_counter()
    try:
        response = _request(
            fb_client, model=fb_model, name=name, system=system, user=user, schema=schema
        )
        payload = _parse(response)
    except Exception as exc:  # noqa: BLE001 — both endpoints down
        log.error("ai fallback failed | name=%s model=%s error=%s", name, fb_model, exc)
        raise AIServiceError(f"model call failed on all endpoints: {exc}") from exc

    usage = getattr(response, "usage", None)
    log.info(
        "ai call ok | name=%s model=%s endpoint=fallback ms=%d in=%s out=%s",
        name,
        fb_model,
        int((time.perf_counter() - fb_started) * 1000),
        getattr(usage, "input_tokens", "?"),
        getattr(usage, "output_tokens", "?"),
    )
    return payload


def _fallback_endpoint(role: str) -> tuple[OpenAI, str] | None:
    """Return (client, model) for the fallback endpoint, or None when disabled."""
    base_url = (current_app.config.get("AI_FALLBACK_BASE_URL") or "").strip()
    api_key = (current_app.config.get("AI_FALLBACK_API_KEY") or "").strip()
    model_key = _ROLE_CONFIG.get(role, _ROLE_CONFIG["main"])[1]
    model = current_app.config.get(model_key)
    # A fallback is meaningful only when it names a model; an empty base_url means
    # "official OpenAI", which still needs its own key.
    if not model:
        return None
    if not base_url and not api_key:
        return None
    if base_url and not api_key:
        # Same-router retry makes no sense; fallback must be a distinct credential.
        return None
    return _client("openai_fallback_client", api_key=api_key, base_url=base_url), model


def stream_json_field(
    *,
    name: str,
    system: str,
    user: str,
    schema: dict,
    model: str,
    field: str,
    on_text,
) -> dict:
    """Stream a structured response, surfacing one string field progressively.

    Emits the growing value of `field` through `on_text(full_text_so_far)` as tokens
    arrive, then returns the fully validated payload (same schema as `complete_json`).

    Resilient by design: any streaming failure raises AIServiceError so the caller can
    fall back to the buffered `complete_json` path. No failover mid-stream (a broken
    stream cannot be resumed), which keeps behaviour predictable.
    """
    api_key = current_app.config.get("OPENAI_API_KEY") or ""
    if not api_key:
        raise AIServiceError("OPENAI_API_KEY is not configured")

    client = _client(
        "openai_client", api_key=api_key, base_url=current_app.config.get("OPENAI_BASE_URL", "")
    )
    started = time.perf_counter()
    raw = ""
    emitted = ""
    try:
        with client.responses.stream(
            model=model,
            input=[
                {"role": "system", "content": system},
                {"role": "user", "content": user},
            ],
            text={
                "format": {"type": "json_schema", "name": name, "strict": True, "schema": schema}
            },
        ) as stream:
            for event in stream:
                if getattr(event, "type", "") == "response.output_text.delta":
                    raw += getattr(event, "delta", "") or ""
                    partial = _extract_partial_string(raw, field)
                    if partial is not None and partial.startswith(emitted) and partial != emitted:
                        emitted = partial
                        on_text(partial)
            final = stream.get_final_response()
    except Exception as exc:  # noqa: BLE001 — any stream problem hands off to the buffered path
        log.warning("ai stream failed | name=%s model=%s error=%s", name, model, exc)
        raise AIServiceError(f"streaming failed: {exc}") from exc

    payload = _parse(final)
    value = str(payload.get(field) or "").strip()
    if not value:
        raise AIServiceError("streamed field is empty")
    if value != emitted:
        on_text(value)  # guarantee the client ends with the validated text

    usage = getattr(final, "usage", None)
    log.info(
        "ai call ok | name=%s model=%s endpoint=primary stream=1 ms=%d in=%s out=%s",
        name,
        model,
        int((time.perf_counter() - started) * 1000),
        getattr(usage, "input_tokens", "?"),
        getattr(usage, "output_tokens", "?"),
    )
    return payload
