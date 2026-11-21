#!/bin/bash
# macOS/Linux wrapper. Windows: py -3 scripts\setup.py
exec python3 "$(cd "$(dirname "$0")" && pwd)/setup.py" "$@"
