var API = "";
var allParams = {};

function toast(msg, type) {
  type = type || "success";
  var el = document.createElement("div");
  el.className = "toast " + type;
  el.textContent = msg;
  document.getElementById("toast-container").appendChild(el);
  setTimeout(function() { el.remove(); }, 3500);
}

async function fetchHealth() {
  try {
    var r = await fetch(API + "/health");
    if (!r.ok) throw new Error(r.status);
    var data = await r.json();
    document.getElementById("status-dot").className = "status-dot online";
    document.getElementById("status-text").textContent = "Connected";
    renderHealth(data);
  } catch (e) {
    document.getElementById("status-dot").className = "status-dot offline";
    document.getElementById("status-text").textContent = "Disconnected";
  }
}

function renderHealth(data) {
  var grid = document.getElementById("health-grid");
  grid.innerHTML = "";
  var components = data.components || data;
  if (typeof components === "object") {
    Object.keys(components).forEach(function(name) {
      var info = components[name];
      var status = (typeof info === "object" && info.error) ? "error" : "ok";
      var div = document.createElement("div");
      div.className = "health-item";
      div.innerHTML = '<span class="dot ' + status + '"></span><span>' + name + "</span>";
      grid.appendChild(div);
    });
  }
}

async function fetchParams() {
  try {
    var r = await fetch(API + "/config");
    if (!r.ok) throw new Error(r.status);
    var data = await r.json();
    allParams = data.current || data;
    renderParams(allParams);
  } catch (e) {
    toast("Failed to load params: " + e.message, "error");
  }
}

function classifyParam(key) {
  var k = key.toLowerCase();
  if (/arena_?13|evolv/.test(k)) return "Arena 13";
  for (var i = 1; i <= 5; i++) {
    if (k.indexOf("arena_" + i) >= 0 || k.indexOf("arena" + i) >= 0) return "Arena " + i;
  }
  if (/scor/.test(k)) return "Scoring";
  if (/vot/.test(k)) return "Voting";
  if (/norm/.test(k)) return "Normalizer";
  if (/backtest/.test(k)) return "Backtester";
  if (/gpu/.test(k)) return "GPU";
  if (/db|postgres|pool/.test(k)) return "DB";
  if (/risk|drawdown|position/.test(k)) return "Risk";
  return "General";
}

function flattenObj(obj, prefix) {
  prefix = prefix || "";
  var result = [];
  Object.keys(obj).forEach(function(k) {
    var v = obj[k];
    var key = prefix ? prefix + "." + k : k;
    if (v && typeof v === "object" && !Array.isArray(v)) {
      result = result.concat(flattenObj(v, key));
    } else {
      result.push([key, v]);
    }
  });
  return result;
}

function renderParams(params, filter) {
  var tbody = document.getElementById("params-body");
  tbody.innerHTML = "";
  var entries = flattenObj(params);
  var fl = (filter || "").toLowerCase();
  var grouped = {};
  entries.forEach(function(entry) {
    var key = entry[0], val = entry[1];
    if (fl && key.toLowerCase().indexOf(fl) < 0) return;
    var group = classifyParam(key);
    if (!grouped[group]) grouped[group] = [];
    grouped[group].push([key, val]);
  });
  var order = ["Arena 1","Arena 2","Arena 3","Arena 4","Arena 5","Arena 13","Scoring","Voting","Normalizer","Backtester","GPU","DB","Risk","General"];
  order.forEach(function(g) {
    if (!grouped[g]) return;
    grouped[g].forEach(function(pair) {
      var key = pair[0], val = pair[1];
      var tr = document.createElement("tr");
      tr.innerHTML = "<td>" + g + "</td><td>" + key + '</td><td class="editable" data-key="' + key + '">' + JSON.stringify(val) + "</td>";
      tr.querySelector(".editable").addEventListener("click", startEdit);
      tbody.appendChild(tr);
    });
  });
}

function startEdit(e) {
  var td = e.currentTarget;
  if (td.querySelector("input")) return;
  var key = td.dataset.key;
  var oldVal = td.textContent;
  var input = document.createElement("input");
  input.value = oldVal;
  td.textContent = "";
  td.appendChild(input);
  input.focus();
  input.addEventListener("keydown", async function(ev) {
    if (ev.key === "Enter") {
      var newVal = input.value;
      try { newVal = JSON.parse(newVal); } catch (_) {}
      try {
        var parts = key.split(".");
        var overrides = {};
        var cur = overrides;
        for (var i = 0; i < parts.length - 1; i++) { cur[parts[i]] = {}; cur = cur[parts[i]]; }
        cur[parts[parts.length - 1]] = newVal;
        var r = await fetch(API + "/config", {
          method: "PUT",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ overrides: overrides }),
        });
        if (!r.ok) throw new Error((await r.json()).detail || r.status);
        toast("Updated " + key);
        fetchParams();
      } catch (err) {
        toast("Error: " + err.message, "error");
        td.textContent = oldVal;
      }
    } else if (ev.key === "Escape") {
      td.textContent = oldVal;
    }
  });
  input.addEventListener("blur", function() { if (td.querySelector("input")) td.textContent = oldVal; });
}

