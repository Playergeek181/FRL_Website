# FRL 2026 Scoreboard Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** A local Flask website on a Raspberry Pi 5 that shows the current team, its 30-minute countdown, the next team, and the live FRL ranking on a TV, controlled from the operator's computer.

**Architecture:** Pure-Python modules for scoring, ranking and timer logic (fully unit-tested, no I/O), a JSON-file store, and a small Flask app exposing one read endpoint (`GET /api/state`) plus write endpoints. Two static pages (TV and control) poll `/api/state` every second and render it; the countdown is drawn locally from the server's `remaining_ms`.

**Tech Stack:** Python ≥ 3.10, Flask 3, pytest; plain HTML/CSS/JS (no build step, no CDN).

**Spec:** `docs/superpowers/specs/2026-10-31-frl-scoreboard-design.md`

## Global Constraints

- All user-facing text in Portuguese (TV and control page).
- Works fully offline: no CDN, no external fonts or scripts.
- Python ≥ 3.10 (dev machine is 3.10, Pi OS Bookworm ships 3.11). Only runtime dependency: Flask.
- Data persists in `data/` (`data/state.json`, `data/logos/`); a restart loses nothing.
- Server listens on `0.0.0.0:8000`. TV page: `/tv`. Control page: `/controle`. `/` redirects to `/tv`.
- No password / authentication (operator confirmed the network is private).
- Do not hard-code the number of teams; the ranking points table always has 11 positions: `[25, 18, 15, 12, 10, 8, 6, 4, 2, 1]`, 11th and below → 0.
- Slot length: 30 minutes = `1_800_000` ms.
- Phase names: 1 "Localização e Mapeamento", 2 "Transporte de Pacotes", 3 "Interação Humano-Enxame", 4 "Navegação em Espaço Confinado".
- The folder is not a git repository and the operator has not asked for commits: **skip commit steps** unless they ask.

## Review Focus

1. **Restart while a slot timer is running** → after restart the countdown continues from the correct remaining time (wall-clock `started_at` persisted). Test in Task 3.
2. **Order edited or team deleted while that team is "NA ARENA"** → no crash; current index clamped, phase shows "Fase encerrada" if past the end. Test in Task 3.
3. **Editing or deleting the best attempt** → phase score falls back to the next best attempt and ranking updates. Test in Task 4.
4. **State file write interrupted / two requests at once** → atomic write (temp file + `os.replace`) under a lock; a missing state file starts empty. Test in Task 3.
5. **Team names with HTML characters, or a non-image logo upload** → names rendered with `textContent` (never `innerHTML`), logo upload restricted to png/jpg/jpeg/webp/svg and rejected with a 400 otherwise. Test in Task 4.

---

## File Structure

```
frl/__init__.py
frl/__main__.py        # python3 -m frl → runs server on 0.0.0.0:8000
frl/constants.py       # PHASE_NAMES, RANK_POINTS, SLOT_MS
frl/scoring.py         # validate_attempt, attempt_points (pure)
frl/ranking.py         # phase_ranking, overall_ranking (pure)
frl/timer.py           # slot timer pure functions
frl/store.py           # Store: JSON persistence + mutations
frl/app.py             # create_app(data_dir) Flask factory + routes
frl/static/common.css
frl/static/tv.html, tv.css, tv.js
frl/static/controle.html, controle.css, controle.js
tests/test_scoring.py, test_ranking.py, test_timer.py, test_store.py, test_app.py
requirements.txt       # flask>=3,<4 ; pytest (dev)
README.md              # run locally, run on the Pi, kiosk autostart
```

---

### Task 1: Project scaffold + scoring

**Files:**
- Create: `requirements.txt`, `frl/__init__.py`, `frl/constants.py`, `frl/scoring.py`
- Test: `tests/test_scoring.py`

**Interfaces:**
- Produces:
  - `frl.constants.PHASE_NAMES: dict[int, str]`, `RANK_POINTS: list[int]`, `SLOT_MS: int = 1_800_000`
  - `validate_attempt(phase: int, inputs: dict) -> list[str]` — list of Portuguese error messages, empty if valid.
  - `attempt_points(phase: int, inputs: dict) -> int` — assumes valid inputs; result clamped to ≥ 0.
  - Input keys (all ints ≥ 0 or bools):
    - Phase 1: `bases` (0–6), `repeats`, `returned`, `open_hw`
    - Phase 2: `lifted` (0–3), `delivered` (≤ lifted), `dropped` (≤ lifted − delivered), `returned`, `open_hw`
    - Phase 3: `recognized`, `bases` (0–6), `repeats`, `cross_repeats`, `returned`, `open_hw`
    - Phase 4: `maze`, `qr` (0–5), `landed`, `open_hw`

