"""Application factory for the AI task-management platform."""
from pathlib import Path

from flask import Flask, jsonify, redirect, render_template, request, url_for
from flask_login import current_user
from sqlalchemy import text

from . import models  # noqa: F401  # register models so db.create_all() sees their tables
from .auth.routes import auth_bp
from .config import Config
from .copilot.routes import copilot_bp
from .extensions import csrf, db, login_manager
from .logging_setup import setup_logging
from .tasks.routes import tasks_bp


def create_app(config_object=Config) -> Flask:
    app = Flask(__name__)
    app.config.from_object(config_object)

    Path(app.instance_path).mkdir(parents=True, exist_ok=True)
    setup_logging(app)

    db.init_app(app)
    login_manager.init_app(app)
    csrf.init_app(app)
    login_manager.login_view = "auth.login"

    app.register_blueprint(auth_bp)
    app.register_blueprint(tasks_bp)
    app.register_blueprint(copilot_bp)

    @app.get("/health")
    def health():
        db.session.execute(text("SELECT 1"))
        return jsonify(status="ok", db="ok")

    @app.route("/")
    def index():
        if current_user.is_authenticated:
            return redirect(url_for("tasks.board"))
        return redirect(url_for("auth.register"))

    @app.after_request
    def log_request(response):
        # Async by construction: this only enqueues (Protocol 4).
        app.logger.info(
            "request | %s %s -> %s", request.method, request.path, response.status_code
        )
        return response

    @app.errorhandler(404)
    def not_found(error):
        return render_template("404.html"), 404

    @app.errorhandler(500)
    def server_error(error):
        app.logger.error("unhandled error | path=%s error=%s", request.path, error)
        return render_template("500.html"), 500

    with app.app_context():
        db.create_all()

    app.logger.info("application ready")
    return app
