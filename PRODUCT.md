# Product

<!-- impeccable:product-schema 1 -->

## Platform

web

## Users

- **The operator (one person).** A single operator/referee runs the event from the control page (`/controle`) on a laptop or phone on the venue network. During each 30-minute slot they start, pause, extend and reset the timer, advance to the next team, log up to three attempts per team per phase, correct earlier attempts, set and draw the flight order, and register teams and logos. They work under time pressure, standing next to the arena, and mistakes must be quick to see and undo.
- **The venue audience.** Spectators and the competing teams watch the TV (`/tv`) in the arena from a distance. They need to read, at a glance and without interaction: which phase is running, which team is flying, how much time is left, who flies next, and the overall standings.

## Product Purpose

The official live scoreboard for the Flying Robots League (FRL) at CBR 2026 (Competição Brasileira de Robótica / RoboCup Brasil). It turns the operator's attempt records into scores and rankings under the 2026 rules and shows the arena state on a TV in real time. Success: the event runs all four phases with correct scores, the TV never needs a click or refresh, and the audience always knows who is flying, the time left and the standings.

## Positioning

Built for this one competition's rules: scoring for the four FRL 2026 phases, three attempts per team per phase (best counts), and ranking points per phase (25, 18, 15, 12, 10, 8, 6, 4, 2, 1, then 0). It runs fully offline on a Raspberry Pi at the venue and survives power loss without any operator action on the TV.

## Operating Context

- Hardware: a Raspberry Pi (Raspberry Pi OS Bookworm) running the Flask server, with Chromium in kiosk mode driving a 16:9 TV in the arena. The operator connects from another device on the same local network.
- No internet at the venue: every asset (fonts, logos, scripts) must be served locally.
- The timer uses the Pi's system clock; the README requires setting the clock (or an RTC) before the event.
- The four phases: 1 Localização e Mapeamento, 2 Transporte de Pacotes, 3 Interação Humano-Enxame, 4 Navegação em Espaço Confinado. Each team gets a 30-minute slot per phase in an operator-defined flight order.
- Language: Brazilian Portuguese throughout the UI.
- Rehearsal ritual (README): cold boot, pull the power mid-slot, and confirm the TV recovers with the correct timer and no clicks.

## Capabilities and Constraints

- Team registry with optional logos (png, jpg, webp, svg) and a per-team open-hardware default.
- Per-phase flight order: manual reordering, plus a fair random draw that applies only once it is saved.
- Timer per slot: start, pause, +1 min, reset, next team. The countdown shows milliseconds.
- Attempt entry with live points preview and validation against the rules; edit and delete earlier attempts, including for a phase other than the active one.
- Ranking: only teams that scored get a position; unscored phases show a dash.
- State is persisted to `data/state.json` with an automatic `.bak` and recovery from corruption.
- Built for CBR 2026 and its rules only. Reuse for other events or editions is not a goal.
- Stack: Python/Flask server with plain HTML, CSS and JS in `frl/static/` (no build step, no framework).

## Brand Commitments

- Event name in use: "Flying Robots League 2026" (TV) and "Placar FRL 2026" (control page).
- **Official CBR / RoboCup / FRL logos and sponsor logos must appear on the TV.** Low-resolution versions from the CBR site are in `logos-oficiais/`; their placement is an open decision.
- Team identity comes from each team's own logo. The current logos in `logos-equipes/` are generated placeholders that teams' real logos may replace.

## Evidence on Hand

- Official rules: `Regras-Flying-Robots-League-CBR-2026-Portugues.pdf`.
- Registered team list from the organisers (`Equipes` image): Capybots, Bahia RT, TechAgroS, GralhaBots, Equipe DroneIFSC, RobôCin, TauraBots, AsiMAV, Black Bee Drones, eVTOL ITA, FBOT @Hydrone.
- Placeholder team logos: `logos-equipes/` (named) and `logos-equipes/icone/` (icon-only, used on the scoreboard).
- Official logos taken from https://cbr.robocup.org.br/ (low resolution; ask the organisers for the originals): `logos-oficiais/cbr-logo.png` (CBR wordmark, 300×106), `logos-oficiais/patrocinio-faixa.png` (Organização / Apoio / Patrocínio strip cropped from the site's footer banner `patrocinio-banner.png`, which is the "Período Eleitoral" version), `logos-oficiais/frl-icone-drone.png` (the site's FRL category icon, 77×77, not a logo).
- Absent, and must not be fabricated: an official FRL logo, a standalone RoboCup Brasil logo file, separate high-resolution sponsor files, real team logos, real scores and results.

## Product Principles

1. **Correct scores above everything.** What the TV shows must match the rules and the operator's records exactly; numbers that are shown twice must agree.
2. **The TV runs itself.** No clicks, refreshes or recovery steps on the TV, ever: offline, after power loss, after a server restart.
3. **Readable from the back of the arena.** The TV answers who is flying, the time left, who is next and the standings at a glance.
4. **Fast and forgiving for one operator.** Frequent actions are one click; destructive or live-affecting actions confirm or stay drafts until saved; mistakes can be edited.
5. **Honest states.** Unscored is a dash, not a zero; empty and finished phases say so plainly.

## Accessibility & Inclusion

- The TV must be legible at viewing distance in a bright venue: large type, high contrast, and no information carried by colour alone.
