"""One scheduled run on GitHub Actions: new GTA clips for every streamer in ci/streamers.json.

For each streamer: find the newest broadcast with GTA in its title, clip only the part not
clipped before (a few hours at most per run), and collect the clips in out/<NAME>/<run>/.
Stops early when Claude's usage limit is reached (that footage is retried next run).
State that must survive between runs lives in state/ and is committed back by the workflow.
"""

import json
import os
import shutil
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SCRIPTS = ROOT / "gta6-clipper" / "scripts"
STATE = ROOT / "state"
OUT = ROOT / "out"
HOME6 = Path(os.environ.get("GTA6CLIP_HOME", str(ROOT / "work-home")))
VENV_PY = Path.home() / ".gta6-clipper" / "venv" / "bin" / "python"


def log(msg):
    print(msg, flush=True)


def read_json(path, default):
    try:
        return json.loads(Path(path).read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return default


def write_json(path, data):
    Path(path).write_text(json.dumps(data, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


ERRORS = []


def ytdlp(*args, timeout=120):
    if not VENV_PY.exists():
        ERRORS.append(f"clipper environment missing ({VENV_PY}): setup failed")
        return ""
    try:
        proc = subprocess.run([str(VENV_PY), "-m", "yt_dlp", *args], capture_output=True, text=True,
                              timeout=timeout)
    except subprocess.TimeoutExpired:
        ERRORS.append("yt-dlp timed out: " + " ".join(args)[-120:])
        return ""
    for line in proc.stderr.splitlines():
        if "ERROR" in line or "WARNING" in line:
            ERRORS.append(line.strip()[:300])
    return proc.stdout + proc.stderr


def is_live(login):
    out = ytdlp("--skip-download", "--print", "is_live", f"https://www.twitch.tv/{login}")
    return any(line.strip() == "True" for line in out.splitlines())


def newest_gta_vod(login):
    """(url, title, start_timestamp) of the newest broadcast with GTA in its title, or None."""
    listing = ytdlp("--flat-playlist", "--playlist-end", "5", "--print", "url",
                    f"https://www.twitch.tv/{login}/videos?filter=archives&sort=time")
    for line in listing.splitlines():
        if "twitch.tv/videos/" not in line:
            continue
        vid = line.strip().split("videos/")[1].split("?")[0].strip("/")
        url = f"https://www.twitch.tv/videos/{vid}"
        meta = ytdlp("--skip-download", "--print", "%(timestamp)s|%(title)s", url)
        rows = [m for m in meta.splitlines() if "|" in m and m.split("|", 1)[0].isdigit()]
        if not rows:
            continue
        ts, title = rows[-1].split("|", 1)
        if "gta" in title.lower() or "grand theft auto" in title.lower():
            return url, title, int(ts)
    return None


def main():
    cfg_all = read_json(ROOT / "ci" / "streamers.json", {})
    HOME6.mkdir(parents=True, exist_ok=True)
    OUT.mkdir(exist_ok=True)
    # Progress (how far each broadcast is clipped) lives in state/, the clipper reads it from HOME6.
    shutil.copyfile(STATE / "progress.json", HOME6 / "progress.json")
    titles = read_json(STATE / "titles.json", {})
    summary, limit_hit = [], False
    clipper_tails = []
    env = dict(os.environ, GTA6CLIP_HOME=str(HOME6), PYTHONUTF8="1")

    for s in cfg_all.get("streamers", []):
        name, login = s["name"], s["login"]
        log(f"\n=== {name} ===")
        live = is_live(login)
        found = newest_gta_vod(login)
        if not found:
            summary.append(f"{name}: no GTA broadcast found among the 5 newest (live: {live})")
            continue
        url, title, ts = found
        age_h = (time.time() - ts) / 3600
        log(f"live: {live} | broadcast: {url} | started {age_h:.0f} h ago | {title}")
        if not live and age_h > cfg_all.get("max_age_hours", 72):
            prog = read_json(HOME6 / "progress.json", {})
            if url not in prog:
                summary.append(f"{name}: newest GTA broadcast is {age_h:.0f} h old and over; waiting")
                continue

        cfg = {
            "language": "en", "no_swearing": True,
            "must_mention": name, "must_hashtags": s["tags"],
            "avoid_titles": titles.get(name, [])[-40:],
            "game_max_x": s.get("game_max_x"),
            "max_new_hours": cfg_all.get("max_new_hours", 6),
        }
        write_json(HOME6 / "config.json", cfg)
        started = time.time()
        proc = subprocess.run([str(VENV_PY), str(SCRIPTS / "run.py"), url, "--new-only",
                               "--clips", str(cfg_all.get("clips_per_run", 5))],
                              capture_output=True, text=True, env=env, stdin=subprocess.DEVNULL)
        out = proc.stdout + proc.stderr
        print(out[-6000:], flush=True)
        clipper_tails.append((name, [l for l in out.splitlines() if l.strip()][-20:]))

        made = 0
        for day in HOME6.glob("20??-??-??"):
            for run_dir in day.iterdir():
                if not run_dir.is_dir() or run_dir.stat().st_mtime < started:
                    continue
                clips = sorted(run_dir.glob("*.mp4"))
                if not clips:
                    continue
                dest = OUT / name / f"{day.name}_{run_dir.name}"
                shutil.copytree(run_dir, dest, dirs_exist_ok=True)
                made += len(clips)
                data = read_json(run_dir / "clips.json", {})
                titles.setdefault(name, []).extend(c.get("hook_text", "") for c in data.get("clips", []))
        summary.append(f"{name}: {made} new clip(s)" + (" (live)" if live else ""))
        if "CLAUDE_LIMIT" in out:
            summary.append("Claude usage limit reached: stopped; the same footage is retried next run")
            limit_hit = True
            break

    shutil.copyfile(HOME6 / "progress.json", STATE / "progress.json")
    for k in titles:
        titles[k] = [t for t in titles[k] if t][-200:]
    write_json(STATE / "titles.json", titles)
    (OUT / "RUN_SUMMARY.txt").write_text("\n".join(summary) + "\n", encoding="utf-8")
    report = [f"# Last run: {time.strftime('%Y-%m-%d %H:%M UTC', time.gmtime())}", "", "## Result", ""]
    report += [f"- {line}" for line in summary] or ["- nothing to report"]
    errs = list(dict.fromkeys(ERRORS))
    if errs:
        report += ["", "## Errors and warnings", ""] + [f"- `{e}`" for e in errs[:30]]
    setup_log = ROOT / "setup_log.txt"
    if setup_log.exists():
        tail = setup_log.read_text(encoding="utf-8", errors="replace").splitlines()[-25:]
        report += ["", "## Clipper setup (last lines)", "", "```", *tail, "```"]
    for name, text in clipper_tails:
        report += ["", f"## {name}: clipper output (last lines)", "", "```", *text, "```"]
    (STATE / "last_run.md").write_text("\n".join(report) + "\n", encoding="utf-8")
    log("\n" + "\n".join(summary))
    return 0 if not limit_hit else 0


if __name__ == "__main__":
    sys.exit(main())
