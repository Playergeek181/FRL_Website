"""Estado da competição, persistido em data/state.json."""
import json
import os
import threading
import time
from pathlib import Path
from typing import Callable
from uuid import uuid4

from . import timer
from .scoring import attempt_points, validate_attempt

MAX_ATTEMPTS = 3
ADD_MS = 60_000


def _wall_clock_ms() -> float:
    return time.time() * 1000


def _new_id() -> str:
    return uuid4().hex[:8]


class Store:
    def __init__(self, data_dir: Path, clock: Callable[[], float] = _wall_clock_ms):
        self.data_dir = Path(data_dir)
        self.clock = clock
        self._lock = threading.RLock()
        self.path = self.data_dir / "state.json"
        if self.path.exists():
            self.state = json.loads(self.path.read_text(encoding="utf-8"))
        else:
            self.state = {
                "teams": [],
                "orders": {str(p): [] for p in range(1, 5)},
                "active_phase": 1,
                "slot": timer.new_slot(0),
                "attempts": [],
            }

    # -- persistência --------------------------------------------------
    def _save(self) -> None:
        self.data_dir.mkdir(parents=True, exist_ok=True)
        tmp = self.data_dir / "state.json.tmp"
        tmp.write_text(json.dumps(self.state, ensure_ascii=False, indent=2), encoding="utf-8")
        os.replace(tmp, self.path)

    def _team(self, team_id: str) -> dict:
        for t in self.state["teams"]:
            if t["id"] == team_id:
                return t
        raise KeyError(team_id)

    def _attempt(self, attempt_id: str) -> dict:
        for a in self.state["attempts"]:
            if a["id"] == attempt_id:
                return a
        raise KeyError(attempt_id)

    @staticmethod
    def _check_phase(phase: int) -> None:
        if phase not in (1, 2, 3, 4):
            raise ValueError(["Fase inválida."])

    # -- equipes -------------------------------------------------------
    def add_team(self, name: str, open_hw_default: bool = False) -> dict:
        with self._lock:
            team = {"id": _new_id(), "name": name, "logo": None,
                    "open_hw_default": bool(open_hw_default)}
            self.state["teams"].append(team)
            self._save()
            return dict(team)

    def update_team(self, team_id, name=None, open_hw_default=None, logo=None) -> dict:
        with self._lock:
            team = self._team(team_id)
            if name is not None:
                team["name"] = name
            if open_hw_default is not None:
                team["open_hw_default"] = bool(open_hw_default)
            if logo is not None:
                team["logo"] = logo
            self._save()
            return dict(team)

    def delete_team(self, team_id) -> None:
        with self._lock:
            team = self._team(team_id)
            self.state["teams"].remove(team)
            for k, order in self.state["orders"].items():
                self.state["orders"][k] = [t for t in order if t != team_id]
            self.state["attempts"] = [a for a in self.state["attempts"]
                                      if a["team_id"] != team_id]
            self._save()

    # -- ordem / fase --------------------------------------------------
    def set_order(self, phase: int, team_ids: list) -> None:
        with self._lock:
            self._check_phase(phase)
            for tid in team_ids:
                self._team(tid)
            self.state["orders"][str(phase)] = list(team_ids)
            self._save()

    def set_phase(self, phase: int) -> None:
        with self._lock:
            self._check_phase(phase)
            self.state["active_phase"] = phase
            self.state["slot"] = timer.new_slot(0)
            self._save()

    # -- cronômetro ----------------------------------------------------
    def timer_action(self, action: str, now_ms=None) -> None:
        with self._lock:
            now = self.clock() if now_ms is None else now_ms
            slot = self.state["slot"]
            if action == "start":
                slot = timer.start(slot, now)
            elif action == "pause":
                slot = timer.pause(slot, now)
            elif action == "add":
                slot = timer.add(slot, ADD_MS, now)
            elif action == "reset":
                slot = timer.reset(slot)
            elif action == "next":
                slot = timer.advance(slot)
            else:
                raise ValueError(["Ação inválida."])
            self.state["slot"] = slot
            self._save()

    def current_and_next(self):
        with self._lock:
            slot = timer.tick(self.state["slot"], self.clock())
            if slot != self.state["slot"]:
                self.state["slot"] = slot
                self._save()
            order = self.state["orders"][str(self.state["active_phase"])]
            idx = slot["index"]
            cur = self._team(order[idx]) if 0 <= idx < len(order) else None
            nxt = self._team(order[idx + 1]) if 0 <= idx + 1 < len(order) else None
            return (dict(cur) if cur else None, dict(nxt) if nxt else None)

    # -- tentativas ----------------------------------------------------
    def add_attempt(self, team_id, phase: int, inputs: dict) -> dict:
        with self._lock:
            self._check_phase(phase)
            self._team(team_id)
            errors = validate_attempt(phase, inputs)
            if errors:
                raise ValueError(errors)
            count = sum(1 for a in self.state["attempts"]
                        if a["team_id"] == team_id and a["phase"] == phase)
            if count >= MAX_ATTEMPTS:
                raise ValueError(["Limite de 3 tentativas por fase atingido."])
            attempt = {"id": _new_id(), "team_id": team_id, "phase": phase,
                       "inputs": dict(inputs), "points": attempt_points(phase, inputs)}
            self.state["attempts"].append(attempt)
            self._save()
            return dict(attempt)

    def update_attempt(self, attempt_id, inputs: dict) -> dict:
        with self._lock:
            attempt = self._attempt(attempt_id)
            errors = validate_attempt(attempt["phase"], inputs)
            if errors:
                raise ValueError(errors)
            attempt["inputs"] = dict(inputs)
            attempt["points"] = attempt_points(attempt["phase"], inputs)
            self._save()
            return dict(attempt)

    def delete_attempt(self, attempt_id) -> None:
        with self._lock:
            self.state["attempts"].remove(self._attempt(attempt_id))
            self._save()

    def best_by_phase(self) -> dict:
        with self._lock:
            result = {}
            for phase in range(1, 5):
                best = {t["id"]: None for t in self.state["teams"]}
                for a in self.state["attempts"]:
                    if a["phase"] == phase and a["team_id"] in best:
                        cur = best[a["team_id"]]
                        best[a["team_id"]] = a["points"] if cur is None else max(cur, a["points"])
                result[phase] = best
            return result
