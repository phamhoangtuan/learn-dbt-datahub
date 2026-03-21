"""Synthetic banking event generator using Faker."""
import json
import random
import uuid
from datetime import timedelta
from pathlib import Path

from faker import Faker

_faker = Faker()
_faker.seed_instance(42)
random.seed(42)

ACCOUNT_TYPES = ["CHECKING", "SAVINGS", "CREDIT"]
ACCOUNT_STATUSES = ["ACTIVE", "INACTIVE", "FROZEN"]
TRANSACTION_TYPES = ["CREDIT", "DEBIT", "TRANSFER"]
TRANSACTION_STATUSES = ["COMPLETED", "PENDING", "FAILED"]


def generate_accounts(n: int = 50) -> list[dict]:
    """Generate at least n synthetic account events (creation + optional updates)."""
    accounts: list[dict] = []
    for i in range(n):
        account_id = f"ACC-{i + 1:05d}"
        customer_id = f"CUST-{random.randint(1, max(1, n // 2)):05d}"
        created_ts = _faker.date_time_between(start_date="-2y", end_date="-6m")
        account_type = random.choice(ACCOUNT_TYPES)

        accounts.append({
            "event_id": str(uuid.uuid4()),
            "event_type": "account_created",
            "event_timestamp": created_ts.isoformat(),
            "account_id": account_id,
            "customer_id": customer_id,
            "account_type": account_type,
            "status": "ACTIVE",
            "balance": round(random.uniform(100.0, 50000.0), 2),
            "currency": "USD",
        })

        if random.random() < 0.3:
            updated_ts = created_ts + timedelta(days=random.randint(1, 180))
            accounts.append({
                "event_id": str(uuid.uuid4()),
                "event_type": "account_updated",
                "event_timestamp": updated_ts.isoformat(),
                "account_id": account_id,
                "customer_id": customer_id,
                "account_type": random.choice(ACCOUNT_TYPES),
                "status": random.choice(ACCOUNT_STATUSES),
                "balance": round(random.uniform(0.0, 100000.0), 2),
                "currency": "USD",
            })

    return accounts


def generate_transactions(account_ids: list[str], n: int = 200) -> list[dict]:
    """Generate exactly n synthetic transaction events referencing the given account IDs."""
    transactions: list[dict] = []
    for i in range(n):
        txn_type = random.choice(TRANSACTION_TYPES)
        account_id = random.choice(account_ids)
        target_account_id = None
        if txn_type == "TRANSFER":
            others = [a for a in account_ids if a != account_id]
            target_account_id = random.choice(others) if others else None

        transactions.append({
            "event_id": str(uuid.uuid4()),
            "event_type": "transaction",
            "event_timestamp": _faker.date_time_between(
                start_date="-6m", end_date="now"
            ).isoformat(),
            "transaction_id": f"TXN-{i + 1:05d}",
            "account_id": account_id,
            "transaction_type": txn_type,
            "amount": round(random.uniform(1.0, 10000.0), 2),
            "currency": "USD",
            "description": _faker.sentence(nb_words=5),
            "target_account_id": target_account_id,
            "status": random.choices(
                TRANSACTION_STATUSES, weights=[0.85, 0.10, 0.05]
            )[0],
        })

    return transactions


def write_jsonl(records: list[dict], path: Path) -> None:
    """Write records to a JSONL file (one JSON object per line)."""
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w") as f:
        for record in records:
            f.write(json.dumps(record) + "\n")


def run(
    num_accounts: int = 50,
    num_transactions: int = 200,
    output_dir: Path = Path("data/landing_zone"),
) -> None:
    """Generate and write banking events to the landing zone."""
    accounts = generate_accounts(num_accounts)
    account_ids = list({a["account_id"] for a in accounts})
    transactions = generate_transactions(account_ids, num_transactions)

    write_jsonl(accounts, output_dir / "accounts.jsonl")
    write_jsonl(transactions, output_dir / "transactions.jsonl")
    print(f"Generated {len(accounts)} account events → {output_dir}/accounts.jsonl")
    print(f"Generated {len(transactions)} transaction events → {output_dir}/transactions.jsonl")
