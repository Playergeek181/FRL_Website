"""Aplicação Flask: páginas e API JSON do placar."""
from pathlib import Path

from flask import Flask, jsonify, redirect, request, send_from_directory
from werkzeug.exceptions import BadRequest, HTTPException

from . import timer
from .constants import PHASE_NAMES
from .ranking import overall_ranking
from .scoring import attempt_points, attempt_problems
from .store import Store

STATIC_DIR = Path(__file__).parent / "static"
LOGO_EXTS = {"png", "jpg", "jpeg", "webp", "svg"}


def _logo_url(logo_dir: Path, logo):
    """URL do logo com ?v=<mtime> para a TV recarregar um logo trocado (mesmo nome)."""
    if not logo:
        return None
    try:
        return f"/logos/{logo}?v={int((logo_dir / logo).stat().st_mtime)}"
    except OSError:
        return f"/logos/{logo}"


def _truthy(value) -> bool:
    return str(value).strip().lower() in ("1", "true", "on", "sim", "yes")


def create_app(data_dir: Path) -> Flask:
    data_dir = Path(data_dir)
    logo_dir = data_dir / "logos"
    app = Flask(__name__, static_folder=None)
    app.config["MAX_CONTENT_LENGTH"] = 5 * 1024 * 1024
    store = Store(data_dir)

    # -- erros ---------------------------------------------------------
    @app.errorhandler(ValueError)
    def _value_error(e):
        errors = e.args[0] if e.args and isinstance(e.args[0], list) else [str(e)]
        return jsonify(errors=errors), 400

    @app.errorhandler(KeyError)
    def _key_error(e):
        return jsonify(errors=["Item não encontrado"]), 404

    @app.errorhandler(HTTPException)
    def _http_error(e):
        if request.path.startswith("/api/"):
            msg = "Arquivo muito grande" if e.code == 413 else (e.description or e.name)
            return jsonify(errors=[msg]), e.code
        return e

    def logo_url(logo):
        return _logo_url(logo_dir, logo)

    def body() -> dict:
        data = request.get_json(silent=True)
        if not isinstance(data, dict):
            raise BadRequest("Corpo JSON inválido")
        return data

    # -- estado --------------------------------------------------------
    def state_json():
        cur, nxt = store.current_and_next()
        s = store.state
        teams = {t["id"]: t for t in s["teams"]}

        def team_view(t):
            return {"id": t["id"], "name": t["name"], "logo": logo_url(t["logo"])} if t else None

        slot = s["slot"]
        phase = s["active_phase"]
        order = s["orders"][str(phase)]
        ranking = []
        for row in overall_ranking([t["id"] for t in s["teams"]], store.best_by_phase()):
            t = teams[row["team_id"]]
            ranking.append({
                "team_id": t["id"], "name": t["name"], "logo": logo_url(t["logo"]),
                "position": row["position"],
                "phase_points": {str(p): v for p, v in row["phase_points"].items()},
                "total": row["total"]})
        return jsonify({
            "phase": phase, "phase_name": PHASE_NAMES[phase],
            "current": team_view(cur), "next": team_view(nxt),
            "phase_finished": bool(order) and cur is None,
            "timer": {"running": bool(slot["running"]),
                      "remaining_ms": timer.remaining(slot, store.clock()),
                      "expired": cur is not None and timer.expired(slot)},
            "slot_index": slot["index"],
            "ranking": ranking,
            "teams": [{"id": t["id"], "name": t["name"], "logo": logo_url(t["logo"]),
                       "open_hw_default": t["open_hw_default"]} for t in s["teams"]],
            "orders": {k: list(v) for k, v in s["orders"].items()},
            "attempts": [{k: a[k] for k in ("id", "team_id", "phase", "inputs", "points")}
                         for a in s["attempts"]],
        })

    # -- páginas -------------------------------------------------------
    @app.get("/")
    def index():
        return redirect("/tv")

    @app.get("/tv")
    def tv():
        return send_from_directory(STATIC_DIR, "tv.html")

    @app.get("/controle")
    def controle():
        return send_from_directory(STATIC_DIR, "controle.html")

    @app.get("/static/<path:filename>")
    def static_files(filename):
        return send_from_directory(STATIC_DIR, filename)

    @app.get("/logos/<path:filename>")
    def logos(filename):
        return send_from_directory(logo_dir, filename)

    @app.get("/api/state")
    def get_state():
        return state_json()

    # -- equipes -------------------------------------------------------
    def logo_ext():
        f = request.files.get("logo")
        if f is None or not f.filename:
            return None, None
        ext = f.filename.rsplit(".", 1)[-1].lower() if "." in f.filename else ""
        if ext not in LOGO_EXTS:
            raise ValueError(["Logo deve ser png, jpg, jpeg, webp ou svg."])
        return f, ext

    def save_logo(team_id, f, ext):
        logo_dir.mkdir(parents=True, exist_ok=True)
        for old in logo_dir.glob(f"{team_id}.*"):
            old.unlink()
        name = f"{team_id}.{ext}"
        f.save(logo_dir / name)
        store.update_team(team_id, logo=name)

    @app.post("/api/teams")
    def add_team():
        name = (request.form.get("name") or "").strip()
        if not name:
            raise ValueError(["Nome da equipe é obrigatório."])
        f, ext = logo_ext()
        team = store.add_team(name, _truthy(request.form.get("open_hw_default", "")))
        if f:
            save_logo(team["id"], f, ext)
        return state_json()

    @app.post("/api/teams/<team_id>")
    def edit_team(team_id):
        store._team(team_id)  # 404 antes de qualquer efeito
        name = request.form.get("name")
        if name is not None:
            name = name.strip()
            if not name:
                raise ValueError(["Nome da equipe é obrigatório."])
        hw = request.form.get("open_hw_default")
        f, ext = logo_ext()
        store.update_team(team_id, name=name,
                          open_hw_default=None if hw is None else _truthy(hw))
        if f:
            save_logo(team_id, f, ext)
        return state_json()

    trash_dir = logo_dir / ".excluidos"   # logo da última equipe excluída, para "Desfazer"

    @app.delete("/api/teams/<team_id>")
    def remove_team(team_id):
        store.delete_team(team_id)
        if trash_dir.exists():
            for old in trash_dir.iterdir():
                old.unlink()
        for old in logo_dir.glob(f"{team_id}.*"):
            trash_dir.mkdir(parents=True, exist_ok=True)
            old.replace(trash_dir / old.name)
        return state_json()

    @app.post("/api/teams/<team_id>/restore")
    def restore_team(team_id):
        team = store.restore_team(team_id)
        if team.get("logo") and (trash_dir / team["logo"]).exists():
            (trash_dir / team["logo"]).replace(logo_dir / team["logo"])
        return state_json()

    # -- ordem / fase / cronômetro ------------------------------------
    @app.post("/api/orders/<int:phase>")
    def set_order(phase):
        ids = body().get("team_ids")
        if not isinstance(ids, list) or not all(isinstance(i, str) for i in ids):
            raise BadRequest("team_ids deve ser uma lista")
        store.set_order(phase, ids)
        return state_json()

    @app.post("/api/phase")
    def set_phase():
        phase = body().get("phase")
        if not isinstance(phase, int) or isinstance(phase, bool):
            raise ValueError(["Fase inválida."])
        store.set_phase(phase)
        return state_json()

    @app.post("/api/timer/<action>")
    def timer_action(action):
        store.timer_action(action)
        return state_json()

    # -- tentativas ----------------------------------------------------
    @app.post("/api/attempts")
    def add_attempt():
        d = body()
        phase = d.get("phase")
        if not isinstance(phase, int) or isinstance(phase, bool):
            raise ValueError(["Fase inválida."])
        if not isinstance(d.get("inputs"), dict):
            raise BadRequest("inputs deve ser um objeto")
        store.add_attempt(d.get("team_id"), phase, d["inputs"])
        return state_json()

    @app.put("/api/attempts/<attempt_id>")
    def edit_attempt(attempt_id):
        inputs = body().get("inputs")
        if not isinstance(inputs, dict):
            raise BadRequest("inputs deve ser um objeto")
        store.update_attempt(attempt_id, inputs)
        return state_json()

    @app.delete("/api/attempts/<attempt_id>")
    def remove_attempt(attempt_id):
        store.delete_attempt(attempt_id)
        return state_json()

    @app.post("/api/preview")
    def preview():
        d = body()
        phase, inputs = d.get("phase"), d.get("inputs")
        if phase not in (1, 2, 3, 4) or isinstance(phase, bool) or not isinstance(inputs, dict):
            raise ValueError(["Fase ou dados inválidos."])
        problems = attempt_problems(phase, inputs)
        if problems:   # "fields" diz quais campos marcar em vermelho no formulário
            return jsonify(errors=[m for _, m in problems],
                           fields=sorted({k for k, _ in problems if k})), 400
        return jsonify(points=attempt_points(phase, inputs))

    return app
