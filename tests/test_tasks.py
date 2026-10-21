from app.extensions import db
from app.models import Task


def create_task(client, title="مراجعة التقرير", **overrides):
    data = {"title": title, "priority": "high", "due_date": "2026-10-25", **overrides}
    return client.post("/tasks/new", data=data)


def test_create_task_appears_on_board(auth_client):
    response = create_task(auth_client, "مهمة أولى")
    assert response.status_code == 302
    body = auth_client.get("/tasks/").get_data(as_text=True)
    assert "مهمة أولى" in body
    assert "2026-10-25" in body


def test_create_task_rejects_empty_title(auth_client):
    response = auth_client.post(
        "/tasks/new", data={"title": "", "priority": "low"}, follow_redirects=True
    )
    assert response.status_code == 200
    assert "تحقق من بيانات المهمة" in response.get_data(as_text=True)
    with auth_client.application.app_context():
        assert Task.query.count() == 0


def test_status_change_persists_and_sets_completed_at(auth_client):
    create_task(auth_client, "مهمة للحالة")
    with auth_client.application.app_context():
        task_id = Task.query.one().id

    response = auth_client.post(f"/tasks/{task_id}/status", data={"status": "done"})
    assert response.status_code == 302

    with auth_client.application.app_context():
        task = db.session.get(Task, task_id)
        assert task.status == "done"
        assert task.completed_at is not None

    body = auth_client.get("/tasks/").get_data(as_text=True)
    assert "تم الإنجاز" in body


def test_status_change_rejects_invalid_value(auth_client):
    create_task(auth_client, "مهمة سليمة")
    with auth_client.application.app_context():
        task_id = Task.query.one().id
    response = auth_client.post(f"/tasks/{task_id}/status", data={"status": "weird"})
    assert response.status_code == 400


def test_edit_updates_task(auth_client):
    create_task(auth_client, "عنوان قديم")
    with auth_client.application.app_context():
        task_id = Task.query.one().id

    response = auth_client.post(
        f"/tasks/{task_id}/edit",
        data={"title": "عنوان جديد", "priority": "urgent", "due_date": ""},
        follow_redirects=True,
    )
    assert response.status_code == 200
    assert "عنوان جديد" in response.get_data(as_text=True)
    with auth_client.application.app_context():
        task = db.session.get(Task, task_id)
        assert task.title == "عنوان جديد"
        assert task.priority == "urgent"
        assert task.due_date is None


def test_delete_removes_task(auth_client):
    create_task(auth_client, "ستُحذف")
    with auth_client.application.app_context():
        task_id = Task.query.one().id

    auth_client.post(f"/tasks/{task_id}/delete")
    with auth_client.application.app_context():
        assert db.session.get(Task, task_id) is None


def test_board_shows_rtl_layout(auth_client):
    body = auth_client.get("/tasks/").get_data(as_text=True)
    assert 'dir="rtl"' in body
    assert 'lang="ar"' in body


def test_other_user_cannot_touch_task(auth_client):
    create_task(auth_client, "مهمة خاصة")
    with auth_client.application.app_context():
        task_id = Task.query.one().id

    other = auth_client.application.test_client()  # independent session
    other.post(
        "/auth/register",
        data={"email": "other@example.com", "password": "passw0rd1", "password2": "passw0rd1"},
    )
    assert other.get(f"/tasks/{task_id}/edit").status_code == 404
    assert other.post(f"/tasks/{task_id}/delete").status_code == 404
    assert other.post(f"/tasks/{task_id}/status", data={"status": "done"}).status_code == 404
    # their own board is empty
    assert "مهمة خاصة" not in other.get("/tasks/").get_data(as_text=True)
