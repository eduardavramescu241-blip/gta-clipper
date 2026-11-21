---
name: "gta6-clipper"
description: GTA 6 stream clipper. Finds the biggest GTA 6 streams (YouTube, Twitch, Kick), listens to the whole stream on the user's computer, has Claude pick the moments that go viral (first reactions to GTA 6, crazy discoveries, insane reactions, funny fails, hot takes) using the transcript plus where the streamer got loud and where chat went off, then makes ready-to-post 9:16 clips with the facecam on top, gameplay below, a hook title bar and word-by-word captions, plus a POST.md with a caption and hashtags per clip. Several streams run at once; ~20 clips a day from 7 streams. Works on macOS and Windows. Runs on the user's own Claude subscription (no API keys, no per-clip fee; it does use subscription usage). Use whenever someone wants to clip GTA 6 (or GTA) streams or streamers, make Shorts/TikToks/Reels from a stream VOD, run clipping campaigns for streamers, or says "clip this stream", "find the best moments", "make clips from Kai Cenat / xQc / any streamer's GTA 6 stream".
---

# GTA 6 Clipper

Streams in, ready-to-post vertical clips out. **You run it; the user only gives links (or nothing: `--find`).**
`SKILL` = the folder this file is in. `RUN` = the command, by system:
- **macOS/Linux:** `bash SKILL/scripts/gta6clip`
- **Windows (PowerShell/cmd):** `py -3 SKILL\scripts\launch.py` (or `SKILL\scripts\gta6clip.cmd`)
Every example below uses `RUN`.
Everything it makes goes to `~/gta6-clips/<date>/<streamer>__<stream title>/`.

## 0. First use on a machine
`python3 SKILL/scripts/setup.py` (Windows: `py -3 SKILL\scripts\setup.py`) until it prints **All set**. It checks
Python 3.9+, ffmpeg, Claude Code, a JS runtime and disk; builds a private Python env in `~/.gta6-clipper`; downloads
Whisper tiny + base (~220 MB) and the facecam finder (0.2 MB, checksum-verified).
Install what's missing the free, official way: Mac `brew install ffmpeg deno`; Windows
`winget install Gyan.FFmpeg DenoLand.Deno`, then open a NEW terminal so PATH updates. Ask before anything needing admin rights.

## 1. What happens to each stream
1. **Audio only** of the whole stream is downloaded (a 4-hour stream ≈ 200-300 MB; video is NOT downloaded).
2. **Listen**: a fast local transcript (Whisper tiny) + loudness per second (yelling, screaming = spikes) + on
   YouTube replays, chat speed per 5 s (chat going off).