- [ ] **Step 1: Set up venv and requirements**

Run: `python3 -m venv .venv && .venv/bin/pip install "flask>=3,<4" pytest`
Write `requirements.txt` with `flask>=3,<4`. Expected: `.venv/bin/python -c "import flask"` exits 0.

- [ ] **Step 2: Write failing tests** in `tests/test_scoring.py`

```python
import pytest
from frl.scoring import attempt_points, validate_attempt

@pytest.mark.parametrize("phase,inputs,expected", [
    (1, dict(bases=5, repeats=1, returned=True, open_hw=True), 380),
    (1, dict(bases=6, repeats=0, returned=True, open_hw=True), 480),
    (1, dict(bases=3, repeats=0, returned=False, open_hw=False), 60),
    (1, dict(bases=0, repeats=2, returned=True, open_hw=True), 0),      # negative → 0, no doubling
    (2, dict(lifted=3, delivered=3, dropped=0, returned=True, open_hw=True), 720),
    (2, dict(lifted=2, delivered=0, dropped=1, returned=True, open_hw=False), 75),  # no delivery → no return bonus
    (2, dict(lifted=2, delivered=1, dropped=0, returned=True, open_hw=False), 200),
    (3, dict(recognized=False, bases=6, repeats=0, cross_repeats=0, returned=True, open_hw=True), 0),
    (3, dict(recognized=True, bases=6, repeats=0, cross_repeats=0, returned=True, open_hw=True), 480),
    (3, dict(recognized=True, bases=4, repeats=1, cross_repeats=1, returned=False, open_hw=False), 65),
    (3, dict(recognized=True, bases=0, repeats=0, cross_repeats=0, returned=True, open_hw=False), 0),
    (4, dict(maze=True, qr=5, landed=True, open_hw=True), 600),
    (4, dict(maze=False, qr=2, landed=True, open_hw=False), 40),         # did not exit maze → no doubling
    (4, dict(maze=True, qr=0, landed=True, open_hw=False), 50),          # no QR → no doubling
])
def test_attempt_points(phase, inputs, expected):
    assert attempt_points(phase, inputs) == expected

def test_validate_rejects_out_of_range():
    assert validate_attempt(1, dict(bases=7, repeats=0, returned=False, open_hw=False))
    assert validate_attempt(2, dict(lifted=1, delivered=2, dropped=0, returned=False, open_hw=False))
    assert validate_attempt(2, dict(lifted=2, delivered=1, dropped=2, returned=False, open_hw=False))
    assert validate_attempt(4, dict(maze=True, qr=6, landed=False, open_hw=False))
    assert validate_attempt(1, dict(bases=-1, repeats=0, returned=False, open_hw=False))
    assert validate_attempt(5, {})                                       # unknown phase

def test_validate_accepts_valid():
    assert validate_attempt(1, dict(bases=6, repeats=3, returned=True, open_hw=False)) == []
```

- [ ] **Step 3: Run tests to verify they fail**

Run: `.venv/bin/pytest tests/test_scoring.py -v` — Expected: FAIL (`ModuleNotFoundError: frl.scoring`).

- [ ] **Step 4: Implement `frl/constants.py` and `frl/scoring.py`**

Order of operations: base = points − penalties; if the phase's return condition holds **and** base > 0 → ×2; if `open_hw` → ×2; return `max(0, result)`. Return conditions: P1 `returned`; P2 `returned and delivered >= 1`; P3 `returned and bases >= 1`; P4 `maze and landed and qr >= 1`. P3 with `recognized=False` → 0. Missing keys in `validate_attempt` are an error.

- [ ] **Step 5: Run tests to verify they pass**

Run: `.venv/bin/pytest tests/test_scoring.py -v` — Expected: all PASS.

---

### Task 2: Ranking

**Files:**
- Create: `frl/ranking.py`
- Test: `tests/test_ranking.py`

