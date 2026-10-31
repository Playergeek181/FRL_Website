from frl.constants import RANK_POINTS

PHASES = (1, 2, 3, 4)


def _points_for(position):
    return RANK_POINTS[position - 1] if position <= len(RANK_POINTS) else 0


def phase_ranking(best):
    """team_id -> {"position": int | None, "points": int}; competition ranking."""
    result = {t: {"position": None, "points": 0} for t in best}
    ranked = sorted(((s, t) for t, s in best.items() if s is not None and s > 0),
                    key=lambda x: -x[0])
    position = 0
    prev = None
    for i, (score, team) in enumerate(ranked, start=1):
        if score != prev:
            position = i
            prev = score
        result[team] = {"position": position, "points": _points_for(position)}
    return result


def overall_ranking(team_ids, best_by_phase):
    per_phase = {p: phase_ranking(best_by_phase.get(p, {})) for p in PHASES}
    rows = []
    for t in team_ids:
        phase_points = {}
        raws = []
        for p in PHASES:
            raw = best_by_phase.get(p, {}).get(t)
            raws.append(raw or 0)
            phase_points[p] = None if raw is None else per_phase[p][t]["points"]
        total = sum(v or 0 for v in phase_points.values())
        scored = sum(1 for v in phase_points.values() if v)
        key = (-total, -scored, *(-r for r in raws))
        rows.append((key, {"team_id": t, "position": 0, "phase_points": phase_points,
                           "total": total, "phases_scored": scored}))
    rows.sort(key=lambda x: x[0])  # stable: keeps input order on ties
    position = 0
    prev = None
    out = []
    for i, (key, row) in enumerate(rows, start=1):
        if key != prev:
            position = i
            prev = key
        row["position"] = position
        out.append(row)
    return out
