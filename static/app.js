/* Paradox AI console — kept simple on purpose */

const $ = (id) => document.getElementById(id);
const SESSION_MARK = "@@SESSION@@";
const ROUTED_MARK = "@@ROUTED@@";

// ── state ──────────────────────────────────────────────────────────
const state = {
  agent: null,
  sessionId: null,
  providers: [],
  authMode: "none",
  googleOk: false,
  isOwner: false,
  ownerHint: "",
  apiKey: localStorage.getItem("paradox_api_key") || "",
  ownerKey: localStorage.getItem("paradox_owner_key") || "",
  imageB64: null,
  busy: false,
  editorPath: null,
};

// ── storage helpers ────────────────────────────────────────────────
function setApiKey(k) {
  state.apiKey = k || "";
  if (state.apiKey) localStorage.setItem("paradox_api_key", state.apiKey);
  else localStorage.removeItem("paradox_api_key");
}
function setOwnerKey(k) {
  state.ownerKey = k || "";
  if (state.ownerKey) localStorage.setItem("paradox_owner_key", state.ownerKey);
  else localStorage.removeItem("paradox_owner_key");
}
function headers(extra) {
  const h = { ...(extra || {}) };
  if (state.apiKey) h["X-API-Key"] = state.apiKey;
  if (state.ownerKey) h["X-Owner-Key"] = state.ownerKey;
  return h;
}

// ── tiny DOM helpers ───────────────────────────────────────────────
function el(tag, cls, text) {
  const n = document.createElement(tag);
  if (cls) n.className = cls;
  if (text != null) n.textContent = text;
  return n;
}

function appendMsg(role, text) {
  const box = $("messages");
  const div = el("div", "msg " + role, text);
  box.appendChild(div);
  box.scrollTop = box.scrollHeight;
  return div;
}

function setMemStatus() {
  const s = $("memStatus");
  if (s) s.textContent = state.sessionId ? "session: " + state.sessionId.slice(0, 8) + "…" : "session: none";
}

function setBusy(on) {
  state.busy = on;
  const btn = $("sendBtn");
  if (btn) {
    btn.disabled = on;
    btn.textContent = on ? "…" : "Send";
  }
}

// ── API ────────────────────────────────────────────────────────────
async function api(path, opts = {}) {
  return fetch(path, { ...opts, headers: headers(opts.headers || {}) });
}

async function apiJson(path, opts = {}) {
  const res = await api(path, opts);
  let data = null;
  try { data = await res.json(); } catch (_) {}
  if (!res.ok) {
    const msg = (data && (data.detail || data.message)) || res.statusText || "request failed";
    throw new Error(typeof msg === "string" ? msg : JSON.stringify(msg));
  }
  return data;
}

// ── stream chat ────────────────────────────────────────────────────
async function sendChat(text) {
  if (!text || !state.agent || state.busy) return;
  setBusy(true);

  appendMsg("user", text);
  $("input").value = "";

  const agentDiv = appendMsg("agent", "");
  agentDiv.classList.add("streaming");

  const body = {
    agent: state.agent,
    message: text,
    session_id: state.sessionId || undefined,
  };
  if (state.imageB64) {
    body.image_b64 = state.imageB64;
    clearImage();
  }

  try {
    const res = await api("/api/chat/stream", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(body),
    });

    if (!res.ok) {
      const err = await res.text();
      agentDiv.textContent = "[error] " + (err || res.statusText);
      agentDiv.classList.remove("streaming");
      setBusy(false);
      return;
    }

    const reader = res.body.getReader();
    const decoder = new TextDecoder();
    let buf = "";
    let display = "";
    let held = "";

    while (true) {
      const { done, value } = await reader.read();
      if (done) break;
      buf = held + decoder.decode(value, { stream: true });
      held = "";

      const peeled = peelMarkers(buf);
      display += peeled.text;
      held = peeled.held;
      agentDiv.textContent = display || "…";
      $("messages").scrollTop = $("messages").scrollHeight;
    }

    if (held) {
      const peeled = peelMarkers(held);
      display += peeled.text;
    }
    agentDiv.textContent = display || "(empty reply)";
  } catch (e) {
    agentDiv.textContent = "[error] " + e.message;
  }

  agentDiv.classList.remove("streaming");
  setMemStatus();
  setBusy(false);
}