**Interfaces:**
- Consumes: `RANK_POINTS` from Task 1.
- Produces:
  - `phase_ranking(best: dict[str, int | None]) -> dict[str, dict]` — `best` maps team_id → best-attempt score, or `None` if no attempt. Returns team_id → `{"position": int | None, "points": int}`. Only scores > 0 are ranked; competition ranking (1, 1, 3); position p → `RANK_POINTS[p-1]` if p ≤ 10 else 0. Score 0 or None → `position None, points 0`.
  - `overall_ranking(team_ids: list[str], best_by_phase: dict[int, dict[str, int | None]]) -> list[dict]` — rows sorted best first:
    `{"team_id", "position": int, "phase_points": {1..4: int | None}, "total": int, "phases_scored": int}`.
    `phase_points[p]` is `None` when the team has no attempt in phase p, otherwise its ranking points. `phases_scored` = number of phases with ranking points > 0. Sort key: `(-total, -phases_scored, -raw1, -raw2, -raw3, -raw4)` where `rawN` is the best score (None → 0). Rows with identical keys share the same position (competition ranking); ties broken for display by team name order is not required — keep input order.

- [ ] **Step 1: Write failing tests** in `tests/test_ranking.py`

```python
from frl.ranking import phase_ranking, overall_ranking

def test_phase_ties_skip_positions():
    r = phase_ranking({"a": 100, "b": 100, "c": 50})
    assert r["a"] == {"position": 1, "points": 25}
    assert r["b"] == {"position": 1, "points": 25}
    assert r["c"] == {"position": 3, "points": 15}

def test_eleventh_gets_zero():
    best = {f"t{i}": 200 - i for i in range(11)}
    r = phase_ranking(best)
    assert r["t9"]["points"] == 1
    assert r["t10"] == {"position": 11, "points": 0}

def test_zero_and_absent_unranked():
    r = phase_ranking({"a": 0, "b": None, "c": 10})
    assert r["a"] == {"position": None, "points": 0}
    assert r["b"] == {"position": None, "points": 0}
    assert r["c"] == {"position": 1, "points": 25}

def test_overall_tiebreak_more_phases_wins():
    # A: 1st in P1 only (25). B: 3rd in P1 (15) + 5th... build so B has 25 over two phases.
    best = {
        1: {"A": 300, "X": 250, "B": 200, "Y": 150, "Z": 100},   # A 25, X 18, B 15, Y 12, Z 10
        2: {"Y": 300, "Z": 250, "X": 200, "C": 150, "B": 100},   # Y 25, Z 18, X 15, C 12, B 10
        3: {}, 4: {},
    }
    rows = overall_ranking(["A", "B", "C", "X", "Y", "Z"], best)
    by = {r["team_id"]: r for r in rows}
    assert by["A"]["total"] == 25 and by["B"]["total"] == 25
    assert by["B"]["position"] < by["A"]["position"]
    assert by["A"]["phase_points"][2] is None
    assert by["B"]["phases_scored"] == 2

def test_overall_tiebreak_phase1_score():
    best = {1: {"A": 100, "B": 90}, 2: {"B": 100, "A": 90}, 3: {}, 4: {}}
    rows = overall_ranking(["B", "A"], best)
    assert [r["team_id"] for r in rows] == ["A", "B"]
    assert rows[0]["position"] == 1 and rows[1]["position"] == 2

def test_overall_full_tie_shares_position():
    best = {1: {"A": 100, "B": 100}, 2: {}, 3: {}, 4: {}}
    rows = overall_ranking(["A", "B"], best)
    assert rows[0]["position"] == rows[1]["position"] == 1

def test_team_with_nothing_is_last():
    best = {1: {"A": 10}, 2: {}, 3: {}, 4: {}}
    rows = overall_ranking(["Z", "A"], best)
    assert rows[-1]["team_id"] == "Z" and rows[-1]["total"] == 0
```

- [ ] **Step 2: Run tests to verify they fail** — `.venv/bin/pytest tests/test_ranking.py -v` → FAIL (module missing).
- [ ] **Step 3: Implement `frl/ranking.py`** per the Interfaces block.
- [ ] **Step 4: Run tests to verify they pass** — `.venv/bin/pytest tests/test_ranking.py -v` → all PASS.

---

### Task 3: Timer and store

**Files:**
- Create: `frl/timer.py`, `frl/store.py`
- Test: `tests/test_timer.py`, `tests/test_store.py`

