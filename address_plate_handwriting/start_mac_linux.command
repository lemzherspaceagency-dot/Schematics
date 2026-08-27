#!/bin/sh
# Double-click this to start the handwriting app.
cd "$(dirname "$0")" || exit 1
exec python3 capture_handwriting.py
