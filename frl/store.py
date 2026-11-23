"""Estado da competição, persistido em data/state.json."""
import json
import os
import shutil
import sys
import re
import threading
import time
import unicodedata
from datetime import datetime
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
        self.bak_path = self.data_dir / "state.json.bak"
        self.backup_dir = self.data_dir / "backups"
        self.last_deleted = None
        self.last_deleted_attempt = None
        self.last_phase = None
        self.state = self._load()

    # -- persistência --------------------------------------------------
    @staticmethod
    def _empty_state() -> dict:
        return {
            "teams": [],
            "orders": {str(p): [] for p in range(0, 5)},
            "active_phase": 1,
            "slot": timer.new_slot(0),
            "attempts": [],
        }

    @staticmethod
    def _warn(msg: str) -> None:
        print(f"!!! FRL AVISO: {msg}", file=sys.stderr, flush=True)

    @staticmethod
    def _read(path: Path):
        """Estado lido de path, ou None se o arquivo estiver ilegível/inválido."""
        try:
            state = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            return None
        keys = ("teams", "orders", "active_phase", "slot", "attempts")
        if not isinstance(state, dict) or any(k not in state for k in keys):
            return None
        if isinstance(state["orders"], dict):
            state["orders"].setdefault("0", [])  # estados salvos antes do Aquecimento
        return state

    def _move_aside(self, path: Path) -> Path:
        stamp = time.strftime("%Y%m%d-%H%M%S")
        dest = path.with_name(f"{path.name}.corrupt-{stamp}")
        n = 1
        while dest.exists():
            dest = path.with_name(f"{path.name}.corrupt-{stamp}-{n}")
            n += 1
        os.replace(path, dest)
        self._warn(f"{path.name} corrompido; movido para {dest}")
        return dest

    def _load(self) -> dict:
        found_bad = False
        for path in (self.path, self.bak_path):
            if not path.exists():
                continue
            state = self._read(path)
            if state is not None:
                if path == self.bak_path:
                    self._warn(f"usando o backup {path} (state.json ausente ou corrompido)")
                return state
            self._move_aside(path)
            found_bad = True
        if found_bad:
            self._warn("nenhum estado utilizável encontrado; começando do zero "
                       "(arquivos corrompidos preservados em data/)")
        return self._empty_state()

    def _save(self) -> None:
        self.data_dir.mkdir(parents=True, exist_ok=True)
        tmp = self.data_dir / "state.json.tmp"
        with open(tmp, "w", encoding="utf-8") as f:
            f.write(json.dumps(self.state, ensure_ascii=False, indent=2))
            f.flush()
            os.fsync(f.fileno())
        if self.path.exists():  # guarda o último arquivo bom como state.json.bak
            bak_tmp = self.data_dir / "state.json.bak.tmp"
            with open(self.path, "rb") as src, open(bak_tmp, "wb") as dst:
                shutil.copyfileobj(src, dst)
                dst.flush()
                os.fsync(dst.fileno())
            os.replace(bak_tmp, self.bak_path)
        os.replace(tmp, self.path)
        try:  # garante que as renomeações sobrevivem a queda de energia
            fd = os.open(self.data_dir, os.O_RDONLY)
            try:
                os.fsync(fd)
            finally:
                os.close(fd)
        except OSError:
            pass

    @staticmethod
    def _slug(text: str) -> str:
        ascii_ = unicodedata.normalize("NFKD", text).encode("ascii", "ignore").decode()
        return re.sub(r"[^a-z0-9]+", "-", ascii_.lower()).strip("-") or "equipe"

    def _backup(self, action: str, team_id: str, phase=None) -> None:
        """Cópia completa do estado em data/backups/ após cada mudança de pontuação.

        O arquivo é um state.json válido: para restaurar, copie-o por cima de
        data/state.json com o servidor parado. Falha aqui nunca impede salvar a pontuação.
        """
        try:
            team = next((t["name"] for t in self.state["teams"] if t["id"] == team_id), "equipe")
            stamp = datetime.fromtimestamp(self.clock() / 1000).strftime("%Y-%m-%d_%H-%M-%S")
            where = f"_fase{phase}" if phase else ""
            base = f"{stamp}{where}_{self._slug(team)}_{action}"
            self.backup_dir.mkdir(parents=True, exist_ok=True)
            dest, n = self.backup_dir / f"{base}.json", 2
            while dest.exists():
                dest, n = self.backup_dir / f"{base}-{n}.json", n + 1
            tmp = dest.with_suffix(".tmp")
            with open(tmp, "w", encoding="utf-8") as f:
                f.write(json.dumps(self.state, ensure_ascii=False, indent=2))
                f.flush()
                os.fsync(f.fileno())
            os.replace(tmp, dest)
        except OSError as e:
            self._warn(f"não foi possível gravar o backup da pontuação: {e}")

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

    def _current_team_id(self):
        order = self.state["orders"][str(self.state["active_phase"])]
        idx = self.state["slot"]["index"]
        return order[idx] if 0 <= idx < len(order) else None

    def _follow_team(self, team_id) -> None:
        """Mantém a equipe que está na arena após mudar a ordem (cronômetro intacto)."""
        order = self.state["orders"][str(self.state["active_phase"])]
        if team_id is not None and team_id in order:
            self.state["slot"] = {**self.state["slot"], "index": order.index(team_id)}
        self._clamp_slot()

    def _clamp_slot(self) -> None:
        """Se o slot passou do fim da ordem, prende o índice e para o cronômetro."""
        n = len(self.state["orders"][str(self.state["active_phase"])])
        slot = self.state["slot"]
        if slot["index"] > n or (slot["index"] >= n and slot["running"]):
            self.state["slot"] = timer.new_slot(n)

    @staticmethod
    def _check_phase(phase: int, warmup: bool = False) -> None:
        """Fases 1-4 pontuam; o Aquecimento (0) só tem ordem e cronômetro."""
        if phase not in ((0, 1, 2, 3, 4) if warmup else (1, 2, 3, 4)):
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
            if any(a["team_id"] == team_id for a in self.state["attempts"]):
                self._backup("antes-de-excluir-equipe", team_id)   # guarda as pontuações que vão sumir
            current = self._current_team_id()
            # o suficiente para "Desfazer" (só em memória; após reiniciar, use data/backups/)
            self.last_deleted = {
                "team": dict(team),
                "team_index": self.state["teams"].index(team),
                "orders": {k: o.index(team_id) for k, o in self.state["orders"].items()
                           if team_id in o},
                "attempts": [(i, dict(a)) for i, a in enumerate(self.state["attempts"])
                             if a["team_id"] == team_id],
            }
            self.state["teams"].remove(team)
            for k, order in self.state["orders"].items():
                self.state["orders"][k] = [t for t in order if t != team_id]
            self.state["attempts"] = [a for a in self.state["attempts"]
                                      if a["team_id"] != team_id]
            self._follow_team(current)
            self._save()

    def restore_team(self, team_id) -> dict:
        """Desfaz a última exclusão de equipe: volta a equipe, suas posições nas ordens e
        suas tentativas, sem mudar quem está na arena."""
        with self._lock:
            snap = self.last_deleted
            if not snap or snap["team"]["id"] != team_id:
                raise ValueError(["Não há exclusão desta equipe para desfazer."])
            current = self._current_team_id()
            team = dict(snap["team"])
            self.state["teams"].insert(min(snap["team_index"], len(self.state["teams"])), team)
            for k, pos in snap["orders"].items():
                order = self.state["orders"][k]
                order.insert(min(pos, len(order)), team_id)
            for i, a in snap["attempts"]:
                self.state["attempts"].insert(min(i, len(self.state["attempts"])), a)
            self.last_deleted = None
            self._follow_team(current)
            self._save()
            return dict(team)

    # -- ordem / fase --------------------------------------------------
    def set_order(self, phase: int, team_ids: list) -> None:
        with self._lock:
            self._check_phase(phase, warmup=True)
            for tid in team_ids:
                self._team(tid)
            current = self._current_team_id()
            self.state["orders"][str(phase)] = list(team_ids)
            self._follow_team(current)
            self._save()

    def set_phase(self, phase: int) -> None:
        with self._lock:
            self._check_phase(phase, warmup=True)
            if phase != self.state["active_phase"]:
                # para "Desfazer" (só em memória): a fase anterior e o slot dela, pausado agora
                slot = timer.pause(timer.tick(self.state["slot"], self.clock()), self.clock())
                self.last_phase = (self.state["active_phase"], slot)
            self.state["active_phase"] = phase
            self.state["slot"] = timer.new_slot(0)
            self._save()

    def undo_phase(self) -> None:
        """Volta à fase ativa anterior, com a mesma equipe e o tempo que ela tinha (pausado)."""
        with self._lock:
            if not self.last_phase:
                raise ValueError(["Não há mudança de fase para desfazer."])
            phase, slot = self.last_phase
            self.state["active_phase"] = phase
            self.state["slot"] = dict(slot)
            self.last_phase = None
            self._clamp_slot()
            self._save()

    # -- cronômetro ----------------------------------------------------
    def timer_action(self, action: str, now_ms=None) -> None:
        with self._lock:
            now = self.clock() if now_ms is None else now_ms
            # aplica o 00:00 antes: pausar logo após o fim grava "Tempo esgotado", não um resto
            slot = timer.tick(self.state["slot"], now)
            if action == "start":
                slot = timer.start(slot, now)
            elif action == "pause":
                slot = timer.pause(slot, now)
            elif action == "add":
                slot = timer.add(slot, ADD_MS, now)
            elif action == "sub":
                slot = timer.sub(slot, ADD_MS, now)
            elif action == "reset":
                # guarda o tempo usado, pausado neste instante, para "Desfazer" (action "back")
                outgoing = {k: v for k, v in timer.pause(slot, now).items() if k != "prev"}
                slot = {**timer.reset(slot), "prev": outgoing}
            elif action == "next":
                # guarda a equipe que sai, pausada neste instante, para "Desfazer" (action "back")
                outgoing = {k: v for k, v in timer.pause(slot, now).items() if k != "prev"}
                slot = {**timer.advance(slot), "prev": outgoing}
            elif action == "back":
                prev = slot.get("prev")
                order = self.state["orders"][str(self.state["active_phase"])]
                if not prev or prev["index"] >= len(order):
                    raise ValueError(["Não há o que desfazer no cronômetro."])
                slot = dict(prev)   # volta pausado, com o tempo de antes de "Próxima" ou "Reiniciar"
            else:
                raise ValueError(["Ação inválida."])
            self.state["slot"] = slot
            self._clamp_slot()
            self._save()

    def current_and_next(self):
        with self._lock:
            slot = timer.tick(self.state["slot"], self.clock())
            before = self.state["slot"]
            self.state["slot"] = slot
            self._clamp_slot()
            if self.state["slot"] != before:
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
            self._backup("salva", attempt["team_id"], attempt["phase"])
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
            self._backup("editada", attempt["team_id"], attempt["phase"])
            return dict(attempt)

    def delete_attempt(self, attempt_id) -> None:
        with self._lock:
            attempt = self._attempt(attempt_id)
            # o suficiente para "Desfazer" (só em memória): volta no mesmo lugar, com o mesmo id e T
            self.last_deleted_attempt = (self.state["attempts"].index(attempt), dict(attempt))
            self.state["attempts"].remove(attempt)
            self._save()
            self._backup("excluida", attempt["team_id"], attempt["phase"])

    def restore_attempt(self, attempt_id) -> dict:
        """Desfaz a última exclusão de tentativa, na posição original (mesmo T1/T2/T3)."""
        with self._lock:
            snap = self.last_deleted_attempt
            if not snap or snap[1]["id"] != attempt_id:
                raise ValueError(["Não há exclusão desta tentativa para desfazer."])
            index, attempt = snap
            self._team(attempt["team_id"])
            count = sum(1 for a in self.state["attempts"]
                        if a["team_id"] == attempt["team_id"] and a["phase"] == attempt["phase"])
            if count >= MAX_ATTEMPTS:
                raise ValueError(["Limite de 3 tentativas por fase atingido: exclua uma antes de desfazer."])
            self.state["attempts"].insert(min(index, len(self.state["attempts"])), dict(attempt))
            self.last_deleted_attempt = None
            self._save()
            self._backup("restaurada", attempt["team_id"], attempt["phase"])
            return dict(attempt)

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
