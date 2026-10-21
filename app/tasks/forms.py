from flask_wtf import FlaskForm
from wtforms import DateField, SelectField, StringField, SubmitField, TextAreaField
from wtforms.validators import DataRequired, Length, Optional

PRIORITY_CHOICES = [
    ("low", "منخفضة"),
    ("medium", "متوسطة"),
    ("high", "عالية"),
    ("urgent", "عاجلة"),
]


class TaskForm(FlaskForm):
    title = StringField(
        "العنوان",
        validators=[DataRequired(message="عنوان المهمة مطلوب"), Length(max=200)],
    )
    description = TextAreaField("الوصف", validators=[Optional(), Length(max=2000)])
    due_date = DateField("تاريخ الاستحقاق", format="%Y-%m-%d", validators=[Optional()])
    priority = SelectField(
        "الأولوية",
        choices=PRIORITY_CHOICES,
        default="medium",
        validators=[DataRequired()],
    )
    submit = SubmitField("حفظ")
