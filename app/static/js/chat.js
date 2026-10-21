// المساعد الذكي — بثّ الرد عبر SSE (التدفق L6). بلا تبعيات.
// يعمل كتحسين تدريجي: لو غاب JS يرجع النموذج إلى المسار المتزامن العادي.
(() => {
  const card = document.getElementById("chat-card");
  const form = document.getElementById("chat-form");
  if (!card || !form) return;

  const streamUrl = card.dataset.streamUrl;
  const thread = document.getElementById("chat-thread");
  const input = document.getElementById("chat-question");
  const sendBtn = document.getElementById("chat-send");
  const token = document.querySelector('meta[name="csrf-token"]')?.content || "";

  let busy = false;

  function hideEmptyState() {
    document.getElementById("chat-empty")?.remove();
  }

  function addBubble(role, text) {
    hideEmptyState();
    const bubble = document.createElement("div");
    bubble.className = "bubble bubble-" + role;

    const label = document.createElement("span");
    label.className = "bubble-role";
    label.textContent = role === "user" ? "أنت" : "المساعد";

    const body = document.createElement("p");
    body.className = "bubble-text";
    body.textContent = text;

    bubble.append(label, body);
    thread.appendChild(bubble);
    thread.scrollTop = thread.scrollHeight;
    return body;
  }

  function setBusy(state) {
    busy = state;
    sendBtn.disabled = state;
    sendBtn.textContent = state ? "…" : "إرسال";
  }

  async function send(question) {
    setBusy(true);
    addBubble("user", question);
    const replyEl = addBubble("assistant", "");
    replyEl.parentElement.classList.add("bubble-typing");

    try {
      const res = await fetch(streamUrl, {
        method: "POST",
        headers: {
          "Content-Type": "application/x-www-form-urlencoded",
          "X-CSRFToken": token,
        },
        body: new URLSearchParams({ question }),
      });

      if (!res.ok || !res.body) throw new Error("stream unavailable");

      const reader = res.body.getReader();
      const decoder = new TextDecoder();
      let buffer = "";
      let failed = false;

      for (;;) {
        const { done, value } = await reader.read();
        if (done) break;
        buffer += decoder.decode(value, { stream: true });

        let idx;
        while ((idx = buffer.indexOf("\n\n")) !== -1) {
          const block = buffer.slice(0, idx);
          buffer = buffer.slice(idx + 2);
          if (!block.startsWith("data: ")) continue;

          let frame;
          try {
            frame = JSON.parse(block.slice(6));
          } catch {
            continue;
          }

          if (frame.type === "delta") {
            replyEl.textContent = frame.text;
            replyEl.parentElement.classList.remove("bubble-typing");
            thread.scrollTop = thread.scrollHeight;
          } else if (frame.type === "done") {
            replyEl.textContent = frame.reply;
            replyEl.parentElement.classList.remove("bubble-typing");
          } else if (frame.type === "error") {
            failed = true;
            replyEl.parentElement.classList.remove("bubble-typing");
            replyEl.textContent = frame.error || "تعذّر الحصول على رد الآن.";
            replyEl.parentElement.classList.add("bubble-error");
          }
        }
      }

      // A stream that produced nothing usable → fall back to a normal page reload.
      if (!failed && !replyEl.textContent.trim()) window.location.reload();
    } catch {
      // Network/stream failure → reload so the server's buffered path answers.
      window.location.reload();
    } finally {
      setBusy(false);
    }
  }

  form.addEventListener("submit", (event) => {
    if (busy) {
      event.preventDefault();
      return;
    }
    const question = input.value.trim();
    if (!question) return;
    event.preventDefault();
    input.value = "";
    send(question);
  });
})();
