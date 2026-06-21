// עדכן לכתובת ה-Render הסופית של ה-backend לאחר deploy
const BACKEND_URL = "https://bilam-czk0.onrender.com";

const STORAGE_KEY_API = "bilam_api_key";
const STORAGE_KEY_HISTORY = "bilam_history";

const chatBox = document.getElementById("chat-box");
const composer = document.getElementById("composer");
const questionInput = document.getElementById("question");
const sendBtn = document.getElementById("send-btn");
const apiKeyInput = document.getElementById("api-key");
const saveKeyBtn = document.getElementById("save-key");
const toggleKeyBtn = document.getElementById("toggle-key");

let history = JSON.parse(localStorage.getItem(STORAGE_KEY_HISTORY) || "[]");

function init() {
  const savedKey = localStorage.getItem(STORAGE_KEY_API);
  if (savedKey) apiKeyInput.value = savedKey;
  history.forEach((entry) => renderMessage(entry.role, entry.text, entry.sources, entry.question));
}

saveKeyBtn.addEventListener("click", () => {
  localStorage.setItem(STORAGE_KEY_API, apiKeyInput.value.trim());
  saveKeyBtn.textContent = "נשמר ✓";
  setTimeout(() => (saveKeyBtn.textContent = "שמור"), 1500);
});

toggleKeyBtn.addEventListener("click", () => {
  apiKeyInput.type = apiKeyInput.type === "password" ? "text" : "password";
});

function renderMessage(role, text, sources, question) {
  const div = document.createElement("div");
  div.className = `msg ${role}`;
  div.textContent = text;

  if (sources && sources.length) {
    const sourcesDiv = document.createElement("div");
    sourcesDiv.className = "sources";
    const label = document.createElement("strong");
    label.textContent = "מקורות:";
    sourcesDiv.appendChild(label);
    const ul = document.createElement("ul");
    sources.forEach((s) => {
      const li = document.createElement("li");
      const refLabel = s.ref_he || `פרק ${s.chapter} פסוק ${s.verse}`;
      li.textContent = s.commentator_name ? `${refLabel} — ${s.commentator_name}` : `${refLabel} — טקסט התורה`;
      ul.appendChild(li);
    });
    sourcesDiv.appendChild(ul);
    div.appendChild(sourcesDiv);
  }

  if (role === "bot" && question) {
    const actions = document.createElement("div");
    actions.className = "msg-actions";
    const dlBtn = document.createElement("button");
    dlBtn.className = "download-btn";
    dlBtn.textContent = "הורד כ-Word";
    dlBtn.addEventListener("click", () => downloadDocx(question));
    actions.appendChild(dlBtn);
    div.appendChild(actions);
  }

  chatBox.appendChild(div);
  chatBox.scrollTop = chatBox.scrollHeight;
}

function saveHistory() {
  localStorage.setItem(STORAGE_KEY_HISTORY, JSON.stringify(history));
}

function getApiKey() {
  return localStorage.getItem(STORAGE_KEY_API) || apiKeyInput.value.trim();
}

async function downloadDocx(question) {
  try {
    const resp = await fetch(`${BACKEND_URL}/generate-docx`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ messages: [{ role: "user", content: question }] }),
    });
    if (!resp.ok) {
      const err = await resp.json().catch(() => ({}));
      alert(err.error || "שגיאה ביצירת המסמך");
      return;
    }
    const blob = await resp.blob();
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = "bilam.docx";
    document.body.appendChild(a);
    a.click();
    a.remove();
    URL.revokeObjectURL(url);
  } catch (e) {
    alert("שגיאת תקשורת עם השרת");
  }
}

composer.addEventListener("submit", async (e) => {
  e.preventDefault();
  const question = questionInput.value.trim();
  if (!question) return;

  const apiKey = getApiKey();
  if (!apiKey) {
    renderMessage("error", "יש להזין מפתח Anthropic API לפני שליחת שאלה.");
    return;
  }

  history.push({ role: "user", text: question });
  renderMessage("user", question);
  saveHistory();
  questionInput.value = "";
  sendBtn.disabled = true;

  try {
    const messages = history
      .filter((h) => h.role === "user" || h.role === "bot")
      .map((h) => ({ role: h.role === "bot" ? "assistant" : "user", content: h.text }));

    const resp = await fetch(`${BACKEND_URL}/chat`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ messages, api_key: apiKey }),
    });
    const data = await resp.json();

    if (!resp.ok) {
      renderMessage("error", data.error || "שגיאה לא ידועה");
      return;
    }

    history.push({ role: "bot", text: data.reply, sources: data.sources, question });
    renderMessage("bot", data.reply, data.sources, question);
    saveHistory();
  } catch (e) {
    renderMessage("error", "שגיאת תקשורת עם השרת");
  } finally {
    sendBtn.disabled = false;
  }
});

init();
