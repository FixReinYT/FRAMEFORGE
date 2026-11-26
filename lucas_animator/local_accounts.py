"""Local-first FRAMEFORGE accounts.

Passwords and recovery codes are PBKDF2 hashes. Session tokens are random,
expire, and are stored hashed in SQLite. Email is an identifier only until a
real mail provider is configured.
"""
from __future__ import annotations

import hashlib
import hmac
import os
import re
import secrets
import sqlite3
import sys
import time
from contextlib import contextmanager
from pathlib import Path

from PIL import Image, ImageOps


class AccountError(ValueError):
    """A safe, user-facing account validation or authentication error."""


def user_data_dir() -> Path:
    if sys.platform == "win32":
        base = Path(os.environ.get("APPDATA") or Path.home())
    elif sys.platform == "darwin":
        base = Path.home() / "Library" / "Application Support"
    else:
        base = Path(os.environ.get("XDG_DATA_HOME") or (Path.home() / ".local" / "share"))
    path = base / "FRAMEFORGE"
    path.mkdir(parents=True, exist_ok=True)
    return path


class LocalAccountStore:
    """Offline account provider; API can later be replaced by a cloud provider."""

    ITERATIONS = 310_000
    SESSION_DAYS = 30

    def __init__(self, directory: str | os.PathLike | None = None):
        self.directory = Path(directory) if directory else user_data_dir()
        self.directory.mkdir(parents=True, exist_ok=True)
        self.database = self.directory / "accounts.sqlite3"
        self.session_file = self.directory / "session.token"
        self.avatar_dir = self.directory / "avatars"
        self.avatar_dir.mkdir(parents=True, exist_ok=True)
        self._initialize()

    @contextmanager
    def _connect(self):
        db = sqlite3.connect(self.database, timeout=10)
        db.row_factory = sqlite3.Row
        db.execute("PRAGMA foreign_keys=ON")
        try:
            yield db
            db.commit()
        except Exception:
            db.rollback()
            raise
        finally:
            db.close()

    def _initialize(self):
        with self._connect() as db:
            db.executescript("""
                CREATE TABLE IF NOT EXISTS accounts (
                    id INTEGER PRIMARY KEY,
                    username TEXT NOT NULL,
                    username_norm TEXT NOT NULL UNIQUE,
                    email TEXT NOT NULL,
                    email_norm TEXT NOT NULL UNIQUE,
                    display_name TEXT NOT NULL,
                    password_salt BLOB NOT NULL,
                    password_hash BLOB NOT NULL,
                    recovery_salt BLOB NOT NULL,
                    recovery_hash BLOB NOT NULL,
                    avatar_path TEXT,
                    created_at INTEGER NOT NULL
                );
                CREATE TABLE IF NOT EXISTS sessions (
                    token_hash TEXT PRIMARY KEY,
                    username_norm TEXT NOT NULL REFERENCES accounts(username_norm) ON DELETE CASCADE,
                    expires_at INTEGER NOT NULL
                );
                CREATE INDEX IF NOT EXISTS idx_sessions_user ON sessions(username_norm);
            """)

    @classmethod
    def _derive(cls, secret: str, salt: bytes) -> bytes:
        return hashlib.pbkdf2_hmac("sha256", secret.encode("utf-8"), salt, cls.ITERATIONS)

    @staticmethod
    def _token_hash(token: str) -> str:
        return hashlib.sha256(token.encode("utf-8")).hexdigest()

    @staticmethod
    def _profile(row):
        if row is None:
            return None
        return {
            "username": row["username"],
            "email": row["email"],
            "display_name": row["display_name"],
            "avatar_path": row["avatar_path"],
            "created_at": row["created_at"],
        }

    @staticmethod
    def _validate_password(password: str):
        if not isinstance(password, str) or len(password) < 10:
            raise AccountError("Пароль должен содержать не менее 10 символов.")
        if len(password) > 256:
            raise AccountError("Пароль слишком длинный.")

    def create_account(self, username: str, email: str, display_name: str, password: str):
        username = (username or "").strip()
        email = (email or "").strip()
        display_name = (display_name or username).strip()
        if not re.fullmatch(r"[A-Za-z0-9_.-]{3,24}", username):
            raise AccountError("Логин: 3–24 символа, латинские буквы, цифры, точка, дефис или подчёркивание.")
        if not re.fullmatch(r"[^\s@]+@[^\s@]+\.[^\s@]{2,}", email):
            raise AccountError("Укажи корректный адрес электронной почты.")
        if not display_name or len(display_name) > 40:
            raise AccountError("Отображаемое имя должно содержать от 1 до 40 символов.")
        self._validate_password(password)
        username_norm, email_norm = username.casefold(), email.casefold()
        salt, recovery_salt = secrets.token_bytes(16), secrets.token_bytes(16)
        recovery_code = secrets.token_urlsafe(12)
        try:
            with self._connect() as db:
                db.execute(
                    """INSERT INTO accounts(username,username_norm,email,email_norm,display_name,
                       password_salt,password_hash,recovery_salt,recovery_hash,created_at)
                       VALUES(?,?,?,?,?,?,?,?,?,?)""",
                    (username, username_norm, email, email_norm, display_name, salt,
                     self._derive(password, salt), recovery_salt,
                     self._derive(recovery_code, recovery_salt), int(time.time()))
                )
                row = db.execute("SELECT * FROM accounts WHERE username_norm=?", (username_norm,)).fetchone()
        except sqlite3.IntegrityError as exc:
            message = str(exc).lower()
            if "username_norm" in message:
                raise AccountError("Этот логин уже занят.") from exc
            if "email_norm" in message:
                raise AccountError("Этот адрес электронной почты уже используется.") from exc
            raise AccountError("Не удалось создать аккаунт: конфликт данных.") from exc
        return self._profile(row), recovery_code

    def _write_session(self, username_norm: str):
        token = secrets.token_urlsafe(32)
        expiry = int(time.time()) + self.SESSION_DAYS * 86400
        with self._connect() as db:
            db.execute("DELETE FROM sessions WHERE username_norm=?", (username_norm,))
            db.execute("INSERT INTO sessions(token_hash,username_norm,expires_at) VALUES(?,?,?)",
                       (self._token_hash(token), username_norm, expiry))
        self.session_file.write_text(token, encoding="utf-8")
        try:
            os.chmod(self.session_file, 0o600)
        except OSError:
            pass

    def login(self, identifier: str, password: str):
        identifier_norm = (identifier or "").strip().casefold()
        with self._connect() as db:
            row = db.execute(
                "SELECT * FROM accounts WHERE username_norm=? OR email_norm=?",
                (identifier_norm, identifier_norm)
            ).fetchone()
        if row is None:
            raise AccountError("Неверный логин, email или пароль.")
        candidate = self._derive(password or "", row["password_salt"])
        if not hmac.compare_digest(candidate, row["password_hash"]):
            raise AccountError("Неверный логин, email или пароль.")
        self._write_session(row["username_norm"])
        return self._profile(row)

    def restore_session(self):
        try:
            token = self.session_file.read_text(encoding="utf-8").strip()
        except OSError:
            return None
        if not token:
            return None
        token_hash = self._token_hash(token)
        with self._connect() as db:
            row = db.execute(
                """SELECT a.*,s.expires_at FROM sessions s
                   JOIN accounts a ON a.username_norm=s.username_norm
                   WHERE s.token_hash=?""", (token_hash,)
            ).fetchone()
            if row is None or row["expires_at"] <= int(time.time()):
                db.execute("DELETE FROM sessions WHERE token_hash=?", (token_hash,))
                try:
                    self.session_file.unlink()
                except OSError:
                    pass
                return None
        return self._profile(row)

    def logout(self):
        try:
            token = self.session_file.read_text(encoding="utf-8").strip()
        except OSError:
            token = ""
        if token:
            with self._connect() as db:
                db.execute("DELETE FROM sessions WHERE token_hash=?", (self._token_hash(token),))
        try:
            self.session_file.unlink()
        except OSError:
            pass

    def reset_password(self, email: str, recovery_code: str, new_password: str):
        self._validate_password(new_password)
        email_norm = (email or "").strip().casefold()
        with self._connect() as db:
            row = db.execute("SELECT * FROM accounts WHERE email_norm=?", (email_norm,)).fetchone()
            if row is None:
                raise AccountError("Аккаунт с таким email не найден на этом компьютере.")
            candidate = self._derive((recovery_code or "").strip(), row["recovery_salt"])
            if not hmac.compare_digest(candidate, row["recovery_hash"]):
                raise AccountError("Код восстановления неверен.")
            password_salt, recovery_salt = secrets.token_bytes(16), secrets.token_bytes(16)
            new_recovery_code = secrets.token_urlsafe(12)
            db.execute(
                """UPDATE accounts SET password_salt=?,password_hash=?,recovery_salt=?,recovery_hash=?
                   WHERE username_norm=?""",
                (password_salt, self._derive(new_password, password_salt),
                 recovery_salt, self._derive(new_recovery_code, recovery_salt), row["username_norm"])
            )
            db.execute("DELETE FROM sessions WHERE username_norm=?", (row["username_norm"],))
        try:
            self.session_file.unlink()
        except OSError:
            pass
        return new_recovery_code

    def update_profile(self, username: str, display_name: str):
        display_name = (display_name or "").strip()
        if not display_name or len(display_name) > 40:
            raise AccountError("Имя профиля должно содержать от 1 до 40 символов.")
        username_norm = (username or "").casefold()
        with self._connect() as db:
            cur = db.execute("UPDATE accounts SET display_name=? WHERE username_norm=?",
                             (display_name, username_norm))
            if not cur.rowcount:
                raise AccountError("Аккаунт не найден.")
            row = db.execute("SELECT * FROM accounts WHERE username_norm=?", (username_norm,)).fetchone()
        return self._profile(row)

    def set_avatar(self, username: str, source_path: str):
        try:
            with Image.open(source_path) as source:
                avatar = ImageOps.fit(source.convert("RGBA"), (256, 256), method=Image.Resampling.LANCZOS)
        except Exception as exc:
            raise AccountError("Не удалось прочитать изображение аватара.") from exc
        safe_name = re.sub(r"[^a-zA-Z0-9_.-]", "_", username)
        target = self.avatar_dir / (safe_name + ".png")
        temp = target.with_suffix(".tmp.png")
        avatar.save(temp, format="PNG")
        os.replace(temp, target)
        username_norm = (username or "").casefold()
        with self._connect() as db:
            cur = db.execute("UPDATE accounts SET avatar_path=? WHERE username_norm=?",
                             (str(target), username_norm))
            if not cur.rowcount:
                raise AccountError("Аккаунт не найден.")
            row = db.execute("SELECT * FROM accounts WHERE username_norm=?", (username_norm,)).fetchone()
        return self._profile(row)
