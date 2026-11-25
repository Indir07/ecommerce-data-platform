"""Environment-backed configuration shared by local scripts and Airflow."""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

from dotenv import load_dotenv

PROJECT_ROOT = Path(__file__).resolve().parents[1]
load_dotenv(PROJECT_ROOT / ".env")


@dataclass(frozen=True)
class Settings:
    postgres_host: str = os.getenv("POSTGRES_HOST", "localhost")
    postgres_port: int = int(os.getenv("POSTGRES_PORT", "5432"))
    postgres_db: str = os.getenv("POSTGRES_DB", "ecommerce")
    postgres_user: str = os.getenv("POSTGRES_USER", "ecommerce")
    postgres_password: str = os.getenv("POSTGRES_PASSWORD", "local-dev-password")
    data_dir: Path = Path(os.getenv("APP_DATA_DIR", str(PROJECT_ROOT / "data")))
    random_seed: int = int(os.getenv("RANDOM_SEED", "2025"))

    def database_kwargs(self) -> dict[str, str | int]:
        return {
            "host": self.postgres_host,
            "port": self.postgres_port,
            "dbname": self.postgres_db,
            "user": self.postgres_user,
            "password": self.postgres_password,
        }


settings = Settings()
