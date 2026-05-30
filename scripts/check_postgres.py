from __future__ import annotations

import os
import sys
from urllib.parse import urlparse

import psycopg
from dotenv import load_dotenv

from productization.postgres_repository import PostgresCloudRepository


def _masked_database_url(raw_url: str) -> str:
    parsed = urlparse(raw_url)
    user = parsed.username or ""
    host = parsed.hostname or ""
    port = f":{parsed.port}" if parsed.port else ""
    return f"{parsed.scheme}://{user}:***@{host}{port}{parsed.path}"


def main() -> int:
    load_dotenv(".env")
    database_url = os.getenv("DATABASE_URL")
    jwt_secret = os.getenv("JWT_SECRET")

    if not database_url:
        print("DATABASE_URL is not configured.", file=sys.stderr)
        return 2
    if not jwt_secret:
        print("JWT_SECRET is not configured.", file=sys.stderr)
        return 2
    if len(jwt_secret) < 32:
        print("JWT_SECRET is configured but shorter than 32 characters.", file=sys.stderr)
        return 2

    print(f"Checking PostgreSQL: {_masked_database_url(database_url)}")
    try:
        with psycopg.connect(database_url, connect_timeout=8) as conn:
            server_version = conn.execute("select version()").fetchone()[0]
        print(f"Connection OK: {server_version.split(',')[0]}")

        repo = PostgresCloudRepository(database_url)
        repo.init_schema()
        print("Schema OK: productization/postgres_schema.sql applied.")
    except Exception as exc:
        print(f"PostgreSQL check failed: {type(exc).__name__}: {exc}", file=sys.stderr)
        return 1

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
