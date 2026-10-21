"""All prompt templates + JSON schemas — single source of truth (L1–L5)."""

_PRIORITY = {"type": "string", "enum": ["low", "medium", "high", "urgent"]}

# ---- L1: free text → tasks --------------------------------------------------
PARSE_SYSTEM = """\
أنت محرّر مهام دقيق. حوّل نص المستخدم إلى مهام منظمة وفق المخطط المطلوب.
قواعد إلزامية:
- الحد الأقصى 8 مهام؛ عنوان محدّد حتى 120 حرفاً، بلغة النص (عربي افتراضياً).
- due_date بصيغة YYYY-MM-DD فقط إن كان التاريخ مستنتجاً بوضوح، وإلا null (لا تخترع تواريخ).
- priority: urgent (فوري/عاجل جداً)، high (مهم جداً)، medium (اعتيادي)، low (ثانوي).
- description: جملة واحدة مفيدة أو "" إذا لم يضف النص وصفاً.
- لا تكرر المهام ولا تُخرج أي نص خارج JSON.
"""

PARSE_SCHEMA = {
    "type": "object",
    "properties": {
        "tasks": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "title": {"type": "string"},
                    "description": {"type": "string"},
                    "due_date": {"type": ["string", "null"]},
                    "priority": _PRIORITY,
                },
                "required": ["title", "description", "due_date", "priority"],
                "additionalProperties": False,
            },
        }
    },
    "required": ["tasks"],
    "additionalProperties": False,
}

# ---- L2: enrich a single task ----------------------------------------------
ENRICH_SYSTEM = """\
قيّم مهمة واحدة وقدّر ما تحتاجها، وفق المخطط المطلوب حصراً.
- priority: low / medium / high / urgent حسب الأثر والاستعجال الظاهري.
- estimated_hours: رقم عشري واقعي بين 0.25 و40، أو null إن تعذّر التقدير.
- tags: حتى 3 وسوم قصيرة (كلمة أو كلمتان بالعربية) تصف مجال المهمة، بلا ترقيم ولا تكرار.
"""

ENRICH_SCHEMA = {
    "type": "object",
    "properties": {
        "priority": _PRIORITY,
        "estimated_hours": {"type": ["number", "null"]},
        "tags": {"type": "array", "items": {"type": "string"}},
    },
    "required": ["priority", "estimated_hours", "tags"],
    "additionalProperties": False,
}

# ---- L3: daily digest -------------------------------------------------------
DIGEST_SYSTEM = """\
أنت مساعد إنتاجية. اكتب ملخّصاً يومياً موجزاً (3–5 أسطر كحد أقصى) عن يوم المستخدم بالعربية المبسطة:
- ابدأ بجملة تقييم عامة لحجم اليوم.
- اذكر ما أُنجز، وما هو قيد التنفيذ، وأهم 2–3 مهام يجب التركيز عليها اليوم، ونبّه لأي مهمة متأخرة.
- بلا تعداد نقطي، بلا عناوين، بلا مقدمات. نص عادي فقط.
"""

DIGEST_SCHEMA = {
    "type": "object",
    "properties": {"summary": {"type": "string"}},
    "required": ["summary"],
    "additionalProperties": False,
}

# ---- L4: weekly plan -------------------------------------------------------
PLAN_SYSTEM = """\
أنت مخطّط أسبوعي. وزّع المهام المعطاة على أيام العمل القادمة وفق المخطط المطلوب.
- day_offset: رقم صحيح من 1 (غداً) إلى 7.
- ضع المهام المُلحّة والمتأخرة في الأيام الأولى، ووازن الحِمل اليومي (~4–6 ساعات كحد أقصى/يوم).
- أعد فقط مهام القائمة المعطاة، بلا اختراع معرّفات.
"""

PLAN_SCHEMA = {
    "type": "object",
    "properties": {
        "items": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "task_id": {"type": "integer"},
                    "day_offset": {"type": "integer"},
                },
                "required": ["task_id", "day_offset"],
                "additionalProperties": False,
            },
        }
    },
    "required": ["items"],
    "additionalProperties": False,
}

# ---- L5: reschedule overdue -----------------------------------------------
RESCHEDULE_SYSTEM = """\
أنت مجدول ذكي. اقترح تاريخاً جديداً (YYYY-MM-DD) لكل مهمة متأخرة، بدءاً من الغد،
موزّعة على الأيام التالية بما يوازن الحِمل (لا تضع كل المهام في يوم واحد، والمهام ذات الأولوية
الأعلى تأخذ أقرب التواريخ). لا تختر تواريخ في الماضي.
"""

RESCHEDULE_SCHEMA = {
    "type": "object",
    "properties": {
        "items": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "task_id": {"type": "integer"},
                    "new_due_date": {"type": "string"},
                },
                "required": ["task_id", "new_due_date"],
                "additionalProperties": False,
            },
        }
    },
    "required": ["items"],
    "additionalProperties": False,
}

# ---- L6: free assistant chat ------------------------------------------------
CHAT_SYSTEM = """\
أنت «مساعد المهام» داخل تطبيق إدارة مهام. تجيب بالعربية الفصحى المبسطة بإيجاز ودقّة.
- لديك لقطة عن مهام المستخدم في نهاية الرسالة؛ اعتمد عليها ولا تخترع مهاماً غير موجودة.
- إن طُلب منك ترتيب الأولويات أو التخطيط، استند إلى الأولوية وتاريخ الاستحقاق الحقيقيين.
- إن لم تتوفر بيانات كافية، اسأل سؤالاً توضيحياً واحداً.
- لا تُخرج JSON ولا تشرح طريقة عملك؛ إجابة نصية مباشرة فقط (3–6 أسطر).
"""

CHAT_SCHEMA = {
    "type": "object",
    "properties": {"reply": {"type": "string"}},
    "required": ["reply"],
    "additionalProperties": False,
}
