import hashlib
import hmac
import json
import os
import secrets
from pathlib import Path

ITERATIONS = 600_000


class LocalAuth:
    def __init__(self, folder):
        self.folder = Path(folder)
        self.folder.mkdir(parents=True, exist_ok=True)
        self.path = self.folder / "credentials.json"

    def exists(self):
        return self.path.exists()

    def _load(self):
        data = json.loads(self.path.read_text(encoding="utf-8"))
        if (
            data.get("version") != 1
            or data.get("iterations") != ITERATIONS
            or not isinstance(data.get("username"), str)
            or not 3 <= len(data["username"]) <= 64
            or len(bytes.fromhex(data["salt"])) != 32
            or len(bytes.fromhex(data["digest"])) != 32
        ):
            raise ValueError("Invalid credentials file")
        return data

    def register(self, username, password):
        username = username.strip()
        if not 3 <= len(username) <= 64:
            raise ValueError("Username must be 3-64 characters")
        if not 8 <= len(password) <= 256:
            raise ValueError("Password must be 8-256 characters")
        if self.exists():
            raise FileExistsError("Account already exists")
        salt = secrets.token_bytes(32)
        digest = hashlib.pbkdf2_hmac(
            "sha256", password.encode("utf-8"), salt, ITERATIONS
        )
        data = dict(
            version=1, username=username, iterations=ITERATIONS,
            salt=salt.hex(), digest=digest.hex()
        )
        fd = os.open(
            self.path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600
        )
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False)
            f.flush()
            os.fsync(f.fileno())

    def verify(self, username, password):
        data = self._load()
        if len(password) > 256:
            return False
        digest = hashlib.pbkdf2_hmac(
            "sha256", password.encode("utf-8"),
            bytes.fromhex(data["salt"]), data["iterations"]
        )
        valid_password = hmac.compare_digest(
            digest, bytes.fromhex(data["digest"])
        )
        valid_username = hmac.compare_digest(
            username.strip().encode("utf-8"),
            data["username"].encode("utf-8")
        )
        return valid_password and valid_username
