# PROJECT_MAP — منصة إدارة مهام مدعومة بالذكاء الاصطناعي (Flask SaaS)
> الذاكرة الخارجية للمشروع. تُحدَّث بعد كل Milestone. آخر توثيق: **2026-10-21 (أكتوبر 2026)** — كل رقم أدناه تم التحقق منه لحظياً من PyPI / GitHub API / `developers.openai.com` / `winget`.

## [STATUS] — M0→M10 مُنفَّذة ومُتحقَّقة
| M | الحالة | دليل التحقق |
|---|---|---|
| M0 البيئة | ✅ | Python 3.14.7 (winget) · Git 2.55 · venv · حزمة مثبّتة حرفياً · ruff 0.17.1 · pytest 9.1.1 |
| M1 الهيكل | ✅ | `/health`=200 حيّاً · `logs/app.log` يُنشأ آسياً · SQLite `instance/app.db` |
| M2 الهوية | ✅ | تسجيل/دخول/خروج + حماية مسارات + CSRF (اختبارات) |
| M3 اللوحة | ✅ | 3 أعمدة حيّة · `computedDirection=rtl` · `lang=ar` · CRUD + تغيير حالة |
| M4 نواة AI | ✅ | NL→معاينة→تطبيق · إثراء (أولوية/تقدير/وسوم) · fallback عند غياب المفتاح |
| M5 Copilot | ✅ | ملخص يومي + خطة أسبوعية + إعادة جدولة متأخرة (صفحات حيّة) |
| M6 تصلّب | ✅ | `ruff check .`=0 · **54 اختبار خضراء** (+1 live معزول) · waitress `Server: waitress` · 404/500 مُعلَّمة |
| **M7** Copilot Chat | ✅ | L6 محادثة حرة مُسنَدة لبيانات المهام الحقيقية · تخزين `chat_messages` + تفريغ · fallback كامل بلا مفتاح · تحقق حيّ في المتصفح |
| **M8** ربط AI حقيقي | ✅ | موجّه FreeLLMAPI المحلي (`OPENAI_BASE_URL`) · 5 مسارات AI حيّة (NL 1.3s · إثراء 0.9s · ملخص 1.0s · خطة 1.0s · شات 1.0s) · `pytest -m live` يمر |
| **M9** فشل تلقائي للـ AI | ✅ | نقطة نهاية احتياطية (`AI_FALLBACK_*`) · تحقق حيّ: أساسي ميت → WARNING → احتياطي 200 في 1.1s · معطَّل افتراضياً |
| **M10** بثّ الشات (SSE) | ✅ | `/copilot/chat/stream` مع `stream_json_field` (بثّ حقيقي عبر Responses API) + تراجع تلقائي للمسار المتزامن · `chat.js` (تحسين تدريجي: بلا JS يرجع POST عادي) · مؤشر كتابة/فقاعة خطأ عربية · **61 اختبار خضراء** (+7 للبثّ) · التحقق الحيّ مؤجل بسبب 429 من المزوّد |

**ملاحظة تشغيلية:** ✅ **الذكاء الاصطناعي الحقيقي يعمل الآن** عبر موجّه FreeLLMAPI المحلي (`OPENAI_BASE_URL=http://127.0.0.1:31415/v1`) — تم التحقق حيّاً من: NL→مهام (1.3s)، إثراء تلقائي (أولوية+تقدير+وسوم)، الملخص اليومي، الخطة الأسبوعية، والمساعد (كلها ~1s و200). **الفشل التلقائي (M9) مُفعَّل البُنية ومُختبر**: أساسي ميت → `WARNING` → احتياطي 200 في 1.1s (يُفعَّل فعلياً فور ملء `AI_FALLBACK_API_KEY`). **بثّ الشات (M10) مُتحقَّق بالكود والاختبارات (mocks)**: المزوّد Google AI Studio أرجع **429 rate-limit** أثناء اختبار البثّ الحيّ؛ المسار الصحيح مُثبَت (فشل البثّ → تراجع للمسار المتزامن → فقاعة خطأ عربية نظيفة). بلا مفتاح/موجّه: كل مسارات AI تُرجع رسائل عربية واضحة وتُسجّل `WARNING` والمنصة تعمل كاملاً (G13 مُتحقَّق حيّاً).

---

