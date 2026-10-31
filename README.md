# Placar FRL 2026

Placar para a Flying Robots League (RoboCup/CBR 2026). Servidor Flask com tela de TV (`/tv`) e tela do operador (`/controle`). Funciona offline.

## Rodar localmente

```bash
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt
.venv/bin/python -m frl
```

O servidor escuta em `0.0.0.0:8000`:

- TV: <http://localhost:8000/tv>
- Operador: <http://localhost:8000/controle>

Os dados ficam em `data/` (`state.json` e `logos/`). Para usar outra pasta, defina `FRL_DATA_DIR`.

## Raspberry Pi (Raspberry Pi OS Bookworm)

1. Copie a pasta do projeto para o Pi (ex.: `/home/pi/FRL_Website`) e rode os mesmos comandos de venv acima (`python3 -m venv .venv` e `pip install -r requirements.txt`).
2. Descubra o IP do Pi com `hostname -I`.
3. O operador abre, em outro dispositivo na mesma rede: `http://<ip>:8000/controle`.

### Iniciar o servidor no boot (systemd)

Crie `/etc/systemd/system/frl.service` (ajuste `User` e os caminhos para o seu usuario/pasta):

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

Ative:

```bash
sudo systemctl daemon-reload
sudo systemctl enable --now frl.service
systemctl status frl.service
journalctl -u frl.service -f   # logs
```

### Modo quiosque na TV (Chromium)

O navegador e `chromium-browser` (em imagens mais novas, `chromium`). Use o que existir no seu Pi.

**labwc** (padrao nas imagens mais novas): adicione ao `~/.config/labwc/autostart`:

```
chromium-browser --kiosk --noerrdialogs --disable-infobars http://localhost:8000/tv &
```

**Wayfire**: em `~/.config/wayfire.ini`, na secao `[autostart]`:

```ini
[autostart]
tv = chromium-browser --kiosk --noerrdialogs --disable-infobars http://localhost:8000/tv
```

Desative o apagamento de tela: `sudo raspi-config` -> Display Options -> Screen Blanking -> No (desativado), e reinicie.

## Backup e nova competicao

- **Backup:** copie a pasta `data/` (ex.: `cp -r data data-backup-$(date +%F)`).
- **Competicao nova do zero:**

```bash
sudo systemctl stop frl.service
mv data data-antigo-$(date +%F)
sudo systemctl start frl.service
```

## Desenvolvimento

```bash
.venv/bin/pip install pytest
.venv/bin/pytest
```
