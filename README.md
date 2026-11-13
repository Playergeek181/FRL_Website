# Placar FRL 2026 · FRL 2026 Scoreboard

[Português](#português) · [English](#english)

Placar da Flying Robots League (RoboCup Brasil / CBR 2026): uma tela para a TV do público e uma página de controle para o operador. Funciona sem internet.

Scoreboard for the Flying Robots League (RoboCup Brasil / CBR 2026): a screen for the audience TV and a control page for the operator. Works without internet.

---

## Português

### O que é

Um pequeno servidor (Python + Flask) que serve duas páginas:

| Página | Endereço | Para quem |
|---|---|---|
| **TV** | `http://localhost:8000/tv` | Telão/TV do público. Só mostra; não tem botões. |
| **Controle** | `http://localhost:8000/controle` | O operador/árbitro: cronômetro, pontuação, ordem de voo e equipes. |

Tudo o que o operador faz aparece na TV em menos de um segundo. Os dados ficam salvos no computador (pasta `data/`), então nada se perde se o computador desligar.

### Rodar no seu computador (localhost)

**Você precisa de:** Python 3.10 ou mais novo ([python.org](https://www.python.org/downloads/); no Windows, marque "Add Python to PATH" ao instalar) e Git (ou baixe o projeto como ZIP pelo GitHub: botão **Code → Download ZIP**).

**1. Baixe o projeto**

```bash
git clone https://github.com/Playergeek181/FRL_Website.git
cd FRL_Website
```

**2. Instale (só na primeira vez, precisa de internet)**

Linux / macOS:

```bash
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt
```

Windows (PowerShell ou Prompt de Comando):

```bat
py -m venv .venv
.venv\Scripts\pip install -r requirements.txt
```

**3. Inicie o placar**

Linux / macOS:

```bash
.venv/bin/python -m frl
```

Windows:

```bat
.venv\Scripts\python -m frl
```

**4. Abra no navegador**

- TV: <http://localhost:8000/tv>
- Controle: <http://localhost:8000/controle>

Deixe a janela do terminal aberta enquanto usa o placar. Para parar, aperte `Ctrl+C` nela.

**Usar em outro aparelho da mesma rede (celular, notebook, TV):** descubra o IP do computador (`hostname -I` no Linux, `ipconfig getifaddr en0` no macOS, `ipconfig` no Windows) e abra `http://<ip>:8000/tv` ou `http://<ip>:8000/controle`. Se não abrir, libere a porta 8000 no firewall do computador.

**Opções:** os dados ficam em `data/` (`state.json`, `logos/` e `backups/`). Para usar outra pasta, defina a variável `FRL_DATA_DIR` antes de iniciar (ex.: `FRL_DATA_DIR=/caminho/da/pasta .venv/bin/python -m frl`).

### Como usar

#### Antes da competição: Preparação

Na página de controle, abra **Preparação** (no fim da página).

1. **Equipes:** digite o nome, escolha o logo (png, jpg, webp ou svg) e clique em **Adicionar equipe**. Depois dá para trocar o nome ou o logo. Os logos reais das equipes estão em `logos-equipes/`.
2. **Ordem de voo:** escolha a fase, clique em **Editar ordem**, adicione as equipes (ou use **Sortear ordem**), ajuste com as setas e clique em **Salvar ordem**. Cada fase tem a sua ordem. Durante a fase, a lista mostra quem já voou, quem está na arena e quem vem a seguir.

#### Durante a competição

1. **Fase ativa:** aparece no topo, ao lado da equipe na arena; para mudar, use **Mudar em Preparação** (a fase muda raramente e mexe na TV, por isso fica longe do cronômetro). A confirmação diz qual equipe entra na arena, e **Desfazer** volta à fase anterior com a equipe e o tempo que ela tinha.
2. **Na arena:** a primeira equipe da ordem de voo entra automaticamente. Ao lado aparece quem vem a seguir.
3. **Cronômetro (30:00 por equipe):**
   - **Iniciar** / **Pausar** (depois de pausar, vira **Retomar**).
   - **+1 min** dá um minuto extra; **−1 min** tira um (corrige um minuto a mais).
   - **Reiniciar** volta a 30:00. **Desfazer**, no aviso, devolve o tempo que a equipe tinha, pausado.
   - **Próxima equipe** chama a próxima da ordem (pede confirmação). Errou? **Desfazer**, no aviso que aparece por alguns segundos, volta a equipe anterior com o tempo que ela tinha, com o cronômetro pausado.
   - Ao chegar a 00:00, o cronômetro **para** e a TV mostra "Tempo esgotado"; a equipe continua na arena até você apertar **Próxima equipe**. Pausado, a TV mostra os números apagados e "Pausado" em destaque. Se a TV ficar mais de 5 s sem falar com o servidor, o cronômetro dela para e aparece "Reconectando…" (volta sozinho).
4. **Registrar tentativa:** escolha a fase e a equipe, preencha os campos (botões − e + ajudam no celular) e clique em **Salvar tentativa**. A fórmula e os pontos aparecem antes de salvar; um campo inválido fica vermelho e explica o problema.
5. **Tentativas:** a lista ao lado mostra as tentativas salvas; dá para editar ou excluir.
6. **Classificação:** embaixo das tentativas, a mesma tabela da TV, para conferir os números.

**Atalhos de teclado** (fora de campos de texto): `Espaço` inicia/pausa, `+` / `−` somam ou tiram 1 minuto, `N` chama a próxima equipe, `Ctrl+Enter` salva a tentativa. Funcionam também logo depois de clicar num botão do cronômetro.

**Excluir equipe** mostra quantas tentativas e pontos serão perdidos e oferece **Desfazer** por alguns segundos (só até o servidor ser reiniciado; depois, use um backup). **Excluir tentativa** também oferece **Desfazer**, que a devolve no mesmo lugar (continua sendo T1, T2 ou T3).

#### Classificação

Para cada fase vale a melhor tentativa da equipe. As equipes são ordenadas por fase e recebem pontos de ranking pela posição; a TV mostra esses pontos por fase (F1 a F4) e o total. Em caso de empate no total, vale o desempate do regulamento: mais fases pontuadas, depois mais pontos na Fase 1, 2, 3 e 4.

### Backup e nova competição

- **Backup manual:** copie a pasta `data/` (ex.: `cp -r data data-backup-$(date +%F)`).
- O servidor mantém uma cópia do último estado bom em `data/state.json.bak`. Se `state.json` estiver corrompido, ele usa o `.bak`, guarda o arquivo ruim como `state.json.corrupt-<data>` e registra um aviso no log.
- **Backup automático da pontuação:** toda vez que uma tentativa é salva, editada ou excluída, o servidor grava uma cópia completa em `data/backups/`, com data, fase, equipe e ação no nome (ex.: `2026-11-05_14-32-10_fase1_capybots_salva.json`). Antes de excluir uma equipe que tem pontos, também guarda `..._antes-de-excluir-equipe.json`. Esses arquivos nunca são apagados nem sobrescritos.
- **Restaurar um backup:** pare o servidor, copie o arquivo escolhido por cima de `data/state.json` e inicie de novo:

```bash
cp data/state.json data/state.json.antes-de-restaurar
cp data/backups/<arquivo-escolhido>.json data/state.json
```

- **Competição nova do zero:** com o servidor parado, renomeie a pasta (`mv data data-antigo-$(date +%F)`) e inicie de novo.

### Raspberry Pi no evento (Raspberry Pi OS Bookworm)

1. Copie o projeto para o Pi (ex.: `/home/pi/FRL_Website`) e rode os comandos de instalação do Linux acima. **Faça isso antes de ir para o local:** a instalação precisa de internet; depois o placar funciona totalmente offline.
2. Descubra o IP do Pi com `hostname -I`. O operador abre `http://<ip>:8000/controle` em outro aparelho na mesma rede.
3. **Acerte o relógio do Pi antes do evento.** O cronômetro usa o relógio do sistema, e o Pi sem internet pode iniciar com a hora errada. Confira com `date` (ajuste com `sudo date -s "2026-11-05 09:00:00"`). Recomenda-se um módulo RTC com bateria.

**Iniciar no boot (systemd):** crie `/etc/systemd/system/frl.service` (ajuste `User` e os caminhos):

```ini
[Unit]
Description=Placar FRL 2026
After=network.target

[Service]
User=pi
WorkingDirectory=/home/pi/FRL_Website
ExecStart=/home/pi/FRL_Website/.venv/bin/python -m frl
Restart=always
RestartSec=2

[Install]
WantedBy=multi-user.target
```

```bash
sudo systemctl daemon-reload
sudo systemctl enable --now frl.service
systemctl status frl.service
journalctl -u frl.service -f   # logs
```

Com o serviço, pare e inicie o placar com `sudo systemctl stop frl.service` e `sudo systemctl start frl.service` (por exemplo, para restaurar um backup).

**TV em modo quiosque (Chromium):** o autostart espera o servidor responder antes de abrir o navegador. Troque `chromium-browser` por `chromium` se o primeiro não existir (`which chromium-browser chromium`).

- **labwc** (imagens mais novas): em `~/.config/labwc/autostart` adicione a linha abaixo. Se esse arquivo existir, ele substitui o `/etc/xdg/labwc/autostart` do sistema; se faltar algo (painel, papel de parede), copie o do sistema e acrescente a linha.

```
sh -c 'until curl -s localhost:8000/api/state >/dev/null; do sleep 1; done; chromium-browser --kiosk --noerrdialogs --disable-session-crashed-bubble --disable-infobars http://localhost:8000/tv' &
```

- **Wayfire**: em `~/.config/wayfire.ini`:

```ini
[autostart]
tv = sh -c 'until curl -s localhost:8000/api/state >/dev/null; do sleep 1; done; chromium-browser --kiosk --noerrdialogs --disable-session-crashed-bubble --disable-infobars http://localhost:8000/tv'
```

**Tela que não apaga:** `sudo raspi-config` → **Display Options → Screen Blanking → No**, e reinicie. Se ainda apagar: no labwc, não copie a linha `swayidle` para o seu autostart; no Wayfire, adicione `[idle]` com `screensaver_timeout = -1` e `dpms_timeout = -1`.

**Ensaio geral:** ligue tudo do zero e confira que a TV abre o placar sozinha; no meio de um voo, **tire o Pi da tomada** e confira que, ao religar, a TV volta com o cronômetro correto sem nenhum clique; confira que a tela não apaga depois de alguns minutos parada.

### Desenvolvimento

```bash
.venv/bin/pip install pytest
.venv/bin/pytest
```

Código em `frl/` (servidor) e `frl/static/` (páginas). Logos oficiais e de patrocinadores em `logos-oficiais/`; logos das equipes em `logos-equipes/`.

---

## English

### What it is

A small server (Python + Flask) that serves two pages:

| Page | Address | Who it's for |
|---|---|---|
| **TV** | `http://localhost:8000/tv` | The audience screen. Display only, no buttons. |
| **Control** | `http://localhost:8000/controle` | The operator/referee: timer, scoring, flight order and teams. |

Everything the operator does shows up on the TV in under a second. Data is saved on the computer (the `data/` folder), so nothing is lost if the computer turns off. The interface is in Portuguese; the button names below are given as they appear on screen.

### Run it on your computer (localhost)

**You need:** Python 3.10 or newer ([python.org](https://www.python.org/downloads/); on Windows, tick "Add Python to PATH" when installing) and Git (or download the project as a ZIP from GitHub: **Code → Download ZIP**).

**1. Get the project**

```bash
git clone https://github.com/Playergeek181/FRL_Website.git
cd FRL_Website
```

**2. Install (first time only, needs internet)**

Linux / macOS:

```bash
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt
```

Windows (PowerShell or Command Prompt):

```bat
py -m venv .venv
.venv\Scripts\pip install -r requirements.txt
```

**3. Start the scoreboard**

Linux / macOS:

```bash
.venv/bin/python -m frl
```

Windows:

```bat
.venv\Scripts\python -m frl
```

**4. Open it in a browser**

- TV: <http://localhost:8000/tv>
- Control: <http://localhost:8000/controle>

Keep the terminal window open while you use the scoreboard. To stop it, press `Ctrl+C` in that window.

**Using it from another device on the same network (phone, laptop, TV):** find the computer's IP address (`hostname -I` on Linux, `ipconfig getifaddr en0` on macOS, `ipconfig` on Windows) and open `http://<ip>:8000/tv` or `http://<ip>:8000/controle`. If it doesn't load, allow port 8000 through the computer's firewall.

**Options:** data lives in `data/` (`state.json`, `logos/` and `backups/`). To use another folder, set `FRL_DATA_DIR` before starting (e.g. `FRL_DATA_DIR=/path/to/folder .venv/bin/python -m frl`).

### How to use it

#### Before the competition: Preparação (setup)

On the control page, open **Preparação** at the bottom of the page.

1. **Equipes (teams):** type the name, pick the logo (png, jpg, webp or svg) and click **Adicionar equipe**. You can change the name or logo later. The teams' real logos are in `logos-equipes/`.
2. **Ordem de voo (flight order):** pick the phase, click **Editar ordem**, add the teams (or use **Sortear ordem** to shuffle), adjust with the arrows and click **Salvar ordem**. Each phase has its own order. During the phase, the list marks who has flown, who is in the arena and who is next.

#### During the competition

1. **Fase ativa (active phase):** shown at the top beside the team in the arena; to change it, use **Mudar em Preparação** (it changes rarely and affects the TV, so it sits away from the timer). The confirmation says which team goes into the arena, and **Desfazer** (undo) goes back to the previous phase with its team and time.
2. **Na arena (in the arena):** the first team in the flight order goes in automatically. Who's next is shown beside it.
3. **Timer (30:00 per team):**
   - **Iniciar** / **Pausar** start and pause (after a pause it reads **Retomar**, resume).
   - **+1 min** adds a minute; **−1 min** takes one off (fixes an extra minute).
   - **Reiniciar** resets to 30:00. **Desfazer** (undo), in the notice, gives back the time the team had, paused.
   - **Próxima equipe** calls the next team in the order (asks to confirm). Pressed it by mistake? **Desfazer** (undo), in the notice shown for a few seconds, brings back the previous team with the time it had, timer paused.
   - At 00:00 the timer **stops** and the TV shows "Tempo esgotado" (time's up); the team stays in the arena until you press **Próxima equipe**. When paused, the TV dims the digits and shows "Pausado" large. If the TV can't reach the server for more than 5 s, its clock stops and "Reconectando…" appears (it recovers by itself).
4. **Registrar tentativa (record an attempt):** pick the phase and team, fill in the fields (the − and + buttons help on a phone) and click **Salvar tentativa**. The formula and points show before you save; an invalid field turns red and says what's wrong.
5. **Tentativas (attempts):** the list beside it shows saved attempts; you can edit or delete them.
6. **Classificação (standings):** below the attempts, the same table as the TV, to check the numbers.

**Keyboard shortcuts** (outside text fields): `Space` start/pause, `+` / `−` add or remove 1 minute, `N` next team, `Ctrl+Enter` save the attempt. They also work right after clicking a timer button.

**Deleting a team** shows how many attempts and points will be lost and offers **Desfazer** (undo) for a few seconds (only until the server restarts; after that, use a backup). **Deleting an attempt** also offers **Desfazer**, which puts it back in the same place (it stays T1, T2 or T3).

#### Standings

In each phase, a team's best attempt counts. Teams are ranked per phase and get ranking points by position; the TV shows those points per phase (F1 to F4) and the total. Ties on the total are broken by the rulebook: more phases scored, then more points in Phase 1, 2, 3 and 4.

### Backups and starting a new competition

- **Manual backup:** copy the `data/` folder (e.g. `cp -r data data-backup-$(date +%F)`).
- The server keeps a copy of the last good state in `data/state.json.bak`. If `state.json` is corrupted, it uses the `.bak`, keeps the bad file as `state.json.corrupt-<date>` and logs a warning.
- **Automatic score backups:** every time an attempt is saved, edited or deleted, the server writes a full copy to `data/backups/`, named with the date, phase, team and action (e.g. `2026-11-05_14-32-10_fase1_capybots_salva.json`). Before deleting a team that has points, it also writes `..._antes-de-excluir-equipe.json`. These files are never deleted or overwritten.
- **Restore a backup:** stop the server, copy the chosen file over `data/state.json` and start it again:

```bash
cp data/state.json data/state.json.antes-de-restaurar
cp data/backups/<chosen-file>.json data/state.json
```

- **Fresh competition:** with the server stopped, rename the folder (`mv data data-old-$(date +%F)`) and start again.

### Raspberry Pi at the event (Raspberry Pi OS Bookworm)

1. Copy the project to the Pi (e.g. `/home/pi/FRL_Website`) and run the Linux install commands above. **Do this before going to the venue:** installing needs internet; after that the scoreboard runs fully offline.
2. Find the Pi's IP with `hostname -I`. The operator opens `http://<ip>:8000/controle` on another device on the same network.
3. **Set the Pi's clock before the event.** The timer uses the system clock, and a Pi without internet may boot with the wrong time. Check with `date` (set it with `sudo date -s "2026-11-05 09:00:00"`). A battery-backed RTC module is recommended.

**Start on boot (systemd):** create `/etc/systemd/system/frl.service` with the same unit file shown in the Portuguese section above (adjust `User` and paths), then:

```bash
sudo systemctl daemon-reload
sudo systemctl enable --now frl.service
systemctl status frl.service
journalctl -u frl.service -f   # logs
```

With the service, stop and start the scoreboard with `sudo systemctl stop frl.service` and `sudo systemctl start frl.service` (for example, to restore a backup).

**TV kiosk mode (Chromium):** use the same autostart line shown in the Portuguese section (labwc: `~/.config/labwc/autostart`; Wayfire: `[autostart]` in `~/.config/wayfire.ini`). It waits for the server to answer before opening the browser. Replace `chromium-browser` with `chromium` if the first doesn't exist. On labwc, a personal autostart file replaces the system one (`/etc/xdg/labwc/autostart`); copy the system file first if the panel or wallpaper goes missing.

**Keep the screen on:** `sudo raspi-config` → **Display Options → Screen Blanking → No**, then reboot. If it still blanks: on labwc, don't copy the `swayidle` line into your autostart; on Wayfire, add `[idle]` with `screensaver_timeout = -1` and `dpms_timeout = -1`.

**Dress rehearsal:** power everything up from cold and check the TV opens the scoreboard by itself; mid-flight, **pull the Pi's plug** and check that, once it's back, the TV shows the correct timer without any clicks; check the screen doesn't blank after a few idle minutes.

### Development

```bash
.venv/bin/pip install pytest
.venv/bin/pytest
```

Server code in `frl/`, pages in `frl/static/`. Official and sponsor logos in `logos-oficiais/`; team logos in `logos-equipes/`.
