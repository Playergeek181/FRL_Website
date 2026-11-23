"""Usuários do placar, persistidos em data/users.json (senhas com hash)."""
import json
import os
import re
import threading
import time
from pathlib import Path

from werkzeug.security import check_password_hash, generate_password_hash

ROLES = ("admin", "operator")
NAME_RE = re.compile(r"^[A-Za-z0-9_.-]{3,32}$")
MIN_PASSWORD = 8
MAX_PASSWORD = 128
# Hash falso para gastar o mesmo tempo quando o usuário não existe.
_DUMMY_HASH = generate_password_hash("dummy-password")


class UserStore:
    def __init__(self, data_dir: Path):
        self.path = Path(data_dir) / "users.json"
        self._lock = threading.RLock()
        self._users = {}
        if self.path.exists():
            self._users = json.loads(self.path.read_text("utf-8"))

    def _save(self):
        self.path.parent.mkdir(parents=True, exist_ok=True)
        tmp = self.path.with_suffix(".tmp")
        tmp.write_text(json.dumps(self._users, indent=2), "utf-8")
        os.chmod(tmp, 0o600)
        os.replace(tmp, self.path)

    @staticmethod
    def _key(name: str) -> str:
        return name.strip().lower()

    def _validate(self, name, password=None):
        errors = []
        if name is not None and not NAME_RE.match(name or ""):
            errors.append("Usuário: 3 a 32 caracteres (letras, números, ponto, hífen ou sublinhado)")
        if password is not None and not (MIN_PASSWORD <= len(password) <= MAX_PASSWORD):
            errors.append(f"Senha: mínimo de {MIN_PASSWORD} caracteres")
        if errors:
            raise ValueError(errors)

    def list(self):
        with self._lock:
            return [{"username": u["username"], "role": u["role"], "created": u["created"]}
                    for u in sorted(self._users.values(), key=lambda u: u["username"].lower())]

    def get(self, name):
        with self._lock:
            return self._users.get(self._key(name or ""))

    def create(self, name, password, role="operator"):
        name = (name or "").strip()
        self._validate(name, password)
        if role not in ROLES:
            raise ValueError(["Perfil inválido"])
        with self._lock:
            if self._key(name) in self._users:
                raise ValueError(["Esse usuário já existe"])
            self._users[self._key(name)] = {
                "username": name, "role": role,
                "hash": generate_password_hash(password), "created": int(time.time())}
            self._save()

    def set_password(self, name, password):
        self._validate(None, password)
        with self._lock:
            u = self._users[self._key(name)]
            u["hash"] = generate_password_hash(password)
            self._save()

    def delete(self, name):
        with self._lock:
            u = self._users[self._key(name)]
            if u["role"] == "admin" and sum(x["role"] == "admin" for x in self._users.values()) <= 1:
                raise ValueError(["Não é possível remover o último administrador"])
            del self._users[self._key(name)]
            self._save()

    def verify(self, name, password):
        """Devolve o usuário (dict) se a senha confere, senão None."""
        u = self.get(name)
        ok = check_password_hash(u["hash"] if u else _DUMMY_HASH, password or "")
        return u if (u and ok) else None

    def ensure_admin(self, name, password):
        """Garante o administrador inicial (FRL_USER/FRL_PASSWORD); a senha do ambiente prevalece."""
        with self._lock:
            u = self.get(name)
            if u is None:
                self.create(name, password, "admin")
            else:
                u["role"] = "admin"
                u["hash"] = generate_password_hash(password)
                self._save()


class LoginThrottle:
    """Bloqueia tentativas em excesso: 5 erros por (IP, usuário) trancam por 60 s."""
    MAX_FAILS, LOCK_S = 5, 60

    def __init__(self, clock=time.monotonic):
        self.clock = clock
        self._fails = {}
        self._lock = threading.Lock()

    def locked(self, key) -> int:
        with self._lock:
            n, until = self._fails.get(key, (0, 0))
            wait = until - self.clock()
            return int(wait) + 1 if wait > 0 else 0

    def fail(self, key):
        with self._lock:
            n, until = self._fails.get(key, (0, 0))
            if until and until <= self.clock():
                n = 0
            n += 1
            self._fails[key] = (n, self.clock() + self.LOCK_S if n >= self.MAX_FAILS else 0)

    def ok(self, key):
        with self._lock:
            self._fails.pop(key, None)
