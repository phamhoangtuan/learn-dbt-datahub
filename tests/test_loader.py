"""Unit tests for ingestion.loader (connector mocked)."""
import json
from pathlib import Path
from unittest.mock import MagicMock, call, patch

import pytest

from ingestion.loader import create_bronze_tables, load_jsonl


def test_create_bronze_tables_executes_ddl():
    """create_bronze_tables calls cursor.execute for both raw tables."""
    cursor = MagicMock()
    create_bronze_tables(cursor)

    assert cursor.execute.call_count == 2
    sql_calls = [c.args[0].upper() for c in cursor.execute.call_args_list]
    assert any("ACCOUNTS_RAW" in s for s in sql_calls)
    assert any("TRANSACTIONS_RAW" in s for s in sql_calls)
    assert all("CREATE TABLE IF NOT EXISTS" in s for s in sql_calls)


def test_load_jsonl_executes_insert_per_row(tmp_path: Path):
    """load_jsonl runs one INSERT per non-empty line."""
    records = [
        {"event_id": "1", "event_type": "account_created"},
        {"event_id": "2", "event_type": "account_updated"},
        {"event_id": "3", "event_type": "account_created"},
    ]
    filepath = tmp_path / "accounts.jsonl"
    filepath.write_text("\n".join(json.dumps(r) for r in records) + "\n")

    cursor = MagicMock()
    load_jsonl(cursor, filepath, "BANK_DB.RAW.ACCOUNTS_RAW")

    assert cursor.execute.call_count == 3
    for c in cursor.execute.call_args_list:
        sql = c.args[0].upper()
        assert "INSERT INTO" in sql
        assert "BANK_DB.RAW.ACCOUNTS_RAW" in sql


def test_load_jsonl_returns_row_count(tmp_path: Path):
    """load_jsonl returns the number of rows loaded."""
    records = [{"id": str(i)} for i in range(5)]
    filepath = tmp_path / "data.jsonl"
    filepath.write_text("\n".join(json.dumps(r) for r in records))

    cursor = MagicMock()
    count = load_jsonl(cursor, filepath, "BANK_DB.RAW.TRANSACTIONS_RAW")

    assert count == 5


def test_load_jsonl_missing_file_raises():
    """load_jsonl raises FileNotFoundError when the file doesn't exist."""
    cursor = MagicMock()
    with pytest.raises(FileNotFoundError):
        load_jsonl(cursor, Path("/nonexistent/file.jsonl"), "SOME_TABLE")
