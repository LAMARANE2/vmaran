from flask import Blueprint, flash, redirect, render_template, url_for
from flask_login import current_user, login_required, login_user, logout_user

from ..extensions import db
from ..models import User
from .forms import LoginForm, RegisterForm, normalize_email

auth_bp = Blueprint("auth", __name__, url_prefix="/auth")


@auth_bp.route("/register", methods=["GET", "POST"])
def register():
    if current_user.is_authenticated:
        return redirect(url_for("tasks.board"))

    form = RegisterForm()
    if form.validate_on_submit():
        user = User(email=normalize_email(form.email.data))
        user.set_password(form.password.data)
        db.session.add(user)
        db.session.commit()
        login_user(user)
        flash("تم إنشاء حسابك بنجاح 🎉", "success")
        return redirect(url_for("tasks.board"))
    return render_template("auth/register.html", form=form)


@auth_bp.route("/login", methods=["GET", "POST"])
def login():
    if current_user.is_authenticated:
        return redirect(url_for("tasks.board"))

    form = LoginForm()
    if form.validate_on_submit():
        user = User.query.filter_by(email=normalize_email(form.email.data)).first()
        if user is None or not user.check_password(form.password.data):
            flash("البريد الإلكتروني أو كلمة المرور غير صحيحة", "error")
            return render_template("auth/login.html", form=form)
        login_user(user)
        flash("أهلاً بعودتك 👋", "success")
        return redirect(url_for("tasks.board"))
    return render_template("auth/login.html", form=form)


@auth_bp.route("/logout", methods=["GET", "POST"])
@login_required
def logout():
    logout_user()
    flash("تم تسجيل خروجك", "success")
    return redirect(url_for("index"))
