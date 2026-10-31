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


def validate_attempt(phase: int, inputs: dict) -> list[str]:
    if phase not in _INTS:
        return ["Fase inválida."]
    errors = []
    for key in _BOOLS[phase]:
        if key not in inputs:
            errors.append(f"Campo obrigatório ausente: {key}.")
        elif not isinstance(inputs[key], bool):
            errors.append(f"Campo '{key}' deve ser verdadeiro ou falso.")
    ints_ok = True
    for key, maximum in _INTS[phase].items():
        if key not in inputs:
            errors.append(f"Campo obrigatório ausente: {key}.")
            ints_ok = False
            continue
        v = inputs[key]
        if not _is_int(v) or v < 0:
            errors.append(f"Campo '{key}' deve ser um inteiro maior ou igual a 0.")
            ints_ok = False
        elif maximum is not None and v > maximum:
            errors.append(f"Campo '{key}' não pode ser maior que {maximum}.")
            ints_ok = False
    if phase == 2 and ints_ok:
        if inputs["delivered"] > inputs["lifted"]:
            errors.append("Pacotes entregues não podem exceder os levantados.")
        elif inputs["dropped"] > inputs["lifted"] - inputs["delivered"]:
            errors.append("Pacotes derrubados não podem exceder os levantados e não entregues.")
    return errors


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
