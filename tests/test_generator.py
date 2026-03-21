"""Unit tests for ingestion.generator."""
import json
from pathlib import Path

import pytest

from ingestion.generator import (
    generate_accounts,
    generate_transactions,
    write_jsonl,
)

_ACCOUNT_KEYS = {
    "event_id",
    "event_type",
    "event_timestamp",
    "account_id",
    "customer_id",
    "account_type",
    "status",
    "balance",
    "currency",
}

_TRANSACTION_KEYS = {
    "event_id",
    "event_type",
    "event_timestamp",
    "transaction_id",
    "account_id",
    "transaction_type",
    "amount",
    "currency",
    "description",
    "target_account_id",
    "status",
}


def test_generate_accounts_count():
    """generate_accounts(n) returns at least n records."""
    accounts = generate_accounts(10)
    assert len(accounts) >= 10


def test_generate_accounts_required_keys():
    """Every account record contains all required fields."""
    accounts = generate_accounts(5)
    for record in accounts:
        assert _ACCOUNT_KEYS.issubset(record.keys()), (
            f"Missing keys: {_ACCOUNT_KEYS - record.keys()}"
        )


def test_generate_accounts_event_types():
    """Account events are only 'account_created' or 'account_updated'."""
    valid = {"account_created", "account_updated"}
    accounts = generate_accounts(20)
    for record in accounts:
        assert record["event_type"] in valid


def test_generate_transactions_count():
    """generate_transactions returns exactly n records."""
    account_ids = [f"ACC-{i:05d}" for i in range(1, 6)]
    transactions = generate_transactions(account_ids, n=15)
    assert len(transactions) == 15


def test_generate_transactions_required_keys():
    """Every transaction record contains all required fields."""
    account_ids = [f"ACC-{i:05d}" for i in range(1, 4)]
    transactions = generate_transactions(account_ids, n=5)
    for record in transactions:
        assert _TRANSACTION_KEYS.issubset(record.keys()), (
            f"Missing keys: {_TRANSACTION_KEYS - record.keys()}"
        )


def test_generate_transactions_reference_accounts():
    """All transaction account_ids reference the provided list."""
    account_ids = [f"ACC-{i:05d}" for i in range(1, 6)]
    transactions = generate_transactions(account_ids, n=30)
    for record in transactions:
        assert record["account_id"] in account_ids


def test_transfer_has_target_account():
    """TRANSFER transactions must have a non-null target_account_id."""
    account_ids = [f"ACC-{i:05d}" for i in range(1, 10)]
    # Generate enough transactions to reliably include at least one TRANSFER
    transactions = generate_transactions(account_ids, n=100)
    transfers = [t for t in transactions if t["transaction_type"] == "TRANSFER"]
    assert len(transfers) > 0, "No TRANSFER transactions generated in 100 records"
    for txn in transfers:
        assert txn["target_account_id"] is not None
        assert txn["target_account_id"] != txn["account_id"]


def test_write_jsonl_creates_file(tmp_path: Path):
    """write_jsonl creates a file with one JSON object per line."""
    records = [
        {"event_id": "1", "event_type": "account_created"},
        {"event_id": "2", "event_type": "account_updated"},
    ]
    output = tmp_path / "out.jsonl"
    write_jsonl(records, output)

    assert output.exists()
    lines = output.read_text().strip().splitlines()
    assert len(lines) == 2
    for i, line in enumerate(lines):
        parsed = json.loads(line)
        assert parsed["event_id"] == str(i + 1)
