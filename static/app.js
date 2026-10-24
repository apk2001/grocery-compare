(function () {
  const chat = document.getElementById("chat");
  const form = document.getElementById("composer");
  const input = document.getElementById("input");
  const sendBtn = document.getElementById("send");
  const resetBtn = document.getElementById("resetBtn");
  const statusEl = document.getElementById("status");

  // Stable per-browser session id.
  let sessionId;
  try {
    sessionId = localStorage.getItem("gc_session");
    if (!sessionId) {
      sessionId = "s_" + Math.random().toString(36).slice(2) + Date.now().toString(36);
      localStorage.setItem("gc_session", sessionId);
    }
  } catch (e) {
    sessionId = "s_" + Math.random().toString(36).slice(2);
  }

  function now() {
    const d = new Date();
    return d.getHours().toString().padStart(2, "0") + ":" + d.getMinutes().toString().padStart(2, "0");
  }

  function scrollDown() {
    chat.scrollTop = chat.scrollHeight;
  }

  // Minimal, safe formatter: escape HTML, then *bold* and _italic_ and newlines.
  function format(text) {
    const esc = (text || "")
      .replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;");
    return esc
      .replace(/\*([^*]+)\*/g, "<b>$1</b>")
      .replace(/_([^_]+)_/g, "<em>$1</em>");
  }

  function addMessage(msg, side) {
    const row = document.createElement("div");
    row.className = "row " + (side || "in");
    const bubble = document.createElement("div");
    bubble.className = "bubble";

    const body = document.createElement("div");
    body.innerHTML = format(msg.text);
    bubble.appendChild(body);

    if (msg.links && msg.links.length) {
      const wrap = document.createElement("div");
      wrap.className = "links";
      msg.links.forEach((l, i) => {
        const a = document.createElement("a");
        a.className = "linkbtn" + (i === 0 && msg.links.length === 1 ? " primary" : "");
        a.href = l.url; a.target = "_blank"; a.rel = "noopener noreferrer";
        a.textContent = l.label;
        wrap.appendChild(a);
      });
      bubble.appendChild(wrap);
    }

    if (msg.buttons && msg.buttons.length) {
      const wrap = document.createElement("div");
      wrap.className = "chips";
      msg.buttons.forEach((b) => {
        const btn = document.createElement("button");
        btn.className = "chip";
        btn.type = "button";
        btn.textContent = b.label;
        btn.addEventListener("click", () => {
          wrap.querySelectorAll(".chip").forEach((c) => (c.disabled = true));
          send(b.value, b.label);
        });
        wrap.appendChild(btn);
      });
      bubble.appendChild(wrap);
    }

    const t = document.createElement("span");
    t.className = "time";
    t.textContent = now();
    bubble.appendChild(t);

    row.appendChild(bubble);
    chat.appendChild(row);
    scrollDown();
  }

  let typingRow;
  function showTyping() {
    statusEl.textContent = "typing…";
    typingRow = document.createElement("div");
    typingRow.className = "row in typing";
    typingRow.innerHTML = '<div class="bubble"><span class="dots"><i></i><i></i><i></i></span></div>';
    chat.appendChild(typingRow);
    scrollDown();
  }
  function hideTyping() {
    statusEl.textContent = "online";
    if (typingRow) { typingRow.remove(); typingRow = null; }
  }

  async function send(text, displayText) {
    const shown = (displayText || text || "").trim();
    if (!shown && text !== "__start__") return;
    if (text !== "__start__") addMessage({ text: shown }, "out");

    showTyping();
    sendBtn.disabled = true;
    try {
      const res = await fetch("/chat", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ session_id: sessionId, text: text }),
      });
      const data = await res.json();
      hideTyping();
      (data.messages || []).forEach((m) => addMessage(m, "in"));
    } catch (e) {
      hideTyping();
      addMessage({ text: "⚠️ Network hiccup — please try again." }, "in");
    } finally {
      sendBtn.disabled = false;
      input.focus();
    }
  }

  form.addEventListener("submit", (e) => {
    e.preventDefault();
    const v = input.value;
    input.value = "";
    send(v);
  });

  resetBtn.addEventListener("click", () => {
    chat.innerHTML = "";
    send("reset");
  });

  // Kick off with the server greeting.
  send("__start__");
})();
