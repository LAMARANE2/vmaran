"""AI operations (L1–L5) built on the single call path."""
import logging
from datetime import date, timedelta

from flask import current_app

from ..extensions import db
from ..models import Tag, Task
from . import prompts
from .client import AIServiceError, complete_json, stream_json_field

log = logging.getLogger(__name__)

PRIORITY_VALUES = ("low", "medium", "high", "urgent")
MAX_TASKS = 8
MAX_INPUT_CHARS = 6000


def clean_task(item: object) -> dict | None:
    """Sanitize one task dict (from the model or from a client payload). None = drop."""
    if not isinstance(item, dict):
        return None
    title = str(item.get("title") or "").strip()[:200]
    if not title:
        return None
    description = str(item.get("description") or "").strip()[:2000] or None
    priority = item.get("priority")
    if priority not in PRIORITY_VALUES:
        priority = "medium"
    due_date = _parse_due_date(item.get("due_date"))
    return {
        "title": title,
        "description": description,
        "priority": priority,
        "due_date": due_date,
    }


def _parse_due_date(value: object) -> date | None:
    if isinstance(value, date):
        return value
    if isinstance(value, str) and value.strip():
        try:
            return date.fromisoformat(value.strip()[:10])
        except ValueError:
            return None
    return None


def parse_tasks(raw_text: str) -> list[dict]:
    """L1: free text → sanitized task dicts (AI_MODEL_MAIN)."""
    text = (raw_text or "").strip()
    if not text:
        raise AIServiceError("empty input")
    data = complete_json(
        name="parse_tasks",
        system=prompts.PARSE_SYSTEM,
        user=text[:MAX_INPUT_CHARS],
        schema=prompts.PARSE_SCHEMA,
        model=current_app.config["AI_MODEL_MAIN"],
    )
    raw_items = data.get("tasks") if isinstance(data.get("tasks"), list) else []
    tasks = [cleaned for item in raw_items[:MAX_TASKS] if (cleaned := clean_task(item))]
    if not tasks:
        raise AIServiceError("no tasks parsed")
    return tasks


def enrich(task: Task) -> None:
    """L2: fill missing intelligence (estimate, default priority, tags).

    Never overwrites explicit user choices; AI failures are logged and swallowed —
    the caller stays best-effort by construction (decision D8).
    """
    try:
        data = complete_json(
            name="enrich_task",
            system=prompts.ENRICH_SYSTEM,
            user=_task_summary(task),
            schema=prompts.ENRICH_SCHEMA,
            model=current_app.config["AI_MODEL_FAST"],
            role="fast",
        )
    except AIServiceError as exc:
        log.warning("enrich skipped | task=%s error=%s", task.id or "new", exc)
        return

    hours = data.get("estimated_hours")
    if task.estimated_hours is None and isinstance(hours, int | float) and 0 < hours <= 40:
        task.estimated_hours = float(hours)

    suggested = data.get("priority")
    if task.priority == "medium" and suggested in PRIORITY_VALUES and suggested != "medium":
        task.priority = suggested

    if not task.tags:
        for name in _clean_tags(data.get("tags")):
            tag = Tag.query.filter_by(user_id=task.user_id, name=name).first()
            if tag is None:
                tag = Tag(user_id=task.user_id, name=name)
                db.session.add(tag)
            task.tags.append(tag)


def _task_summary(task: Task) -> str:
    parts = [f"العنوان: {task.title}"]
    if task.description:
        parts.append(f"الوصف: {task.description}")
    parts.append(f"الأولوية الحالية: {task.priority}")
    if task.due_date:
        parts.append(f"الاستحقاق: {task.due_date.isoformat()}")
    parts.append(f"الحالة: {task.status}")
    return "\n".join(parts)


