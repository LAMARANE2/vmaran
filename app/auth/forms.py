from flask_wtf import FlaskForm
from wtforms import PasswordField, StringField, SubmitField
from wtforms.validators import DataRequired, Email, EqualTo, Length, ValidationError

from ..models import User


class RegisterForm(FlaskForm):
    email = StringField(
        "البريد الإلكتروني",
        validators=[
            DataRequired(message="البريد الإلكتروني مطلوب"),
            Email(message="صيغة البريد غير صالحة"),
            Length(max=255),
        ],
    )
    password = PasswordField(
        "كلمة المرور",
        validators=[
            DataRequired(message="كلمة المرور مطلوبة"),
            Length(min=8, max=128, message="كلمة المرور يجب أن تكون 8 أحرف على الأقل"),
        ],
    )
    password2 = PasswordField(
        "تأكيد كلمة المرور",
        validators=[
            DataRequired(message="تأكيد كلمة المرور مطلوب"),
            EqualTo("password", message="كلمتا المرور غير متطابقتين"),
        ],
    )
    submit = SubmitField("إنشاء الحساب")

    def validate_email(self, field: StringField) -> None:
        if User.query.filter_by(email=normalize_email(field.data)).first():
            raise ValidationError("البريد الإلكتروني مسجّل مسبقاً")


class LoginForm(FlaskForm):
    email = StringField(
        "البريد الإلكتروني",
        validators=[
            DataRequired(message="البريد الإلكتروني مطلوب"),
            Email(message="صيغة البريد غير صالحة"),
        ],
    )
    password = PasswordField(
        "كلمة المرور",
        validators=[DataRequired(message="كلمة المرور مطلوبة")],
    )
    submit = SubmitField("دخول")


def normalize_email(value: str) -> str:
    return value.strip().lower()
