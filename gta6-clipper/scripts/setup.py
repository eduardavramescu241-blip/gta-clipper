#!/usr/bin/env python3
"""One-time setup for gta6-clipper (macOS, Windows, Linux). Safe to run again.
Prints "All set" at the end. Uses only the standard library."""

import hashlib
import os
import platform
import shutil
import subprocess
import sys
import urllib.request
from pathlib import Path

WIN = os.name == "nt"
MAC = sys.platform == "darwin"
ENV_DIR = Path.home() / ".gta6-clipper"
VENV = ENV_DIR / "venv"
VENV_PY = VENV / ("Scripts/python.exe" if WIN else "bin/python")
HERE = Path(__file__).resolve().parent
MODEL_URL = ("https://github.com/opencv/opencv_zoo/raw/main/models/"
             "face_detection_yunet/face_detection_yunet_2023mar.onnx")
MODEL_SHA256 = "8f2383e4dd3cfbb4553ea8718107fc0423210dc964f9f4280604804ed2552fa4"
PACKAGES = ["faster-whisper", "opencv-python-headless<5", "pillow", "numpy", "yt-dlp"]  # yt-dlp: always latest on purpose

if WIN:
    os.system("")   # lets the console show colours

missing = []


def ok(msg):
    print(f"\033[32m✓\033[0m {msg}")


def bad(msg):
    print(f"\033[31m✗\033[0m {msg}")
    missing.append(msg)


def hint(mac, win, other):
    return mac if MAC else win if WIN else other


print("gta6-clipper setup")
if sys.version_info < (3, 9):
    bad("Python 3.9 or newer is needed")
else:
    ok(f"Python {platform.python_version()}")

if shutil.which("ffmpeg") and shutil.which("ffprobe"):
    ok("ffmpeg")
else:
    bad("ffmpeg missing: " + hint("brew install ffmpeg", "winget install Gyan.FFmpeg  (then open a NEW terminal)",
                                  "install ffmpeg with your package manager"))
if shutil.which("claude"):
    ok("Claude Code")
else:
    bad("claude missing: install Claude Code first (https://docs.claude.com/en/docs/claude-code)")
if any(shutil.which(x) for x in ("deno", "node", "bun")):
    ok("JavaScript runtime (YouTube needs one)")
else:
    bad("no deno/node: " + hint("brew install deno", "winget install DenoLand.Deno  (then open a NEW terminal)",
                                "install deno or node"))
free_gb = shutil.disk_usage(Path.home()).free / 1e9
if free_gb >= 2:
    ok(f"disk: {free_gb:.0f} GB free")
else:
    bad(f"only {free_gb:.1f} GB free; setup needs ~1 GB, clipping ~0.1 GB per stream hour")
if missing:
    print("\nFix the ✗ lines above, then run this again.")
    sys.exit(1)

ENV_DIR.mkdir(parents=True, exist_ok=True)
if not VENV_PY.exists():
    if shutil.which("uv"):
        r = subprocess.run(["uv", "venv", "-q", "--python", "3.11", str(VENV)])
        if r.returncode:
            subprocess.run(["uv", "venv", "-q", str(VENV)], check=True)
    else:
        subprocess.run([sys.executable, "-m", "venv", str(VENV)], check=True)
if shutil.which("uv"):
    cmd = ["uv", "pip", "install", "-q", "--python", str(VENV_PY), "-U", *PACKAGES]
else:
    subprocess.run([str(VENV_PY), "-m", "pip", "install", "-q", "-U", "pip"], check=True)
    cmd = [str(VENV_PY), "-m", "pip", "install", "-q", "-U", *PACKAGES]
subprocess.run(cmd, check=True)
ok(f"Python packages (private env in {ENV_DIR})")

env = dict(os.environ, PYTHONUTF8="1")
code = ("from faster_whisper import WhisperModel\n"
        "for n in ('tiny','base'): WhisperModel(n, device='cpu', compute_type='int8')\n")
if subprocess.run([str(VENV_PY), "-c", code], env=env).returncode:
    bad("Whisper model download failed (check the internet connection and run setup again)")
    sys.exit(1)
ok("Whisper models (tiny = listening, base = captions)")

model = ENV_DIR / "models" / "yunet.onnx"
model.parent.mkdir(parents=True, exist_ok=True)


def good(p):
    return p.exists() and hashlib.sha256(p.read_bytes()).hexdigest() == MODEL_SHA256


if not good(model):
    try:
        with urllib.request.urlopen(MODEL_URL, timeout=60) as r:
            data = r.read()
        if hashlib.sha256(data).hexdigest() == MODEL_SHA256:
            model.write_bytes(data)
        else:
            print("! facecam model failed its checksum; not installed")
    except OSError as exc:
        print(f"! facecam model download failed ({exc})")
if good(model):
    ok("facecam finder (OpenCV YuNet, checksum verified)")
else:
    print("! clips will fall back to a simpler face finder")

home = Path.home() / "gta6-clips"
home.mkdir(parents=True, exist_ok=True)
if not (home / "streamers.txt").exists():
    shutil.copy(HERE.parent / "streamers.txt", home / "streamers.txt")
ok(f"watchlist: {home / 'streamers.txt'}")
launch = HERE / "launch.py"
print(f"\nAll set. Try:  {'py -3' if WIN else 'python3'} \"{launch}\" --find --list")
