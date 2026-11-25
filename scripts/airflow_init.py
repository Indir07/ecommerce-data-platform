"""Initialize Airflow metadata and ensure the local admin account exists."""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path


def main() -> None:
    subprocess.run(["airflow", "db", "migrate"], check=True)
    subprocess.run(
        [sys.executable, str(Path(__file__).with_name("create_airflow_user.py"))],
        check=True,
    )


if __name__ == "__main__":
    main()