def _clean_tags(raw: object) -> list[str]:
    if not isinstance(raw, list):
        return []
    seen: set[str] = set()
    out: list[str] = []
    for item in raw:
        name = str(item).strip().strip("،,.;:!?")[:40]
        if not name or name in seen:
            continue
        seen.add(name)
        out.append(name)
        if len(out) == 3:
            break
    return out


def digest(tasks: list[Task], today: date) -> str:
    """L3: today's tasks → short Arabic summary (AI_MODEL_MAIN)."""
    lines = [
        f"اليوم: {today.isoformat()}",
        f"الكل: {len(tasks)}",
        f"قيد الانتظار: {sum(1 for t in tasks if t.status == 'todo')}",
        f"قيد التنفيذ: {sum(1 for t in tasks if t.status == 'doing')}",
        f"مُنجز اليوم: {sum(1 for t in tasks if t.status == 'done')}",
        f"متأخر: {sum(1 for t in tasks if is_overdue(t, today))}",
        "المهام:",
    ]
    for task in tasks[:30]:
        due = task.due_date.isoformat() if task.due_date else "بلا استحقاق"
        lines.append(f"- [{task.status}/{task.priority}] {task.title} (استحقاق: {due})")
    data = complete_json(
        name="daily_digest",
        system=prompts.DIGEST_SYSTEM,
        user="\n".join(lines),
        schema=prompts.DIGEST_SCHEMA,
        model=current_app.config["AI_MODEL_MAIN"],
    )
    summary = str(data.get("summary") or "").strip()
    if not summary:
        raise AIServiceError("empty digest")
    return summary


def plan_week(tasks: list[Task]) -> list[tuple[int, date]]:
    """L4: open tasks → [(task_id, suggested_due_date)] within the next 7 days."""
    if not tasks:
        raise AIServiceError("no tasks to plan")
    lines = ["المهام:"]
    for task in tasks[:40]:
        limit = task.due_date.isoformat() if task.due_date else "بلا"
        lines.append(f"- id={task.id} | {task.title} | priority={task.priority} | استحقاق={limit}")
    lines.append("\nضّع كل المهام المعطاة في الخطة.")
    data = complete_json(
        name="weekly_plan",
        system=prompts.PLAN_SYSTEM,
        user="\n".join(lines),
        schema=prompts.PLAN_SCHEMA,
        model=current_app.config["AI_MODEL_MAIN"],
    )
    today = date.today()
    allowed = {t.id for t in tasks}
    out: list[tuple[int, date]] = []
    for item in data.get("items") if isinstance(data.get("items"), list) else []:
        if not isinstance(item, dict):
            continue
        task_id = item.get("task_id")
        offset = item.get("day_offset")
        if task_id not in allowed or not isinstance(offset, int) or not 1 <= offset <= 7:
            continue
        out.append((task_id, today + timedelta(days=offset)))
    if not out:
        raise AIServiceError("plan contained no usable items")
    return out


def reschedule_overdue(tasks: list[Task], today: date) -> list[tuple[Task, date]]:
    """L5: overdue tasks → [(task, new_due_date)] strictly in the future."""
    if not tasks:
        raise AIServiceError("no overdue tasks")
    lines = [f"اليوم: {today.isoformat()}", "المهام المتأخرة:"]
    for task in tasks[:30]:
        lines.append(
            f"- id={task.id} | {task.title} | priority={task.priority} "
            f"| استحقاق فائت={task.due_date.isoformat() if task.due_date else 'بلا'}"
        )
    data = complete_json(
        name="reschedule_overdue",
        system=prompts.RESCHEDULE_SYSTEM,
        user="\n".join(lines),
        schema=prompts.RESCHEDULE_SCHEMA,
        model=current_app.config["AI_MODEL_MAIN"],
    )
    by_id = {t.id: t for t in tasks}
    out: list[tuple[Task, date]] = []
    for item in data.get("items") if isinstance(data.get("items"), list) else []:
        if not isinstance(item, dict):
            continue
        task = by_id.get(item.get("task_id"))
        new_date = _parse_due_date(item.get("new_due_date"))
        if task is None or new_date is None or new_date <= today:
            continue
        out.append((task, new_date))
    if not out:
        raise AIServiceError("reschedule contained no usable items")
    return out


