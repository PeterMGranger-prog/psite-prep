from __future__ import annotations

import os
import shutil
import sys
from pathlib import Path


def main() -> None:
    base = Path(__file__).resolve().parent
    seed_database = base / "psite_prep.db"
    runtime_database = Path("/tmp/psite_prep.db")

    shutil.copy2(seed_database, runtime_database)
    os.environ["DATABASE_PATH"] = str(runtime_database)

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