**Interfaces:**
- Consumes: `SLOT_MS`, `validate_attempt`, `attempt_points`.
- Produces:
  - Timer dict shape (stored in state as `state["slot"]`): `{"index": int, "running": bool, "remaining_ms": int, "started_at": float | None}` (`started_at` = wall-clock ms when last started; `remaining_ms` = remaining at that moment).
  - `frl.timer`: `new_slot(index=0) -> dict`, `remaining(slot, now_ms) -> int` (≥ 0), `start(slot, now_ms) -> dict`, `pause(slot, now_ms) -> dict`, `add(slot, ms, now_ms) -> dict`, `reset(slot) -> dict` (30:00, stopped, same index), `advance(slot) -> dict` (index+1, fresh stopped 30:00), `tick(slot, now_ms) -> dict` (if running and remaining == 0 → `advance`). All pure, return new dicts.
  - `class Store(data_dir: Path, clock: Callable[[], float] = wall-clock ms)`:
    - `state` shape: `{"teams": [{"id", "name", "logo": str | None, "open_hw_default": bool}], "orders": {"1".."4": [team_id]}, "active_phase": int, "slot": <timer dict>, "attempts": [{"id", "team_id", "phase", "inputs", "points"}]}`
    - Team: `add_team(name: str, open_hw_default: bool = False) -> dict`, `update_team(team_id, name=None, open_hw_default=None, logo=None) -> dict`, `delete_team(team_id) -> None` (also removes from orders and deletes its attempts).
    - Order/phase: `set_order(phase: int, team_ids: list[str]) -> None`, `set_phase(phase: int) -> None` (resets slot to `new_slot(0)`).
    - Timer: `timer_action(action: str, now_ms=None) -> None` for `"start" | "pause" | "add" | "reset" | "next"` (`add` = +60 000 ms).
    - Attempts: `add_attempt(team_id, phase, inputs) -> dict` (raises `ValueError(list_of_errors)` if invalid or team already has 3 attempts in that phase), `update_attempt(attempt_id, inputs) -> dict`, `delete_attempt(attempt_id) -> None`. Points computed with `attempt_points` and stored.
    - `best_by_phase() -> dict[int, dict[str, int | None]]` (None for teams without attempts in that phase).
    - `current_and_next() -> tuple[dict | None, dict | None]` — applies `tick`, clamps; current is `None` when `slot.index >= len(order)` ("Fase encerrada").
    - Persistence: every mutation writes `data/state.json` atomically (write `state.json.tmp`, `os.replace`) under a `threading.Lock`; constructor loads the file or starts empty with `active_phase=1`.

- [ ] **Step 1: Write failing timer tests** in `tests/test_timer.py`

```python
from frl import timer as t

def test_countdown_and_pause():
    s = t.start(t.new_slot(), now_ms=0)
    assert t.remaining(s, 60_000) == 1_740_000
    s = t.pause(s, 60_000)
    assert t.remaining(s, 999_999) == 1_740_000 and not s["running"]

def test_add_minute_while_running():
    s = t.add(t.start(t.new_slot(), 0), 60_000, 10_000)
    assert t.remaining(s, 10_000) == 1_850_000

def test_tick_auto_advances_and_waits():
    s = t.tick(t.start(t.new_slot(index=2), 0), 1_800_001)
    assert s == {"index": 3, "running": False, "remaining_ms": 1_800_000, "started_at": None}

def test_reset_keeps_index():
    s = t.reset(t.start(t.new_slot(index=1), 0))
    assert s["index"] == 1 and s["remaining_ms"] == 1_800_000 and not s["running"]
```

- [ ] **Step 2: Write failing store tests** in `tests/test_store.py` (use `tmp_path`, a fake clock `lambda: now[0]`):

