# GTA 6 Clipper: a Claude Code skill (macOS + Windows)

Give it GTA 6 streams, or let it find the biggest ones itself, and it gives you ready-to-post vertical clips:
the streamer's first reactions, crazy discoveries, insane reactions and funny moments, each with the facecam on
top, gameplay below, a hook title and word-by-word captions. Every clip comes with a caption and hashtags to paste.

- **It reads the whole stream for you.** It listens to every minute, marks where the streamer got loud and where
  chat went off, and Claude picks the moments worth posting.
- **Several streams at once.** `--find --streams 7` ≈ 21 clips.
- **No per-clip fee.** Transcribing and rendering run on your computer. Picking the moments sends transcript text to Claude
  through your own subscription (it uses some of your usage). No API keys.
- **Small downloads.** Only the stream's audio plus the minutes that become clips (≈0.1 GB per stream hour).

## Install
Download the zip (don't unzip it), open Claude Code in a new session and paste this:

> Install the skill in the zip file gta6-clipper-skill.zip in my Downloads folder: unzip it into
> ~/.claude/skills/ so the folder is ~/.claude/skills/gta6-clipper, then run
> `bash ~/.claude/skills/gta6-clipper/scripts/setup.sh` until it prints "All set" (install anything it
> says is missing the free, official way, like `brew install ffmpeg deno`). Then run
> `bash ~/.claude/skills/gta6-clipper/scripts/gta6clip --find --list` and tell me what it found.

Windows: use `winget install Gyan.FFmpeg DenoLand.Deno` instead of brew, then run
`py -3 %USERPROFILE%\.claude\skills\gta6-clipper\scripts\setup.py` and later `...\scripts\launch.py`.

Setup checks ffmpeg, Claude Code and disk space, installs what it needs (~0.5 GB) and prints **All set**.
Then say: *"clip this stream: <link>"* or *"find today's biggest GTA 6 streams and clip them"*.

Needs Claude Code, Python 3.9+, `ffmpeg` and `deno` or `node`. Mac: `brew install ffmpeg deno`. Windows: `winget install Gyan.FFmpeg DenoLand.Deno`.
On Windows, Chrome-family browsers often block cookie reading: use `--cookies firefox` or `--cookies-file`.

## Good to know
- Age-restricted YouTube streams (common with GTA) and Kick need your browser login: add `--cookies chrome`.
- Your list of streamers to check is `~/gta6-clips/streamers.txt`. Put the streamers you clip for in it.
- Twitch's live top list needs your own free Twitch app key (steps in SKILL.md). Without it, YouTube search and
  your watchlist still work.
- Watch each clip before you post it. Clip streamers who are fine with clipping; most big ones run clipping
  programs and pay per view.

Layout: `SKILL.md` (what Claude follows) · `scripts/launch.py` / `gta6clip` / `gta6clip.cmd` (the command) · `scripts/setup.py` ·
`scripts/clipper/` (find, fetch, scan, moments, layout, render, captions, hook) · `streamers.txt` (default watchlist).
