#!/bin/sh
set -eu
mkdir -p "$(dirname "${DATABASE_PATH:-/data/psite_prep.db}")"
if [ ! -f "${DATABASE_PATH:-/data/psite_prep.db}" ]; then
  cp /app/psite_prep.db "${DATABASE_PATH:-/data/psite_prep.db}"
fi
exec gunicorn --workers "${WEB_CONCURRENCY:-2}" --threads 4 --timeout 120 --bind "0.0.0.0:${PORT:-8000}" app:app
