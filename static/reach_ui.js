/* Reach tab + vault panel — loaded after app.js */
(function () {
  function ready(fn) {
    if (document.readyState !== "loading") fn();
    else document.addEventListener("DOMContentLoaded", fn);
  }

  function headers() {
    var h = { "Content-Type": "application/json" };
    var k = localStorage.getItem("paradox_api_key");
    var o = localStorage.getItem("paradox_owner_key");
    if (k) h["X-API-Key"] = k;
    if (o) h["X-Owner-Key"] = o;
    return h;
  }

  function setMsg(text, ok) {
    var el = document.getElementById("vaultMsg");
    if (!el) return;
    el.textContent = text || "";
    el.style.color = ok ? "var(--teal)" : "var(--ember)";
  }

  function paintBadges(status) {
    var plats = (status && status.platforms) || {};
    var tw = plats.twitter || {};
    var rd = plats.reddit || {};
    var bTw = document.getElementById("badgeTwitter");
    var bRd = document.getElementById("badgeReddit");
    if (bTw) {
      bTw.textContent = "twitter: " + (tw.configured ? "unlocked" : "locked");
      bTw.style.color = tw.configured ? "var(--teal)" : "var(--text-dim)";
    }
    if (bRd) {
      bRd.textContent = "reddit: " + (rd.configured ? "unlocked" : "locked");
      bRd.style.color = rd.configured ? "var(--teal)" : "var(--text-dim)";
    }
  }

  async function refreshVault() {
    try {
      var r = await fetch("/api/vault/status", { headers: headers() });
      var data = await r.json().catch(function () { return {}; });
      if (!r.ok) {
        setMsg(data.detail || "owner key required for vault", false);
        paintBadges({ platforms: {} });
        return;
      }
      paintBadges(data);
      setMsg("vault ok", true);
    } catch (e) {
      setMsg(e.message || String(e), false);
    }
  }

  async function saveTwitter() {
    var auth = ((document.getElementById("vaultTwAuth") || {}).value || "").trim();
    var ct0 = ((document.getElementById("vaultTwCt0") || {}).value || "").trim();
    if (!auth || !ct0) { setMsg("need both auth_token and ct0", false); return; }
    try {
      var r = await fetch("/api/vault/twitter", {
        method: "PUT",
        headers: headers(),
        body: JSON.stringify({ platform: "twitter", secrets: { auth_token: auth, ct0: ct0 } }),
      });
      var data = await r.json().catch(function () { return {}; });
      if (!r.ok) { setMsg(data.detail || "save failed", false); return; }
      setMsg("twitter cookies saved", true);
      var a = document.getElementById("vaultTwAuth"); if (a) a.value = "";
      var c = document.getElementById("vaultTwCt0"); if (c) c.value = "";
      refreshVault();
    } catch (e) { setMsg(e.message || String(e), false); }
  }

  async function clearTwitter() {
    try {
      var r = await fetch("/api/vault/twitter", { method: "DELETE", headers: headers() });
      if (!r.ok) {
        var data = await r.json().catch(function () { return {}; });
        setMsg(data.detail || "clear failed", false); return;
      }
      setMsg("twitter cleared", true); refreshVault();
    } catch (e) { setMsg(e.message || String(e), false); }
  }

  async function saveReddit() {
    var cookie = ((document.getElementById("vaultRdCookie") || {}).value || "").trim();
    if (!cookie) { setMsg("paste reddit cookie header", false); return; }
    try {
      var r = await fetch("/api/vault/reddit", {
        method: "PUT",
        headers: headers(),
        body: JSON.stringify({ platform: "reddit", secrets: { cookie: cookie } }),
      });
      var data = await r.json().catch(function () { return {}; });
      if (!r.ok) { setMsg(data.detail || "save failed", false); return; }
      setMsg("reddit cookie saved", true);
      var t = document.getElementById("vaultRdCookie"); if (t) t.value = "";
      refreshVault();
    } catch (e) { setMsg(e.message || String(e), false); }
  }

  async function clearReddit() {
    try {
      var r = await fetch("/api/vault/reddit", { method: "DELETE", headers: headers() });
      if (!r.ok) {
        var data = await r.json().catch(function () { return {}; });
        setMsg(data.detail || "clear failed", false); return;
      }
      setMsg("reddit cleared", true); refreshVault();
    } catch (e) { setMsg(e.message || String(e), false); }
  }

  ready(function () {
    var btn = document.getElementById("reachGoBtn");
    if (btn) {
      btn.onclick = async function () {
        var mode = (document.getElementById("reachMode") || {}).value || "read";
        var input = ((document.getElementById("reachInput") || {}).value || "").trim();
        var out = document.getElementById("reachOut");
        if (!out) return;
        out.textContent = "…";
        try {
          if (mode === "doctor") {
            var r0 = await fetch("/api/reach/doctor", { headers: headers() });
            out.textContent = JSON.stringify(await r0.json(), null, 2);
            return;
          }
          if (mode === "vault") {
            await refreshVault();
            var rV = await fetch("/api/vault/status", { headers: headers() });
            out.textContent = JSON.stringify(await rV.json(), null, 2);
            return;
          }
          if (!input && mode !== "v2ex") {
            out.textContent = "enter a URL or query";
            return;
          }
          var path = "/api/reach/read";
          var body = { url: input || "hot" };
          if (mode === "search" || mode === "github-search") {
            path = mode === "search" ? "/api/reach/search" : "/api/reach/github-search";
            body = { query: input, limit: 8 };
          } else if (mode === "youtube") {
            path = "/api/reach/youtube";
            body = { url: input, lang: "en" };
          } else if (mode === "web") path = "/api/reach/web";
          else if (mode === "rss") path = "/api/reach/rss";
          else if (mode === "github") path = "/api/reach/github";
          else if (mode === "v2ex") {
            path = "/api/reach/v2ex";
            body = { target: input || "hot", limit: 15 };
          } else if (mode === "twitter") {
            path = "/api/reach/twitter";
            body = /^(https?:|status\/|\d+$)/i.test(input)
              ? { url: input }
              : { query: input, limit: 10 };
          } else if (mode === "reddit") {
            path = "/api/reach/reddit";
            body = /reddit\.com|redd\.it|^r\//i.test(input)
              ? { url: input }
              : { query: input, limit: 10 };
          }
          var res = await fetch(path, {
            method: "POST",
            headers: headers(),
            body: JSON.stringify(body),
          });
          var data = await res.json().catch(function () { return {}; });
          if (!res.ok) {
            out.textContent = data.detail || res.statusText || "error";
            return;
          }
          if (
            data.text &&
            (data.backend === "timedtext" ||
              data.backend === "fxtwitter" ||
              data.content_type === "markdown" ||
              data.content_type === "text")
          ) {
            out.textContent =
              (data.title || data.author ? (data.title || "@" + data.author) + "\n\n" : "") +
              data.text +
              (data.backend ? "\n\n— " + data.backend : "");
            return;
          }
          if (data.kind === "hot" || data.kind === "latest") {
            var lines = ["V2EX " + data.kind + " (" + (data.count || 0) + ")"];
            (data.items || []).forEach(function (it, i) {
              lines.push(i + 1 + ". [" + (it.node || "?") + "] " + (it.title || ""));
            });
            out.textContent = lines.join("\n");
            return;
          }
          out.textContent = JSON.stringify(data, null, 2);
        } catch (err) {
          out.textContent = err.message || String(err);
        }
      };
    }

    var rf = document.getElementById("vaultRefreshBtn");
    if (rf) rf.onclick = refreshVault;
    var ts = document.getElementById("vaultTwSave");
    if (ts) ts.onclick = saveTwitter;
    var tc = document.getElementById("vaultTwClear");
    if (tc) tc.onclick = clearTwitter;
    var rs = document.getElementById("vaultRdSave");
    if (rs) rs.onclick = saveReddit;
    var rc = document.getElementById("vaultRdClear");
    if (rc) rc.onclick = clearReddit;
    refreshVault();
  });
})();
