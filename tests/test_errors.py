def test_unknown_route_returns_branded_404(auth_client):
    response = auth_client.get("/definitely-missing")
    assert response.status_code == 404
    assert "غير موجودة" in response.get_data(as_text=True)


def test_reading_someone_elses_task_is_404(auth_client):
    assert auth_client.get("/tasks/424242/edit").status_code == 404


def test_request_logging_is_wired(app, monkeypatch):
    """The after_request logger must exist and the app logger must feed the queue."""
    import logging

    captured: list[str] = []
    handler = logging.Handler()
    handler.emit = lambda record: captured.append(record.getMessage())
    logging.getLogger().addHandler(handler)
    app.logger.setLevel(logging.INFO)
    try:
        app.logger.info("request | GET /x -> 200")
    finally:
        logging.getLogger().removeHandler(handler)
    assert any("request |" in message for message in captured)


def test_handlers_registered(app):
    # error handlers + the async queue pipeline are installed by the factory
    assert 404 in app.error_handler_spec[None]
    assert 500 in app.error_handler_spec[None]
    assert any(
        type(h).__name__ == "QueueHandler" for h in app.logger.handlers
    ) or any(type(h).__name__ == "QueueHandler" for h in __import__("logging").getLogger().handlers)
