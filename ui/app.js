const state = {
  sources: [],
  selected: 0,
};

const fields = [
  "name",
  "provider",
  "source",
  "url",
  "file",
  "platform",
  "kind",
  "entity",
  "profile",
  "purpose",
  "limit",
  "title",
];

const rows = document.querySelector("#sourceRows");
const form = document.querySelector("#sourceForm");
const statusText = document.querySelector("#statusText");
const modelText = document.querySelector("#modelText");
const logOutput = document.querySelector("#logOutput");
const chatMessages = document.querySelector("#chatMessages");
let lastRevision = "";

async function api(path, options = {}) {
  const response = await fetch(path, {
    headers: { "Content-Type": "application/json" },
    ...options,
  });
  const data = await response.json();
  if (!response.ok) throw new Error(data.error || response.statusText);
  return data;
}

function log(message) {
  const time = new Date().toLocaleTimeString();
  logOutput.textContent = `[${time}] ${message}\n` + logOutput.textContent;
}

async function loadSources() {
  const data = await api("/api/sources");
  const status = await api("/api/status");
  state.sources = data.sources || [];
  state.selected = Math.min(state.selected, Math.max(state.sources.length - 1, 0));
  statusText.textContent = `${state.sources.length}件の監視対象 / ${data.config}`;
  const llm = status.llm || {};
  modelText.textContent = `最高品質: ${llm.model || "local"} / reasoning ${llm.reasoning_effort || "-"} / image ${llm.image_model || "-"}` +
    (llm.api_key_available ? "" : " / APIキー未設定時はローカル改善");
  renderRows();
  renderForm();
}

function filteredSources() {
  const profile = document.querySelector("#profileFilter").value;
  const platform = document.querySelector("#platformFilter").value;
  return state.sources
    .map((item, index) => ({ item, index }))
    .filter(({ item }) => !profile || item.profile === profile)
    .filter(({ item }) => !platform || item.platform === platform);
}

function renderRows() {
  rows.innerHTML = "";
  for (const { item, index } of filteredSources()) {
    const tr = document.createElement("tr");
    tr.className = index === state.selected ? "selected" : "";
    tr.innerHTML = `
      <td>${escapeHtml(item.name || "")}</td>
      <td>${escapeHtml(item.platform || "")}</td>
      <td>${escapeHtml(item.profile || "")}</td>
      <td>${escapeHtml(item.purpose || "")}</td>
      <td>${escapeHtml(item.provider || "")}</td>
      <td>${escapeHtml(String(item.limit || ""))}</td>
    `;
    tr.addEventListener("click", () => {
      commitForm();
      state.selected = index;
      renderRows();
      renderForm();
    });
    rows.appendChild(tr);
  }
}

function renderForm() {
  const item = currentItem();
  for (const field of fields) {
    const input = form.elements[field];
    if (!input) continue;
    input.value = item?.[field] ?? "";
  }
  document.querySelector("#deleteBtn").disabled = !item;
}

function commitForm() {
  const item = currentItem();
  if (!item) return;
  for (const field of fields) {
    const input = form.elements[field];
    if (!input) continue;
    const value = input.value.trim();
    if (!value) {
      delete item[field];
    } else if (field === "limit") {
      item[field] = Number(value);
    } else {
      item[field] = value;
    }
  }
}

function currentItem() {
  return state.sources[state.selected];
}

function addSource() {
  commitForm();
  state.sources.push({
    name: "新しい監視対象",
    provider: "hermes_x",
    platform: "x",
    kind: "post",
    entity: "nakano-yusaku",
    profile: "personal",
    purpose: "style",
    limit: 30,
  });
  state.selected = state.sources.length - 1;
  renderRows();
  renderForm();
}

function deleteSource() {
  if (!currentItem()) return;
  state.sources.splice(state.selected, 1);
  state.selected = Math.max(0, state.selected - 1);
  renderRows();
  renderForm();
}

async function saveSources() {
  commitForm();
  const data = await api("/api/sources", {
    method: "POST",
    body: JSON.stringify({ sources: state.sources }),
  });
  state.sources = data.sources || state.sources;
  renderRows();
  renderForm();
  log("保存しました");
}

async function runCrawl() {
  commitForm();
  await saveSources();
  const data = await api("/api/crawl", { method: "POST", body: "{}" });
  log(data.output || "クロール完了");
}

async function runExport() {
  commitForm();
  const item = currentItem() || {};
  const data = await api("/api/export", {
    method: "POST",
    body: JSON.stringify({
      out_dir: "knowledge",
      clean: true,
      entity: item.entity || "nakano-yusaku",
    }),
  });
  log(`出力しました\n${(data.paths || []).join("\n")}`);
}

