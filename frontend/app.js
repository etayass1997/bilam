const byId = (id) => document.getElementById(id);
const number = (value) => new Intl.NumberFormat("he-IL").format(value);

function element(tag, className, value) {
  const node = document.createElement(tag);
  if (className) node.className = className;
  if (value !== undefined) node.textContent = String(value);
  return node;
}

function setStatus(id, message, isError = false) {
  const node = byId(id);
  node.textContent = message;
  node.classList.toggle("error", isError);
}

async function api(path, params = {}) {
  const url = new URL(path, location.origin);
  for (const [key, value] of Object.entries(params)) {
    if (value) url.searchParams.set(key, value);
  }
  const response = await fetch(url, { headers: { Accept: "application/json" } });
  const data = await response.json();
  if (!response.ok) throw new Error(data.error || "הבקשה נכשלה. נסו שוב.");
  return data;
}

function safeSourceUrl(raw) {
  try {
    const url = new URL(raw);
    return ["http:", "https:"].includes(url.protocol) ? url.href : null;
  } catch { return null; }
}

function sourceCard(title, body, url) {
  const card = element("article", "source-card");
  card.append(element("h3", "", title), element("p", "", body));
  const safeUrl = safeSourceUrl(url);
  if (safeUrl) {
    const link = element("a", "", "פתיחת המקור בספריא");
    link.href = safeUrl;
    link.target = "_blank";
    link.rel = "noopener noreferrer";
    card.append(link);
  }
  return card;
}

async function submit(form, statusId, resultsId, work) {
  const button = form.querySelector('button[type="submit"]');
  const results = byId(resultsId);
  button.disabled = true;
  results.replaceChildren();
  setStatus(statusId, "מחפש במאגר…");
  try { await work(results); }
  catch (error) {
    setStatus(statusId, error instanceof TypeError ? "לא ניתן להתחבר לשרת. בדקו את החיבור לאינטרנט ונסו שוב." : error.message, true);
  } finally { button.disabled = false; }
}

document.querySelectorAll(".tab").forEach((tab) => {
  tab.addEventListener("click", () => {
    document.querySelectorAll(".tab").forEach((item) => {
      const active = item === tab;
      item.classList.toggle("active", active);
      item.setAttribute("aria-selected", String(active));
      byId(item.dataset.panel).hidden = !active;
    });
  });
});

byId("search-form").addEventListener("submit", (event) => {
  event.preventDefault();
  const form = event.currentTarget;
  submit(form, "search-status", "search-results", async (results) => {
    const data = await api("/api/search", { query: byId("search-query").value.trim(), parasha: byId("search-parasha").value, limit: "10" });
    setStatus("search-status", data.count ? `${number(data.count)} מקורות נמצאו` : "לא נמצאו מקורות. נסו ניסוח אחר.");
    for (const source of data.sources) results.append(sourceCard(source.source_label, source.text, source.source_url));
  });
});

byId("count-form").addEventListener("submit", (event) => {
  event.preventDefault();
  const form = event.currentTarget;
  submit(form, "count-status", "count-results", async (results) => {
    const data = await api("/api/count-word", { word: byId("count-word").value.trim(), parasha: byId("count-parasha").value, match_type: byId("match-type").value });
    setStatus("count-status", "הספירה הושלמה");
    results.append(element("div", "summary", `${number(data.total_occurrences)} מופעים ב־${number(data.verses_count)} פסוקים`));
    if (data.matches_truncated) results.append(element("p", "muted", "מוצגים 25 הפסוקים הראשונים בלבד; הסכום כולל את כולם."));
    for (const match of data.matches) results.append(sourceCard(`${match.ref_he} · ${number(match.count)} מופעים`, match.verse_text));
  });
});

byId("stats-form").addEventListener("submit", (event) => {
  event.preventDefault();
  const form = event.currentTarget;
  submit(form, "stats-status", "stats-results", async (results) => {
    const data = await api("/api/parasha-stats", { parasha: byId("stats-parasha").value });
    setStatus("stats-status", data.parasha);
    results.append(element("div", "summary", `${number(data.total_verses)} פסוקים · ${number(data.total_words)} מילים`));
    results.append(element("p", "muted", `פרקים: ${data.chapters.map(number).join(", ")}`));
  });
});

async function initialize() {
  try {
    const [portions, health] = await Promise.all([api("/api/parashot"), api("/health")]);
    for (const id of ["search-parasha", "count-parasha", "stats-parasha"]) {
      const select = byId(id);
      for (const parasha of portions.parashot) {
        const option = element("option", "", parasha);
        option.value = parasha;
        select.append(option);
      }
    }
    byId("corpus-status").textContent = `${number(health.doc_count)} יחידות מקור זמינות לחיפוש.`;
  } catch {
    byId("corpus-status").textContent = "המאגר אינו זמין כרגע. בדקו את החיבור לאינטרנט.";
  }
  try {
    const { plugin_url: pluginUrl } = await api("/config");
    const url = new URL(pluginUrl);
    if (url.protocol === "https:" && ["chatgpt.com", "www.chatgpt.com"].includes(url.hostname)) byId("plugin-link").href = url.href;
  } catch { /* The mobile search works without a ChatGPT plugin link. */ }
}
initialize();

if ("serviceWorker" in navigator) window.addEventListener("load", () => navigator.serviceWorker.register("./service-worker.js").catch(() => {}));
let installPrompt;
window.addEventListener("beforeinstallprompt", (event) => {
  event.preventDefault();
  installPrompt = event;
  byId("install-button").hidden = false;
});
byId("install-button").addEventListener("click", async () => {
  if (!installPrompt) return;
  installPrompt.prompt();
  await installPrompt.userChoice;
  installPrompt = undefined;
  byId("install-button").hidden = true;
});
