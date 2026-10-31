(function () {
  "use strict";
  var $ = function (id) { return document.getElementById(id); };
  var PALETTE = ["#e76f51", "#2a9d8f", "#8338ec", "#f4a261", "#3a86ff", "#e63946", "#06d6a0", "#ff006e", "#8ac926", "#fb8500"];
  var FIELDS = {
    1: [["int", "bases", "Bases visitadas (1ª vez)", 6, "× 20"],
        ["int", "repeats", "Pousos repetidos", null, "× −5"],
        ["bool", "returned", "Retornou autonomamente e pousou na base de decolagem", "(×2)"],
        ["bool", "open_hw", "Drone open-hardware", "(×2)"]],
    2: [["int", "lifted", "Kits identificados, agarrados e levantados", 3, "× 40"],
        ["int", "delivered", "Kits entregues na base correta", 3, "× 20"],
        ["int", "dropped", "Kits derrubados", 3, "× −5"],
        ["bool", "returned", "Retornou autonomamente e pousou na base de decolagem", "(×2, exige 1 entrega)"],
        ["bool", "open_hw", "Drone open-hardware", "(×2)"]],
    3: [["bool", "recognized", "Operador reconhecido", "(sem isso, 0 pontos)"],
        ["int", "bases", "Bases visitadas (1ª vez)", 6, "× 20"],
        ["int", "repeats", "Pousos repetidos", null, "× −5"],
        ["int", "cross_repeats", "Pousos em base já usada pelo outro drone", null, "× −10"],
        ["bool", "returned", "Retornou autonomamente e pousou na base de decolagem", "(×2, exige 1 base)"],
        ["bool", "open_hw", "Drone open-hardware", "(×2)"]],
    4: [["bool", "maze", "Navegou pelo labirinto (entrada → saída)", "(+50)"],
        ["int", "qr", "QR codes lidos", 5, "× 20"],
        ["bool", "landed", "Pousou na base final após sair", "(×2, exige labirinto e 1 QR)"],
        ["bool", "open_hw", "Drone open-hardware", "(×2)"]]
  };

  var state = null, receivedAt = 0;
  var sig = {};                       // assinatura do que foi desenhado por seção
  var teamTouched = false;            // operador escolheu equipe manualmente
  var editingId = null;               // tentativa em edição
  var formKey = "";                   // equipe|fase|edição do formulário atual
  var orderDraft = null, orderDirty = false, orderPhase = null;
  var previewSeq = 0, bust = {};
  var toastTimer = null;

  function hash(s) { var h = 0; for (var i = 0; i < s.length; i++) h = (h * 31 + s.charCodeAt(i)) >>> 0; return h; }
  function initials(name) {
    var w = String(name).trim().split(/\s+/).filter(Boolean);
    if (!w.length) return "?";
    if (w.length === 1) return Array.from(w[0]).slice(0, 2).join("").toUpperCase();
    return (Array.from(w[0])[0] + Array.from(w[1])[0]).toUpperCase();
  }
  function logoEl(team) {
    var el;
    if (team.logo) {
      el = document.createElement("img");
      el.className = "logo"; el.alt = "";
      el.src = team.logo + (bust[team.id] ? "?v=" + bust[team.id] : "");
      el.onerror = function () { el.replaceWith(logoEl({ id: team.id, name: team.name })); };
    } else {
      el = document.createElement("span");
      el.className = "logo";
      el.style.background = PALETTE[hash(String(team.id)) % PALETTE.length];
      el.textContent = initials(team.name);
    }
    return el;
  }
  function el(tag, props, children) {
    var e = document.createElement(tag);
    if (props) Object.keys(props).forEach(function (k) { e[k] = props[k]; });
    (children || []).forEach(function (c) { e.appendChild(typeof c === "string" ? document.createTextNode(c) : c); });
    return e;
  }
  function fmt(ms) {
    var s = Math.ceil(Math.max(0, ms) / 1000), m = Math.floor(s / 60), r = s % 60;
    return (m < 10 ? "0" : "") + m + ":" + (r < 10 ? "0" : "") + r;
  }
  function teamById(id) { return state.teams.filter(function (t) { return t.id === id; })[0]; }
  function toast(msgs) {
    var t = $("toast");
    t.textContent = [].concat(msgs).join(" ");
    t.hidden = false;
    clearTimeout(toastTimer);
    toastTimer = setTimeout(function () { t.hidden = true; }, 6000);
  }

  // -- API -------------------------------------------------------------
  function api(method, url, body, isForm) {
    var opts = { method: method, headers: {} };
    if (body !== undefined) {
      if (isForm) opts.body = body;
      else { opts.body = JSON.stringify(body); opts.headers["Content-Type"] = "application/json"; }
    }
    return fetch(url, opts).then(function (r) {
      return r.json().then(function (j) {
        if (!r.ok) { var e = new Error("api"); e.errors = j.errors || ["Erro " + r.status]; throw e; }
        return j;
      }, function () { var e = new Error("api"); e.errors = ["Erro " + r.status]; throw e; });
    });
  }
  function act(p) {
    return p.then(function (s) { applyState(s); return s; }, function (e) {
      toast(e.errors || "Sem conexão com o servidor."); throw e;
    });
  }
  function quiet(p) { return p.catch(function () {}); }

  // -- renderização ----------------------------------------------------
  function applyState(s) { state = s; receivedAt = Date.now(); render(); }

  function render() {
    renderArena();
    renderTeamSelect();
    renderForm();
    renderAttempts();
    renderOrder();
    renderTeams();
  }

  function remainingMs() {
    var t = state.timer;
    return t.running ? Math.max(0, t.remaining_ms - (Date.now() - receivedAt)) : t.remaining_ms;
  }
  function renderCountdown() {
    if (!state) return;
    var ms = remainingMs(), c = $("countdown");
    c.textContent = fmt(ms);
    c.classList.toggle("low", ms <= 60000);
  }

  function renderArena() {
    var sel = $("phase-select");
    if (document.activeElement !== sel) sel.value = String(state.phase);
    $("phase-name").textContent = state.phase_name;
    $("arena-name").textContent = state.current ? state.current.name :
      (state.phase_finished ? "fase encerrada" : "—");
    $("next-name").textContent = state.next ? state.next.name : "—";
    $("b-start").disabled = state.timer.running || !state.current;
    $("b-pause").disabled = !state.timer.running;
    renderCountdown();
  }

  function selectedTeamId() { return $("team-select").value || null; }

  function renderTeamSelect() {
    var s = $("team-select");
    var key = JSON.stringify(state.teams.map(function (t) { return [t.id, t.name]; }));
    var cur = state.current ? state.current.id : null;
    var prev = s.value;
    if (sig.teamSel !== key) {
      sig.teamSel = key;
      s.textContent = "";
      state.teams.forEach(function (t) { s.appendChild(el("option", { value: t.id, textContent: t.name })); });
      if (!teamById(prev)) teamTouched = false;
      s.value = teamTouched && teamById(prev) ? prev : "";
    } else if (teamTouched && !teamById(prev)) teamTouched = false;
    if (editingId) return;
    if (!teamTouched) {
      var want = cur && teamById(cur) ? cur : (teamById(s.value) ? s.value : (state.teams[0] || {}).id);
      if (want) s.value = want;
    }
  }

  function thisAttempts(teamId, phase) {
    return state.attempts.filter(function (a) { return a.team_id === teamId && a.phase === phase; });
  }

  function renderForm() {
    var tid = selectedTeamId(), phase = editingId ? editingPhase() : state.phase;
    var key = [tid, phase, editingId].join("|");
    var team = tid ? teamById(tid) : null;
    $("record-title").textContent = editingId ? "Editar tentativa" :
      "Registrar tentativa" + (team ? " – " + team.name : "");
    $("cancel-edit").hidden = !editingId;
    $("save-attempt").textContent = editingId ? "Salvar alterações" : "Salvar tentativa";
    $("save-attempt").disabled = !tid;
    $("team-select").disabled = !!editingId;
    if (key === formKey) return;
    formKey = key;
    buildFields(phase, editingId ? editingInputs() : null, team);
    preview();
  }
  function editingAttempt() {
    return state.attempts.filter(function (a) { return a.id === editingId; })[0];
  }
  function editingPhase() { var a = editingAttempt(); return a ? a.phase : state.phase; }
  function editingInputs() { var a = editingAttempt(); return a ? a.inputs : null; }

  function buildFields(phase, values, team) {
    var box = $("fields");
    box.textContent = "";
    FIELDS[phase].forEach(function (f) {
      var kind = f[0], key = f[1], row = el("div", { className: "field" });
      var inp;
      if (kind === "int") {
        inp = el("input", { type: "number", step: 1, min: 0, id: "f-" + key });
        if (f[3] !== null) inp.max = f[3];
        inp.value = values ? values[key] : 0;
        row.appendChild(el("label", { htmlFor: inp.id, textContent: f[2] }));
        row.appendChild(inp);
        row.appendChild(el("span", { className: "hint", textContent: f[4] + (f[3] !== null ? " (máx. " + f[3] + ")" : "") }));
      } else {
        inp = el("input", { type: "checkbox", id: "f-" + key });
        inp.checked = values ? !!values[key] : (key === "open_hw" && team ? !!team.open_hw_default : false);
        row.appendChild(inp);
        row.appendChild(el("label", { htmlFor: inp.id, textContent: f[2] }));
        row.appendChild(el("span", { className: "hint", textContent: f[3] }));
      }
      inp.dataset.kind = kind; inp.dataset.key = key;
      inp.addEventListener("input", preview);
      inp.addEventListener("change", preview);
      box.appendChild(row);
    });
  }

  function readInputs() {
    var out = {};
    document.querySelectorAll("#fields input").forEach(function (i) {
      if (i.dataset.kind === "bool") out[i.dataset.key] = i.checked;
      else out[i.dataset.key] = i.value.trim() === "" || !/^-?\d+$/.test(i.value.trim()) ? null : parseInt(i.value, 10);
    });
    return out;
  }
  function currentPhase() { return editingId ? editingPhase() : state.phase; }

  function formulaText(phase, i) {
    var n = function (v) { return typeof v === "number" ? v : 0; };
    var base, doubled;
    if (phase === 1) {
      base = [20 * n(i.bases), -5 * n(i.repeats)]; doubled = i.returned;
    } else if (phase === 2) {
      base = [40 * n(i.lifted), 20 * n(i.delivered), -5 * n(i.dropped)];
      doubled = i.returned && n(i.delivered) >= 1;
    } else if (phase === 3) {
      if (!i.recognized) return "Operador não reconhecido";
      base = [20 * n(i.bases), -5 * n(i.repeats), -10 * n(i.cross_repeats)];
      doubled = i.returned && n(i.bases) >= 1;
    } else {
      base = [i.maze ? 50 : 0, 20 * n(i.qr)]; doubled = i.maze && i.landed && n(i.qr) >= 1;
    }
    var sum = base.reduce(function (a, b) { return a + b; }, 0);
    var txt = "";
    base.forEach(function (v, idx) {
      if (idx === 0) txt = String(Math.abs(v) === v ? v : "−" + Math.abs(v));
      else txt += (v < 0 ? " − " : " + ") + Math.abs(v);
    });
    var mult = "";
    if (doubled && sum > 0) mult += " × 2";
    if (i.open_hw) mult += " × 2";
    if (base.length > 1 || mult) txt = "(" + txt + ")" ;
    return txt + mult;
  }

  function preview() {
    var seq = ++previewSeq, phase = currentPhase(), inputs = readInputs();
    var f = $("formula"), err = $("form-errors");
    api("POST", "/api/preview", { phase: phase, inputs: inputs }).then(function (r) {
      if (seq !== previewSeq) return;
      err.textContent = "";
      f.textContent = "Pontos: " + formulaText(phase, inputs) + " = ";
      f.appendChild(el("b", { textContent: String(r.points) }));
    }, function (e) {
      if (seq !== previewSeq) return;
      f.textContent = "Pontos: —";
      err.textContent = e.errors ? e.errors.join(" ") : "Sem conexão com o servidor.";
    });
  }

  function renderAttempts() {
    var tid = selectedTeamId(), phase = state.phase;
    var team = tid ? teamById(tid) : null;
    $("attempts-title").textContent = "Tentativas" + (team ? " – " + team.name : "") + ", Fase " + phase;
    var list = team ? thisAttempts(tid, phase) : [];
    var key = JSON.stringify([tid, phase, list, editingId]);
    if (sig.attempts === key) return;
    sig.attempts = key;
    var ul = $("attempts-list");
    ul.textContent = "";
    var best = -1;
    list.forEach(function (a, idx) { if (best < 0 || a.points > list[best].points) best = idx; });
    for (var k = 0; k < 3; k++) {
      var a = list[k], li = el("li");
      li.appendChild(el("span", { className: "att-label", textContent: "T" + (k + 1) }));
      if (!a) { li.appendChild(el("span", { className: "att-pts muted", textContent: "—" })); ul.appendChild(li); continue; }
      var pts = el("span", { className: "att-pts" }, [String(a.points) + " "]);
      if (k === best) pts.appendChild(el("span", { className: "star", textContent: "★", title: "melhor" }));
      li.appendChild(pts);
      var ed = el("button", { textContent: "Editar" });
      ed.onclick = (function (id) { return function () { startEdit(id); }; })(a.id);
      var del = el("button", { textContent: "Apagar", className: "danger" });
      del.onclick = (function (id, n) { return function () {
        if (!confirm("Apagar a tentativa T" + n + "?")) return;
        if (editingId === id) stopEdit();
        quiet(act(api("DELETE", "/api/attempts/" + id)));
      }; })(a.id, k + 1);
      li.appendChild(ed); li.appendChild(del);
      if (a.id === editingId) li.appendChild(el("span", { className: "muted", textContent: "em edição" }));
      ul.appendChild(li);
    }
  }

  function startEdit(id) { editingId = id; formKey = ""; render(); }
  function stopEdit() { editingId = null; formKey = ""; sig.attempts = null; render(); }

  // -- ordem -----------------------------------------------------------
  function renderOrder() {
    var phase = state.phase, server = (state.orders[String(phase)] || []).filter(function (id) { return teamById(id); });
    if (orderPhase !== phase) { orderPhase = phase; orderDirty = false; orderDraft = null; }
    if (!orderDirty || orderDraft === null) orderDraft = server.slice();
    else orderDraft = orderDraft.filter(function (id) { return teamById(id); });
    $("order-title").textContent = "Ordem da fase " + phase;
    var key = JSON.stringify([phase, orderDraft, orderDirty, state.teams.map(function (t) { return [t.id, t.name]; })]);
    $("order-dirty").textContent = orderDirty ? "alterações não salvas" : "";
    if (sig.order === key) return;
    sig.order = key;
    var ol = $("order-list");
    ol.textContent = "";
    orderDraft.forEach(function (id, idx) {
      var li = el("li");
      li.appendChild(el("span", { className: "n", textContent: teamById(id).name }));
      var up = el("button", { textContent: "↑", title: "subir", disabled: idx === 0 });
      var dn = el("button", { textContent: "↓", title: "descer", disabled: idx === orderDraft.length - 1 });
      var rm = el("button", { textContent: "✕", title: "remover da ordem" });
      up.onclick = function () { moveOrder(idx, -1); };
      dn.onclick = function () { moveOrder(idx, 1); };
      rm.onclick = function () { orderDraft.splice(idx, 1); orderDirty = true; sig.order = null; renderOrder(); };
      [up, dn, rm].forEach(function (b) { li.appendChild(b); });
      ol.appendChild(li);
    });
    var add = $("order-add"), prev = add.value;
    add.textContent = "";
    state.teams.filter(function (t) { return orderDraft.indexOf(t.id) < 0; }).forEach(function (t) {
      add.appendChild(el("option", { value: t.id, textContent: t.name }));
    });
    if (prev && Array.prototype.some.call(add.options, function (o) { return o.value === prev; })) add.value = prev;
    $("order-add-btn").disabled = !add.options.length;
  }
  function moveOrder(idx, d) {
    var j = idx + d;
    if (j < 0 || j >= orderDraft.length) return;
    var t = orderDraft[idx]; orderDraft[idx] = orderDraft[j]; orderDraft[j] = t;
    orderDirty = true; sig.order = null; renderOrder();
  }

  // -- equipes ---------------------------------------------------------
  function renderTeams() {
    var ul = $("teams-list");
    var key = JSON.stringify(state.teams) + JSON.stringify(bust);
    if (sig.teams === key) return;
    if (ul.contains(document.activeElement)) return;   // não atrapalhar edição
    sig.teams = key;
    ul.textContent = "";
    state.teams.forEach(function (t) {
      var li = el("li");
      li.appendChild(logoEl(t));
      var name = el("input", { type: "text", value: t.name });
      var hw = el("input", { type: "checkbox", checked: t.open_hw_default });
      var file = el("input", { type: "file", accept: ".png,.jpg,.jpeg,.webp,.svg" });
      var save = el("button", { textContent: "Salvar" });
      var del = el("button", { textContent: "Excluir", className: "danger" });
      save.onclick = function () {
        var fd = new FormData();
        fd.append("name", name.value);
        fd.append("open_hw_default", hw.checked ? "1" : "0");
        if (file.files[0]) fd.append("logo", file.files[0]);
        var hadFile = !!file.files[0];
        quiet(act(api("POST", "/api/teams/" + t.id, fd, true)).then(function () {
          if (hadFile) bust[t.id] = Date.now();
          sig.teams = null; renderTeams();
        }));
      };
      del.onclick = function () {
        if (!confirm("Excluir a equipe \"" + t.name + "\" e suas tentativas?")) return;
        quiet(act(api("DELETE", "/api/teams/" + t.id)));
      };
      var hwl = el("label", { className: "check" }, [hw, "open-hardware por padrão"]);
      [name, hwl, file, save, del].forEach(function (x) { li.appendChild(x); });
      ul.appendChild(li);
    });
  }

  // -- eventos ---------------------------------------------------------
  document.querySelectorAll("[data-timer]").forEach(function (b) {
    b.onclick = function () {
      if (b.dataset.confirm && !confirm(b.dataset.confirm)) return;
      quiet(act(api("POST", "/api/timer/" + b.dataset.timer)));
    };
  });
  $("phase-select").onchange = function () {
    var p = parseInt(this.value, 10);
    if (editingId) stopEdit();
    quiet(act(api("POST", "/api/phase", { phase: p })));
    this.blur();
  };
  $("team-select").onchange = function () { teamTouched = true; formKey = ""; render(); };
  $("save-attempt").onclick = function () {
    var inputs = readInputs(), p;
    if (editingId) p = api("PUT", "/api/attempts/" + editingId, { inputs: inputs });
    else p = api("POST", "/api/attempts", { team_id: selectedTeamId(), phase: state.phase, inputs: inputs });
    var wasEditing = !!editingId;
    quiet(act(p).then(function () {
      $("form-errors").textContent = "";
      if (wasEditing) stopEdit(); else { formKey = ""; render(); }
    }));
  };
  $("cancel-edit").onclick = stopEdit;
  $("order-add-btn").onclick = function () {
    var v = $("order-add").value;
    if (!v) return;
    orderDraft.push(v); orderDirty = true; sig.order = null; renderOrder();
  };
  $("order-save").onclick = function () {
    var phase = state.phase;
    quiet(act(api("POST", "/api/orders/" + phase, { team_ids: orderDraft })).then(function () {
      orderDirty = false; sig.order = null; renderOrder();
    }));
  };
  $("team-add").onsubmit = function (e) {
    e.preventDefault();
    var name = $("new-name").value.trim();
    if (!name) return;
    var fd = new FormData();
    fd.append("name", name);
    fd.append("open_hw_default", $("new-hw").checked ? "1" : "0");
    var f = $("new-logo").files[0];
    if (f) fd.append("logo", f);
    quiet(act(api("POST", "/api/teams", fd, true)).then(function () {
      $("team-add").reset();
    }));
  };

  // -- polling ---------------------------------------------------------
  function poll() {
    api("GET", "/api/state").then(function (s) {
      $("offline").hidden = true;
      applyState(s);
    }, function () { $("offline").hidden = false; });
  }
  poll();
  setInterval(poll, 1000);
  setInterval(renderCountdown, 250);
})();