```python
def test_restart_keeps_running_timer(tmp_path):     # Review Focus 1
    now = [0]; s = Store(tmp_path, clock=lambda: now[0])
    a = s.add_team("A"); s.set_order(1, [a["id"]]); s.timer_action("start")
    now[0] = 600_000
    s2 = Store(tmp_path, clock=lambda: now[0])
    assert timer.remaining(s2.state["slot"], now[0]) == 1_200_000

def test_delete_current_team_clamps(tmp_path):       # Review Focus 2
    s = Store(tmp_path); a = s.add_team("A"); b = s.add_team("B")
    s.set_order(1, [a["id"], b["id"]]); s.timer_action("next")
    s.delete_team(b["id"])
    assert s.current_and_next() == (None, None)

def test_auto_advance_shows_next(tmp_path):
    now = [0]; s = Store(tmp_path, clock=lambda: now[0])
    a, b = s.add_team("A"), s.add_team("B"); s.set_order(1, [a["id"], b["id"]])
    s.timer_action("start"); now[0] = 1_800_001
    cur, nxt = s.current_and_next()
    assert cur["id"] == b["id"] and nxt is None and not s.state["slot"]["running"]

def test_fourth_attempt_rejected(tmp_path):
    s = Store(tmp_path); a = s.add_team("A")
    inp = dict(bases=1, repeats=0, returned=False, open_hw=False)
    for _ in range(3): s.add_attempt(a["id"], 1, inp)
    with pytest.raises(ValueError): s.add_attempt(a["id"], 1, inp)

def test_best_by_phase(tmp_path):
    s = Store(tmp_path); a = s.add_team("A"); b = s.add_team("B")
    s.add_attempt(a["id"], 1, dict(bases=2, repeats=0, returned=False, open_hw=False))
    s.add_attempt(a["id"], 1, dict(bases=4, repeats=0, returned=False, open_hw=False))
    assert s.best_by_phase()[1] == {a["id"]: 80, b["id"]: None}

def test_missing_file_starts_empty_and_write_is_atomic(tmp_path):   # Review Focus 4
    s = Store(tmp_path); s.add_team("A")
    assert (tmp_path / "state.json").exists() and not (tmp_path / "state.json.tmp").exists()
    assert Store(tmp_path).state["teams"][0]["name"] == "A"
```

- [ ] **Step 3: Run tests to verify they fail** — `.venv/bin/pytest tests/test_timer.py tests/test_store.py -v` → FAIL.
- [ ] **Step 4: Implement `frl/timer.py` and `frl/store.py`** per the Interfaces block. IDs: `uuid4().hex[:8]`.
- [ ] **Step 5: Run tests to verify they pass** — same command → all PASS.

---

### Task 4: Flask app and API

**Files:**
- Create: `frl/app.py`, `frl/__main__.py`
- Test: `tests/test_app.py`

**Interfaces:**
- Consumes: `Store`, `overall_ranking`, `phase_ranking`, `attempt_points`, `validate_attempt`, `PHASE_NAMES`, `timer.remaining`.
- Produces (used by Tasks 5–6):
  - `create_app(data_dir: Path) -> Flask`. `python3 -m frl` runs it with `data_dir = <project>/data` (override via `FRL_DATA_DIR`) on `0.0.0.0:8000`.
  - `GET /` → 302 `/tv`; `GET /tv` → `static/tv.html`; `GET /controle` → `static/controle.html`; `GET /logos/<file>` → from `data/logos/`.
  - `GET /api/state` → JSON:
    ```
    {"phase": int, "phase_name": str,
     "current": team|null, "next": team|null, "phase_finished": bool,
     "timer": {"running": bool, "remaining_ms": int},
     "ranking": [{"team_id","name","logo","position","phase_points":{"1".."4": int|null},"total"}],
     "teams": [...], "orders": {...}, "attempts": [...]}
    ```
    `team` = `{"id","name","logo"}` where `logo` is a URL (`/logos/<file>`) or null. `phase_finished` is true when the active phase has a non-empty order and `current` is null.
  - Writes (JSON bodies unless noted; every write returns the same body as `GET /api/state`; validation errors → 400 `{"errors": [str]}`):
    - `POST /api/teams` (multipart: `name`, optional `open_hw_default`, optional file `logo`), `POST /api/teams/<id>` (same fields, partial), `DELETE /api/teams/<id>`
    - `POST /api/orders/<phase>` `{"team_ids": [...]}`
    - `POST /api/phase` `{"phase": 1..4}`
    - `POST /api/timer/<action>` (start|pause|add|reset|next)
    - `POST /api/attempts` `{"team_id","phase","inputs"}`, `PUT /api/attempts/<id>` `{"inputs"}`, `DELETE /api/attempts/<id>`
    - `POST /api/preview` `{"phase","inputs"}` → `{"points": int}` or 400 `{"errors": [...]}`
  - Logo: allowed extensions `png, jpg, jpeg, webp, svg`; saved as `data/logos/<team_id>.<ext>`; `MAX_CONTENT_LENGTH = 5 MB`.

