(function () {
  "use strict";
  var state = null, receivedAt = 0, lastKey = "";
  var $ = function (id) { return document.getElementById(id); };
  var PALETTE = ["#e76f51", "#2a9d8f", "#8338ec", "#f4a261", "#3a86ff", "#e63946", "#06d6a0", "#ff006e", "#8ac926", "#fb8500"];

  function hash(s) {
    var h = 0;
    for (var i = 0; i < s.length; i++) h = (h * 31 + s.charCodeAt(i)) >>> 0;
    return h;
  }
  function initials(name) {
    var w = String(name).trim().split(/\s+/).filter(Boolean);
    if (!w.length) return "?";
    if (w.length === 1) return Array.from(w[0]).slice(0, 2).join("").toUpperCase();
    return (Array.from(w[0])[0] + Array.from(w[1])[0]).toUpperCase();
  }
  function logoEl(team, id) {
    var el;
    if (team.logo) {
      el = document.createElement("img");
      el.className = "logo";
      el.alt = "";
      el.src = team.logo;
      el.onerror = function () { el.replaceWith(logoEl({ name: team.name }, id)); };
    } else {
      el = document.createElement("span");
      el.className = "logo";
      el.style.background = PALETTE[hash(String(id)) % PALETTE.length];
      el.textContent = initials(team.name);
    }
    return el;
  }
  function fmt(ms) {
    var s = Math.ceil(Math.max(0, ms) / 1000);
    var m = Math.floor(s / 60), r = s % 60;
    return (m < 10 ? "0" : "") + m + ":" + (r < 10 ? "0" : "") + r;
  }
  function remaining() {
    var t = state.timer, ms = t.remaining_ms;
    if (t.running) ms -= Date.now() - receivedAt;
    return Math.max(0, ms);
  }

  function renderCountdown() {
    var el = $("countdown");
    if (!el || !state) return;
    var ms = remaining();
    el.textContent = fmt(ms);
    el.classList.toggle("low", ms < 300000);
  }

  function render() {
    var s = state;
    $("phase").textContent = "FASE " + s.phase + " · " + String(s.phase_name).toUpperCase();

    var body = $("arena-body");
    body.textContent = "";
    if (s.current) {
      body.appendChild(logoEl(s.current, s.current.id));
      var n = document.createElement("div");
      n.className = "arena-name";
      n.textContent = s.current.name;
      var c = document.createElement("div");
      c.className = "countdown";
      c.id = "countdown";
      body.appendChild(n);
      body.appendChild(c);
      renderCountdown();
    } else {
      var m = document.createElement("div");
      m.className = "arena-msg";
      m.textContent = s.phase_finished ? "Fase encerrada" : "Aguardando ordem";
      body.appendChild(m);
    }

    var nl = $("next-logo");
    nl.textContent = "";
    if (s.next) nl.appendChild(logoEl(s.next, s.next.id));
    nl.style.display = s.next ? "" : "none";
    $("next-name").textContent = s.next ? s.next.name : "–";

    var tb = $("rank-body");
    tb.textContent = "";
    var rows = s.ranking.length;
    // linhas cabem na tela: fonte proporcional ao número de equipes
    var fs = Math.max(1.6, Math.min(3.6, 72 / (rows + 1) / 1.8));
    $("rank").style.fontSize = fs + "vh";
    s.ranking.forEach(function (r) {
      var tr = document.createElement("tr");
      function td(text, cls) {
        var d = document.createElement("td");
        if (cls) d.className = cls;
        d.textContent = text;
        tr.appendChild(d);
        return d;
      }
      td(r.position === null || r.position === undefined ? "–" : r.position);  // só quem pontuou tem posição
      var lc = td("");
      var lg = logoEl(r, r.team_id);
      lg.style.width = lg.style.height = (fs * 1.3) + "vh";
      lg.style.fontSize = (fs * 0.5) + "vh";
      lc.appendChild(lg);
      td(r.name, "name");
      for (var p = 1; p <= 4; p++) {
        var v = r.phase_points[String(p)];
        td(v === null || v === undefined ? "–" : v);
      }
      td(r.total, "total");
      tb.appendChild(tr);
    });
  }

  function poll() {
    fetch("/api/state", { cache: "no-store" })
      .then(function (r) { if (!r.ok) throw new Error(r.status); return r.json(); })
      .then(function (j) {
        var key = JSON.stringify([j.phase, j.phase_name, j.current, j.next, j.phase_finished, j.ranking]);
        state = j;
        receivedAt = Date.now();
        $("offline").hidden = true;
        if (key !== lastKey) { lastKey = key; render(); } else renderCountdown();
      })
      .catch(function () { $("offline").hidden = false; });
  }

  poll();
  setInterval(poll, 1000);
  setInterval(renderCountdown, 250);
})();
