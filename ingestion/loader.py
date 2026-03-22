"""Load JSONL files from the landing zone into Snowflake Emulator Bronze tables."""
import os
from pathlib import Path

import snowflake.connector

_DEFAULTS: dict[str, object] = {
    "host": "localhost",
    "port": 8082,
    "user": "test",
    "password": "test",
    "database": "BANK_DB",
    "schema": "RAW",
    "warehouse": "test",
}

_DDL: dict[str, str] = {
    "ACCOUNTS_RAW": "CREATE TABLE IF NOT EXISTS ACCOUNTS_RAW (data TEXT)",
    "TRANSACTIONS_RAW": "CREATE TABLE IF NOT EXISTS TRANSACTIONS_RAW (data TEXT)",
}


def get_connection() -> snowflake.connector.SnowflakeConnection:
    """Return a connector connection to the Snowflake Emulator."""
    return snowflake.connector.connect(
        account=os.getenv("SNOWFLAKE_ACCOUNT", "emulator"),
        host=os.getenv("SNOWFLAKE_HOST", str(_DEFAULTS["host"])),
        port=int(os.getenv("SNOWFLAKE_PORT", str(_DEFAULTS["port"]))),
        user=os.getenv("SNOWFLAKE_USER", str(_DEFAULTS["user"])),
        password=os.getenv("SNOWFLAKE_PASSWORD", str(_DEFAULTS["password"])),
        database=os.getenv("SNOWFLAKE_DATABASE", str(_DEFAULTS["database"])),
        schema=os.getenv("SNOWFLAKE_SCHEMA", str(_DEFAULTS["schema"])),
        warehouse=os.getenv("SNOWFLAKE_WAREHOUSE", str(_DEFAULTS["warehouse"])),
        protocol="http",
    )


def create_bronze_tables(cursor) -> None:
    """Create Bronze raw tables if they don't already exist."""
    for ddl in _DDL.values():
        cursor.execute(ddl)


def load_jsonl(cursor, filepath: Path, table: str) -> int:
    """Load a JSONL file into a Bronze table. Returns the number of rows inserted."""
    if not filepath.exists():
        raise FileNotFoundError(f"Landing zone file not found: {filepath}")

    count = 0
    with filepath.open() as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            escaped = line.replace("'", "\\'")
            cursor.execute(
                f"INSERT INTO {table} (data) VALUES ('{escaped}')"
            )
            count += 1
    return count


def run(data_dir: Path = Path("data/landing_zone")) -> None:
    """Load both JSONL files from data_dir into the Bronze layer."""
    conn = get_connection()
    try:
        cur = conn.cursor()
        create_bronze_tables(cur)

        accounts_count = load_jsonl(
            cur, data_dir / "accounts.jsonl", "ACCOUNTS_RAW"
        )
        transactions_count = load_jsonl(
            cur, data_dir / "transactions.jsonl", "TRANSACTIONS_RAW"
        )

        # Emulator uses autocommit — skip explicit COMMIT.
        print(f"Loaded {accounts_count} account events → ACCOUNTS_RAW")
        print(f"Loaded {transactions_count} transaction events → TRANSACTIONS_RAW")
    finally:
        conn.close()