- [ ] **Step 1: Write failing tests** in `tests/test_app.py` (fixture: `create_app(tmp_path).test_client()`)

```python
def test_state_empty(client):
    s = client.get("/api/state").get_json()
    assert s["phase"] == 1 and s["phase_name"] == "Localização e Mapeamento"
    assert s["current"] is None and s["ranking"] == []

def test_full_flow(client):
    a = client.post("/api/teams", data={"name": "Falcon"}).get_json()["teams"][0]["id"]
    client.post("/api/orders/1", json={"team_ids": [a]})
    client.post("/api/timer/start")
    s = client.post("/api/attempts", json={"team_id": a, "phase": 1,
        "inputs": dict(bases=5, repeats=1, returned=True, open_hw=True)}).get_json()
    assert s["current"]["name"] == "Falcon" and s["timer"]["running"]
    assert s["ranking"][0]["phase_points"]["1"] == 25 and s["ranking"][0]["total"] == 25

def test_delete_best_attempt_falls_back(client):          # Review Focus 3
    a = client.post("/api/teams", data={"name": "A"}).get_json()["teams"][0]["id"]
    def add(b): return client.post("/api/attempts", json={"team_id": a, "phase": 1,
        "inputs": dict(bases=b, repeats=0, returned=False, open_hw=False)}).get_json()
    add(2); s = add(5)
    best = max(s["attempts"], key=lambda x: x["points"])
    s = client.delete(f"/api/attempts/{best['id']}").get_json()
    assert max(x["points"] for x in s["attempts"]) == 40

def test_invalid_attempt_400(client):
    a = client.post("/api/teams", data={"name": "A"}).get_json()["teams"][0]["id"]
    r = client.post("/api/attempts", json={"team_id": a, "phase": 1,
        "inputs": dict(bases=9, repeats=0, returned=False, open_hw=False)})
    assert r.status_code == 400 and r.get_json()["errors"]

def test_preview(client):
    r = client.post("/api/preview", json={"phase": 2,
        "inputs": dict(lifted=3, delivered=3, dropped=0, returned=True, open_hw=True)})
    assert r.get_json() == {"points": 720}

def test_logo_rejects_non_image(client):                  # Review Focus 5
    r = client.post("/api/teams", data={"name": "<b>X</b>",
        "logo": (io.BytesIO(b"x"), "evil.exe")}, content_type="multipart/form-data")
    assert r.status_code == 400

def test_logo_upload_served(client):
    s = client.post("/api/teams", data={"name": "A",
        "logo": (io.BytesIO(b"\x89PNG"), "a.png")}, content_type="multipart/form-data").get_json()
    url = s["teams"][0]["logo"]
    assert url.startswith("/logos/") and client.get(url).status_code == 200

def test_pages(client):
    assert client.get("/").status_code == 302
    assert client.get("/tv").status_code == 200 and client.get("/controle").status_code == 200
```

- [ ] **Step 2: Run tests to verify they fail** — `.venv/bin/pytest tests/test_app.py -v` → FAIL.
- [ ] **Step 3: Implement `frl/app.py` and `frl/__main__.py`** per the Interfaces block. Create empty placeholder `frl/static/tv.html` and `controle.html` so page tests pass (filled in Tasks 5–6).
- [ ] **Step 4: Run all tests** — `.venv/bin/pytest -v` → all PASS.

---

### Task 5: TV page

**Files:**
- Create/replace: `frl/static/tv.html`, `frl/static/tv.css`, `frl/static/tv.js`, `frl/static/common.css`

**Interfaces:**
- Consumes: `GET /api/state` (Task 4).

Layout (approved mockup "A", see spec): full-viewport 16:9, dark background (`#0d1b2a`, cards `#1b263b`, countdown `#ffd166`).
- Left column (flex 1): phase label `FASE {n} · {PHASE_NAME UPPERCASE}`; card "NA ARENA" with large logo (~18vh), team name, countdown `MM:SS` (~16vh font, `font-variant-numeric: tabular-nums`); card "PRÓXIMA" with smaller logo and name. When `phase_finished`: card shows "Fase encerrada"; when no order set: "Aguardando ordem".
- Right column (flex 1.3): "CLASSIFICAÇÃO" table — `#`, logo (small), Equipe, F1, F2, F3, F4, **Total**. `null` → "–". All rows visible: font size scales with `vh` so 11+ rows fit without scrolling.
- Logo fallback: colored circle with the team's initials (color derived from a hash of the team id).
- Behavior: poll `/api/state` every 1000 ms; keep `remaining_ms` and the local receive time, redraw the countdown every 250 ms locally (`remaining_ms - (Date.now() - receivedAt)` when running, clamped at 0). Countdown turns red below 5:00. Render all names with `textContent`. On fetch failure, keep the last state and show a small "sem conexão" indicator.

