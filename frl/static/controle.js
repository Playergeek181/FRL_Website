(function () {
  "use strict";
  var $ = function (id) { return document.getElementById(id); };
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
  var previewSeq = 0;
  var attPhase = null, attPhaseTouched = false;  // fase do painel de tentativas (segue a ativa)
  var ophase = null, ophaseTouched = false;      // fase do painel de ordem (segue a ativa)
  var orderEditing = false;                      // lista de ordem só vira editável em "Editar ordem"
  var LOW_MS = 300000;                           // últimos 5 min: mesmo limiar da TV (tv.js)
  var SLOT_MS = 1800000;                         // 30:00, igual a constants.SLOT_MS
  var wasExpired = null;                         // para avisar uma vez quando o tempo acaba
  function icon(d) {
    return '<svg width="14" height="14" viewBox="0 0 14 14" aria-hidden="true"><path d="' + d +
      '" fill="none" stroke="currentColor" stroke-width="1.7" stroke-linecap="round" stroke-linejoin="round"/></svg>';
  }
  var ICON = { up: icon("M3 9l4-4 4 4"), down: icon("M3 5l4 4 4-4"), x: icon("M3.5 3.5l7 7M10.5 3.5l-7 7"),
               minus: icon("M3 7h8"), plus: icon("M3 7h8M7 3v8") };
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
      el.src = team.logo;   // a URL já traz ?v=<mtime> do servidor
      el.onerror = function () { el.replaceWith(logoEl({ id: team.id, name: team.name })); };
    } else {
      el = document.createElement("span");
      el.className = "logo";
      var h = (hash(String(team.id)) % 12) * 30;   // mesmo matiz da TV
      el.style.background = "hsl(" + h + " 32% 17%)";
      el.style.color = "hsl(" + h + " 70% 78%)";
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
  function pad(n, w) { n = String(n); while (n.length < w) n = "0" + n; return n; }
  function fmt(ms) {
    ms = Math.max(0, Math.floor(ms));
    var s = Math.floor(ms / 1000), m = Math.floor(s / 60);
    return pad(m, 2) + ":" + pad(s % 60, 2) + "." + pad(ms % 1000, 3);
  }
  function teamById(id) { return state.teams.filter(function (t) { return t.id === id; })[0]; }
  // kind: "error" (padrão) ou "ok"; action: { label, run } vira um botão (ex.: Desfazer).
  function toast(msgs, kind, action) {
    var t = $("toast");
    t.textContent = "";
    t.className = kind === "ok" ? "ok" : "error";
    t.appendChild(el("span", { textContent: [].concat(msgs).join(" ") }));
    if (action) {
      var b = el("button", { textContent: action.label });
      b.onclick = function () { t.hidden = true; action.run(); };
      t.appendChild(b);
    }
    var close = el("button", { className: "x", title: "fechar", ariaLabel: "fechar",
      innerHTML: '<svg width="10" height="10" viewBox="0 0 12 12" aria-hidden="true"><path d="M2 2l8 8M10 2l-8 8" stroke="currentColor" stroke-width="1.6" stroke-linecap="round"/></svg>' });
    close.onclick = function () { t.hidden = true; };
    t.appendChild(close);
    t.hidden = false;
    clearTimeout(toastTimer);
    toastTimer = setTimeout(function () { t.hidden = true; }, action ? 8000 : (kind === "ok" ? 4000 : 10000));
  }
  function ok(msg, action) { toast(msg, "ok", action); }
  function teamPhaseAttempts(st, teamId, phase) {
    return st.attempts.filter(function (a) { return a.team_id === teamId && a.phase === phase; });
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
        if (!r.ok) { var e = new Error("api"); e.errors = j.errors || ["Erro " + r.status]; e.fields = j.fields; throw e; }
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
  var prepDecided = false;
  function applyState(s) {
    state = s; receivedAt = Date.now();
    if (!prepDecided) {
      prepDecided = true;
      var needs = !s.teams.length || !(s.orders[String(s.phase)] || []).length;
      $("prep").open = needs || prepPref === "1";
    }
    render();
  }

  function render() {
    renderAttPhase();
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
  // Pronto / Em voo / Pausado / Tempo esgotado: o mesmo texto que a TV mostra.
  function timerState(ms) {
    if (!state.current) return "";
    if (ms === 0) return "Tempo esgotado";
    if (state.timer.running) return ms < LOW_MS ? "Em voo · últimos 5 min" : "Em voo";
    return ms >= SLOT_MS ? "Pronto para iniciar" : "Pausado";
  }
  var lastSpoken = "";
  function renderCountdown() {
    if (!state) return;
    var ms = remainingMs(), c = $("countdown");
    c.textContent = fmt(ms);
    c.classList.toggle("low", ms < LOW_MS);
    var st = timerState(ms), chip = $("timer-state");
    if (chip.textContent !== st) {
      chip.textContent = st;
      chip.className = "t-state" + (ms === 0 ? " up" : (state.timer.running ? " run" : ""));
      $("arena").classList.toggle("expired", ms === 0 && !!state.current);
    }
    var spoken = fmt(ms).slice(0, 5) + " restantes";     // leitor de tela: segundos, não ms
    if (spoken !== lastSpoken) { lastSpoken = spoken; c.setAttribute("aria-label", spoken); }
  }

  function renderArena() {
    var sel = $("phase-select");
    if (document.activeElement !== sel) sel.value = String(state.phase);
    $("phase-name").textContent = state.phase_name;
    var noOrder = !state.current && !state.phase_finished;
    $("arena-name").textContent = state.current ? state.current.name :
      (state.phase_finished ? "Fase encerrada" : "Sem ordem de voo");
    $("next-name").textContent = state.next ? state.next.name : (state.current ? "última equipe da fase" : "—");
    $("next-line").hidden = noOrder;
    $("open-prep").hidden = !noOrder;
    $("arena").classList.toggle("noteam", !state.current);
    var t = state.timer, expired = !!t.expired;
    var paused = !t.running && !expired && t.remaining_ms < SLOT_MS;
    $("b-start").textContent = paused ? "Retomar" : "Iniciar";
    $("b-start").disabled = t.running || expired || !state.current;
    $("b-pause").disabled = !t.running;
    $("b-plus").disabled = !state.current;
    $("b-reset").disabled = !state.current;
    $("b-next").disabled = !state.current;
    $("b-next").className = expired ? "primary" : "go";   // em 00:00 o próximo passo é chamar a próxima
    if (wasExpired === false && expired && state.current)
      toast("Tempo esgotado: " + state.current.name + ". Registre a última tentativa e chame a próxima equipe.");
    wasExpired = expired;
    renderCountdown();
  }

  function selectedTeamId() { return $("team-select").value || null; }

  // fase usada por "Registrar tentativa" / "Tentativas": segue a fase ativa até o
  // operador escolher outra (corrigir fase anterior sem mexer na TV/cronômetro)
  function renderAttPhase() {
    if (!attPhaseTouched || attPhase === null) attPhase = state.phase;
    var sel = $("att-phase-select");
    if (document.activeElement !== sel) sel.value = String(editingId ? editingPhase() : attPhase);
    sel.disabled = !!editingId;
    $("att-phase-note").textContent = attPhase !== state.phase ?
      "Registrando na Fase " + attPhase + "; a arena está na Fase " + state.phase + "." : "";
  }
  function panelTeams() {   // equipes da ordem desta fase primeiro, depois as demais
    var order = (state.orders[String(attPhase)] || []).filter(function (id) { return teamById(id); });
    return order.map(teamById).concat(state.teams.filter(function (t) { return order.indexOf(t.id) < 0; }));
  }

  function renderTeamSelect() {
    var s = $("team-select");
    var teams = panelTeams();
    var key = JSON.stringify(teams.map(function (t) { return [t.id, t.name]; }));
    // só segue a equipe da arena quando o painel está na fase ativa
    var cur = state.current && attPhase === state.phase ? state.current.id : null;
    var prev = s.value;
    if (sig.teamSel !== key) {
      sig.teamSel = key;
      s.textContent = "";
      teams.forEach(function (t) { s.appendChild(el("option", { value: t.id, textContent: t.name })); });
      if (!teamById(prev)) teamTouched = false;
      s.value = teamTouched && teamById(prev) ? prev : "";
    } else if (teamTouched && !teamById(prev)) teamTouched = false;
    if (editingId) return;
    if (!teamTouched) {
      var want = cur && teamById(cur) ? cur :
        (teamById(prev) ? prev : (teamById(s.value) ? s.value : (teams[0] || {}).id));
      if (want) s.value = want;
    }
  }

  function thisAttempts(teamId, phase) {
    return state.attempts.filter(function (a) { return a.team_id === teamId && a.phase === phase; });
  }

  function renderForm() {
    if (editingId && !editingAttempt()) { stopEdit(); return; }   // apagada em outro lugar
    var tid = selectedTeamId(), phase = editingId ? editingPhase() : attPhase;
    var key = [tid, phase, editingId].join("|");
    var team = tid ? teamById(tid) : null;
    $("record-title").textContent = editingId ? "Editar tentativa" :
      "Registrar tentativa" + (team ? " – " + team.name : "") + ", Fase " + phase;
    $("cancel-edit").hidden = !editingId;
    $("save-attempt").textContent = editingId ? "Salvar alterações" : "Salvar tentativa";
    var full = !editingId && team && thisAttempts(tid, phase).length >= 3;
    $("save-attempt").disabled = !tid || full || formInvalid;
    $("save-note").textContent = full ? team.name + " já tem 3 tentativas na Fase " + phase +
      ". Para corrigir, use Editar em uma delas." : "";
    $("team-select").disabled = !!editingId;
    if (key === formKey) return;
    formKey = key; formInvalid = false;
    buildFields(phase, editingId ? editingInputs() : null, team);
    preview();
  }
  function editingAttempt() {
    return state.attempts.filter(function (a) { return a.id === editingId; })[0];
  }
  function editingPhase() { var a = editingAttempt(); return a ? a.phase : attPhase; }
  function editingInputs() { var a = editingAttempt(); return a ? a.inputs : null; }

  function buildFields(phase, values, team) {
    var box = $("fields");
    box.textContent = "";
    FIELDS[phase].forEach(function (f) {
      var kind = f[0], key = f[1], row = el("div", { className: "field" });
      var inp;
      if (kind === "int") {
        inp = el("input", { type: "number", step: 1, min: 0, id: "f-" + key, inputMode: "numeric" });
        if (f[3] !== null) inp.max = f[3];
        inp.value = values ? values[key] : 0;
        var bump = function (input, d) { return function () {
          var v = parseInt(input.value, 10); v = isNaN(v) ? 0 : v + d;
          if (v < 0) v = 0;
          if (input.max !== "" && v > +input.max) v = +input.max;
          input.value = v;
          input.dispatchEvent(new Event("input"));
        }; };
        var minus = el("button", { type: "button", className: "stp", tabIndex: -1, ariaLabel: "menos 1: " + f[2], innerHTML: ICON.minus });
        var plus = el("button", { type: "button", className: "stp", tabIndex: -1, ariaLabel: "mais 1: " + f[2], innerHTML: ICON.plus });
        minus.onclick = bump(inp, -1); plus.onclick = bump(inp, 1);
        row.appendChild(el("label", { htmlFor: inp.id, textContent: f[2] }));
        row.appendChild(el("div", { className: "stepper" }, [minus, inp, plus]));
        row.appendChild(el("span", { className: "hint", textContent: f[4] + (f[3] !== null ? " (máx. " + f[3] + ")" : "") }));
      } else {
        row.className = "field bool";
        inp = el("input", { type: "checkbox", id: "f-" + key });
        inp.checked = values ? !!values[key] : (key === "open_hw" && team ? !!team.open_hw_default : false);
        row.appendChild(el("label", { className: "check" }, [inp, el("span", { textContent: f[2] })]));
        row.appendChild(el("span", { className: "hint", textContent: f[3] }));
      }
      inp.dataset.kind = kind; inp.dataset.key = key;
      var touch = function () { teamTouched = true; preview(); };  // parar de seguir a arena
      inp.addEventListener("input", touch);
      inp.addEventListener("change", touch);
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
  function currentPhase() { return editingId ? editingPhase() : attPhase; }

  function formulaText(phase, i) {
    var n = function (v) { return typeof v === "number" ? v : 0; };
    var base, doubled;
    if (phase === 1) {
      base = [20 * n(i.bases), -5 * n(i.repeats)]; doubled = i.returned;
    } else if (phase === 2) {
      base = [40 * n(i.lifted), 20 * n(i.delivered), -5 * n(i.dropped)];
      doubled = i.returned && n(i.delivered) >= 1;
    } else if (phase === 3) {
      if (!i.recognized) return null;
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

  var formInvalid = false;
  function markInvalid(fields) {
    document.querySelectorAll("#fields input").forEach(function (i) {
      var bad = fields.indexOf(i.dataset.key) >= 0;
      i.setAttribute("aria-invalid", bad ? "true" : "false");
      i.closest(".field").classList.toggle("bad", bad);
    });
  }
  function preview() {
    var seq = ++previewSeq, phase = currentPhase(), inputs = readInputs();
    var f = $("formula"), err = $("form-errors");
    api("POST", "/api/preview", { phase: phase, inputs: inputs }).then(function (r) {
      if (seq !== previewSeq) return;
      err.textContent = ""; markInvalid([]); formInvalid = false;
      var calc = formulaText(phase, inputs);
      f.textContent = "Pontos: " + (calc === null ? "" : calc + " = ");
      f.appendChild(el("b", { textContent: String(r.points) }));
      if (calc === null) f.appendChild(el("span", { textContent: "operador não reconhecido" }));
      renderForm();
    }, function (e) {
      if (seq !== previewSeq) return;
      f.textContent = "Pontos: —";
      err.textContent = e.errors ? e.errors.join(" ") : "Sem conexão com o servidor.";
      markInvalid(e.fields || []); formInvalid = !!e.fields;
      renderForm();
    });
  }

  function renderAttempts() {
    var tid = selectedTeamId(), phase = attPhase;
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
      if (k === best) pts.appendChild(el("span", { className: "star", textContent: "melhor" }));
      li.appendChild(pts);
      li.appendChild(el("span", { className: "att-calc", textContent: formulaText(a.phase, a.inputs) || "operador não reconhecido" }));
      var ed = el("button", { textContent: "Editar" });
      ed.onclick = (function (id) { return function () { startEdit(id); }; })(a.id);
      var del = el("button", { textContent: "Excluir", className: "danger" });
      del.onclick = (function (att, n, tname) { return function () {
        var what = "T" + n + " de " + tname + " (Fase " + att.phase + ", " + att.points + " pts)";
        if (!confirm("Excluir " + what + "?")) return;
        if (editingId === att.id) stopEdit();
        quiet(act(api("DELETE", "/api/attempts/" + att.id)).then(function () {
          ok(what + " excluída.", { label: "Desfazer", run: function () {
            quiet(act(api("POST", "/api/attempts", { team_id: att.team_id, phase: att.phase, inputs: att.inputs }))
              .then(function () { ok("Tentativa restaurada (" + att.points + " pts)."); }));
          } });
        }));
      }; })(a, k + 1, team.name);
      li.appendChild(el("span", { className: "att-actions" }, [ed, del]));
      if (a.id === editingId) li.appendChild(el("span", { className: "muted", textContent: "em edição" }));
      ul.appendChild(li);
    }
  }

  function startEdit(id) { editingId = id; formKey = ""; render(); }
  function stopEdit() { editingId = null; teamTouched = false; formKey = ""; sig.attempts = null; render(); }

  // -- ordem -----------------------------------------------------------
  function renderOrder() {
    if (!ophaseTouched || ophase === null) ophase = state.phase;
    var osel = $("order-phase-select");
    if (document.activeElement !== osel) osel.value = String(ophase);
    var phase = ophase, server = (state.orders[String(phase)] || []).filter(function (id) { return teamById(id); });
    if (orderPhase !== phase) { orderPhase = phase; orderDirty = false; orderDraft = null; orderEditing = false; }
    if (!orderDirty || orderDraft === null) orderDraft = server.slice();
    else orderDraft = orderDraft.filter(function (id) { return teamById(id); });
    $("order-title").textContent = "Ordem de voo";
    $("order-note").textContent = phase !== state.phase ?
      "Esta é a ordem da Fase " + phase + "; a arena está na Fase " + state.phase + ". Salvar não muda a arena." : "";
    $("order-view").hidden = orderEditing;
    $("order-editing").hidden = !orderEditing;
    $("order-edit").textContent = orderDraft.length ? "Editar ordem" : "Montar ordem";
    $("order-empty").hidden = orderDraft.length > 0;
    $("order-save").disabled = !orderDirty;
    // na fase ativa, a lista mostra o andamento: quem já voou, quem está na arena, quem vem a seguir
    var live = phase === state.phase && !orderEditing && !orderDirty;
    var slot = live ? state.slot_index : -1, hasCur = !!state.current;
    var key = JSON.stringify([phase, orderDraft, orderDirty, orderEditing, slot, hasCur, state.teams.map(function (t) { return [t.id, t.name]; })]);
    $("order-dirty").textContent = orderDirty ? "alterações não salvas" : "";
    if (sig.order === key) return;
    sig.order = key;
    var ol = $("order-list");
    ol.textContent = "";
    orderDraft.forEach(function (id, idx) {
      var li = el("li");
      li.appendChild(el("span", { className: "n", textContent: teamById(id).name }));
      if (slot >= 0) {
        var tag = idx < slot ? ["done", "voou"] : idx === slot && hasCur ? ["cur", "na arena"] :
          idx === slot + 1 && hasCur ? ["nxt", "a seguir"] : null;
        if (tag) { li.className = tag[0]; li.appendChild(el("span", { className: "o-tag", textContent: tag[1] })); }
      }
      ol.appendChild(li);
      if (!orderEditing) return;
      var nm = teamById(id).name;
      var up = el("button", { innerHTML: ICON.up, title: "subir", ariaLabel: "subir " + nm, disabled: idx === 0 });
      var dn = el("button", { innerHTML: ICON.down, title: "descer", ariaLabel: "descer " + nm, disabled: idx === orderDraft.length - 1 });
      var rm = el("button", { className: "rm", title: "remover da ordem", ariaLabel: "remover " + nm + " da ordem", innerHTML: ICON.x });
      up.onclick = function () { moveOrder(idx, -1); };
      dn.onclick = function () { moveOrder(idx, 1); };
      rm.onclick = function () { orderDraft.splice(idx, 1); orderDirty = true; sig.order = null; renderOrder(); };
      [up, dn, rm].forEach(function (b) { li.appendChild(b); });
    });
    var add = $("order-add"), prev = add.value;
    add.textContent = "";
    state.teams.filter(function (t) { return orderDraft.indexOf(t.id) < 0; }).forEach(function (t) {
      add.appendChild(el("option", { value: t.id, textContent: t.name }));
    });
    if (prev && Array.prototype.some.call(add.options, function (o) { return o.value === prev; })) add.value = prev;
    $("order-add-btn").disabled = !add.options.length;
    $("order-add-row").hidden = !add.options.length;
    $("order-shuffle").disabled = (orderDraft.length || state.teams.length) < 2;
  }
  // Fisher–Yates com crypto.getRandomValues: sorteio justo, sem viés do Math.random.
  function randInt(n) {
    var buf = new Uint32Array(1), lim = Math.floor(4294967296 / n) * n, x;
    do { crypto.getRandomValues(buf); x = buf[0]; } while (x >= lim);
    return x % n;
  }
  function shuffleOrder() {
    var n = state.attempts.filter(function (a) { return a.phase === ophase; }).length;
    if (n && !confirm("Já há " + n + (n === 1 ? " tentativa registrada" : " tentativas registradas") +
        " na Fase " + ophase + ". Sortear a ordem mesmo assim?")) return;
    // lista vazia: sorteia todas as equipes cadastradas
    var list = orderDraft.length ? orderDraft.slice() : state.teams.map(function (t) { return t.id; });
    for (var i = list.length - 1; i > 0; i--) {
      var j = randInt(i + 1), t = list[i]; list[i] = list[j]; list[j] = t;
    }
    orderDraft = list; orderDirty = true; sig.order = null; renderOrder();
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
    var key = JSON.stringify(state.teams);
    if (sig.teams === key) return;
    var act0 = document.activeElement;                 // não atrapalhar edição de campos
    if (act0 && ul.contains(act0) && act0.tagName === "INPUT") return;
    sig.teams = key;
    ul.textContent = "";
    if (state.teams.length) ul.appendChild(el("li", { className: "teams-head", ariaHidden: "true" },
      [el("span"), el("span", { textContent: "Equipe" }), el("span", { textContent: "Open-hardware por padrão" })]));
    state.teams.forEach(function (t) {
      var li = el("li", { className: "team-row" });
      li.appendChild(logoEl(t));
      var name = el("input", { type: "text", value: t.name, ariaLabel: "Nome da equipe" });
      var hw = el("input", { type: "checkbox", checked: t.open_hw_default });
      var file = el("input", { type: "file", accept: ".png,.jpg,.jpeg,.webp,.svg" });
      var fileLbl = el("label", { className: "file" }, [file, el("span", { className: "file-btn", textContent: "Trocar logo" }),
        el("span", { className: "file-name", textContent: "" })]);
      file.onchange = function () { fileName(file); };
      var save = el("button", { textContent: "Salvar" });
      var del = el("button", { textContent: "Excluir", className: "danger" });
      save.onclick = function () {
        save.blur();
        var fd = new FormData();
        fd.append("name", name.value);
        fd.append("open_hw_default", hw.checked ? "1" : "0");
        if (file.files[0]) fd.append("logo", file.files[0]);
        quiet(act(api("POST", "/api/teams/" + t.id, fd, true)).then(function () {
          sig.teams = null; renderTeams();
          ok("Equipe " + name.value.trim() + " salva.");
        }));
      };
      del.onclick = function () {
        del.blur();
        var atts = state.attempts.filter(function (a) { return a.team_id === t.id; });
        var lost = "";
        if (atts.length) {
          var by = {};
          atts.forEach(function (a) { by[a.phase] = Math.max(by[a.phase] || 0, a.points); });
          lost = " e " + (atts.length === 1 ? "sua tentativa" : "suas " + atts.length + " tentativas") + " (" +
            Object.keys(by).map(function (ph) { return "Fase " + ph + ": " + by[ph] + " pts"; }).join(", ") + ")";
        }
        if (!confirm("Excluir a equipe " + t.name + lost + "?")) return;
        quiet(act(api("DELETE", "/api/teams/" + t.id)).then(function () {
          ok("Equipe " + t.name + " excluída.", { label: "Desfazer", run: function () {
            quiet(act(api("POST", "/api/teams/" + t.id + "/restore")).then(function () {
              sig.teams = null; renderTeams();
              ok("Equipe " + t.name + " restaurada" + (atts.length > 1 ? " com suas tentativas." : atts.length ? " com sua tentativa." : "."));
            }));
          } });
        }));
      };
      hw.setAttribute("aria-label", "open-hardware por padrão: " + t.name);
      var hwl = el("label", { className: "check hw" }, [hw]);
      [name, hwl, fileLbl, save, el("span", { className: "gap" }), del].forEach(function (x) { li.appendChild(x); });
      ul.appendChild(li);
    });
  }

  function fileName(input) {
    var span = input.parentNode.querySelector(".file-name");
    if (!span) return;
    span.textContent = input.files[0] ? input.files[0].name : (input.id === "new-logo" ? "nenhum arquivo" : "");
  }

  // -- eventos ---------------------------------------------------------
  $("new-logo").onchange = function () { fileName(this); };
  $("open-prep").onclick = function () {
    $("prep").open = true;
    $("prep").scrollIntoView({ behavior: "smooth", block: "start" });
    $("order-edit").focus({ preventScroll: true });
  };
  // Preparação: aberta quando falta algo (sem equipes ou sem ordem na fase ativa); senão lembra a escolha.
  var prepPref = null;
  try { prepPref = localStorage.getItem("frl-prep-open"); } catch (e) {}
  $("prep").addEventListener("toggle", function () {
    try { localStorage.setItem("frl-prep-open", this.open ? "1" : "0"); } catch (e) {}
  });
  function timerConfirm(action) {
    var cur = state.current, nxt = state.next;
    if (!cur) return null;
    if (action === "next") return nxt ?
      "Encerrar " + cur.name + " e chamar " + nxt.name + "? O cronômetro volta a 30:00." :
      "Encerrar " + cur.name + "? É a última equipe da fase.";
    if (action === "reset") return "Reiniciar o cronômetro de " + cur.name + "? Ele volta a 30:00 e o tempo usado se perde.";
    return null;
  }
  document.querySelectorAll("[data-timer]").forEach(function (b) {
    b.onclick = function () {
      var action = b.dataset.timer, q = timerConfirm(action), cur = state.current;
      if (q && !confirm(q)) return;
      quiet(act(api("POST", "/api/timer/" + action)).then(function (s) {
        if (action === "next") ok(s.current ? "Na arena: " + s.current.name + "." : "Fase encerrada: todas as equipes voaram.");
        else if (action === "reset" && cur) ok("Cronômetro de " + cur.name + " reiniciado.");
      }));
    };
  });
  $("phase-select").onchange = function () {
    var p = parseInt(this.value, 10);
    if (p === state.phase) { this.blur(); return; }
    if (!confirm("Mudar a fase ativa reinicia o cronômetro da arena. Continuar?")) {
      this.value = String(state.phase); this.blur(); return;
    }
    if (editingId) stopEdit();
    attPhaseTouched = false;            // painel de tentativas volta a seguir a fase ativa
    quiet(act(api("POST", "/api/phase", { phase: p })));
    this.blur();
  };
  $("att-phase-select").onchange = function () {   // não chama /api/phase: TV e cronômetro intactos
    attPhase = parseInt(this.value, 10);
    attPhaseTouched = attPhase !== state.phase;
    teamTouched = false; formKey = ""; sig.attempts = null;
    this.blur();
    render();
  };
  $("team-select").onchange = function () { teamTouched = true; formKey = ""; render(); };
  $("save-attempt").onclick = function () {
    var inputs = readInputs(), p;
    if (editingId) p = api("PUT", "/api/attempts/" + editingId, { inputs: inputs });
    else p = api("POST", "/api/attempts", { team_id: selectedTeamId(), phase: attPhase, inputs: inputs });
    var wasEditing = !!editingId, tid = selectedTeamId(), team = teamById(tid);
    var ph = editingId ? editingPhase() : attPhase, eid = editingId;
    quiet(act(p).then(function (s) {
      var list = teamPhaseAttempts(s, tid, ph);
      var idx = wasEditing ? list.map(function (a) { return a.id; }).indexOf(eid) : list.length - 1;
      var a = list[idx];
      if (a && team) ok("T" + (idx + 1) + (wasEditing ? " atualizada: " : " salva: ") + team.name +
        ", Fase " + ph + ", " + a.points + " pts.");
      $("form-errors").textContent = "";
      teamTouched = false;
      if (wasEditing) stopEdit(); else { formKey = ""; render(); }
    }));
  };
  $("cancel-edit").onclick = stopEdit;
  $("order-add-btn").onclick = function () {
    var v = $("order-add").value;
    if (!v) return;
    orderDraft.push(v); orderDirty = true; sig.order = null; renderOrder();
  };
  $("order-shuffle").onclick = shuffleOrder;
  $("order-edit").onclick = function () { orderEditing = true; sig.order = null; renderOrder(); };
  $("order-cancel").onclick = function () {
    if (orderDirty && !confirm("Descartar as alterações não salvas da ordem?")) return;
    orderEditing = false; orderDirty = false; orderDraft = null; sig.order = null; renderOrder();
  };
  $("order-phase-select").onchange = function () {
    var p = parseInt(this.value, 10);
    if (orderDirty && !confirm("Descartar as alterações não salvas da ordem?")) { this.value = String(ophase); return; }
    ophase = p; ophaseTouched = p !== state.phase; sig.order = null;
    this.blur();
    renderOrder();
  };
  $("order-save").onclick = function () {
    var phase = ophase;
    quiet(act(api("POST", "/api/orders/" + phase, { team_ids: orderDraft })).then(function () {
      orderDirty = false; orderEditing = false; sig.order = null; renderOrder();
      ok("Ordem da Fase " + phase + " salva.");
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
      fileName($("new-logo"));
      ok("Equipe " + name + " adicionada.");
    }));
  };

  // Atalhos: Espaço inicia/pausa e N chama a próxima equipe (fora de campos de texto);
  // Ctrl+Enter salva a tentativa de qualquer lugar. As confirmações continuam valendo.
  document.addEventListener("keydown", function (e) {
    if (!state || e.altKey || e.metaKey) return;
    if (e.ctrlKey && e.key === "Enter") {
      if (!$("save-attempt").disabled) { e.preventDefault(); $("save-attempt").click(); }
      return;
    }
    if (e.ctrlKey) return;
    var t = e.target, tag = t && t.tagName;
    if (tag === "INPUT" || tag === "SELECT" || tag === "TEXTAREA" || tag === "BUTTON" || tag === "SUMMARY" ||
        (t && t.isContentEditable)) return;
    if (e.key === " ") {
      var b = state.timer.running ? $("b-pause") : $("b-start");
      e.preventDefault();
      if (!b.disabled) b.click();
    } else if (e.key === "n" || e.key === "N") {
      if (!$("b-next").disabled) { e.preventDefault(); $("b-next").click(); }
    }
  });

  // -- polling ---------------------------------------------------------
  function poll() {
    api("GET", "/api/state").then(function (s) {
      $("offline").hidden = true;
      applyState(s);
    }, function () { $("offline").hidden = false; });
  }
  poll();
  setInterval(poll, 1000);
  (function frame() { renderCountdown(); requestAnimationFrame(frame); })();
})();
