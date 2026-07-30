import os
import subprocess
import sys


def main() -> None:
    port = os.environ.get("PORT", "8000")
    command = [
        sys.executable,
        "-m",
        "gunicorn",
        "app:app",
        "--bind",
        f"0.0.0.0:{port}",
        "--workers",
        "2",
        "--threads",
        "4",
        "--timeout",
        "120",
    ]
    os.execvp(command[0], command)


if __name__ == "__main__":
    main()