- [ ] **Step 1: Implement the three files.**
- [ ] **Step 2: Manual check** — `.venv/bin/python -m frl`, add 2 teams with `curl -F name=A localhost:8000/api/teams` etc., set order, `curl -X POST localhost:8000/api/timer/start`, open `http://localhost:8000/tv` at 1920×1080. Expected: layout matches the mockup, countdown ticks, starting/pausing via curl reflects within ~1 s, a team named `<b>X</b>` shows literally.
- [ ] **Step 3: Run all tests** — `.venv/bin/pytest -v` → still PASS.

---

### Task 6: Control page

**Files:**
- Create/replace: `frl/static/controle.html`, `frl/static/controle.css`, `frl/static/controle.js`

**Interfaces:**
- Consumes: all endpoints from Task 4.

Sections, all Portuguese labels (polling `/api/state` every 1000 ms; do not overwrite form fields the operator is editing):
1. **Arena** (top bar): phase selector (Fase 1–4 → `POST /api/phase`), "Na arena: {name}", countdown, buttons ▶ Iniciar / ⏸ Pausar / +1 min / ↺ Reiniciar / ⏭ Próxima equipe (→ `/api/timer/<action>`), "Próxima: {name}". "Reiniciar" and "Próxima equipe" ask `confirm()` first.
2. **Registrar tentativa**: team select (defaults to the team in the arena), phase = active phase, the phase's inputs (number inputs with min/max from Task 1, checkboxes; `open_hw` prefilled from team's `open_hw_default`). Live points via `POST /api/preview` on every change, shown as the formula text, e.g. `(100 − 5) × 2 × 2 = 380`, plus errors. "Salvar tentativa" → `POST /api/attempts`.
3. **Tentativas** of the selected team in the active phase: list T1–T3 with points, ★ on the best; "Editar" loads the inputs into the form and saves with `PUT`; "Apagar" with `confirm()` → `DELETE`.
4. **Ordem da fase {n}**: list of teams in this phase's order with ↑/↓ buttons and add/remove; "Salvar ordem" → `POST /api/orders/<n>`.
5. **Equipes**: add team (name, logo file, "open-hardware por padrão" checkbox); per team: rename, change logo, delete (`confirm()`).

- [ ] **Step 1: Implement the three files.**
- [ ] **Step 2: Manual check** — with the server running, from `/controle`: add 3 teams with one logo, set phase 1 order, start/pause/+1/next and watch `/tv` in a second window update within ~1 s; record an attempt (5 bases, 1 repeat, returned, open-hw) → preview shows 380 and TV ranking updates; edit and delete an attempt; let a slot run out (temporarily `curl -X POST .../api/timer/start` after setting `remaining_ms` low by editing `data/state.json` while stopped, then restarting) → TV advances to next team, stopped at 30:00.
- [ ] **Step 3: Run all tests** — `.venv/bin/pytest -v` → still PASS.

---

### Task 7: Raspberry Pi setup docs

**Files:**
- Create: `README.md`

Content (Portuguese or English — Portuguese preferred):
- Run locally: `python3 -m venv .venv && .venv/bin/pip install -r requirements.txt && .venv/bin/python -m frl`.
- On the Pi (Raspberry Pi OS Bookworm): copy folder, same venv commands; find IP with `hostname -I`; operator opens `http://<ip>:8000/controle`.
- systemd service `frl.service` (unit file contents included) so the server starts on boot.
- Kiosk: autostart Chromium with `chromium-browser --kiosk --noerrdialogs --disable-infobars http://localhost:8000/tv` (Wayfire/labwc autostart entry for Bookworm), and disabling screen blanking (`raspi-config` → Display → Screen Blanking off).
- Backup: copy the `data/` folder.

- [ ] **Step 1: Write `README.md`.**
- [ ] **Step 2: Verify the local run command from a clean venv** — `rm -rf .venv` then follow the README; Expected: server starts and `curl -s localhost:8000/api/state` returns JSON.