async function ingestFile() {
  commitForm();
  const item = currentItem() || {};
  const file = document.querySelector("#manualFile").value.trim() || item.file;
  if (!file) {
    log("ファイルパスを入力してください");
    return;
  }
  const data = await api("/api/ingest-file", {
    method: "POST",
    body: JSON.stringify({
      file,
      source: item.source || item.name || "Manual Upload",
      platform: item.platform || "local",
      kind: item.kind || "artifact",
      entity: item.entity,
      profile: item.profile,
      purpose: item.purpose,
      title: item.title,
    }),
  });
  if (!data.ok) {
    log(data.error || "取り込みに失敗しました");
    return;
  }
  log(`手動取り込み: inserted ${data.inserted}, updated ${data.updated}, skipped ${data.skipped}`);
}

function selectedRoute() {
  const item = currentItem() || {};
  return {
    entity: item.entity || "nakano-yusaku",
    profile: item.profile || "personal",
    purpose: item.purpose || "creative",
  };
}

async function saveArtifact() {
  commitForm();
  const route = selectedRoute();
  const text = document.querySelector("#artifactText").value.trim();
  if (!text) {
    log("制作物本文を入力してください");
    return;
  }
  const data = await api("/api/artifact", {
    method: "POST",
    body: JSON.stringify({
      title: document.querySelector("#artifactTitle").value.trim() || "制作物",
      kind: document.querySelector("#artifactKind").value,
      purpose: document.querySelector("#artifactPurpose").value || route.purpose,
      entity: route.entity,
      profile: route.profile,
      text,
    }),
  });
  log(`制作物を保存: inserted ${data.inserted}, updated ${data.updated}, skipped ${data.skipped}`);
}

async function sendChat() {
  commitForm();
  const input = document.querySelector("#chatInput");
  const message = input.value.trim() || "中野優作仕様にブラッシュアップして";
  const draft = document.querySelector("#artifactText").value.trim();
  if (!draft && !message) return;
  input.value = "";
  addChat("user", message);

  const route = selectedRoute();
  const data = await api("/api/chat/refine", {
    method: "POST",
    body: JSON.stringify({
      draft,
      message,
      asset: document.querySelector("#artifactKind").value,
      entity: "nakano-yusaku",
      profile: "personal",
      style_purpose: "style",
      target_entity: route.entity,
      target_profile: route.profile,
    }),
  });
  lastRevision = data.revised_text || "";
  const modelLine = data.model_used ? `使用モデル: ${data.model_used}\n\n` : "";
  addChat("bot", modelLine + (data.message || "改善案を作成しました。"));
}

function addChat(role, text) {
  const bubble = document.createElement("div");
  bubble.className = role === "user" ? "userBubble" : "botBubble";
  bubble.textContent = text;
  chatMessages.appendChild(bubble);
  chatMessages.scrollTop = chatMessages.scrollHeight;
}

function applyRevision() {
  if (!lastRevision) {
    log("まだ改善案がありません");
    return;
  }
  document.querySelector("#artifactText").value = lastRevision;
  log("改善案を本文へ反映しました");
}

function escapeHtml(value) {
  return value.replace(/[&<>"']/g, (char) => ({
    "&": "&amp;",
    "<": "&lt;",
    ">": "&gt;",
    '"': "&quot;",
    "'": "&#39;",
  })[char]);
}

for (const field of fields) {
  const input = form.elements[field];
  if (input) input.addEventListener("input", () => {
    commitForm();
    renderRows();
  });
}

document.querySelector("#reloadBtn").addEventListener("click", loadSources);
document.querySelector("#saveBtn").addEventListener("click", saveSources);
document.querySelector("#crawlBtn").addEventListener("click", runCrawl);
document.querySelector("#exportBtn").addEventListener("click", runExport);
document.querySelector("#addBtn").addEventListener("click", addSource);
document.querySelector("#deleteBtn").addEventListener("click", deleteSource);
document.querySelector("#ingestFileBtn").addEventListener("click", ingestFile);
document.querySelector("#saveArtifactBtn").addEventListener("click", saveArtifact);
document.querySelector("#sendChatBtn").addEventListener("click", sendChat);
document.querySelector("#applyRevisionBtn").addEventListener("click", applyRevision);
document.querySelector("#chatInput").addEventListener("keydown", (event) => {
  if (event.key === "Enter") {
    event.preventDefault();
    sendChat();
  }
});
document.querySelector("#clearLogBtn").addEventListener("click", () => { logOutput.textContent = ""; });
document.querySelector("#profileFilter").addEventListener("change", renderRows);
document.querySelector("#platformFilter").addEventListener("change", renderRows);

loadSources().catch((error) => {
  statusText.textContent = "読み込みに失敗しました";
  log(error.message);
});
