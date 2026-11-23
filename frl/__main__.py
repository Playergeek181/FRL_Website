import os
import sys
from pathlib import Path

from .app import create_app

user = os.environ.get("FRL_USER")
password = os.environ.get("FRL_PASSWORD")
if not user or not password:
    sys.exit("Defina FRL_USER e FRL_PASSWORD antes de iniciar (usuário e senha do operador).\n"
             "Set FRL_USER and FRL_PASSWORD before starting (operator login).")

data_dir = Path(os.environ.get("FRL_DATA_DIR") or Path(__file__).resolve().parent.parent / "data")
create_app(data_dir, auth=(user, password)).run(host="0.0.0.0", port=8000, threaded=True)
