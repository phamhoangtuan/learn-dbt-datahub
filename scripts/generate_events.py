"""CLI: generate synthetic banking events to data/landing_zone/."""
import argparse
from pathlib import Path

from ingestion.generator import run

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Generate synthetic banking events")
    parser.add_argument("--accounts", type=int, default=50, help="Number of accounts (default: 50)")
    parser.add_argument("--transactions", type=int, default=200, help="Number of transactions (default: 200)")
    parser.add_argument("--output-dir", type=Path, default=Path("data/landing_zone"), help="Output directory")
    args = parser.parse_args()
    run(args.accounts, args.transactions, args.output_dir)