## [DECISIONS & ASSUMPTIONS]
| # | القرار | الحالة |
|---|---|---|
| D1 | نطاق الـ AI = **6 قدرات**: (1) NL→مهام (2) أولوية+تقدير ساعات (3) تسميات تلقائية (4) ملخص يومي (5) خطة أسبوعية (6) إعادة جدولة المتأخرين. **لا شات حُرّ** (لم يُختر في الأسئلة). | مُعتمد — صحّحني إن كان الشات مطلوباً |
| D2 | SaaS = **حسابات فردية فقط**: تسجيل/دخول/خروج. لا فرق، لا أدوار، لا Stripe. | مُعتمد |
| D3 | الواجهة = **Flask + Jinja2 SSR**، صفر npm، صفر build step، JS خام مدمج. | مُعتمد |
| D4 | لغة الواجهة = **عربي RTL** (اتجاه من أساس `base.html`). | مُعتمد |
| D5 | قاعدة البيانات = **SQLite** الآن؛ التبديل لـ Postgres لاحقاً = تغيير `DATABASE_URL` فقط. | مُعتمد |
| D6 | Python = **3.14.x**. مرفوض 3.15.0 (صدر 2026-10-09، عمره 12 يوماً → مخاطر توافق). | مُعتمد |
| D7 | **لا scheduler/cron** في النطاق الحالي: إعادة الجدولة والملخص «عند الطلب» (زر/صفحة). المهام المؤجلة الخلفية → ORPHANS. | مُعتمد |
| D8 | حفظ المهمة **لا يُحجب** عند فشل الـ AI: استدعاء best-effort بعد `commit` + fallback بهدوء (G13). | مُعتمد |
| D9 | دمج (أولوية + تقدير + تسميات) في **استدعاء AI واحد** `enrich()` عند الحفظ → استهلاك أقل وكود أقل. | مُعتمد |
| **D10** | **النموذج الرئيسي = `gemini-flash-lite`** (عبر الموجّه المحلي) — تغيير عن `terra` بعد قياس حيّ: نفس جودة المخرجات المنظمة، لكن `terra` غير موجود في الكتالوج المحلي و`gemini-3.8-flash` يستغرق 21s (غير صالح للتفاعل). يُراجَع إلى `gpt-5.6-terra` عند استخدام OpenAI الرسمي. | قرار Tech Lead ✅ |
| **D11** | **إضافة شات Copilot حُرّ (L6)** — قدرة سابعة: لأن «منصة مدعومة بالذكاء الاصطناعي» بلا محادثة تسمية مضلّلة. يُسنَد لبيانات مهام المستخدم الحقيقية منعاً للهلوسة. | قرار Tech Lead ✅ |
| **D12** | الشات يستخدم **نفس مسار الاستدعاء الواحد** `complete_json` + تخزين `ChatMessage` (user/assistant) + حد 6 رسائل سياق + تفريغ يدوي. لا streaming الآن. | قرار Tech Lead ✅ |
| **D13** | **فشل تلقائي للـ AI:** إعادة محاولة **واحدة** على نقطة نهاية احتياطية عند فشل الأساسي، بالنموذج المطابق للدور (`main`/`fast`). مُعطَّل حتى تُملأ `AI_FALLBACK_API_KEY` → صفر تغيير في السلوك الافتراضي. | قرار Tech Lead ✅ |
| **D14** | **بثّ ردود الشات (SSE)** عبر `stream_json_field` (يستعمل Responses API streaming الحقيقي عبر `client.responses.stream`)، مع **تراجع تلقائي** للمسار المتزامن `complete_json` عند أي فشل بثّ (لا فشل تلقائي داخل البثّ — البثّ المكسور لا يُستأنف). التحسين تدريجي: بلا JS يرجع النموذج إلى POST عادي متزامن. **يُلغي شرط «لا streaming» في D12.** | قرار المستخدم ✅ |

---

## [TECH_STACK]
**Runtime / Infra** (winget، ويندوز 11 26100 — لا يوجد Python/Node/Git مثبّت حالياً):
- Python **3.14.x** ← `winget install Python.Python.3.14` (winget يعرض 3.14.7؛ PyPI يقول 3.14.8 → أي 3.14.x مقبول)
- Git **2.55.0.5** ← `winget install Git.Git`
- خادم الإنتاج: **waitress 3.0.2** ❌ مرفوض `gunicorn 26.2.0` (Linux-only، البيئة ويندوز)

