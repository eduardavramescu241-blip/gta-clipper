"""Downloads with yt-dlp. The whole stream is fetched as AUDIO only; video is fetched
only for the few minutes that become clips. A 6-hour stream costs ~300 MB, not ~10 GB."""

import glob
import json
import shutil
import urllib.parse
import urllib.request
from pathlib import Path

from .util import log, run


def base_args(url, cookies=None, cookie_file=None):
    """JS runtime for YouTube (else yt-dlp quietly drops good formats) + browser cookies."""
    args = []
    if "youtu" in url and not shutil.which("deno"):
        for runtime in ("node", "bun"):
            path = shutil.which(runtime)
            if path:
                args += ["--js-runtimes", f"{runtime}:{path}"]
                break
    if cookie_file:
        args += ["--cookies", str(cookie_file)]
    elif cookies:
        args += ["--cookies-from-browser", cookies]
    return args


def info(url, args, workdir):
    """Stream metadata (title, channel, length, live status). Cached."""
    cache = workdir / "info.json"
    if cache.exists():
        return json.loads(cache.read_text())
    raw = run(["yt-dlp", "-J", "--no-playlist", *args, url], timeout=180)
    full = json.loads(raw)
    keep = {k: full.get(k) for k in (
        "id", "title", "channel", "uploader", "duration", "view_count", "live_status",
        "was_live", "is_live", "webpage_url", "extractor_key", "timestamp", "release_timestamp",
    )}
    keep["name"] = keep.get("channel") or keep.get("uploader") or "stream"
    cache.write_text(json.dumps(keep, indent=2))
    return keep


LIVE_URLS = set()   # streams still live: read through a frozen copy of their playlist

FFMPEG_NET = ["-protocol_whitelist", "file,http,https,tcp,tls,crypto"]


def frozen_playlist(url, args, fmt, dest):
    """A live broadcast's playlist keeps growing, so yt-dlp/ffmpeg wait for the stream to
    end. Save the playlist as it is NOW, with absolute segment links and an end marker:
    then it reads like a finished VOD (finite and seekable)."""
    out = run(["yt-dlp", "--no-playlist", "-g", "-f", fmt, *args, url], timeout=180)
    m3u8 = [l.strip() for l in out.splitlines() if l.strip().startswith("http")]
    if not m3u8:
        raise RuntimeError("could not get the stream's playlist link")
    src = m3u8[0]
    req = urllib.request.Request(src, headers={"User-Agent": "Mozilla/5.0"})
    text = urllib.request.urlopen(req, timeout=60).read().decode("utf-8", "replace")
    lines, segs = [], 0
    for line in text.splitlines():
        line = line.strip()
        if not line or line.startswith("#EXT-X-ENDLIST") or line.startswith("#EXT-X-PLAYLIST-TYPE"):
            continue
        if line.startswith("#EXT-X-MAP:") and 'URI="' in line:
            a, b = line.split('URI="', 1)
            uri, rest = b.split('"', 1)
            line = f'{a}URI="{urllib.parse.urljoin(src, uri)}"{rest}'
        elif not line.startswith("#"):
            line = urllib.parse.urljoin(src, line)
            segs += 1
        lines.append(line)
    if not segs:
        raise RuntimeError("the stream's playlist has no segments yet")
    lines.insert(1, "#EXT-X-PLAYLIST-TYPE:VOD")
    lines.append("#EXT-X-ENDLIST")
    dest.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return dest


def audio(url, args, workdir):
    """The whole stream's audio. Reused if already downloaded. (Always the full audio:
    YouTube throttles partial downloads, so a slice is slower than the whole thing.)"""
    done = [p for p in workdir.glob("audio.*") if not p.name.endswith((".part", ".ytdl"))]
    if done and url not in LIVE_URLS:   # a live stream has grown since: always fetch it fresh
        log(f"reusing downloaded audio ({done[0].stat().st_size / 1e6:.0f} MB)", "ok")
        return done[0]
    log("downloading the stream's audio (video comes later, only for the clips)...", "step")
    if url in LIVE_URLS:
        for leftover in workdir.glob("audio.*"):
            leftover.unlink(missing_ok=True)
        plist = frozen_playlist(url, args, "ba/wa/w", workdir / "live_audio.m3u8")
        tmp = workdir / "audio_tmp.m4a"
        run(["ffmpeg", "-y", "-v", "error", "-nostdin", *FFMPEG_NET, "-i", str(plist),
             "-vn", "-c:a", "copy", "-bsf:a", "aac_adtstoasc", str(tmp)], timeout=7200)
        tmp.rename(workdir / "audio.m4a")
        done = [workdir / "audio.m4a"]
        log(f"audio: {done[0].stat().st_size / 1e6:.0f} MB (stream so far)", "ok")
        return done[0]
    run(["yt-dlp", "--no-playlist", "-f", "ba/wa/w", "-o", str(workdir / "audio.%(ext)s"),
         "--newline", "-N", "4", *args, url], timeout=7200)
    done = [p for p in workdir.glob("audio.*") if not p.name.endswith((".part", ".ytdl"))]
    if not done:
        raise RuntimeError("yt-dlp finished but no audio file appeared")
    log(f"audio: {done[0].stat().st_size / 1e6:.0f} MB", "ok")
    return done[0]


def section(url, args, start, end, dest, cfg):
    """Video for one clip only: [start, end] seconds of the stream."""
    if dest.exists() and dest.stat().st_size > 10000:
        return dest
    h = cfg["max_height"]
    for leftover in glob.glob(str(dest) + "*"):
        Path(leftover).unlink(missing_ok=True)
    if url in LIVE_URLS:
        plist = frozen_playlist(url, args, f"b[height<={h}]/b", dest.with_suffix(".m3u8"))
        run(["ffmpeg", "-y", "-v", "error", "-nostdin", *FFMPEG_NET, "-ss", f"{start:.2f}",
             "-i", str(plist), "-t", f"{end - start:.2f}", "-c", "copy",
             "-bsf:a", "aac_adtstoasc", "-movflags", "+faststart", str(dest)], timeout=1800)
        if not dest.exists():
            raise RuntimeError(f"no video came back for {start:.0f}-{end:.0f}s")
        return dest
    run([
        "yt-dlp", "--no-playlist",
        "-f", f"bv*[height<={h}]+ba/b[height<={h}]/bv*+ba/b",
        "--merge-output-format", "mp4",
        "--download-sections", f"*{start:.2f}-{end:.2f}",
        "-o", str(dest), *args, url,
    ], timeout=1800)
    if not dest.exists():
        raise RuntimeError(f"no video came back for {start:.0f}-{end:.0f}s")
    return dest
