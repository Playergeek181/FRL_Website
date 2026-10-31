# FRL 2026 Scoreboard — Design

## Intent

A local website for the RoboCup Brasil Flying Robots League (FRL) 2026 competition. A
Raspberry Pi 5 connected to a TV everyone in the venue can see shows:

- the team currently in the arena, with a 30-minute countdown for its slot,
- the next team,
- the live overall ranking (ranking points per phase + total).

One person (the organizer, "the operator") controls everything from their own computer
on the same local network: team setup, per-phase draw order, the timer, and entering
what happened in each attempt. The site computes the points from the official rules
(`Regras-Flying-Robots-League-CBR-2026-Portugues.pdf` in the project root).

Why: so the audience and teams can see who is up, how much time is left, and where
everyone stands without the operator doing arithmetic by hand during the event.

The operator and Claude will polish the look together after a first working version.

## Goals

- TV display page: full-screen, readable from across a room, no interaction needed, updates
  automatically when the operator changes anything.
- Operator control page: set up teams, set the order per phase, control the timer, record
  attempts by filling in what happened, see points computed live, edit/delete attempts.
- Scoring and ranking that match the rules PDF exactly.
- Survives a Pi reboot or server restart without losing data.
- Works fully offline (no internet at the venue assumed; no CDN assets).

## Non-goals

- Per-attempt timer (10 min / 15 min). Only the 30-minute slot timer is shown.
- Multiple operators / user accounts.
- Public internet access, hosting, or remote viewing.
- Warm-up / inspection scheduling, TDP management.
- Fixed clock-time schedule — the operator starts each slot manually.

## Anti-goals (would be a failure even if it "works")

- Wrong points or wrong ranking order vs. the rules.
- TV text too small or cluttered to read from a distance.
- Losing entered scores on a restart.
- The TV page needing someone to click or refresh it during the event.

## Constraints

