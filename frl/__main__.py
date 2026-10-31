import os
from pathlib import Path

from .app import create_app

data_dir = Path(os.environ.get("FRL_DATA_DIR") or Path(__file__).resolve().parent.parent / "data")
create_app(data_dir).run(host="0.0.0.0", port=8000, threaded=True)
