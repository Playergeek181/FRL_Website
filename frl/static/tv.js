(function () {
  "use strict";
  var SLOT_MS = 1800000;   // 30:00, igual a constants.SLOT_MS
  var LOW_MS = 300000;     // últimos 5 min: mesmo limiar da página de controle
  var PHASES = { 1: "Localização e Mapeamento", 2: "Transporte de Pacotes", 3: "Interação Humano-Enxame", 4: "Navegação em Espaço Confinado" };
  var state = null, receivedAt = 0, lastKey = "";
  var $ = function (id) { return document.getElementById(id); };

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
  // Cada equipe tem um matiz estável; o selo é um tom escuro dele com a sigla clara.
  function tint(el, id) {
    var h = (hash(String(id)) % 12) * 30;
    el.style.background = "hsl(" + h + " 32% 17%)";
    el.style.color = "hsl(" + h + " 70% 78%)";
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
      tint(el, id);
      el.textContent = initials(team.name);
    }
    return el;
  }
  function make(tag, cls, text) {
    var e = document.createElement(tag);
    if (cls) e.className = cls;
    if (text !== undefined) e.textContent = text;
    return e;
  }
  function pad(n, w) { n = String(n); while (n.length < w) n = "0" + n; return n; }
  // Returns ["MM:SS", ".mmm"] for the big digits and the smaller milliseconds.
  function fmtParts(ms) {
    ms = Math.max(0, Math.floor(ms));
    var s = Math.floor(ms / 1000), m = Math.floor(s / 60);
    return [pad(m, 2) + ":" + pad(s % 60, 2), "." + pad(ms % 1000, 3)];
  }
  // Sem dados novos por STALE_MS, o relógio para de contar sozinho: se o operador pausou
  // enquanto a TV estava sem conexão, a sala não pode ver uma contagem que não é real.
  var STALE_MS = 5000, failed = false;
  function stale() { return state && Date.now() - receivedAt > STALE_MS; }
  function remaining() {
    var t = state.timer, ms = t.remaining_ms;
    if (t.running) ms -= Math.min(Date.now() - receivedAt, STALE_MS);
    return Math.max(0, ms);
  }
  var linkKey = "";
  function renderLink() {                      // roda a cada quadro: só mexe no DOM quando muda
    var off = !!stale(), key = off + "|" + failed;
    if (key === linkKey) return;
    linkKey = key;
    document.body.classList.toggle("stale", off);
    $("offline").textContent = off ? "Reconectando… o cronômetro está parado nesta tela" : "Sem conexão com o servidor";
    $("offline").hidden = !(failed || off);
  }

  function renderCountdown() {
    var el = $("countdown");
    if (!el || !state) return;
    var ms = remaining(), p = fmtParts(ms), low = ms < LOW_MS;
    if (!el.firstChild || el.firstChild.className !== "cd-main") {
      el.textContent = "";
      el.appendChild(make("span", "cd-main"));
      el.appendChild(make("span", "cd-ms"));
    }
    el.firstChild.textContent = p[0];
    el.lastChild.textContent = p[1];
    el.classList.toggle("low", low);
    var total = Math.max(SLOT_MS, state.timer.remaining_ms);
    var bar = $("slot");
    bar.firstChild.style.width = (100 * ms / total).toFixed(2) + "%";
    bar.classList.toggle("low", low);
    var st = ms === 0 ? "Tempo esgotado" :
      (state.timer.running ? (low ? "Em voo · últimos 5 min" : "Em voo") : (ms >= total ? "Pronto para iniciar" : "Pausado"));
    // pausado precisa ser visível do fundo da arena: dígitos apagados e a palavra em destaque
    var paused = !state.timer.running && ms > 0 && ms < total;
    el.classList.toggle("paused", paused);
    bar.classList.toggle("paused", paused);
    $("slot-state").textContent = st;
    $("slot-state").parentNode.classList.toggle("up", ms === 0);
    $("slot-state").parentNode.classList.toggle("paused", paused);
    var spoken = p[0] + " restantes";      // leitores de tela: segundos, não milissegundos
    if (el.getAttribute("aria-label") !== spoken) el.setAttribute("aria-label", spoken);
    $("slot-total").textContent = "de " + fmtParts(total)[0];
  }

  function renderPhases(s) {
    var ol = $("phases");
    ol.textContent = "";
    for (var p = 1; p <= 4; p++) {
      var li = make("li", p === s.phase ? "active" : (p < s.phase ? "done" : ""));
      li.appendChild(document.createTextNode("Fase " + p));
      if (p < s.phase) li.appendChild(make("span", "dn", " concluída"));   // em palavra, não só cor
      if (p === s.phase) li.appendChild(make("span", "pn", " · " + (s.phase_name || PHASES[p])));
      ol.appendChild(li);
    }
    var ths = document.querySelectorAll("#rank th.ph");
    for (var i = 0; i < ths.length; i++) ths[i].classList.toggle("active", Number(ths[i].dataset.p) === s.phase);
  }

  function renderArena(s) {
    var body = $("arena-body");
    body.textContent = "";
    // sem equipe na arena, o título diz em que fase estamos em vez de "Na arena" sobre o vazio
    $("arena-h").textContent = s.current ? "Na arena" : "Fase " + s.phase + " · " + (s.phase_name || PHASES[s.phase]);
    if (s.current) {
      var row = make("div", "arena-team");
      row.appendChild(logoEl(s.current, s.current.id));
      row.appendChild(make("div", "arena-name", s.current.name));
      body.appendChild(row);
      var c = make("div", "countdown");
      c.id = "countdown";
      c.setAttribute("role", "timer");
      body.appendChild(c);
      var bar = make("div", "slot");
      bar.id = "slot";
      bar.appendChild(document.createElement("i"));
      body.appendChild(bar);
      var cap = make("div", "slot-cap");
      var a = make("b"); a.id = "slot-state";
      var b = make("span"); b.id = "slot-total";
      cap.appendChild(a); cap.appendChild(b);
      body.appendChild(cap);
      renderCountdown();
    } else {
      body.appendChild(make("div", "arena-msg", s.phase_finished ? "Fase encerrada" : "Aguardando ordem"));
      body.appendChild(make("div", "arena-msg-sub", s.phase_finished ?
        "Todas as equipes da Fase " + s.phase + " já voaram." : "A ordem de voo da Fase " + s.phase + " ainda não foi definida."));
      if (s.phase_finished && PHASES[s.phase + 1]) {
        var nx = make("div", "arena-next");
        nx.appendChild(make("span", "lbl", "Próxima fase"));
        nx.appendChild(make("b", "", "Fase " + (s.phase + 1) + " · " + PHASES[s.phase + 1]));
        body.appendChild(nx);
      }
    }
  }

  function renderQueue(s) {
    var ol = $("queue-list");
    ol.textContent = "";
    var order = (s.orders && s.orders[String(s.phase)]) || [];
    var byId = {};
    (s.teams || []).forEach(function (t) { byId[t.id] = t; });
    var start = s.next ? order.indexOf(s.next.id) : -1;
    var ids = start < 0 ? (s.next ? [s.next.id] : []) : order.slice(start, start + 3);
    ids = ids.filter(function (id) { return byId[id]; });
    // sem equipe na arena, o painel da arena já diz "Aguardando ordem" / "Fase encerrada"
    $("queue").hidden = !ids.length && !s.current;
    if (!ids.length) {
      ol.appendChild(make("li", "empty", "Esta é a última equipe da fase"));
      return;
    }
    ids.forEach(function (id, k) {
      var t = byId[id], li = make("li", k === 0 ? "first" : "");
      li.appendChild(logoEl(t, id));
      li.appendChild(make("span", "q-name", t.name));
      ol.appendChild(li);
    });
  }

  function renderRanking(s) {
    var tb = $("rank-body");
    tb.textContent = "";
    var flying = s.current ? s.current.id : null;
    s.ranking.forEach(function (r) {
      var tr = document.createElement("tr");
      if (r.position === 1 && r.total > 0) tr.className = "lead";
      if (r.team_id === flying) tr.className += " flying";
      function td(text, cls) {
        var d = make("td", cls, String(text));
        tr.appendChild(d);
        return d;
      }
      var unranked = r.position === null || r.position === undefined;   // só quem pontuou tem posição
      td(unranked ? "–" : r.position, "pos" + (unranked ? " nil" : ""));
      var lc = td("", "lg");
      lc.appendChild(logoEl(r, r.team_id));
      td(r.name, "name");
      for (var p = 1; p <= 4; p++) {
        var v = r.phase_points[String(p)];
        var nil = v === null || v === undefined;
        // 0 de quem não tem posição fica apagado como o "–" do total: voou, mas não pontuou
        td(nil ? "–" : v, "ph" + (nil || (unranked && v === 0) ? " nil" : "") + (p === s.phase ? " active" : ""));
      }
      td(unranked ? "–" : r.total, "total" + (unranked ? " nil" : ""));
      tb.appendChild(tr);
    });
    // mesmo total mas posições diferentes: o desempate das regras decidiu; diz qual é o critério
    var posByTotal = {}, tie = false;
    s.ranking.forEach(function (r) {
      if (r.position === null || r.position === undefined) return;
      var seen = posByTotal[r.total];
      if (seen !== undefined && seen !== r.position) tie = true;
      posByTotal[r.total] = r.position;
    });
    $("tie-note").hidden = !tie;
    fitRanking();
  }

  // Todas as linhas cabem no cartão: começa grande e diminui a fonte até caber.
  function fitRanking() {
    var table = $("rank"), card = $("standings");
    var pad = parseFloat(getComputedStyle(card).paddingBottom) || 0, note = $("tie-note");
    var limit = card.getBoundingClientRect().bottom - pad - (note.hidden ? 0 : note.offsetHeight);
    var fs = 4.4;
    table.style.fontSize = fs + "vh";
    while (fs > 1.3 && table.getBoundingClientRect().bottom > limit) {
      fs -= 0.1;
      table.style.fontSize = fs.toFixed(2) + "vh";
    }
  }
  // Faixa de patrocinadores: a maior altura de logo em que a linha inteira cabe na largura.
  function fitSponsors() {
    var band = $("sponsors"), fs = 6.4;
    band.style.fontSize = fs + "vh";
    while (fs > 2 && band.scrollWidth > band.clientWidth + 1) {
      fs -= 0.1;
      band.style.fontSize = fs.toFixed(2) + "vh";
    }
  }
  window.addEventListener("load", function () { fitSponsors(); if (state) fitRanking(); });
  window.addEventListener("resize", function () { fitSponsors(); if (state) fitRanking(); });

  function render() {
    renderPhases(state);
    renderArena(state);
    renderQueue(state);
    renderRanking(state);
  }

  function poll() {
    fetch("/api/state", { cache: "no-store" })
      .then(function (r) { if (!r.ok) throw new Error(r.status); return r.json(); })
      .then(function (j) {
        var key = JSON.stringify([j.phase, j.phase_name, j.current, j.next, j.phase_finished, j.ranking, j.orders, j.teams]);
        state = j;
        receivedAt = Date.now();
        failed = false;
        renderLink();
        if (key !== lastKey) { lastKey = key; render(); } else renderCountdown();
      })
      .catch(function () { failed = true; renderLink(); });
  }

  poll();
  setInterval(poll, 1000);
  (function frame() { renderCountdown(); renderLink(); requestAnimationFrame(frame); })();
})();