/** Strip control markers. Returns { text, held }. */
function peelMarkers(raw) {
  let text = raw;

  let m = text.match(/@@SESSION@@([\s\S]*?)@@SESSION@@/);
  if (m) {
    state.sessionId = m[1];
    text = text.replace(m[0], "");
  }

  m = text.match(/@@ROUTED@@([\s\S]*?)@@ROUTED@@/);
  if (m) {
    const routed = m[1];
    text = text.replace(m[0], "");
    if (routed && routed !== state.agent) {
      const bar = $("connectionBar");
      if (bar) bar.textContent = "routed → " + routed + " · " + (connectionSummary(routed) || "");
    }
  }

  // incomplete marker — hold from first @@
  const i = text.indexOf("@@");
  if (i >= 0) {
    return { text: text.slice(0, i), held: text.slice(i) };
  }
  return { text, held: "" };
}

// ── image attach ───────────────────────────────────────────────────
function clearImage() {
  state.imageB64 = null;
  const prev = $("imgPreview");
  if (prev) { prev.style.display = "none"; prev.removeAttribute("src"); }
  const clr = $("imgClear");
  if (clr) clr.style.display = "none";
  const inp = $("imgInput");
  if (inp) inp.value = "";
}

function onImagePicked(file) {
  if (!file) return clearImage();
  const reader = new FileReader();
  reader.onload = () => {
    const dataUrl = reader.result;
    const i = dataUrl.indexOf(",");
    state.imageB64 = i >= 0 ? dataUrl.slice(i + 1) : dataUrl;
    const prev = $("imgPreview");
    if (prev) { prev.src = dataUrl; prev.style.display = "block"; }
    const clr = $("imgClear");
    if (clr) clr.style.display = "inline-block";
  };
  reader.readAsDataURL(file);
}

// ── providers ──────────────────────────────────────────────────────
function connectionSummary(id) {
  if (id === "auto") return "router picks a provider per message";
  if (id === "consensus") return "asks every provider, then merges";
  const p = state.providers.find((x) => x.id === id);
  if (!p) return "";
  if (p.connection && p.connection.summary) return p.connection.summary;
  return (p.kind || "") + (p.base_url ? " · " + p.base_url : "");
}

function updateConnectionBar() {
  const bar = $("connectionBar");
  if (!bar) return;
  let text = connectionSummary(state.agent) || "pick a provider";
  const p = state.providers.find((x) => x.id === state.agent);
  if (p && p.connection && p.connection.unofficial) text += "  · unofficial";
  bar.textContent = text;
}

function renderAgents() {
  const strip = $("agentStrip");
  strip.innerHTML = "";
  if (!state.agent && state.providers.length) state.agent = state.providers[0].id;

  const addNode = (id, label, removable) => {
    const node = el("div", "agent-node" + (id === state.agent ? " active" : ""), label);
    node.onclick = () => { state.agent = id; renderAgents(); updateConnectionBar(); };
    if (removable) {
      const x = el("span", null, " ×");
      x.onclick = async (e) => {
        e.stopPropagation();
        if (!confirm("Remove " + id + "?")) return;
        await api("/api/providers/" + encodeURIComponent(id), { method: "DELETE" });
        if (state.agent === id) state.agent = null;
        await loadProviders();
      };
      node.appendChild(x);
    }
    strip.appendChild(node);
  };

  state.providers.forEach((p) => addNode(p.id, p.name || p.id, state.isOwner));
  addNode("auto", "auto-route", false);
  addNode("consensus", "consensus", false);

  if (state.isOwner) {
    const btn = el("button", "add-provider-btn", "+ add model");
    btn.onclick = () => $("providerModalOverlay").classList.add("open");
    strip.appendChild(btn);
  }
  updateConnectionBar();
  renderPipelineRoles();
}

async function loadProviders() {
  try {
    const data = await apiJson("/api/providers");
    state.providers = data.providers || [];
  } catch (_) { state.providers = []; }
  renderAgents();
}

