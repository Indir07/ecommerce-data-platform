"""Create the local Airflow admin user once, without failing on restarts."""

from __future__ import annotations

import json
import os
import subprocess


def main() -> None:
    username = os.environ.get("_AIRFLOW_WWW_USER_USERNAME", "admin")
    password = os.environ.get("_AIRFLOW_WWW_USER_PASSWORD", "admin")
    output = subprocess.run(
        ["airflow", "users", "list", "--output", "json"],
        check=True,
        capture_output=True,
        text=True,
    )
    users = json.loads(output.stdout)
    if any(user.get("username") == username for user in users):
        print(f"Airflow user {username!r} already exists")
        return

    subprocess.run(
        [
            "airflow",
            "users",
            "create",
            "--username",
            username,
            "--firstname",
            "Local",
            "--lastname",
            "Admin",
            "--role",
            "Admin",
            "--email",
            f"{username}@example.test",
            "--password",
            password,
        ],
        check=True,
    )


if __name__ == "__main__":
    main()