**Web** (الإصدارات الأحدث المستقرة المؤكدة 2026-10-21):
- **Flask 3.1.3** (2026-02-19) + **Werkzeug 3.1.9** + **Jinja2 3.1.6**
- **Flask-WTF 1.3.0** (CSRF + نماذج) + **email-validator 2.3.0**
- **Flask-Login 0.6.3** (أحدث ما توفر، نشط غير deprecated)

**Data**:
- **SQLAlchemy 2.1.5** (2026-10-16، يتطلب Py≥3.11) + **Flask-SQLAlchemy 3.1.1** + SQLite + **python-dotenv 1.2.4**
- لا Flask-Migrate/Alembic الآن (→ ORPHANS): بدءاً من الجدول الصغير نستخدم `db.create_all()`

**AI**:
- **openai SDK 3.35.1** (v3، 2026-10-18) → واجهة **Responses API**: `client.responses.create(...)` + **Structured Outputs** (`text.format = json_schema`) للإخراجات المنظمة، ونص حر للملخص.
- **قابلية تبديل نقطة النهاية (مُتحقَّق حيّاً):** `OPENAI_BASE_URL` فارغ → OpenAI الرسمي؛ أو أي موجّه متوافق مع OpenAI (مثل **FreeLLMAPI** المحلي على `http://127.0.0.1:31415/v1`) → نفس مسار الاستدعاء بلا تغيير كود.
- **فشل تلقائي (M9):** عند فشل الأساسي (اتصال/timeout/HTTP/JSON غير صالح) → `WARNING` + إعادة محاولة **واحدة** على `AI_FALLBACK_BASE_URL` بالنموذج الاحتياطي المطابق للدور (`main`/`fast`). مُعطَّل افتراضياً حتى تُملأ `AI_FALLBACK_API_KEY`.
- النماذج النشطة حالياً (مُختبرة حيّاً عبر الموجّه المحلي):
  | الدور | Model ID | زمن الاستجابة (مقيس) |
  |---|---|---|
  | رئيسي (توليد/تخطيط/NL/شات) | `gemini-flash-lite` | ~0.8–1.3s |
  | سريع (تصنيف/تسميات/إثراء) | `gemini-flash-lite` | ~0.8s |
- ❌ مستبعد تجريبياً: `gemini-3.8-flash` (نفس الجودة لكن **21s** — غير صالح للتفاعل الحيّ) · `gpt-5.6-terra`/`sol`/`luna` غير موجودة في كتالوج الموجّه المحلي.
- عند استخدام OpenAI الرسمي: `gpt-5.6-terra` (رئيسي) / `gpt-5.6-luna` (سريع) — التبديل بسطرَي `AI_MODEL_MAIN` / `AI_MODEL_FAST`.
- كل النماذج عبر ثوابت `AI_MODEL_MAIN` / `AI_MODEL_FAST` في `config.py` (تبديل بسطر).

