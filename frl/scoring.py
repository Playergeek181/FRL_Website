"""Pontuação das tentativas por fase (regras FRL 2026)."""

_BOOLS = {
    1: ["returned", "open_hw"],
    2: ["returned", "open_hw"],
    3: ["recognized", "returned", "open_hw"],
    4: ["maze", "landed", "open_hw"],
}
# campo -> máximo (None = sem limite superior)
_INTS = {
    1: {"bases": 6, "repeats": None},
    2: {"lifted": 3, "delivered": 3, "dropped": 3},
    3: {"bases": 6, "repeats": None, "cross_repeats": None},
    4: {"qr": 5},
}


def _is_int(v):
    return isinstance(v, int) and not isinstance(v, bool)


# Nomes dos campos como aparecem na página de controle (mensagens de erro legíveis).
LABELS = {
    "bases": "Bases visitadas", "repeats": "Pousos repetidos",
    "cross_repeats": "Pousos em base já usada pelo outro drone",
    "lifted": "Kits levantados", "delivered": "Kits entregues", "dropped": "Kits derrubados",
    "qr": "QR codes lidos", "returned": "Retornou e pousou na base de decolagem",
    "open_hw": "Drone open-hardware", "recognized": "Operador reconhecido",
    "maze": "Navegou pelo labirinto", "landed": "Pousou na base final",
}


def attempt_problems(phase: int, inputs: dict) -> list[tuple]:
    """Lista de (campo, mensagem); campo é None quando o erro não é de um campo só."""
    if phase not in _INTS:
        return [(None, "Fase inválida.")]
    out = []
    for key in _BOOLS[phase]:
        if key not in inputs:
            out.append((key, f"{LABELS[key]}: campo ausente."))
        elif not isinstance(inputs[key], bool):
            out.append((key, f"{LABELS[key]}: marque ou desmarque."))
    ints_ok = True
    for key, maximum in _INTS[phase].items():
        if key not in inputs:
            out.append((key, f"{LABELS[key]}: campo ausente."))
            ints_ok = False
            continue
        v = inputs[key]
        if not _is_int(v) or v < 0:
            out.append((key, f"{LABELS[key]}: use um número inteiro, de 0 para cima."))
            ints_ok = False
        elif maximum is not None and v > maximum:
            out.append((key, f"{LABELS[key]}: no máximo {maximum}."))
            ints_ok = False
    if phase == 2 and ints_ok:
        if inputs["delivered"] > inputs["lifted"]:
            out.append(("delivered", "Kits entregues não podem passar dos kits levantados."))
        elif inputs["dropped"] > inputs["lifted"] - inputs["delivered"]:
            out.append(("dropped", "Kits derrubados não podem passar dos levantados e não entregues."))
    return out


def validate_attempt(phase: int, inputs: dict) -> list[str]:
    return [m for _, m in attempt_problems(phase, inputs)]


def attempt_points(phase: int, inputs: dict) -> int:
    i = inputs
    if phase == 1:
        base = 20 * i["bases"] - 5 * i["repeats"]
        doubled = i["returned"]
    elif phase == 2:
        base = 40 * i["lifted"] + 20 * i["delivered"] - 5 * i["dropped"]
        doubled = i["returned"] and i["delivered"] >= 1
    elif phase == 3:
        if not i["recognized"]:
            return 0
        base = 20 * i["bases"] - 5 * i["repeats"] - 10 * i["cross_repeats"]
        doubled = i["returned"] and i["bases"] >= 1
    elif phase == 4:
        base = (50 if i["maze"] else 0) + 20 * i["qr"]
        doubled = i["maze"] and i["landed"] and i["qr"] >= 1
    else:
        raise ValueError(f"Fase inválida: {phase}")
    if doubled and base > 0:
        base *= 2
    if i["open_hw"]:
        base *= 2
    return max(0, base)
