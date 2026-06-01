from __future__ import annotations

import base64
import hashlib
import hmac
import json
import os
import time
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from uuid import uuid4


class AuthError(ValueError):
    pass


def _jwt_secret() -> str:
    return os.getenv("JWT_SECRET") or "local-dev-jwt-secret"


def _b64url_encode(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).rstrip(b"=").decode("ascii")


def _b64url_decode(data: str) -> bytes:
    padding = "=" * (-len(data) % 4)
    return base64.urlsafe_b64decode(data + padding)


def create_access_token(payload: dict, expires_in_seconds: int = 7 * 24 * 60 * 60) -> str:
    now = int(time.time())
    claims = dict(payload)
    claims.setdefault("iat", now)
    claims["exp"] = now + expires_in_seconds
    header = {"alg": "HS256", "typ": "JWT"}
    signing_input = ".".join(
        [
            _b64url_encode(json.dumps(header, separators=(",", ":")).encode("utf-8")),
            _b64url_encode(json.dumps(claims, separators=(",", ":")).encode("utf-8")),
        ]
    )
    signature = hmac.new(_jwt_secret().encode("utf-8"), signing_input.encode("ascii"), hashlib.sha256).digest()
    return f"{signing_input}.{_b64url_encode(signature)}"


def decode_access_token(token: str) -> dict:
    try:
        header_b64, payload_b64, signature_b64 = token.split(".", 2)
    except ValueError as exc:
        raise AuthError("Invalid or expired token.") from exc

    signing_input = f"{header_b64}.{payload_b64}"
    expected_signature = hmac.new(
        _jwt_secret().encode("utf-8"),
        signing_input.encode("ascii"),
        hashlib.sha256,
    ).digest()
    try:
        actual_signature = _b64url_decode(signature_b64)
    except Exception as exc:
        raise AuthError("Invalid or expired token.") from exc
    if not hmac.compare_digest(actual_signature, expected_signature):
        raise AuthError("Invalid or expired token.")

    try:
        payload = json.loads(_b64url_decode(payload_b64).decode("utf-8"))
    except Exception as exc:
        raise AuthError("Invalid or expired token.") from exc

    if int(payload.get("exp", 0)) < int(time.time()):
        raise AuthError("Invalid or expired token.")
    if not payload.get("user_id"):
        raise AuthError("Invalid or expired token.")
    return payload


@dataclass
class InMemoryAuthStore:
    users_by_phone: dict[str, dict] = field(default_factory=dict)
    codes_by_phone: dict[str, dict] = field(default_factory=dict)

    def save_code(self, *, phone: str, code: str, expires_at: int) -> None:
        self.codes_by_phone[phone] = {"code": code, "expires_at": expires_at, "used": False}

    def consume_code(self, *, phone: str, code: str) -> None:
        record = self.codes_by_phone.get(phone)
        if not record or record["used"] or record["code"] != code or int(record["expires_at"]) < int(time.time()):
            raise AuthError("Invalid or expired verification code.")
        record["used"] = True

    def get_or_create_user(self, *, phone: str) -> dict:
        user = self.users_by_phone.get(phone)
        if user is None:
            user = {"id": str(uuid4()), "phone": phone, "nickname": "", "created_at": int(time.time())}
            self.users_by_phone[phone] = user
        user["last_login"] = int(time.time())
        return dict(user)


class PostgresAuthStore:
    def __init__(self, database_url: str) -> None:
        self.database_url = database_url

    def init_schema(self) -> None:
        import psycopg

        schema_path = Path(__file__).with_name("postgres_schema.sql")
        with psycopg.connect(self.database_url) as conn:
            conn.execute(schema_path.read_text(encoding="utf-8"))

    def save_code(self, *, phone: str, code: str, expires_at: int) -> None:
        import psycopg

        expires_at_dt = datetime.fromtimestamp(expires_at, tz=UTC)
        with psycopg.connect(self.database_url) as conn:
            conn.execute(
                """
                INSERT INTO sms_codes (phone, code, expires_at, used)
                VALUES (%s, %s, %s, false)
                """,
                (phone, code, expires_at_dt),
            )

    def consume_code(self, *, phone: str, code: str) -> None:
        import psycopg

        with psycopg.connect(self.database_url) as conn:
            row = conn.execute(
                """
                UPDATE sms_codes
                SET used = true
                WHERE id = (
                    SELECT id
                    FROM sms_codes
                    WHERE phone = %s
                      AND code = %s
                      AND used = false
                      AND expires_at >= now()
                    ORDER BY created_at DESC
                    LIMIT 1
                )
                RETURNING id
                """,
                (phone, code),
            ).fetchone()
            if row is None:
                raise AuthError("Invalid or expired verification code.")

    def get_or_create_user(self, *, phone: str) -> dict:
        import psycopg
        from psycopg.rows import dict_row

        with psycopg.connect(self.database_url, row_factory=dict_row) as conn:
            user = conn.execute("SELECT * FROM users WHERE phone = %s", (phone,)).fetchone()
            if user is None:
                user = conn.execute(
                    """
                    INSERT INTO users (phone, nickname, last_login)
                    VALUES (%s, '', now())
                    RETURNING *
                    """,
                    (phone,),
                ).fetchone()
            else:
                user = conn.execute(
                    "UPDATE users SET last_login = now() WHERE id = %s RETURNING *",
                    (user["id"],),
                ).fetchone()
        return _serialize_user(user)


class AuthService:
    def __init__(self, store: InMemoryAuthStore | PostgresAuthStore) -> None:
        self.store = store

    @property
    def test_mode(self) -> bool:
        return os.getenv("SMS_ACCESS_KEY") is None

    def send_code(self, *, phone: str) -> dict:
        normalized_phone = _normalize_phone(phone)
        code = "000000" if self.test_mode else _generate_code()
        self.store.save_code(phone=normalized_phone, code=code, expires_at=int(time.time()) + 300)
        return {"ok": True, "expires_in_seconds": 300, "test_mode": self.test_mode}

    def verify_code(self, *, phone: str, code: str) -> dict:
        normalized_phone = _normalize_phone(phone)
        normalized_code = code.strip()
        self.store.consume_code(phone=normalized_phone, code=normalized_code)
        user = self.store.get_or_create_user(phone=normalized_phone)
        token = create_access_token({"user_id": user["id"], "phone": normalized_phone})
        return {"access_token": token, "token_type": "bearer", "user": user}


def _normalize_phone(phone: str) -> str:
    normalized = "".join(ch for ch in phone.strip() if ch.isdigit() or ch == "+")
    if len(normalized) < 6:
        raise AuthError("Invalid phone number.")
    return normalized


def _generate_code() -> str:
    return str(int(time.time() * 1000) % 1_000_000).zfill(6)


def _serialize_user(user: dict) -> dict:
    result = dict(user)
    if "id" in result:
        result["id"] = str(result["id"])
    for key in ("created_at", "last_login"):
        value = result.get(key)
        if isinstance(value, datetime):
            result[key] = value.isoformat()
    return result


_auth_service: AuthService | None = None


def create_auth_service(store: InMemoryAuthStore | None = None) -> AuthService:
    if store is not None:
        return AuthService(store)
    database_url = os.getenv("DATABASE_URL")
    if database_url:
        postgres_store = PostgresAuthStore(database_url)
        postgres_store.init_schema()
        return AuthService(postgres_store)
    return AuthService(InMemoryAuthStore())


def get_auth_service() -> AuthService:
    global _auth_service
    if _auth_service is None:
        _auth_service = create_auth_service()
    return _auth_service