// ── workspace ──────────────────────────────────────────────────────
async function loadFiles() {
  const list = $("fileList");
  try {
    const data = await apiJson("/api/workspace/files");
    list.innerHTML = "";
    (data.files || []).forEach((f) => {
      const row = el("div", "file-row", f);
      row.onclick = () => openInEditor(f);
      list.appendChild(row);
    });
    if (!(data.files || []).length) list.textContent = "(empty)";
  } catch (_) { list.textContent = "(unreachable)"; }
}

async function loadSnapshots() {
  try {
    const data = await apiJson("/api/snapshots");
    $("snapList").textContent = (data.snapshots || []).map((s) => s.id).join(", ") || "(none)";
  } catch (_) {}
}

async function openInEditor(path) {
  try {
    const data = await apiJson("/api/workspace/file?path=" + encodeURIComponent(path));
    state.editorPath = path;
    $("editorPath").textContent = path;
    $("editorArea").value = data.content || "";
    document.querySelectorAll(".tab").forEach((t) => t.classList.toggle("active", t.dataset.view === "editor"));
    document.querySelectorAll(".view").forEach((v) => v.classList.toggle("active", v.id === "view-editor"));
  } catch (e) { alert(e.message); }
}

// ── account ────────────────────────────────────────────────────────
async function refreshOwner() {
  try {
    const data = await apiJson("/api/owner-status");
    state.isOwner = !!data.is_owner;
    state.ownerHint = data.hint || state.ownerHint;
  } catch (_) { state.isOwner = false; }
}

async function renderAccount() {
  const area = $("accountArea");
  area.innerHTML = "";

  if (state.authMode !== "accounts") {
    const keyIn = el("input");
    keyIn.placeholder = "X-API-Key (optional)";
    keyIn.value = state.apiKey;
    keyIn.oninput = () => setApiKey(keyIn.value.trim());
    const ownIn = el("input");
    ownIn.type = "password";
    ownIn.placeholder = "owner key";
    ownIn.value = state.ownerKey;
    ownIn.onchange = async () => {
      setOwnerKey(ownIn.value.trim());
      await refreshOwner();
      renderAgents();
    };
    area.appendChild(keyIn);
    area.appendChild(ownIn);
    return;
  }

  if (!state.apiKey) {
    const btn = el("button", "ws-btn", "sign in");
    btn.onclick = () => $("authModalOverlay").classList.add("open");
    area.appendChild(btn);
    return;
  }

  try {
    const me = await apiJson("/api/auth/me");
    area.appendChild(el("span", null, me.email + " · " + (me.unlimited_credits ? "∞" : me.credits + " credits")));
    const out = el("button", "ws-btn", "log out");
    out.onclick = () => { setApiKey(""); renderAccount(); };
    area.appendChild(out);
  } catch (_) {
    setApiKey("");
    renderAccount();
  }
}

// ── pipeline roles ─────────────────────────────────────────────────
function renderPipelineRoles() {
  const elp = $("pipelineRoles");
  if (!elp) return;
  elp.innerHTML = "";
  ["architect", "coder", "reviewer"].forEach((key) => {
    const wrap = el("label", null, key + " ");
    const sel = el("select");
    sel.id = "role_" + key;
    state.providers.forEach((p) => {
      const o = el("option", null, p.id);
      o.value = p.id;
      sel.appendChild(o);
    });
    wrap.appendChild(sel);
    elp.appendChild(wrap);
  });
}

// ── provider presets ───────────────────────────────────────────────
const PRESETS = {
  omegatech: { kind: "http_get", base: "https://omegatech-api.dixonomega.tech/api/ai", path: "/Claude", msg: "text", env: "" },
  nvidia: { kind: "openai_compatible", base: "https://integrate.api.nvidia.com/v1", model: "z-ai/glm-5.2", env: "NVIDIA_API_KEY" },
  openai: { kind: "openai_compatible", base: "https://api.openai.com/v1", model: "gpt-4o-mini", env: "OPENAI_API_KEY" },
  groq: { kind: "openai_compatible", base: "https://api.groq.com/openai/v1", model: "llama-3.3-70b-versatile", env: "GROQ_API_KEY" },
};

