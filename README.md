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

Crie `/etc/systemd/system/frl.service` (ajuste `User` e os caminhos para o seu usuário/pasta):

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

Ative o serviço:

```bash
sudo systemctl daemon-reload
sudo systemctl enable --now frl.service
systemctl status frl.service
journalctl -u frl.service -f   # logs
```

### Modo quiosque na TV (Chromium)

O navegador é `chromium-browser`; em imagens mais novas o binário se chama `chromium`. **Troque por `chromium` se `chromium-browser` não existir** (teste com `which chromium-browser chromium`).

Para a TV nunca precisar de clique ou F5, o autostart espera o servidor responder antes de abrir o Chromium (senão, se o navegador subir primeiro, aparece uma página de erro).

**labwc** (padrão nas imagens mais novas): crie/edite `~/.config/labwc/autostart` e adicione:

```
sh -c 'until curl -s localhost:8000/api/state >/dev/null; do sleep 1; done; chromium-browser --kiosk --noerrdialogs --disable-infobars http://localhost:8000/tv' &
```

Atenção: se `~/.config/labwc/autostart` existir, ele substitui o `/etc/xdg/labwc/autostart` do sistema. Se faltar algo (painel, papel de parede), copie o arquivo do sistema para lá e acrescente a linha acima.

**Wayfire**: em `~/.config/wayfire.ini`, na seção `[autostart]`:

```ini
[autostart]
tv = sh -c 'until curl -s localhost:8000/api/state >/dev/null; do sleep 1; done; chromium-browser --kiosk --noerrdialogs --disable-infobars http://localhost:8000/tv'
```

(Em ambos, troque `chromium-browser` por `chromium` se necessário.)

### Desativar o apagamento de tela

Rode `sudo raspi-config` e vá em **Display Options → Screen Blanking → No** (desativar); reinicie o Pi.

Se a tela ainda apagar (Wayland):

- **labwc**: o apagamento vem de uma linha `swayidle` no autostart do sistema (`/etc/xdg/labwc/autostart`). Ao usar `~/.config/labwc/autostart` próprio, não copie essa linha (ou comente-a).
- **Wayfire**: em `~/.config/wayfire.ini` adicione `[idle]` com `screensaver_timeout = -1` e `dpms_timeout = -1`.

## Backup e nova competição

- **Backup:** copie a pasta `data/` (ex.: `cp -r data data-backup-$(date +%F)`).
- **Competição nova do zero:**

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
