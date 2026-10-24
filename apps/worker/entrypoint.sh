#!/bin/sh
set -e

echo "Starting RQ media worker..."
exec python -m app.worker
