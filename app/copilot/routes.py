import json
import logging
import queue
import threading
from datetime import date

from flask import (
    Blueprint,
    Response,
    current_app,
    flash,
    jsonify,
    redirect,
    render_template,
    request,
    stream_with_context,
    url_for,
)
from flask_login import current_user, login_required

from ..ai import services as ai_services
from ..ai.client import AIServiceError
from ..extensions import db
from ..models import ChatMessage, Task

log = logging.getLogger(__name__)

copilot_bp = Blueprint("copilot", __name__, url_prefix="/copilot")


def _my_tasks() -> list[Task]:
    return Task.query.filter_by(user_id=current_user.id).order_by(Task.created_at.desc()).all()


def _sse(payload: dict) -> str:
    """Encode one SSE frame (newline-delimited JSON, no comments/framing ambiguity)."""
    return f"data: {json.dumps(payload, ensure_ascii=False)}\n\n"


@copilot_bp.post("/parse")
@login_required
def parse():
    """L1 step 1: free text → preview JSON (never touches the DB)."""
    raw = request.form.get("text") or (request.get_json(silent=True) or {}).get("text") or ""
    if not raw.strip():
        return jsonify(error="اكتب نص المهام أولاً"), 400
    try:
        tasks = ai_services.parse_tasks(raw)
    except AIServiceError as exc:
        log.warning("parse rejected | user=%s error=%s", current_user.id, exc)
        return jsonify(error="تعذّر تحليل النص بالذكاء الاصطناعي — حاول بصيغة أبسط"), 502
    return jsonify(tasks=tasks)


@copilot_bp.post("/parse/apply")
@login_required
def parse_apply():
    """L1 step 2: confirmed preview → tasks (server re-sanitizes everything)."""
    payload = request.get_json(silent=True) or {}
    items = payload.get("tasks")
    if not isinstance(items, list):
        return jsonify(error="بيانات غير صالحة"), 400

    created = 0
    for item in items[: ai_services.MAX_TASKS]:
        cleaned = ai_services.clean_task(item)
        if cleaned is None:
            continue
        db.session.add(Task(user_id=current_user.id, **cleaned))
        created += 1
    db.session.commit()
    log.info("tasks created from nl | user=%s count=%d", current_user.id, created)
    return jsonify(created=created)


@copilot_bp.get("/digest")
@login_required
def digest():
    """L3: daily summary of today's tasks."""
    today = date.today()
    tasks = _my_tasks()
    stats = {
        "total": len(tasks),
        "todo": sum(1 for t in tasks if t.status == "todo"),
        "doing": sum(1 for t in tasks if t.status == "doing"),
        "done": sum(1 for t in tasks if t.status == "done"),
        "overdue": sum(1 for t in tasks if ai_services.is_overdue(t, today)),
    }
    summary, error = None, None
    if tasks:
        try:
            summary = ai_services.digest(tasks, today)
        except AIServiceError as exc:
            log.warning("digest failed | user=%s error=%s", current_user.id, exc)
            error = "تعذّر توليد الملخص الآن — تحقق من إعداد مفتاح الذكاء الاصطناعي."
    return render_template(
        "copilot/digest.html", stats=stats, summary=summary, error=error, today=today
    )


@copilot_bp.get("/plan")
@login_required
def plan():
    """L4: this week's plan preview (no DB writes)."""
    tasks = [t for t in _my_tasks() if t.status != "done"]
    entries, error = [], None
    if tasks:
        try:
            for task_id, when in ai_services.plan_week(tasks):
                task = next((t for t in tasks if t.id == task_id), None)
                if task is not None:
                    entries.append({"task": task, "when": when})
        except AIServiceError as exc:
            log.warning("plan failed | user=%s error=%s", current_user.id, exc)
            error = "تعذّر توليد الخطة الآن — تحقق من إعداد مفتاح الذكاء الاصطناعي."
    return render_template("copilot/plan.html", entries=entries, error=error, today=date.today())


@copilot_bp.post("/plan/apply")
@login_required
def plan_apply():
    """L4 apply: persist suggested dates (only for the current user's tasks)."""
    raw_ids = request.form.getlist("task_id")
    raw_dates = request.form.getlist("due_date")
    updated = 0
    for task_id, raw_date in zip(raw_ids, raw_dates):
        if not task_id.isdigit():
            continue
        task = db.session.get(Task, int(task_id))
        if task is None or task.user_id != current_user.id:
            continue
        parsed = ai_services._parse_due_date(raw_date)
        if parsed is None:
            continue
        task.due_date = parsed
        updated += 1
    db.session.commit()
    flash(f"تم تحديث تواريخ {updated} مهمة", "success")
    return redirect(url_for("copilot.plan"))


