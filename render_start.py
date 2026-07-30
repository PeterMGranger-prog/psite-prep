from __future__ import annotations

import os
import shutil
import sys
from pathlib import Path


def main() -> None:
    base = Path(__file__).resolve().parent
    database_path = Path(os.environ.get("DATABASE_PATH", "/var/data/psite_prep.db"))
    seed_database = base / "psite_prep.db"

    database_path.parent.mkdir(parents=True, exist_ok=True)
    if not database_path.exists():
        shutil.copy2(seed_database, database_path)

    os.environ["DATABASE_PATH"] = str(database_path)
    port = os.environ.get("PORT", "10000")
    command = [
        sys.executable,
        "-m",
        "gunicorn",
        "app:app",
        "--bind",
        f"0.0.0.0:{port}",
        "--workers",
        "1",
        "--threads",
        "4",
        "--timeout",
        "120",
    ]
    os.execvp(command[0], command)


if __name__ == "__main__":
    main()
