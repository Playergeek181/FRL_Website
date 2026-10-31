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

1. Copie a pasta do projeto para o Pi (ex.: `/home/pi/FRL_Website`) e rode os mesmos comandos de venv acima (`python3 -m venv .venv` e `pip install -r requirements.txt`). **Faça isso antes de ir para o local da competição:** a instalação baixa pacotes e precisa de internet; depois disso o placar funciona totalmente offline.
2. Descubra o IP do Pi com `hostname -I`.
3. O operador abre, em outro dispositivo na mesma rede: `http://<ip>:8000/controle`.
4. **Acerte o relógio do Pi antes do evento.** O cronômetro usa o relógio do sistema; o Raspberry Pi não tem relógio próprio e, sem internet, pode iniciar com a hora errada e ser corrigido no meio de uma rodada. Confira com `date` (ajuste com `sudo date -s "2026-11-05 09:00:00"` se necessário). Recomenda-se um módulo RTC com bateria (o Pi 5 tem conector para bateria do RTC).

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
sh -c 'until curl -s localhost:8000/api/state >/dev/null; do sleep 1; done; chromium-browser --kiosk --noerrdialogs --disable-session-crashed-bubble --disable-infobars http://localhost:8000/tv' &
```

Atenção: se `~/.config/labwc/autostart` existir, ele substitui o `/etc/xdg/labwc/autostart` do sistema. Se faltar algo (painel, papel de parede), copie o arquivo do sistema para lá e acrescente a linha acima.

**Wayfire**: em `~/.config/wayfire.ini`, na seção `[autostart]`:

```ini
[autostart]
tv = sh -c 'until curl -s localhost:8000/api/state >/dev/null; do sleep 1; done; chromium-browser --kiosk --noerrdialogs --disable-session-crashed-bubble --disable-infobars http://localhost:8000/tv'
```

(Em ambos, troque `chromium-browser` por `chromium` se necessário. A opção `--disable-session-crashed-bubble` evita o balão "restaurar páginas" depois de uma queda de energia.)

### Desativar o apagamento de tela

Rode `sudo raspi-config` e vá em **Display Options → Screen Blanking → No** (desativar); reinicie o Pi.

Se a tela ainda apagar (Wayland):

- **labwc**: o apagamento vem de uma linha `swayidle` no autostart do sistema (`/etc/xdg/labwc/autostart`). Ao usar `~/.config/labwc/autostart` próprio, não copie essa linha (ou comente-a).
- **Wayfire**: em `~/.config/wayfire.ini` adicione `[idle]` com `screensaver_timeout = -1` e `dpms_timeout = -1`.

### Ensaio geral antes do evento

Faça um ensaio completo no Pi e na TV reais, do jeito que serão usados:

- Ligue tudo do zero (boot a frio) e confira que a TV abre o placar sozinha.
- Cadastre equipes, inicie o cronômetro e, no meio de um slot, **tire o Pi da tomada**. Ao religar, a TV deve voltar ao placar com o cronômetro correto **sem nenhum clique**.
- Confira que a tela não apaga depois de alguns minutos parada.

## Backup e nova competição

- **Backup:** copie a pasta `data/` (ex.: `cp -r data data-backup-$(date +%F)`).
- O servidor mantém sozinho uma cópia do último estado bom em `data/state.json.bak`. Se `state.json` estiver corrompido, ele usa o `.bak`, guarda o arquivo ruim como `state.json.corrupt-<data>` e registra um aviso no log (`journalctl -u frl.service`).
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