function applyPreset(name) {
  const p = PRESETS[name];
  if (!p) return;
  $("pf_kind").value = p.kind;
  $("pf_base_url").value = p.base || "";
  if (p.path) $("pf_path").value = p.path;
  if (p.msg) $("pf_message_param").value = p.msg;
  if (p.model) $("pf_model").value = p.model;
  $("pf_api_key_env").value = p.env || "";
  toggleKindFields();
}

function toggleKindFields() {
  const kind = $("pf_kind").value;
  $("kind_openai").classList.toggle("show", kind === "openai_compatible");
  $("kind_http").classList.toggle("show", kind === "http_get");
}

// ── wire events ────────────────────────────────────────────────────
function wire() {
  $("tabs").onclick = (e) => {
    const tab = e.target.closest(".tab");
    if (!tab) return;
    document.querySelectorAll(".tab").forEach((t) => t.classList.toggle("active", t === tab));
    document.querySelectorAll(".view").forEach((v) => v.classList.toggle("active", v.id === "view-" + tab.dataset.view));
  };

  $("composer").onsubmit = (e) => { e.preventDefault(); sendChat($("input").value.trim()); };
  $("input").onkeydown = (e) => {
    if (e.key === "Enter" && !e.shiftKey) { e.preventDefault(); sendChat($("input").value.trim()); }
  };
  $("forgetBtn").onclick = async () => {
    if (state.sessionId) {
      try { await api("/api/session/" + state.sessionId, { method: "DELETE" }); } catch (_) {}
    }
    state.sessionId = null;
    setMemStatus();
    $("messages").innerHTML = "";
    appendMsg("agent", "Session cleared. Pick a provider and say something.");
  };

  if ($("imgBtn")) $("imgBtn").onclick = () => $("imgInput").click();
  if ($("imgInput")) $("imgInput").onchange = (e) => onImagePicked(e.target.files[0]);
  if ($("imgClear")) $("imgClear").onclick = clearImage;

  $("refreshBtn").onclick = loadFiles;
  $("uploadBtn").onclick = () => $("zipInput").click();
  $("zipInput").onchange = async (e) => {
    const file = e.target.files[0];
    if (!file) return;
    const form = new FormData();
    form.append("file", file);
    await api("/api/workspace/upload", { method: "POST", body: form });
    loadFiles();
  };
  $("exportBtn").onclick = async () => {
    const res = await api("/api/workspace/export");
    const blob = await res.blob();
    const a = el("a");
    a.href = URL.createObjectURL(blob);
    a.download = "paradox-workspace.zip";
    a.click();
  };
  $("snapBtn").onclick = async () => {
    await apiJson("/api/snapshots", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ label: null }),
    });
    loadSnapshots();
  };
  $("saveBtn").onclick = async () => {
    if (!state.editorPath) return alert("no file open");
    await apiJson("/api/workspace/file", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ path: state.editorPath, content: $("editorArea").value }),
    });
  };

  $("previewGoBtn").onclick = () => {
    const path = $("previewPath").value.trim() || "index.html";
    const q = state.apiKey ? "&api_key=" + encodeURIComponent(state.apiKey) : "";
    $("previewFrame").src = "/preview/" + path + "?t=" + Date.now() + q;
  };
  $("previewReloadBtn").onclick = () => $("previewGoBtn").click();

  $("pipelineForm").onsubmit = async (e) => {
    e.preventDefault();
    const task = $("pipelineInput").value.trim();
    if (!task) return;
    try {
      const data = await apiJson("/api/pipeline", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          task,
          write_files: true,
          role_providers: {
            architect: $("role_architect")?.value || "glm",
            coder: $("role_coder")?.value || "claude",
            reviewer: $("role_reviewer")?.value || "gpt4mini",
          },
        }),
      });
      $("pipelineBody").textContent = JSON.stringify(data, null, 2);
      loadFiles();
    } catch (err) { $("pipelineBody").textContent = err.message; }
  };

  $("runBtn").onclick = async () => {
    try {
      const data = await apiJson("/api/execute", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ command: $("runCommand").value.trim() }),
      });
      $("runOutput").textContent = JSON.stringify(data, null, 2);
    } catch (err) { $("runOutput").textContent = err.message; }
  };
  $("autofixBtn").onclick = async () => {
    try {
      const data = await apiJson("/api/execute/autofix", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          command: $("runCommand").value.trim(),
          file_path: $("runFile").value.trim() || null,
        }),
      });
      $("runOutput").textContent = JSON.stringify(data, null, 2);
    } catch (err) { $("runOutput").textContent = err.message; }
  };

  $("providerCancelBtn").onclick = () => $("providerModalOverlay").classList.remove("open");
  $("pf_kind").onchange = toggleKindFields;
  $("pf_preset").onchange = () => applyPreset($("pf_preset").value);
  $("providerForm").onsubmit = async (e) => {
    e.preventDefault();
    const kind = $("pf_kind").value;
    const body = {
      id: $("pf_id").value.trim(),
      name: $("pf_name").value.trim() || undefined,
      kind,
      base_url: $("pf_base_url").value.trim(),
      description: $("pf_description").value.trim() || undefined,
      api_key: $("pf_api_key").value.trim() || undefined,
      api_key_env: $("pf_api_key_env").value.trim() || undefined,
      platform: $("pf_preset").value || "custom",
      supports_streaming: $("pf_streaming").checked,
      supports_images: $("pf_images").checked,
    };
    if (kind === "openai_compatible") body.model = $("pf_model").value.trim();
    else {
      body.path = $("pf_path").value.trim() || undefined;
      body.message_param = $("pf_message_param").value.trim() || undefined;
      body.session_param = $("pf_session_param").value.trim() || undefined;
      body.image_param = $("pf_image_param").value.trim() || undefined;
    }
    try {
      const data = await apiJson("/api/providers", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(body),
      });
      $("providerModalOverlay").classList.remove("open");
      state.agent = data.id;
      await loadProviders();
    } catch (err) {
      const errEl = $("providerModalErr");
      errEl.textContent = err.message;
      errEl.style.display = "block";
    }
  };

  let authTab = "login";
  $("authCancelBtn").onclick = () => $("authModalOverlay").classList.remove("open");
  $("authTabLogin").onclick = () => { authTab = "login"; $("signupTermsRow").style.display = "none"; };
  $("authTabSignup").onclick = () => { authTab = "signup"; $("signupTermsRow").style.display = "block"; };
  $("googleLoginBtn").onclick = () => { location.href = "/auth/google/login"; };
  $("authForm").onsubmit = async (e) => {
    e.preventDefault();
    const errEl = $("authModalErr");
    const email = $("auth_email").value.trim();
    const password = $("auth_password").value;
    if (authTab === "signup" && !$("auth_accept_terms").checked) {
      errEl.textContent = "accept terms";
      errEl.style.display = "block";
      return;
    }
    try {
      const data = await apiJson(authTab === "signup" ? "/api/auth/signup" : "/api/auth/login", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(authTab === "signup"
          ? { email, password, accepted_terms: true }
          : { email, password }),
      });
      setApiKey(data.api_key);
      $("authModalOverlay").classList.remove("open");
      await renderAccount();
      loadProviders();
      loadFiles();
    } catch (err) {
      errEl.textContent = err.message;
      errEl.style.display = "block";
    }
  };
}

async function boot() {
  const params = new URLSearchParams(location.search);
  const hash = new URLSearchParams((location.hash || "").replace(/^#/, ""));
  const token = params.get("login_token") || hash.get("login_token");
  const err = params.get("login_error");
  if (token) {
    setApiKey(token);
    history.replaceState({}, "", location.pathname);
  } else if (err) {
    alert("Sign-in failed: " + decodeURIComponent(err));
    history.replaceState({}, "", location.pathname);
  }

  try {
    const meta = await (await fetch("/api/meta")).json();
    state.authMode = meta.auth_mode || "none";
    state.googleOk = !!meta.google_login_available;
    state.ownerHint = meta.owner_hint || "";
  } catch (_) {}

  if (state.googleOk) $("googleLoginBlock").style.display = "block";

  wire();
  await refreshOwner();
  await renderAccount();
  await loadProviders();
  loadFiles();
  loadSnapshots();
  setMemStatus();
}

boot();
