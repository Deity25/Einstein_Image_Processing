#!/bin/bash
# Double-click this file on macOS after granting execute permission.
# It launches a local Python server, without any remote network calls.
cd "$(dirname "$0")" || exit 1
(sleep 2; open "http://127.0.0.1:8765") &
exec python3 server.py