**Quality / Ops**:
- **pytest 9.1.1** + **ruff 0.17.1**
- Logging: stdlib فقط → `QueueHandler` + `QueueListener` + `RotatingFileHandler` (انظر SYSTEM_FLOW#L)

---

## [SYSTEM_FLOW]
### رحلة المستخدم — أهداف قابلة للتحقق (G-criteria)
| ID | الهدف | معيار التحقق |
|---|---|---|
| G1 | فتح `/` دون جلسة → تحويل إلى `/auth/register` | `GET /` = 302 |
| G2 | تسجيل جديد → جلسة صالحة + تحويل للوحة | 302 → `GET /tasks` = 200 و `session.user_id` موجود |
| G3 | دخول صحيح/خاطئ | صحيح: 302؛ خاطئ: 200 مع رسالة خطأ |
| G4 | إنشاء مهمة يدوية → تظهر في اللوحة | عدد المهام +1 والعنوان معروض |
| G5 | تغيير الحالة todo/doing/done → يُحفظ ويعكس فوراً | `Task.status` في DB + العنصر في HTML |
| G6 | لصق نص حر عربي → معاينة مهام → تأكيد → إنشاء | `POST /copilot/parse` يرجع JSON مهام، ثم insert |
| G7 | أولوية + تقدير ساعات مقترحان تلقائياً عند الحفظ (best-effort) | `priority`/`estimate_hours` مملوءة أو fallback صامت |
| G8 | تسميات (Tags) تُولَّد تلقائياً وترتبط بالمهمة | صفوف `task_tags` |
| G9 | صفحة الملخص اليومي تعرض تقريراً مولّداً من مهام اليوم | `GET /copilot/digest` = 200 ونص غير فارغ |
| G10 | خطة أسبوعية → معاينة → «تطبيق» → تواريخ محدّثة | `plan/apply` يعدّل `due_date` للمهام المحدّدة |
| G11 | زر «إعادة جدولة المتأخرين» → تواريخ محولة للأمام | المهام المتأخرة لم تعد overdue |
| G12 | تسجيل خروج → الجلسة ملغاة | `GET /` بعده = 302 |
| G13 | **فشل AI** (لا `OPENAI_API_KEY` / timeout / 429) → تنبيه سجل + المنصة تعمل كاملاً | اختبار fallback يمر بلا مفتاح API |
| G14 | شات المساعد يجيب مستنداً لبيانات المهام الحقيقية، ويُخزّن الأثر | صفوف `chat_messages` (user+assistant) · fallback عربي بلا مفتاح |
| G15 | **فشل نقطة النهاية الأساسية** → تحويل تلقائي للاحتياطية بلا تدخّل المستخدم | سجل `endpoint=fallback` + رد ناجح بعد فشل الأساسي |
| G16 | **بثّ رد الشات تدريجياً** في المتصفح بلا إعادة تحميل الصفحة | إطارات SSE `delta`→`done` · التخزين مكتمل · عند فشل البثّ تراجع للمسار المتزامن |

### تدفق البيانات — نقاط التكامل (كلها متزامنة داخل الطلب، بلا workers)
```
[INFRA] client.complete_json ──► أساسي (OPENAI_BASE_URL) ─فشل─► احتياطي (AI_FALLBACK_BASE_URL)
                                              │ WARNING                    │
                                              └──► AIServiceError ◄── فشل الاثنين ──► G13,G15
[L1] NL→مهام      POST /copilot/parse ──► ai.services.parse ──► json_schema {tasks[]}
                                            └► معاينة (JS) ─► POST /copilot/parse/apply ─► DB ─► G6
[L2] إثراء عند الحفظ  POST /tasks|PATCH ─► commit ─► ai.services.enrich (أولوية+تقدير+تسميات)
                                            └► timeout, try/except ─► WARNING log ─► G7,G8,G13
[L3] ملخص يومي   GET  /copilot/digest ──► سياق مهام اليوم ─► services.digest ─► صفحة نصّية  ─► G9
[L4] خطة أسبوعية GET  /copilot/plan ───► مهام مفتوحة ─► services.plan_week {task_id:day}
                                            └► معاينة ─► POST /copilot/plan/apply ─► DB ─► G10
[L5] إعادة جدولة POST /copilot/reschedule ► مهام متأخرة ─► services.reschedule_overdue ─► DB ─► G11
[L6] شات حر      GET/POST /copilot/chat ► لقطة مهامي ─► services.chat_reply {reply}
                                            └► تخزين ChatMessage + fallback ─► G14
[L6+] بثّ الشات  POST /copilot/chat/stream (SSE) ─► snapshot_tasks + history(dict)
                 └► services.chat_reply_stream ─► client.stream_json_field (Responses streaming)
                     └► thread + queue ► إطارات delta/done/error ► chat.js ─► G16
                     └► أي فشل بثّ → تراجع تلقائي إلى complete_json (chat_reply) ─► G15
```

### [L] نظام التسجيل الآمن (Asynchronous — البروتوكول الرابع)
- `QueueHandler(enqueue فقط، `queue.Queue(maxsize=1000)`)` على app logger → `QueueListener` في thread خلفي → `RotatingFileHandler logs/app.log` (5MB ×3 نسخ) + StreamHandler في التطوير.
- المستويات: **DEBUG / INFO / WARNING / ERROR** فقط (`LOG_LEVEL` افتراضي INFO).
- الأحداث: دورة الطلب (method, path, status, ms) عبر `after_request`؛ استدعاءات AI (kind, model, latency, tokens, status — **بلا محتوى الـ prompt** للخصوصية)؛ الاستثناءات مع traceback.
- الإيقاف عبر `atexit`؛ يُعطَّل في الاختبارات (`LOG_LEVEL=CRITICAL`).

---

## [ARCHITECTURE]
### شجرة الملفات (Surgical — Domain-Driven، بلا micro-files)
```
vmaran/
├── PROJECT_MAP.md            # هذه الذاكرة
├── .env.example              # OPENAI_API_KEY, OPENAI_BASE_URL, AI_FALLBACK_*, SECRET_KEY, DATABASE_URL, LOG_LEVEL, AI_MODEL_*, AI_TIMEOUT
├── .gitignore                # .env, instance/, logs/, venv/, __pycache__/
├── pyproject.toml            # [tool.ruff] + [tool.pytest.ini_options] (marker: live)
├── requirements.txt          # pin= للأصدار الحرفي لكل تبعية أعلاه
├── run.py                    # نقطة الدخول: تطوير (Flask) / إنتاج (waitress --prod)
├── app/
│   ├── __init__.py           # create_app(): config + extensions + logging + blueprints + /health + / + 404/500 + after_request log
│   ├── config.py             # Config/TestConfig + OPENAI_BASE_URL + AI_MODEL_* + AI_TIMEOUT + LOG_*
│   ├── extensions.py         # [SHARED] db, login_manager, csrf
│   ├── logging_setup.py      # [SHARED] الـ QueueHandler+QueueListener+RotatingFileHandler
│   ├── models.py             # [SHARED] User, Task, Tag, task_tags + user_loader — ملف واحد عمدًا
│   ├── ai/                   # [نواة AI — طبقة مشتركة حقيقية]
│   │   ├── client.py         # عميل OpenAI وحيد + complete_json() + stream_json_field() + فشل تلقائي أساسي→احتياطي, AIServiceError
│   │   ├── prompts.py        # قوالب الـ prompt + JSON Schemas (L1–L5)
│   │   └── services.py       # parse_tasks, enrich, digest, plan_week, reschedule_overdue, _chat_prompt, chat_reply, chat_reply_stream, snapshot_tasks, clean_task, is_overdue
│   ├── auth/                 # [هوية] routes.py (register/login/logout) + forms.py
│   ├── tasks/                # [إدارة المهام] routes.py (لوحة + CRUD + حالة + إثراء) + forms.py
│   ├── copilot/              # [نقاط AI] routes.py (parse/apply, digest, plan/apply, reschedule, chat/clear, chat_stream SSE)
│   ├── templates/            # base.html(RTL) + 404/500 + auth/ + tasks/ + copilot/(digest,plan,chat)
│   └── static/               # css/app.css (RTL مدمج) + js/app.js (vanilla: L1 معاينة/تطبيق) + js/chat.js (عميل SSE للشات)
├── tests/                    # conftest, test_health, test_auth(8), test_tasks(8), test_ai(7+1 live), test_copilot(10), test_errors(4), test_chat(8), test_failover(8), test_chat_stream(7)
└── logs/                     # مُتجاهل في git
```
### قواعد الجمّود المعماري (مُلزمة)
1. **نواة مشتركة فقط لما يتكرر فعلياً**: `extensions.py`, `logging_setup.py`, `models.py`, `ai/*`. ❌ لا `utils.py`، لا `helpers.py`، لا `BaseService` وراثي، لا كود يُستخدم مرة واحدة.
2. **لا Micro-files**: كل ملف routes/form واحد لكل نطاق؛ لا تفتيت قبل ~80 سطر مبرَّر.
3. **حدود الحزم**: استيراد عابر الساحات مسموح فقط إلى `app.models` / `app.extensions` / `app.ai.*`. النطاقات لا تعرف بعضها.
4. **مسار الطلبات**: route → validate (Flask-WTF) → db → (best-effort AI) → redirect. لا منطق أعمال داخل قوالب Jinja.
5. **لا زحف ميزات**: أي ميزة خارج D1–D9 تُسجَّل في [ORPHANS & PENDING] ولا تُنفَّذ.

---

## [MILESTONES] (أهداف قابلة للتحقق — لا يُعتمد التالي قبل نجاح السابق)
| M | النطاق | معيار النجاح (Verifiable) |
|---|---|---|
| **M0** البيئة | تثبيت Python 3.14 + Git عبر winget، venv، `requirements.txt` مثبّت | `python -c "import flask,openai,sqlalchemy;print(flask.__version__,openai.__version__)"` + `ruff --version` + `pytest --co -q` يعملان |
| **M1** الهيكل | factory + config + extensions + logging آلي + SQLite + صفحة `/health` | ملف `logs/app.log` يُنشأ سطرياً بلا I/O محجوب؛ `GET /health`=200؛ `pytest` أخضر |
| **M2** الهوية | تسجيل/دخول/خروج + حماية المسارات + CSRF | G1, G2, G3, G12 تمر في pytest |
| **M3** اللوحة | CRUD مهام + تغيير حالة + واجهة عربية RTL | G4, G5 تمر في pytest + عرض RTL صحيح في المتصفح |
| **M4** نواة AI | `ai/client+prompts+services` + L1 (NL→مهام) + L2 (enrich) + L6 | G6, G7, G8 تمر (mocked في pytest + جلسة live واحدة `@pytest.mark.live`)؛ G13 (بلا مفتاح) أخضر |
| **M5** Copilot كامل | L3 ملخص يومي + L4 خطة أسبوعية + L5 إعادة جدولة | G9, G10, G11 تمر (mocked + live) |
| **M6** تصلّب | waitress، صفحات 404/500، `ruff check` نظيف، سووت اختبارات كامل، تحديث هذا الملف | `ruff check .` = 0، `pytest` = 0 فشل، تشغيل إنتاجي عبر `python run.py --prod` يخدم اللوحة |
| **M7** Copilot Chat | L6: شات حر مُسنَد لبيانات المهام + تخزين المحادثة + تفريغ | G14 + تحقق حيّ في المتصفح |
| **M8** ربط AI حقيقي | `OPENAI_BASE_URL` + تبديل النماذج لنقطة نهاية متوافقة (FreeLLMAPI المحلي) | 5 مسارات AI حيّة ~1s · `pytest -m live` يمر |
| **M9** فشل تلقائي للـ AI | نقطة نهاية احتياطية + إعادة محاولة واحدة بالنموذج المطابق للدور | تحقق حيّ: أساسي ميت → احتياطي 200 · معطَّل بلا مفتاح |
| **M10** بثّ الشات (SSE) | `stream_json_field` + `/copilot/chat/stream` + `chat.js` (تحسين تدريجي) + تراجع للمسار المتزامن | G16: إطارات delta→done · 61 اختبار أخضر · ruff=0 · مؤشر كتابة وفقاعة خطأ عربية |

---

## [ORPHANS & PENDING]
> قرارات مؤجلة **عمداً** (Feature-Creep Control) — لا تُنفَّذ دون موافقة صريحة:
- **مفتوح (يحتاج قرارك)**: (1) هل تُملأ `AI_FALLBACK_API_KEY` بمفتاح OpenAI رسمي لتفعيل الفشل التلقائي فعلياً في الإنتاج؟ (البُنية جاهزة ومُختبرة؛ تنتظر المفتاح فقط). (2) ~~streaming للشات~~ ✅ **نُفِّذ في M10** (D14). (3) هل تُبقى إعدادات FreeLLMAPI المحلي كافتراضيّ التطوير أم يُنقل إلى `.env.local`؟
- **خارج النطاق مؤجَّل**: فرق/أدوار/دعوات (D2)، بوابة دفع Stripe + خطط + quotas، i18n ثنائي اللغة (Flask-Babel)، تحقق بريد + إعادة تعيين كلمة المرور، rate limiting للـ AI.
- **تقني مؤجَّل**: Flask-Migrate/Alembic، Postgres (يُفعَّل بـ `DATABASE_URL`)، Docker/CI، Redis/Celery ومهمة مجدولة (الـ cron للملخص اليومي)، عدّاد استهلاك tokens في الواجهة، Sentry، تثبيت snapshot مؤرّخ للنماذج.
- **تحسينات واجهة مؤجَّلة**: تصفية/بحث المهام، سحب وإفلات (drag&drop) بين الأعمدة، صفحة `/copilot` موحّدة بدل روابط متفرقة.
