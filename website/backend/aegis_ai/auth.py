from __future__ import annotations

from contextlib import closing
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
import hashlib
import hmac
from pathlib import Path
import re
import secrets
import sqlite3

from .schemas import AuthUser
from .settings import Settings
from .storage import utc_now


_EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")
_PASSWORD_ITERATIONS = 210_000


@dataclass(frozen=True)
class AuthSession:
    token: str
    user: AuthUser
    expires_at: str


class AccountStore:
    def __init__(self, project_root: Path, settings: Settings):
        self.project_root = project_root
        self.db_path = self._resolve_db_path(settings.aegis_database_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._init_db()

    def create_account(self, *, name: str, email: str, password: str) -> AuthUser:
        display_name = self._clean_name(name)
        normalized_email = self._normalize_email(email)
        self._validate_password(password)
        created_at = utc_now()
        user_id = f"user_{secrets.token_urlsafe(18)}"
        password_hash = self._hash_password(password)

        with closing(self._connect()) as conn:
            try:
                with conn:
                    conn.execute(
                        """
                        insert into user_accounts (
                            id, name, email, password_hash, created_at, plan, role, status
                        ) values (?, ?, ?, ?, ?, ?, ?, ?)
                        """,
                        (user_id, display_name, normalized_email, password_hash, created_at, "free", "user", "active"),
                    )
            except sqlite3.IntegrityError as exc:
                raise ValueError("An account already exists for that email address.") from exc

        return AuthUser(
            id=user_id,
            name=display_name,
            email=normalized_email,
            created_at=created_at,
            plan="free",
            role="user",
            status="active",
        )

    def authenticate(self, *, email: str, password: str, remember_me: bool = False) -> AuthSession:
        normalized_email = self._normalize_email(email)
        with closing(self._connect()) as conn:
            row = conn.execute(
                """
                select id, name, email, password_hash, created_at, plan, role, status
                from user_accounts
                where email = ?
                """,
                (normalized_email,),
            ).fetchone()

        if row is None or not self._verify_password(password, str(row["password_hash"])):
            raise PermissionError("Invalid email or password.")

        if row["status"] != "active":
            raise PermissionError("This account is not active.")

        return self.create_session(self._row_to_user(row), remember_me=remember_me)

    def create_session(self, user: AuthUser, *, remember_me: bool = False) -> AuthSession:
        token = f"aegis_{secrets.token_urlsafe(36)}"
        token_hash = self._token_hash(token)
        created_at = utc_now()
        expires_at = (
            datetime.now(timezone.utc) + timedelta(days=30 if remember_me else 1)
        ).isoformat(timespec="seconds")

        with closing(self._connect()) as conn:
            with conn:
                conn.execute(
                    """
                    insert into auth_sessions (
                        token_hash, user_id, created_at, expires_at, remember_me
                    ) values (?, ?, ?, ?, ?)
                    """,
                    (token_hash, user.id, created_at, expires_at, 1 if remember_me else 0),
                )

        return AuthSession(token=token, user=user, expires_at=expires_at)

    def user_for_token(self, token: str) -> tuple[AuthUser, str] | None:
        token_hash = self._token_hash(token)
        with closing(self._connect()) as conn:
            with conn:
                row = conn.execute(
                    """
                    select
                        sessions.expires_at as session_expires_at,
                        accounts.id as id,
                        accounts.name as name,
                        accounts.email as email,
                        accounts.created_at as created_at,
                        accounts.plan as plan,
                        accounts.role as role,
                        accounts.status as status
                    from auth_sessions sessions
                    join user_accounts accounts on accounts.id = sessions.user_id
                    where sessions.token_hash = ?
                    """,
                    (token_hash,),
                ).fetchone()

                if row is None:
                    return None

                if self._is_expired(str(row["session_expires_at"])) or row["status"] != "active":
                    conn.execute("delete from auth_sessions where token_hash = ?", (token_hash,))
                    return None

        return self._row_to_user(row), str(row["session_expires_at"])

    def delete_session(self, token: str) -> None:
        with closing(self._connect()) as conn:
            with conn:
                conn.execute("delete from auth_sessions where token_hash = ?", (self._token_hash(token),))

    def _init_db(self) -> None:
        with closing(self._connect()) as conn:
            with conn:
                conn.execute("pragma foreign_keys = on")
                conn.execute(
                    """
                    create table if not exists user_accounts (
                        id text primary key,
                        name text not null,
                        email text not null unique,
                        password_hash text not null,
                        created_at text not null,
                        plan text not null default 'free',
                        role text not null default 'user',
                        status text not null default 'active'
                    )
                    """
                )
                conn.execute(
                    """
                    create table if not exists auth_sessions (
                        token_hash text primary key,
                        user_id text not null,
                        created_at text not null,
                        expires_at text not null,
                        remember_me integer not null default 0,
                        foreign key(user_id) references user_accounts(id) on delete cascade
                    )
                    """
                )
                conn.execute("create index if not exists idx_auth_sessions_user_id on auth_sessions(user_id)")

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        return conn

    def _resolve_db_path(self, configured: str) -> Path:
        path = Path(configured).expanduser()
        if not path.is_absolute():
            path = self.project_root / path
        return path.resolve()

    def _clean_name(self, value: str) -> str:
        name = value.strip()
        if len(name) < 2:
            raise ValueError("Name must be at least 2 characters.")
        return name[:120]

    def _normalize_email(self, value: str) -> str:
        email = value.strip().lower()
        if not _EMAIL_RE.match(email):
            raise ValueError("Enter a valid email address.")
        return email

    def _validate_password(self, value: str) -> None:
        if len(value) < 8:
            raise ValueError("Password must be at least 8 characters.")

    def _hash_password(self, password: str) -> str:
        salt = secrets.token_hex(16)
        digest = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt.encode("utf-8"), _PASSWORD_ITERATIONS)
        return f"pbkdf2_sha256${_PASSWORD_ITERATIONS}${salt}${digest.hex()}"

    def _verify_password(self, password: str, stored: str) -> bool:
        try:
            algorithm, iterations_raw, salt, expected = stored.split("$", 3)
            iterations = int(iterations_raw)
        except ValueError:
            return False

        if algorithm != "pbkdf2_sha256" or iterations < 1:
            return False

        digest = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt.encode("utf-8"), iterations)
        return hmac.compare_digest(digest.hex(), expected)

    def _token_hash(self, token: str) -> str:
        return hashlib.sha256(token.encode("utf-8", errors="ignore")).hexdigest()

    def _is_expired(self, expires_at: str) -> bool:
        try:
            parsed = datetime.fromisoformat(expires_at)
        except ValueError:
            return True
        if parsed.tzinfo is None:
            parsed = parsed.replace(tzinfo=timezone.utc)
        return parsed <= datetime.now(timezone.utc)

    def _row_to_user(self, row: sqlite3.Row) -> AuthUser:
        return AuthUser(
            id=str(row["id"]),
            name=str(row["name"]),
            email=str(row["email"]),
            created_at=str(row["created_at"]),
            plan=str(row["plan"]),
            role=str(row["role"]),
            status=str(row["status"]),
        )
