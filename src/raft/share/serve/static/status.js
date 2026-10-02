/* Fill control-plane + apps panels from GET /api/status (see ServePage). */
(function () {
  var COLUMNS = ["name", "group", "status", "cpu", "memory", "uptime"];
  var HEADERS = ["Name", "Group", "Status", "CPU", "Memory", "Uptime"];

  function el(id) {
    return document.getElementById(id);
  }

  function setLoading(busy) {
    var node = el("status-loading");
    if (!node) return;
    node.hidden = !busy;
    node.setAttribute("aria-busy", busy ? "true" : "false");
  }

  function showError(message) {
    var node = el("status-error");
    if (!node) return;
    node.hidden = false;
    node.textContent = message;
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
    setLoading(true);
    fetch("/api/status")
      .then(function (res) {
        if (!res.ok) throw new Error("status " + res.status);
        return res.json();
      })
      .then(function (data) {
        applyPayload(data);
        setLoading(false);
      })
      .catch(function () {
        setLoading(false);
        showError("Failed to load status. Refresh the page or check raft serve.");
      });
  }

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", loadStatus);
  } else {
    loadStatus();
  }
})();
