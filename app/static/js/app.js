// لوحة المهام — التفاعل الذكي من نص حر (التدفق L1). بلا تبعيات.
(() => {
  const token = document.querySelector('meta[name="csrf-token"]')?.content || "";
  const textEl = document.getElementById("nl-text");
  if (!textEl) return;

  const statusEl = document.getElementById("nl-status");
  const preview = document.getElementById("nl-preview");
  const list = document.getElementById("nl-list");
  const analyzeBtn = document.getElementById("nl-analyze");
  const applyBtn = document.getElementById("nl-apply");
  const cancelBtn = document.getElementById("nl-cancel");
  const LABELS = { low: "منخفضة", medium: "متوسطة", high: "عالية", urgent: "عاجلة" };
  let parsed = [];

  function renderPreview() {
    list.textContent = "";
    for (const task of parsed) {
      const item = document.createElement("li");

      const title = document.createElement("strong");
      title.textContent = task.title;
      item.appendChild(title);

      const badge = document.createElement("span");
      const priority = LABELS[task.priority] ? task.priority : "medium";
      badge.className = "badge badge-" + priority;
      badge.textContent = LABELS[priority];
      item.appendChild(badge);

      if (task.due_date) {
        const due = document.createElement("span");
        due.className = "muted small";
        due.textContent = "📅 " + task.due_date;
        item.appendChild(due);
      }
      if (task.description) {
        const desc = document.createElement("p");
        desc.className = "task-desc";
        desc.textContent = task.description;
        item.appendChild(desc);
      }
      list.appendChild(item);
    }
  }

  async function analyze() {
    const text = textEl.value.trim();
    if (!text) {
      statusEl.textContent = "اكتب نصاً أولاً";
      return;
    }
    analyzeBtn.disabled = true;
    statusEl.textContent = "جارٍ التحليل…";
    try {
      const res = await fetch("/copilot/parse", {
        method: "POST",
        headers: {
          "Content-Type": "application/x-www-form-urlencoded",
          "X-CSRFToken": token,
        },
        body: new URLSearchParams({ text }),
      });
      const data = await res.json();
      if (!res.ok) {
        statusEl.textContent = data.error || "حدث خطأ أثناء التحليل";
        return;
      }
      parsed = data.tasks || [];
      renderPreview();
      preview.hidden = false;
      statusEl.textContent = "تم التحليل ✅ راجع المعاينة ثم اضغط «تطبيق وإنشاء»";
    } catch {
      statusEl.textContent = "تعذّر الاتصال بالخادم";
    } finally {
      analyzeBtn.disabled = false;
    }
  }

  async function apply() {
    if (!parsed.length) return;
    applyBtn.disabled = true;
    statusEl.textContent = "جارٍ الإنشاء…";
    try {
      const res = await fetch("/copilot/parse/apply", {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          "X-CSRFToken": token,
        },
        body: JSON.stringify({ tasks: parsed }),
      });
      if (res.ok) {
        location.reload();
        return;
      }
      const data = await res.json().catch(() => ({}));
      statusEl.textContent = data.error || "تعذّر إنشاء المهام";
    } catch {
      statusEl.textContent = "تعذّر الاتصال بالخادم";
    } finally {
      applyBtn.disabled = false;
    }
  }

  analyzeBtn?.addEventListener("click", analyze);
  applyBtn?.addEventListener("click", apply);
  cancelBtn?.addEventListener("click", () => {
    preview.hidden = true;
    parsed = [];
    statusEl.textContent = "";
  });
})();