var ARENAS = ["arena_1", "arena_2", "arena_3", "arena_4", "arena_5", "arena_13"];
var ACTIONS = ["start", "stop", "pause", "resume"];

function renderArenas() {
  var grid = document.getElementById("arena-grid");
  grid.innerHTML = "";
  ARENAS.forEach(function(name) {
    var card = document.createElement("div");
    card.className = "arena-card";
    var label = name.replace("_", " ").replace(/\b\w/g, function(c) { return c.toUpperCase(); });
    var btns = "";
    ACTIONS.forEach(function(action) {
      var cls = action === "stop" ? "stop" : action === "pause" ? "pause" : "";
      btns += '<button class="' + cls + '" data-arena="' + name + '" data-action="' + action + '">' + action.charAt(0).toUpperCase() + action.slice(1) + "</button>";
    });
    card.innerHTML = "<h3>" + label + '</h3><div class="btn-row">' + btns + "</div>";
    grid.appendChild(card);
  });
  grid.addEventListener("click", async function(e) {
    if (e.target.tagName !== "BUTTON") return;
    var arena = e.target.dataset.arena;
    var action = e.target.dataset.action;
    try {
      var r = await fetch(API + "/arena/control", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ arena_name: arena, action: action }),
      });
      var data = await r.json();
      if (data.success) toast(arena + ": " + action + " OK");
      else toast(arena + ": " + data.message, "error");
    } catch (err) {
      toast("Control error: " + err.message, "error");
    }
  });
}

async function fetchCosts() {
  try {
    var r = await fetch(API + "/costs");
    if (!r.ok) throw new Error(r.status);
    var data = await r.json();
    renderCosts(data);
  } catch (e) {
    toast("Failed to load costs: " + e.message, "error");
  }
}

function renderCosts(data) {
  var tbody = document.getElementById("cost-body");
  tbody.innerHTML = "";
  var symbols = data.symbols || data;
  if (typeof symbols !== "object") return;
  Object.keys(symbols).forEach(function(sym) {
    var info = symbols[sym];
    var tr = document.createElement("tr");
    tr.innerHTML = "<td>" + sym + "</td>" +
      '<td class="editable" data-sym="' + sym + '" data-field="maker_bps">' + (info.maker_bps != null ? info.maker_bps : "-") + "</td>" +
      '<td class="editable" data-sym="' + sym + '" data-field="taker_bps">' + (info.taker_bps != null ? info.taker_bps : "-") + "</td>" +
      '<td class="editable" data-sym="' + sym + '" data-field="slippage_bps">' + (info.slippage_bps != null ? info.slippage_bps : "-") + "</td>" +
      "<td>" + (info.funding_8h_avg_bps != null ? info.funding_8h_avg_bps : "-") + "</td>";
    tr.querySelectorAll(".editable").forEach(function(td) { td.addEventListener("click", startCostEdit); });
    tbody.appendChild(tr);
  });
}

function startCostEdit(e) {
  var td = e.currentTarget;
  if (td.querySelector("input")) return;
  var sym = td.dataset.sym;
  var field = td.dataset.field;
  var oldVal = td.textContent;
  var input = document.createElement("input");
  input.value = oldVal;
  td.textContent = "";
  td.appendChild(input);
  input.focus();
  input.addEventListener("keydown", async function(ev) {
    if (ev.key === "Enter") {
      var val = parseFloat(input.value);
      if (isNaN(val)) { toast("Invalid number", "error"); td.textContent = oldVal; return; }
      try {
        var body = { symbol: sym };
        body[field] = val;
        var r = await fetch(API + "/costs", {
          method: "PUT",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify(body),
        });
        if (!r.ok) throw new Error((await r.json()).detail || r.status);
        toast("Updated " + sym + " " + field);
        fetchCosts();
      } catch (err) {
        toast("Error: " + err.message, "error");
        td.textContent = oldVal;
      }
    } else if (ev.key === "Escape") {
      td.textContent = oldVal;
    }
  });
  input.addEventListener("blur", function() { if (td.querySelector("input")) td.textContent = oldVal; });
}

document.getElementById("param-search").addEventListener("input", function(e) {
  renderParams(allParams, e.target.value);
});

renderArenas();
fetchHealth();
fetchParams();
fetchCosts();
setInterval(fetchHealth, 10000);
