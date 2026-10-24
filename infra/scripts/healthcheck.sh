#!/bin/sh
set -e

# Call the API's readiness endpoint using Python standard library
python3 -c "
import urllib.request
import sys

try:
    req = urllib.request.Request('http://127.0.0.1:8000/health/ready')
    with urllib.request.urlopen(req, timeout=2.5) as resp:
        if resp.status == 200:
            sys.exit(0)
        else:
            sys.exit(1)
except Exception:
    sys.exit(1)
"
