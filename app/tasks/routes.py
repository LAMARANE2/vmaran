from datetime import UTC, datetime

from flask import Blueprint, abort, flash, redirect, render_template, request, url_for
from flask_login import current_user, login_required

from ..ai import services as ai_services
from ..extensions import db
from ..models import Task
from .forms import TaskForm

tasks_bp = Blueprint("tasks", __name__, url_prefix="/tasks")

STATUSES = ("todo", "doing", "done")
STATUS_LABELS = {"todo": "قيد الانتظار", "doing": "قيد التنفيذ", "done": "تم الإنجاز"}


def _get_task_or_404(task_id: int) -> Task:
    task = db.session.get(Task, task_id)
    if task is None or task.user_id != current_user.id:
        abort(404)
    return task


@tasks_bp.get("/")
@login_required
def board():
    tasks = Task.query.filter_by(user_id=current_user.id).order_by(Task.created_at.desc()).all()
    grouped = {status: [t for t in tasks if t.status == status] for status in STATUSES}
    return render_template(
        "tasks/board.html",
        grouped=grouped,
        status_labels=STATUS_LABELS,
        form=TaskForm(),
    )


@tasks_bp.post("/new")
@login_required
def create():
    form = TaskForm()
    if not form.validate_on_submit():
        flash("تحقق من بيانات المهمة المُدخلة", "error")
        return redirect(url_for("tasks.board"))

    task = Task(
        user_id=current_user.id,
        title=form.title.data.strip(),
        description=(form.description.data or "").strip() or None,
        due_date=form.due_date.data,
        priority=form.priority.data,
    )
    db.session.add(task)
    ai_services.enrich(task)  # L2 best-effort: priority/estimate/tags (D8: never blocks)
    db.session.commit()
    flash("تمت إضافة المهمة ✅", "success")
    return redirect(url_for("tasks.board"))


@tasks_bp.route("/<int:task_id>/edit", methods=["GET", "POST"])
@login_required
def edit(task_id: int):
    task = _get_task_or_404(task_id)
    form = TaskForm(obj=task)
    if form.validate_on_submit():
        task.title = form.title.data.strip()
        task.description = (form.description.data or "").strip() or None
        task.due_date = form.due_date.data
        task.priority = form.priority.data
        ai_services.enrich(task)
        db.session.commit()
        flash("تم تحديث المهمة", "success")
        return redirect(url_for("tasks.board"))
    return render_template("tasks/edit.html", form=form, task=task)


@tasks_bp.post("/<int:task_id>/status")
@login_required
def set_status(task_id: int):
    task = _get_task_or_404(task_id)
    status = request.form.get("status", "")
    if status not in STATUSES:
        abort(400)
    task.status = status
    task.completed_at = datetime.now(UTC) if status == "done" else None
    db.session.commit()
    flash("تم تحديث حالة المهمة", "success")
    return redirect(url_for("tasks.board"))


@tasks_bp.post("/<int:task_id>/delete")
@login_required
def delete(task_id: int):
    task = _get_task_or_404(task_id)
    db.session.delete(task)
    db.session.commit()
    flash("تم حذف المهمة", "success")
    return redirect(url_for("tasks.board"))
