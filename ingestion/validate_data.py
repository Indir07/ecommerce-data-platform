"""Validate one generated batch and write accepted rows and quality reports."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from ingestion.config import settings
from ingestion.validation import validate_batch


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--batch-id", type=int, default=1)
    parser.add_argument("--input-dir", type=Path)
    parser.add_argument("--output-dir", type=Path)
    args = parser.parse_args()
    input_dir = args.input_dir or settings.data_dir / "raw" / f"batch_{args.batch_id:08d}"
    output_dir = args.output_dir or settings.data_dir / "validated" / f"batch_{args.batch_id:08d}"
    metrics = validate_batch(input_dir, output_dir)
    print(json.dumps(metrics["totals"], sort_keys=True))


if __name__ == "__main__":
    main()