- Runs on a Raspberry Pi 5 (Raspberry Pi OS); TV shows the display page in a browser on the Pi.
- Operator reaches the control page from another computer on the same network via the Pi's IP.
- User-facing text in **Portuguese** (TV and control page).
- 11 teams in 2026 (the app should not hard-code 11 teams, but the ranking table always has 11 positions, per the rules).
- Language/stack: **Python** server (Claude's call). No build step required for the frontend;
  plain HTML/CSS/JS served by the Python app. Persistence in a local file (SQLite or JSON — builder's choice).

## Decisions made with the operator

### TV display (layout "A", approved from mockup)

16:9 split screen, dark background:

- **Left column**
  - Current phase label, e.g. "FASE 2 · TRANSPORTE DE PACOTES".
  - "NA ARENA" card: large team logo, team name, very large `MM:SS` countdown from 30:00.
  - "PRÓXIMA" card: smaller logo + name of the next team in this phase's order.
- **Right column (wider)**: ranking table — position, small logo, team name, ranking points
  earned in P1, P2, P3, P4 (dash if not yet scored/played), **Total**. All teams visible
  without scrolling.
- Updates on its own when the operator changes anything (timer, scores, order, current team).

### Team logos

- Operator uploads a logo per team when setting up teams.
- Teams without a logo show a colored circle with the team's initials.

### Timer

- 30-minute countdown per team slot. The operator starts it manually.
- Operator can pause, resume, add time (+1 min), and reset.
- When it reaches 0:00, the display automatically advances: the next team in the order
  becomes "NA ARENA" with a fresh 30:00, **not started**, waiting for the operator to press start.
  The following team becomes "PRÓXIMA".
- Operator can also manually advance to the next team at any time ("Próxima equipe").

### Order per phase

- The draw order is different for each phase. The operator enters/edits the team order
  for each phase. The operator picks which phase is currently active; the TV shows that
  phase's current/next team.

### Recording attempts (control page)

The operator fills in what happened; points are computed and shown live before saving.
Up to 3 attempts per team per phase; the **best** attempt is the team's phase score.
Attempts can be edited or deleted.

Inputs and formulas per phase (from the rules PDF):

**Phase 1 — Localização e Mapeamento (max 480)**
- Bases visited for the first time (0–6): +20 each
- Repeated landings: −5 each
- Returned autonomously and landed on the takeoff base: ×2 (only if score positive)
- Open-hardware drone: ×2

**Phase 2 — Transporte de Pacotes (max 720)**
- Kits identified, grabbed and lifted (0–3): +40 each
- Kits delivered to a correct base (0–3, ≤ lifted): +20 each
- Kits dropped outside the correct base: −5 each
- Returned autonomously and landed on takeoff base, **with ≥1 kit delivered**: ×2 (only if positive)
- Open-hardware: ×2

**Phase 3 — Interação Humano-Enxame (max 480)**
- Operator (human) recognized and shown in terminal: required — if not, attempt scores 0
- Bases visited for the first time (0–6): +20 each
- Repeated landings on a base by the same drone: −5 each
- (Two-drone runs) landing on a base the other drone already used: −10 each
- Returned autonomously after ≥1 base (with two drones, **both** must land on the takeoff base): ×2 (only if positive)
- Open-hardware: ×2

**Phase 4 — Navegação em Espaço Confinado (max 600)**
- Navigated the maze (entered at red arrow, exited at blue arrow): +50
- Distinct QR codes read (0–5): +20 each
- Landed autonomously on the final base after exiting, **with ≥1 QR read**: ×2
- Open-hardware: ×2

Order of operations: base points/penalties → autonomous-return ×2 (if conditions met and
score positive) → open-hardware ×2. Example: P1, 5 bases, 1 repeat, returned, open-hardware
→ (100 − 5) × 2 × 2 = 380. Maxima check: P1 6×20×2×2 = 480, P2 3×60×2×2 = 720,
P3 6×20×2×2 = 480, P4 (50+100)×2×2 = 600.

### Ranking (from the rules PDF, "O VENCEDOR")

- Per phase, teams are ordered by their best-attempt score; position → ranking points:
  1º 25, 2º 18, 3º 15, 4º 12, 5º 10, 6º 8, 7º 6, 8º 4, 9º 2, 10º 1, 11º/absent 0.
- A team that did not participate or scored 0 in a phase gets 0 ranking points there.
- Ties within a phase share the same position, using **standard competition ranking
  (1, 1, 3)** — confirmed by the operator: tied teams both get the shared position's
  points, the next team skips positions.
- Total = sum of ranking points across the 4 phases.
- Overall tiebreakers, in order:
  1. Scored in more different phases;
  2. Higher Phase 1 score; 3. Phase 2; 4. Phase 3; 5. Phase 4;
  6. Still tied → same overall position.
- Only teams that scored in at least one phase may occupy 1st–3rd (naturally true if
  zero-total teams sort below; teams with zero in all phases can be shown at the bottom).
- **"Scored in a phase" means earned ranking points > 0 in that phase** (placed 10th or
  better with a positive score) — confirmed by the operator. Used for tiebreaker 1 and for
  top-3 eligibility. A team with a positive phase score that places 11th does not count.

## Claude's calls (not explicitly confirmed by the operator)

- Python server, plain HTML/JS frontend, local-file persistence.
- Open-hardware is a checkbox **per attempt** (team may use different drones per phase).
  Builder may prefill it from a per-team default.
- Negative attempt scores are stored as 0.
- When the last team in a phase's order runs out of time (or is advanced past), the left
  column shows "Fase encerrada" with no current/next team until the operator picks a phase.
- On the TV, a dash (–) means the team has no recorded attempt in that phase; a team that
  flew but placed without ranking points shows 0.
- Input validation: counts are bounded by the rules (bases 0–6, kits 0–3, delivered ≤ lifted,
  QR 0–5); dropped kits ≤ lifted − delivered; at most 3 attempts per team per phase.
- **No password on the control page** — confirmed by the operator: the network is private.
- Timer state is kept on the server as (started-at, remaining) so the TV and control page
  agree and a page reload doesn't reset it; clients render the countdown locally.

## Left to the builder

- Web framework, persistence format, and live-update mechanism (polling vs SSE/WebSocket),
  as long as the TV updates within ~1–2 s and works offline.
- Exact visual styling (to be polished with the operator later), within the approved layout.
- Logo storage location and accepted image formats.
- Setup instructions for running on the Pi and opening the TV page full-screen (kiosk mode).
