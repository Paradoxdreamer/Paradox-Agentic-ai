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
        } else if (mode === "web") {
          path = "/api/reach/web";
        } else if (mode === "rss") {
          path = "/api/reach/rss";
        } else if (mode === "github") {
          path = "/api/reach/github";
        } else if (mode === "v2ex") {
          path = "/api/reach/v2ex";
          body = { target: input || "hot", limit: 15 };
        }
        var res = await fetch(path, {
          method: "POST",
          headers: headers(),
          body: JSON.stringify(body),
        });
        var data = await res.json().catch(function () {
          return {};
        });
        if (!res.ok) {
          out.textContent = data.detail || res.statusText || "error";
          return;
        }
        if (
          data.text &&
          (data.backend === "timedtext" ||
            data.content_type === "markdown" ||
            data.content_type === "text")
        ) {
          out.textContent =
            (data.title ? data.title + "\n\n" : "") +
            data.text +
            (data.backend ? "\n\n— " + data.backend : "");
          return;
        }
        if (data.kind === "hot" || data.kind === "latest") {
          var lines = ["V2EX " + data.kind + " (" + (data.count || 0) + ")"];
          (data.items || []).forEach(function (it, i) {
            lines.push(
              (i + 1) +
                ". [" +
                (it.node || "?") +
                "] " +
                (it.title || "") +
                " — @" +
                (it.author || "") +
                " · " +
                (it.replies || 0) +
                " replies"
            );
            if (it.url) lines.push("   " + it.url);
          });
          lines.push("— " + (data.backend || "v2ex"));
          out.textContent = lines.join("\n");
          return;
        }
        if (data.kind === "topic" && data.topic) {
          var t = data.topic;
          var lines2 = [
            t.title || "topic",
            "node: " + (t.node || "") + " · @" + (t.author || "") + " · replies: " + (t.replies || 0),
            t.url || "",
            "",
            (t.content || "").slice(0, 4000),
            "",
            "— replies (" + (data.reply_count || 0) + ") —",
          ];
          (data.replies || []).slice(0, 20).forEach(function (r) {
            lines2.push("@" + (r.author || "?") + ": " + (r.content || "").slice(0, 400));
          });
          lines2.push("— " + (data.backend || "v2ex"));
          out.textContent = lines2.join("\n");
          return;
        }
        out.textContent = JSON.stringify(data, null, 2);
      } catch (err) {
        out.textContent = err.message || String(err);
      }
    };
  });
})();
