#!/usr/bin/env python3
"""Cross-platform launcher: runs run.py inside the private env made by setup.py.
macOS/Linux: python3 launch.py ...   Windows: py -3 launch.py ..."""

import os
import subprocess
import sys
from pathlib import Path

ENV = Path.home() / ".gta6-clipper" / "venv"
PY = ENV / ("Scripts/python.exe" if os.name == "nt" else "bin/python")
HERE = Path(__file__).resolve().parent

if not PY.exists():
    sys.exit(f"Not set up yet. Run:  {'py -3' if os.name == 'nt' else 'python3'} \"{HERE / 'setup.py'}\"")
env = dict(os.environ, PYTHONUTF8="1", PYTHONIOENCODING="utf-8")
env["PATH"] = str(PY.parent) + os.pathsep + env.get("PATH", "")
sys.exit(subprocess.call([str(PY), str(HERE / "run.py"), *sys.argv[1:]], env=env))
