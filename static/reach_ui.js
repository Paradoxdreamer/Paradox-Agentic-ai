/* Reach tab handlers — loaded after app.js */
(function () {
  function ready(fn) {
    if (document.readyState !== "loading") fn();
    else document.addEventListener("DOMContentLoaded", fn);
  }
  ready(function () {
    var btn = document.getElementById("reachGoBtn");
    if (!btn) return;
    btn.onclick = async function () {
      var mode = (document.getElementById("reachMode") || {}).value || "read";
      var input = ((document.getElementById("reachInput") || {}).value || "").trim();
      var out = document.getElementById("reachOut");
      if (!out) return;
      out.textContent = "…";
      function headers() {
        var h = { "Content-Type": "application/json" };
        var k = localStorage.getItem("paradox_api_key");
        var o = localStorage.getItem("paradox_owner_key");
        if (k) h["X-API-Key"] = k;
        if (o) h["X-Owner-Key"] = o;
        return h;
      }
      try {
        if (mode === "doctor") {
          var r0 = await fetch("/api/reach/doctor", { headers: headers() });
          out.textContent = JSON.stringify(await r0.json(), null, 2);
          return;
        }
        if (!input) { out.textContent = "enter a URL or query"; return; }
        var path = "/api/reach/read";
        var body = { url: input };
        if (mode === "search" || mode === "github-search") {
          path = mode === "search" ? "/api/reach/search" : "/api/reach/github-search";
          body = { query: input, limit: 8 };
        } else if (mode === "youtube") {
          path = "/api/reach/youtube";
          body = { url: input, lang: "en" };
        } else if (mode === "web") path = "/api/reach/web";
        else if (mode === "rss") path = "/api/reach/rss";
        else if (mode === "github") path = "/api/reach/github";
        var res = await fetch(path, { method: "POST", headers: headers(), body: JSON.stringify(body) });
        var data = await res.json().catch(function () { return {}; });
        if (!res.ok) {
          out.textContent = data.detail || res.statusText || "error";
          return;
        }
        if (data.text && (data.backend === "timedtext" || data.content_type === "markdown" || data.content_type === "text")) {
          out.textContent = (data.title ? data.title + "\n\n" : "") + data.text + (data.backend ? "\n\n— " + data.backend : "");
        } else {
          out.textContent = JSON.stringify(data, null, 2);
        }
      } catch (err) {
        out.textContent = err.message || String(err);
      }
    };
  });
})();
