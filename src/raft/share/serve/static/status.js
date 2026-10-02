/* Fill control-plane + apps panels from GET /api/status (see ServePage). */
(function () {
  var COLUMNS = ["name", "group", "status", "cpu", "memory", "uptime"];
  var HEADERS = ["Name", "Group", "Status", "CPU", "Memory", "Uptime"];
  var inFlight = false;

  function el(id) {
    return document.getElementById(id);
  }

  function setLoading(busy) {
    var node = el("status-loading");
    var btn = el("status-refresh");
    if (node) {
      node.hidden = !busy;
      node.setAttribute("aria-busy", busy ? "true" : "false");
    }
    if (btn) {
      btn.disabled = busy;
      btn.classList.toggle("is-loading", busy);
    }
  }

  function showError(message) {
    var node = el("status-error");
    if (!node) return;
    node.hidden = false;
    node.textContent = message;
  }

  function clearError() {
    var node = el("status-error");
    if (!node) return;
    node.hidden = true;
    node.textContent = "";
  }

  function emptyMessage(text) {
    var p = document.createElement("p");
    p.className = "muted";
    p.textContent = text;
    return p;
  }

  function tableFor(rows) {
    var table = document.createElement("table");
    var thead = document.createElement("thead");
    var hr = document.createElement("tr");
    HEADERS.forEach(function (label) {
      var th = document.createElement("th");
      th.textContent = label;
      hr.appendChild(th);
    });
    thead.appendChild(hr);
    table.appendChild(thead);
    var tbody = document.createElement("tbody");
    rows.forEach(function (row) {
      var tr = document.createElement("tr");
      COLUMNS.forEach(function (key) {
        var td = document.createElement("td");
        td.textContent = row[key] == null ? "" : String(row[key]);
        tr.appendChild(td);
      });
      tbody.appendChild(tr);
    });
    table.appendChild(tbody);
    return table;
  }

  function fillPanel(panelId, rows, emptyText) {
    var panel = el(panelId);
    if (!panel) return;
    panel.textContent = "";
    if (!rows || !rows.length) {
      panel.appendChild(emptyMessage(emptyText));
      return;
    }
    panel.appendChild(tableFor(rows));
  }

  function applyPayload(data) {
    fillPanel("control-plane-panel", data.control_plane, "No control-plane services in snapshot.");
    fillPanel("apps-panel", data.apps, "No applied apps (or none in snapshot).");
  }

  function loadStatus() {
    if (inFlight) return;
    inFlight = true;
    clearError();
    setLoading(true);
    fetch("/api/status")
      .then(function (res) {
        if (!res.ok) throw new Error("status " + res.status);
        return res.json();
      })
      .then(function (data) {
        applyPayload(data);
        inFlight = false;
        setLoading(false);
      })
      .catch(function () {
        inFlight = false;
        setLoading(false);
        showError("Failed to load status. Refresh or check raft serve.");
      });
  }

  function bindRefresh() {
    var btn = el("status-refresh");
    if (btn) btn.addEventListener("click", loadStatus);
  }

  function start() {
    bindRefresh();
    loadStatus();
  }

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", start);
  } else {
    start();
  }
})();