@copilot_bp.post("/reschedule")
@login_required
def reschedule():
    """L5: push overdue tasks to new dates, all in one action."""
    today = date.today()
    overdue = [t for t in _my_tasks() if ai_services.is_overdue(t, today)]
    if not overdue:
        flash("لا توجد مهام متأخرة 👏", "success")
        return redirect(url_for("tasks.board"))
    try:
        changes = ai_services.reschedule_overdue(overdue, today)
    except AIServiceError as exc:
        log.warning("reschedule failed | user=%s error=%s", current_user.id, exc)
        flash("تعذّر إعادة الجدولة الآن — تحقق من إعداد مفتاح الذكاء الاصطناعي.", "error")
        return redirect(url_for("tasks.board"))

    for task, new_date in changes:
        task.due_date = new_date
    db.session.commit()
    log.info("overdue rescheduled | user=%s count=%d", current_user.id, len(changes))
    flash(f"تمت إعادة جدولة {len(changes)} مهمة متأخرة ✅", "success")
    return redirect(url_for("tasks.board"))


@copilot_bp.route("/chat", methods=["GET", "POST"])
@login_required
def chat():
    """L6: free assistant grounded in the user's real tasks."""
    error = None
    if request.method == "POST":
        question = (request.form.get("question") or "").strip()
        if not question:
            flash("اكتب سؤالك أولاً", "error")
            return redirect(url_for("copilot.chat"))

        history = (
            ChatMessage.query.filter_by(user_id=current_user.id)
            .order_by(ChatMessage.created_at.desc())
            .limit(6)
            .all()
        )[::-1]
        db.session.add(ChatMessage(user_id=current_user.id, role="user", content=question[:1000]))
        try:
            reply = ai_services.chat_reply(_my_tasks(), history, question, date.today())
        except AIServiceError as exc:
            log.warning("chat failed | user=%s error=%s", current_user.id, exc)
            db.session.commit()  # keep the question so the user can retry visibly
            flash("تعذّر الحصول على رد الآن — تحقق من إعداد مفتاح الذكاء الاصطناعي.", "error")
            return redirect(url_for("copilot.chat"))
        db.session.add(ChatMessage(user_id=current_user.id, role="assistant", content=reply))
        db.session.commit()
        return redirect(url_for("copilot.chat"))

    messages = (
        ChatMessage.query.filter_by(user_id=current_user.id)
        .order_by(ChatMessage.created_at.asc())
        .limit(50)
        .all()
    )
    return render_template("copilot/chat.html", messages=messages, error=error)


@copilot_bp.post("/chat/clear")
@login_required
def chat_clear():
    ChatMessage.query.filter_by(user_id=current_user.id).delete()
    db.session.commit()
    flash("تم تفريغ المحادثة", "success")
    return redirect(url_for("copilot.chat"))


@copilot_bp.post("/chat/stream")
@login_required
def chat_stream():
    """L6 streaming: SSE reply, persisted exactly like the buffered path.

    Emits newline-delimited `data:` JSON frames: {type: delta|done|error, ...}.
    Always persists the assistant message (even on failure) so the transcript and
    history stay consistent with what the user saw.
    """
    question = (request.form.get("question") or "").strip()
    if not question:
        return jsonify(error="اكتب سؤالك أولاً"), 400

    user_id = current_user.id
    tasks = ai_services.snapshot_tasks(_my_tasks())
    history = [
        {"role": m.role, "content": m.content}
        for m in (
            ChatMessage.query.filter_by(user_id=user_id)
            .order_by(ChatMessage.created_at.desc())
            .limit(6)
            .all()
        )[::-1]
    ]
    db.session.add(ChatMessage(user_id=user_id, role="user", content=question[:1000]))
    db.session.commit()

    today = date.today()
    app = current_app._get_current_object()
    log.info("chat stream start | user=%s", user_id)

    def _frames():
        events: queue.Queue = queue.Queue()
        result: dict = {}

        def worker():
            # The model call runs off-request; it needs its own app context.
            with app.app_context():
                try:
                    result["reply"] = ai_services.chat_reply_stream(
                        tasks,
                        history,
                        question,
                        today,
                        lambda full: events.put(("delta", full)),
                    )
                except AIServiceError as exc:
                    result["error"] = exc
                except Exception as exc:  # noqa: BLE001 — surface unexpected failures in-thread
                    log.exception("chat stream worker crashed | user=%s", user_id)
                    result["error"] = exc
                finally:
                    events.put(("__end__", None))

        thread = threading.Thread(target=worker, daemon=True)
        thread.start()
        log.info("chat stream worker started | user=%s", user_id)

        last_text = ""
        while True:
            kind, payload = events.get()
            if kind == "__end__":
                break
            if kind == "delta" and payload != last_text:
                last_text = payload
                yield _sse({"type": "delta", "text": payload})

        thread.join()

        if "error" in result:
            log.warning("chat stream failed | user=%s error=%s", user_id, result["error"])
            yield _sse({"type": "error", "error": "تعذّر الحصول على رد الآن."})
            return

        reply = result["reply"]
        db.session.add(ChatMessage(user_id=user_id, role="assistant", content=reply))
        db.session.commit()
        log.info("chat stream done | user=%s chars=%d", user_id, len(reply))
        yield _sse({"type": "done", "reply": reply})

    return Response(stream_with_context(_frames()), mimetype="text/event-stream")
