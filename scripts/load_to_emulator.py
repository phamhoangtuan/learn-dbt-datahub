"""CLI: load JSONL files from the landing zone into Snowflake Emulator Bronze tables."""
import argparse
from pathlib import Path

from ingestion.loader import run

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Load events into Bronze layer")
    parser.add_argument("--data-dir", type=Path, default=Path("data/landing_zone"), help="Landing zone directory")
    args = parser.parse_args()
    run(args.data_dir)
