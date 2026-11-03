"""Cronômetro de slot (funções puras; retornam novos dicts)."""
from .constants import SLOT_MS


def new_slot(index: int = 0) -> dict:
    return {"index": index, "running": False, "remaining_ms": SLOT_MS, "started_at": None}


def remaining(slot: dict, now_ms: float) -> int:
    if not slot["running"]:
        return max(0, int(slot["remaining_ms"]))
    # relógio que volta (ajuste NTP/RTC) não pode dar mais tempo que o restante salvo
    elapsed = max(0, now_ms - slot["started_at"])
    return max(0, min(int(slot["remaining_ms"]), int(slot["remaining_ms"] - elapsed)))


def expired(slot: dict) -> bool:
    """Tempo esgotado: parado em 00:00 até o operador chamar a próxima equipe."""
    return not slot["running"] and int(slot["remaining_ms"]) <= 0


def start(slot: dict, now_ms: float) -> dict:
    if slot["running"] or expired(slot):   # em 00:00 só +1 min, Reiniciar ou Próxima
        return dict(slot)
    return {**slot, "running": True, "started_at": now_ms}


def pause(slot: dict, now_ms: float) -> dict:
    return {**slot, "running": False, "remaining_ms": remaining(slot, now_ms), "started_at": None}


def add(slot: dict, ms: int, now_ms: float) -> dict:
    rem = remaining(slot, now_ms) + ms
    if slot["running"]:
        return {**slot, "remaining_ms": rem, "started_at": now_ms}
    return {**slot, "remaining_ms": rem}


def reset(slot: dict) -> dict:
    return new_slot(slot["index"])


def advance(slot: dict) -> dict:
    return new_slot(slot["index"] + 1)


def tick(slot: dict, now_ms: float) -> dict:
    """Ao chegar a 00:00 o cronômetro para e a equipe continua na arena (Tempo esgotado)."""
    if slot["running"] and remaining(slot, now_ms) == 0:
        return {**slot, "running": False, "remaining_ms": 0, "started_at": None}
    return slot