3. **Pick**: Claude (`claude -p`, the user's subscription) reads the transcript in 12-minute parts, 4 at a time,
   with `[LOUD +NdB]` and `[CHAT xN]` marks, and returns the strongest moments: `first_reaction`, `discovery`,
   `reaction`, `funny`, `take`, each with a hook title, caption, hashtags and a 1-100 score. Best N per stream kept.
4. **Make**: for each pick, only that minute of video is downloaded (1080p), lined up with the stream audio to the
   frame, framed 9:16 (facecam found automatically → cam on top, gameplay below; big face → follow it; no face →
   whole frame on blur), hook bar on the seam, exact word-by-word captions (Whisper base), loudness −14 LUFS.
5. `POST.md` (paste-ready caption + hashtags + where in the stream), `clips.json`, `report.json` (time per stage).

## 2. Run it
Run long jobs in the background and tell the user what's happening in plain words.
```bash
RUN URL                      # one stream, 3 clips
RUN URL URL URL --clips 4    # several streams, 2 at a time
RUN --find --list            # just show today's biggest GTA streams
RUN --find --streams 7       # find them and clip them (~21 clips)
RUN URL --section "2:00:00-4:00:00"   # only part of a long stream
```
| flag | use |
|---|---|
| `--clips N` | clips per stream (default 3) |
| `--streams N` | with `--find`: how many streams (default 5) |
| `--parallel N` | streams at the same time (default 2; 3+ on a strong Mac) |
| `--section A-B` | only that part (`h:mm:ss-h:mm:ss`); for live streams, clip the new hours only |
| `--cookies chrome` | use the browser login: **needed for Kick** and sub-only Twitch VODs (on Windows prefer `firefox`) |
| `--cookies-file F` | a `cookies.txt` exported from the browser; most reliable on Windows |
| `--layout stream/face/fit` | force a look (default `auto` decides per clip) |
| `--model sonnet` | a lighter Claude model for picking, to save usage |
| `--fast` | hardware encoding (Mac VideoToolbox; NVIDIA/Intel/AMD on Windows) if the machine has it, much faster |
| `--redo` | pick the moments again (keeps the downloaded audio) |
| `--keep-audio` | keep the audio after clipping (default: deleted to save disk) |

Re-running the same command resumes: finished steps are cached in `~/gta6-clips/work/`.

## 3. Finding streams (`--find`)
Sources, biggest first, one per streamer:
- **YouTube**: today's most-viewed long streams for "GTA 6 stream" (no key needed).
- **Watchlist** `~/gta6-clips/streamers.txt` (`twitch:login`, `youtube:@handle`): each one's newest VOD from the
  last 36 h with "GTA" in the title. Edit this list with the user: add the streamers they clip for.
- **Twitch top live GTA 6 streams**: only with the user's own free Twitch app key. Steps: dev.twitch.tv/console →
  Register Your Application (any name, redirect `http://localhost`, category Other) → copy Client ID, make a Client
  Secret → put `TWITCH_CLIENT_ID=...` and `TWITCH_CLIENT_SECRET=...` in `~/gta6-clips/.env`.
Until the game is out the finder mostly returns GTA 5 / countdown streams; after launch it's GTA 6.

## 4. Launch day playbook (GTA 6 releases Nov 19, 2026 on PS5 + Xbox Series; store listings show an unlock at local midnight, Rockstar has not officially announced a time)
- The night before: `--find --list` to see who's live; add the big GTA streamers to the watchlist.
- Every 2-3 hours: `--find --streams 7` (a live stream is clipped up to "now"; next run use `--section` from where
  the last run stopped, the times are in `report.json`). Offer to set this up with /loop. Each run uses Claude subscription usage (picking is the heavy part); `--model sonnet` and fewer streams lower it.
- First hours = **first reactions** (the opening, the first drive, the map, the first police chase). Post those first.
- A clip earns most in its first hours: post as soon as clips are out; watch each one before posting.

## 5. Before the user posts
Open each clip (or a frame from it) and check: the facecam crop shows the face, captions are readable, the hook bar
names the right streamer. The user posts; never post for them. `POST.md` has the caption for each.
Settings live in `~/gta6-clips/config.json` (any key from `scripts/clipper/config.py`, e.g. `clip lengths`,
`claude_parallel`, `cam_height`, caption colours).

## 6. Problems
- **"Sign in to confirm your age"** (many GTA streams on YouTube) → `--cookies chrome` (the browser the user is
  signed into YouTube with; macOS asks for keychain access once). **Kick 403** and **Twitch sub-only VODs** → same.
- **Windows: ffmpeg / claude / deno not found** → open a NEW terminal after installing; check with `ffmpeg -version`.
- **Windows: cookies error with chrome/edge/brave** → use `--cookies firefox` or `--cookies-file cookies.txt`.
- **Wrong caption font** → set `"font"` in `~/gta6-clips/config.json` to a font installed on the machine.
- **"sound match weak"** on a clip → the clip may be a second off; re-run with `--redo` or check that clip.
- **Slow listening** → long streams take ~1-2 min per hour of stream on an M-series Mac; use `--section`.
- **Claude found nothing** → low-energy stream; try another stream or `--clips` lower.
- **Disk** → ~0.1 GB per stream hour while working; audio is deleted after the clips are made.