def is_overdue(task: Task, today: date) -> bool:
    return task.status != "done" and task.due_date is not None and task.due_date < today


def _chat_prompt(tasks: list, history: list, question: str, today: date) -> str:
    """Shared grounding text for both buffered and streaming chat replies (L6).

    Accepts tasks/history as ORM objects or as plain snapshots (`(role, content)` /
    dicts), so this can run off-request in a worker thread without a live session.
    """
    def _field(obj, key):
        if isinstance(obj, dict):
            return obj.get(key)
        return getattr(obj, key, None)

    lines = [
        f"عدد المهام: {len(tasks)}",
        f"متأخرة: {sum(1 for t in tasks if _is_overdue_snapshot(t, today))}",
        f"اليوم: {today.isoformat()}",
        "المهام:",
    ]
    for task in tasks[:40]:
        due = _field(task, "due_date")
        due = due.isoformat() if hasattr(due, "isoformat") else (due or "بلا استحقاق")
        lines.append(
            f"- [{_field(task, 'status')}/{_field(task, 'priority')}] "
            f"{_field(task, 'title')} (استحقاق: {due})"
        )

    conversation = ["\n\nسياق محادثة سابق:"]
    for message in history:
        role = _field(message, "role")
        speaker = "المستخدم" if role == "user" else "المساعد"
        conversation.append(f"{speaker}: {_field(message, 'content')}")
    conversation.append(f"\nسؤال المستخدم: {question}")
    return "\n".join(lines + conversation)


def _is_overdue_snapshot(task, today: date) -> bool:
    """is_overdue for plain task snapshots (works off-request, no session needed)."""
    if isinstance(task, Task):
        return is_overdue(task, today)
    status = task.get("status") if isinstance(task, dict) else getattr(task, "status", None)
    due = task.get("due_date") if isinstance(task, dict) else getattr(task, "due_date", None)
    return status != "done" and due is not None and due < today


def snapshot_tasks(tasks: list[Task]) -> list[dict]:
    """Plain, session-free copies of tasks — safe to use in a worker thread."""
    return [
        {
            "title": t.title,
            "status": t.status,
            "priority": t.priority,
            "due_date": t.due_date,
        }
        for t in tasks
    ]


def chat_reply(tasks: list[Task], history: list, question: str, today: date) -> str:
    """L6: answer a free question grounded in the user's real task snapshot."""
    data = complete_json(
        name="assistant_chat",
        system=prompts.CHAT_SYSTEM,
        user=_chat_prompt(tasks, history, question, today),
        schema=prompts.CHAT_SCHEMA,
        model=current_app.config["AI_MODEL_MAIN"],
    )
    reply = str(data.get("reply") or "").strip()
    if not reply:
        raise AIServiceError("empty chat reply")
    return reply


def chat_reply_stream(tasks: list[Task], history: list, question: str, today: date, on_text) -> str:
    """L6 streaming: same grounding, but emits reply text progressively.

    Falls back to the buffered `chat_reply` when streaming is unavailable so the
    user always gets an answer (Protocol 5).
    """
    prompt = _chat_prompt(tasks, history, question, today)
    try:
        data = stream_json_field(
            name="assistant_chat",
            system=prompts.CHAT_SYSTEM,
            user=prompt,
            schema=prompts.CHAT_SCHEMA,
            model=current_app.config["AI_MODEL_MAIN"],
            field="reply",
            on_text=on_text,
        )
    except AIServiceError as exc:
        log.warning("chat stream unavailable, buffering | error=%s", exc)
        return chat_reply(tasks, history, question, today)
    reply = str(data.get("reply") or "").strip()
    if not reply:
        raise AIServiceError("empty chat reply")
    return reply
