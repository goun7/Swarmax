/* swarmax landing demo-motoru - statik render.
 *
 * Tarayici DISARINA bugunu cagrisi YAPMAZ: JSON-RPC/HTTP/fetch/yerel-sunucu
 * hicbiri yoktur; tum veriler bu sayfaya gomuludur (<script type=...> veya
 * <noscript> icindeki demo-data.json yedegini okur). sunucuyu YALNIZCA
 * `python3 -m http.server landing/` ile yerel-statik-dagitim icin kullanin.
 */
"use strict";

function renderDemo(root, demo) {
  if (!root || !demo) return;
  var lang = document.documentElement.getAttribute("lang") || "tr";
  function N(id) { return root.querySelector(id); }

  /* ---- filo-genel-bakis ---- */
  var s = demo.fleet_status ? demo.fleet_status.summary : null;
  if (s) {
    var m = N("#fleet-metrics");
    if (m) {
      m.querySelector('[data-k="agents"]').textContent = String(s.agents);
      m.querySelector('[data-k="open"]').textContent = String(s.open_alarms);
      m.querySelector('[data-k="breached"]').textContent = String(s.breached);
      m.querySelector('[data-k="events"]').textContent = String(s.events_24h);
    }
  }
  var agents = demo.agents || [];
  var alarms = (demo.fleet_status && demo.fleet_status.open_alarms) || [];
  var alarmAgent = {};
  alarms.forEach(function (a) { alarmAgent[a.agent_id] = (alarmAgent[a.agent_id] || 0) + 1; });

  function healthOf(a) {
    var n = alarmAgent[a.agent_id] || 0;
    if (n === 0) return ["healthy", "saglikli"];
    if (n <= 1) return ["warn", "uyari"];
    return ["warn", "uyari"];
  }

  var counts = { healthy: 0, warn: 0, unknown: 0 };
  agents.forEach(function (a) {
    var h = (a.status === "active") ? healthOf(a) : ["unknown", "belirsiz"];
    counts[h[0]] += 1;
  });
  ["healthy", "warn", "unknown"].forEach(function (k) {
    var el = N('[data-health="' + k + '"]');
    if (el) el.textContent = String(counts[k]);
  });
  var bar = N("#health-bar");
  if (bar) {
    var total = Math.max(1, agents.length);
    ["healthy", "warn", "unknown"].forEach(function (k) {
      var seg = bar.querySelector(".h-" + k);
      if (seg) seg.style.width = ((counts[k] / total) * 100).toFixed(1) + "%";
    });
  }

  /* ---- ajan-tablosu ---- */
  var tbody = N("#agent-tbody");
  if (tbody) {
    tbody.textContent = "";
    agents.forEach(function (a) {
      var tr = document.createElement("tr");
      var h = (a.status === "active") ? healthOf(a) : ["unknown", "belirsiz"];
      var nAl = alarmAgent[a.agent_id] || 0;
      var cal = (a.status === "unknown") ? "-" : (nAl ? "analiz-zorunlu" : "kalibre");
      tr.innerHTML =
        '<td class="mono">' + esc(a.agent_id) + "</td>" +
        '<td class="hide-sm">' + esc(a.fleet_name) + "</td>" +
        '<td class="hide-sm">' + esc(a.role) + "</td>" +
        '<td><span class="st st-' + h[0] + '">' + h[1] + "</span></td>" +
        '<td class="mono">' + String(nAl) + "</td>" +
        '<td class="hide-sm">' + cal + "</td>";
      tbody.appendChild(tr);
    });
  }

  /* ---- acik-alarm kuyrugu ---- */
  var abody = N("#alarm-tbody");
  if (abody) {
    abody.textContent = "";
    var sevOrder = { Emergency: 0, Critical: 1, Medium: 2, Low: 3 };
    alarms.slice().sort(function (x, y) {
      return (sevOrder[x.severity] - sevOrder[y.severity]) ||
        String(x.sla_hours) .localeCompare(String(y.sla_hours), undefined, { numeric: true });
    }).forEach(function (a) {
      var tr = document.createElement("tr");
      tr.innerHTML =
        '<td class="mono">' + esc(a.alarm_id.replace(/^alm_/, "")) + "</td>" +
        '<td class="mono">' + esc(a.agent_id) + "</td>" +
        "<td>" + esc(a.signal) + "</td>" +
        '<td><span class="sev sev-' + esc(a.severity) + '">' + esc(a.severity) + "</span></td>" +
        '<td class="mono">' + String(a.sla_hours) + " sa</td>" +
        '<td class="hide-sm">' + esc(a.reason) + "</td>" +
        '<td class="hide-sm">' + esc(a.protection) + "</td>";
      abody.appendChild(tr);
    });
  }

  /* ---- audit-trail zaman-cizelgesi ---- */
  var tl = N("#audit-timeline");
  if (tl) {
    tl.textContent = "";
    var events = demo.audit_trail_events || [];
    events.forEach(function (e) {
      var li = document.createElement("li");
      if (e.event_type === "ledger_seal") li.className = "seal";
      li.innerHTML =
        '<div class="t-meta">seq ' + String(e.seq) + " &middot; " +
        esc(e.created_at) + "</div>" +
        '<div class="t-title">' + esc(e.event_type) + "</div>" +
        '<div class="t-meta">payload ' + esc(e.payload_hash.slice(0, 16)) +
        " &hellip; prev " + esc(e.prev_hash.slice(0, 16)) + " &hellip;</div>";
      tl.appendChild(li);
    });
  }
  var at = demo.audit_trail;
  if (at) {
    var box = N("#audit-summary");
    if (box) {
      var chainOk = at.chain && at.chain.ok;
      var sealsOk = at.seals && at.seals.all_ok;
      box.innerHTML =
        '<div><span class="st st-' + (chainOk ? "healthy" : "warn") + '">' +
        "hash-zinciri " + (chainOk ? "tamam" : "kirik") + "</span> " +
        '<span class="st st-' + (sealsOk ? "healthy" : "warn") + '">' +
        String((at.seals && at.seals.count) || 0) + " muhur dogrulandi</span></div>" +
        '<div class="small muted" style="margin-top:6px">zincir ' +
        String((at.chain && at.chain.entries_checked) || 0) +
        " giris &middot; kanit mihirleri Ed25519/Merkle (RFC 8032)</div>";
    }
  }

  /* ---- ornek-ajan-sayfasi (agent_health) ---- */
  var ah = demo.agent_health_example;
  if (ah && ah.state) {
    var card = N("#agent-example");
    if (card) {
      var tools = ah.state.tools_7d || [];
      var toolHtml = tools.map(function (t) {
        return '<li><code>' + esc(t.tool_name) + "</code> &times; " + String(t.c) + "</li>";
      }).join("");
      card.innerHTML =
        '<div class="aid mono">' + esc(ah.agent.agent_id) +
          ' <span class="demo-tag">agent_health ornegi</span></div>' +
        '<div class="arow muted">' + esc(ah.agent.fleet_name) + " / " +
          esc(ah.agent.role) + " / " + esc(ah.agent.status) + "</div>" +
        '<table style="margin:10px 0"><tbody>' +
        row("etkinlik-24s", String(ah.state.events_24h)) +
        row("maliyet-24s / toplam", String(ah.state.cost_24h) + " / " +
            String(ah.state.cost_total)) +
        row("hata-24s", String(ah.state.errors_24h)) +
        row("acik-alarm / ticket", String(ah.state.open_alarms) + " / " +
            String(ah.state.open_tickets)) +
        row("kalibrasyon", esc(ah.state.calibration)) +
        "</tbody></table>" +
        '<div class="arow muted">son-7-gun arac-kullanimi:</div>' +
        '<ul class="small">' + toolHtml + "</ul>";
    }
  }

  /* ---- MCP arac listesi ---- */
  var mcp = demo.mcp_tools || [];
  var mtbody = N("#mcp-tbody");
  if (mtbody) {
    mtbody.textContent = "";
    mcp.forEach(function (t) {
      var tr = document.createElement("tr");
      tr.innerHTML =
        '<td><span class="tool-tag">' + esc(t.name) + "</span></td>" +
        "<td>" + esc(t.required.join(", ") || "-") + "</td>" +
        "<td>" + esc(JSON.stringify(t.arguments)) + "</td>" +
        '<td class="mono small">' + esc(t.returns) + "</td>";
      mtbody.appendChild(tr);
    });
  }

  function row(k, v) {
    return "<tr><td class='muted'>" + k + "</td><td>" + v + "</td></tr>";
  }
  function esc(s) {
    return String(s).replace(/&/g, "&amp;").replace(/</g, "&lt;")
      .replace(/>/g, "&gt;").replace(/"/g, "&quot;");
  }
}

(function () {
  var root = document;
  var demo = null;
  var el = document.getElementById("swarmax-demo-data");
  if (el && el.textContent) {
    try { demo = JSON.parse(el.textContent); } catch (e) { demo = null; }
  }
  if (!demo && window.SWARMAX_DEMO) demo = window.SWARMAX_DEMO;
  if (!demo) {
    var fallback = document.getElementById("demo-data-fallback");
    if (fallback) fallback.style.display = "block";
    return;
  }
  renderDemo(root, demo);
})();
