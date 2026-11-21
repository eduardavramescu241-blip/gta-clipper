"""Pick the moments worth clipping. Claude reads the stream's transcript, marked where
the streamer got loud and where chat went off, through your own `claude` CLI, so it
runs on your Claude subscription. Windows are read in parallel."""

import json
import re
import shutil
import subprocess
from concurrent.futures import ThreadPoolExecutor

import numpy as np

from .config import campaign_text
from .util import clean_env, log

PROMPT = """You clip livestreams for TikTok, Reels and YouTube Shorts and you are paid per \
view. This is part of a stream by {streamer}, titled "{title}". The game is GTA 6 \
(Grand Theft Auto VI), the biggest game launch in years, so moments about GTA 6 travel \
furthest.

Below is a timestamped transcript (seconds). It mixes the streamer's voice with game, \
trailer and video audio, so judge who is talking from context. Markers on a line:
- [LOUD +NdB] the audio jumped N dB above the last two minutes (yelling, screaming, hype)
- [CHAT xN] chat was moving N times faster than usual (the audience reacted)
Markers are strong hints, not proof: a loud gunshot is not a reaction.

Find the {want} STRONGEST standalone clips in this excerpt. What wins for GTA 6:
- first_reaction: the first time they see or play something in GTA 6, their honest first words
- discovery: they find or notice something crazy, hidden or unexpected in the game
- reaction: an insane reaction, losing it, screaming, speechless, jumping out of the chair
- funny: a fail, a chaotic moment, a roast, a bit that makes people send it to a friend
- take: a strong opinion about GTA 6 (best game ever, worth the wait...)
- quote: a memorable, quotable line the streamer says

A clip works when it opens on the hook (never on "uh so yeah"), makes sense with zero \
context, and pays off before it ends. Reject: menus, loading, reading donations, \
sponsor reads, quiet stretches, anything whose payoff is outside this excerpt. \
Also reject moments where the screen mostly shows a title card, a game or brand logo, \
a countdown or start screen, or a sponsor overlay: clips must show gameplay or the streamer. \
Vary the picks: different kinds of moments, different hook wording. \
Prefer moments with little or no swearing (swear words get muted), and never put swear words \
in hook_text, caption or title.

Rules:
- start and end are seconds inside {lo:.0f}-{hi:.0f}, {min_d}-{max_d} s long, no overlaps.
- start = the moment the first attention-grabbing line, reaction or visual begins (at most \
1 s before it). No warm-up, greetings, menus or quiet build-up before it: viewers decide in \
the first 2 seconds, and about half swipe away by second 3 when a clip opens on setup. \
If the moment needs context, open on its most intriguing line and let the context follow.
- No stretch longer than 3 s without the streamer talking or reacting. End right after the \
payoff (the laugh or reaction), never on a quiet game screen.
- Favour hooks people react to: "imagine if..." ideas, funny comparisons ("GTA 6 is just X"), \
relatable reactions; avoid slow scenes where the streamer is quiet.
- Fewer than {want} is fine if fewer are genuinely strong.

Return ONLY a JSON array, no prose, no code fence:
[{{"start": 1312.5, "end": 1349.0, "kind": "reaction",
  "title": "short internal name",
  "hook_text": "TIM sees the GTA 6 MAP for the FIRST TIME 😭",
  "caption": "a post caption that drives comments, under 150 chars",
  "hashtags": ["#gta6", "#gtavi", "#timthetatman"],
  "score": 88,
  "reason": "one sentence on why this will hold attention"}}]

score is 1-100 predicted retention; be harsh, 85+ only for clips you'd bet on.
hook_text is the title bar on top of the video and decides if people stop scrolling:
4-12 words, casual, name the streamer, CAPITALISE the 2-3 words carrying the drama, \
tease the payoff instead of stating it, a 😭 or 💀 only when it's funny. \
No "INSANE MOMENT YOU WON'T BELIEVE" clickbait without specifics.

{campaign}
TRANSCRIPT:
{transcript}
"""


def _enforce(m, cfg):
    """Make sure every pick carries the campaign's required name and hashtags (and no swearing)."""
    if cfg.get("no_swearing", True):
        from .clean import mask_text
        for k in ("hook_text", "caption", "title"):
            if m.get(k):
                m[k] = mask_text(m[k])
    name = (cfg.get("must_mention") or "").strip()
    if name:
        hook = str(m.get("hook_text") or "").strip()
        if name.lower() not in hook.lower():
            m["hook_text"] = f"{name} {hook}".strip()
        cap = str(m.get("caption") or "").strip()
        if name.lower() not in cap.lower():
            m["caption"] = f"{name}: {cap}".strip()
    tags = [t if str(t).startswith("#") else "#" + str(t) for t in (m.get("hashtags") or [])]
    must = cfg.get("must_hashtags") or []
    must = [must] if isinstance(must, str) else list(must)
    seen, out = set(), []
    for t in must + tags:
        if t.lower() not in seen:
            seen.add(t.lower())
            out.append(t)
    m["hashtags"] = out
    return m


def _lines(words, loud, chat, cfg, line_seconds=8):
    """~8 s lines with [LOUD]/[CHAT] markers. Cheap in tokens, easy to read."""
    lines, cur, start = [], [], None
    chat_base = float(np.median([c for c in chat if c > 0])) if chat and any(chat) else 0

    def flush(t0, t1, text):
        tags = []
        if len(loud):
            a, b = int(t0), max(int(t0) + 1, int(np.ceil(t1)))
            peak = float(np.max(loud[a:b])) if a < len(loud) else 0
            if peak >= cfg["loud_db"]:
                tags.append(f"[LOUD +{peak:.0f}dB]")
        if chat_base:
            a, b = int(t0 // 5), int(t1 // 5) + 2      # chat lags the moment a little
            seg = chat[a:b]
            if seg:
                ratio = max(seg) / chat_base
                if ratio >= 2.5:
                    tags.append(f"[CHAT x{ratio:.0f}]")
        lines.append((t0, (" ".join(tags) + " " if tags else "") + text))

    for w in words:
        if start is None:
            start = w["s"]
        cur.append(w["w"])
        if w["e"] - start >= line_seconds:
            flush(start, w["e"], " ".join(cur))
            cur, start = [], None
    if cur:
        flush(start, words[-1]["e"], " ".join(cur))
    return lines


LIMIT_WORDS = ("usage limit", "limit reached", "rate limit", "rate_limit", "quota",
               "out of credits", "credit balance", "limit will reset", "too many requests", "429")


def _ask(prompt, cfg):
    cmd = [shutil.which("claude") or "claude", "-p"]
    if cfg.get("claude_model"):
        cmd += ["--model", cfg["claude_model"]]
    proc = subprocess.run(cmd, input=prompt, capture_output=True, text=True, encoding="utf-8",
                          errors="replace", timeout=600, env=clean_env())
    if proc.returncode != 0:
        raise RuntimeError(f"claude -p failed: {(proc.stderr or proc.stdout or '').strip()[:300]}")
    return proc.stdout


def _parse(raw):
    text = raw.strip()
    fence = re.search(r"```(?:json)?\s*(.+?)```", text, re.S)
    if fence:
        text = fence.group(1).strip()
    if not text.startswith("["):
        m = re.search(r"\[\s*\{.*\}\s*\]", text, re.S)
        if not m:
            return []
        text = m.group(0)
    try:
        out = json.loads(text)
    except json.JSONDecodeError:
        return []
    return out if isinstance(out, list) else []


def _snap(m, words, cfg):
    """Move Claude's rough times onto real word edges; enforce the length limits."""
    start, end = float(m["start"]), float(m["end"])
    near = [w for w in words if w["s"] >= start - 1.5]
    if not near:
        return None
    first = min(near, key=lambda w: abs(w["s"] - start))
    inside = [w for w in words if first["s"] <= w["s"] and w["e"] <= end + 1.5]
    if not inside:
        return None
    last = min(inside, key=lambda w: abs(w["e"] - end))
    lo, hi = cfg["min_duration"], cfg["max_duration"]
    if last["e"] - first["s"] > hi:
        fit = [w for w in inside if w["e"] - first["s"] <= hi]
        if not fit:
            return None
        ends = [w for w in fit if w["w"].rstrip().endswith((".", "!", "?"))]
        last = ends[-1] if ends else fit[-1]
    if last["e"] - first["s"] < lo:
        after = [w for w in words if w["e"] > last["e"] and w["e"] - first["s"] <= hi]
        reach = [w for w in after if w["e"] - first["s"] >= lo]
        if reach:
            last = reach[0]
        elif after:
            last = after[-1]
        if last["e"] - first["s"] < lo:
            return None
    # Dead air: a long silence early on loses viewers, so reject; later on, end the clip before it.
    span = [w for w in words if first["s"] <= w["s"] and w["e"] <= last["e"]]
    gap_max = cfg.get("max_silence", 4.5)
    for a, b in zip(span, span[1:]):
        if b["s"] - a["e"] > gap_max:
            if a["e"] - first["s"] >= lo:
                last = a
                break
            return None
    m["start"] = round(max(0.0, first["s"] - 0.25), 2)
    m["end"] = round(min(last["e"] + 0.7, m["start"] + hi), 2)
    return m


def _dedupe(cands):
    kept = []
    for m in sorted(cands, key=lambda m: -float(m.get("score", 0))):
        span = m["end"] - m["start"]
        if all(min(m["end"], k["end"]) - max(m["start"], k["start"])
               <= 0.3 * min(span, k["end"] - k["start"]) for k in kept):
            kept.append(m)
    return kept


def find(scan, loud_rel, chat, workdir, cfg, stream):
    cache = workdir / "moments.json"
    if cache.exists():
        found = json.loads(cache.read_text())
        log(f"reusing {len(found)} picked moment(s)", "ok")
        return found

    words = scan["words"]
    lines = _lines(words, loud_rel, chat or [], cfg)
    first, total = words[0]["s"], words[-1]["e"]
    window = cfg["chunk_minutes"] * 60
    chunks = []
    for i in range(int(np.ceil((total - first) / window))):
        lo, hi = first + i * window, min(first + (i + 1) * window, total)
        body = [f"[{t:.1f}] {text}" for t, text in lines if lo <= t < hi]
        if sum(len(b.split()) for b in body) >= 30:
            chunks.append((lo, hi, "\n".join(body)))
    if not chunks:
        raise RuntimeError("not enough talking in this stream to clip")

    want = max(2, min(5, round(cfg["clips_per_stream"] / len(chunks)) + 2))
    log(f"Claude is reading {len(chunks)} part(s) of the stream, "
        f"{cfg['claude_parallel']} at a time...", "step")

    def work(chunk):
        lo, hi, body = chunk
        prompt = PROMPT.format(
            streamer=stream["name"], title=stream["title"], want=want, lo=lo, hi=hi,
            min_d=cfg["min_duration"], max_d=cfg["max_duration"], transcript=body,
            campaign=campaign_text(cfg))
        try:
            got = _parse(_ask(prompt, cfg))
        except (RuntimeError, subprocess.TimeoutExpired) as exc:
            text = str(exc).lower()
            if any(w in text for w in LIMIT_WORDS):
                limited.append(str(exc)[:200])
            log(f"  part {lo / 60:.0f}-{hi / 60:.0f} min skipped: {str(exc)[:120]}", "warn")
            return []
        ok = []
        for m in got:
            try:
                if lo - 5 <= float(m["start"]) < hi + 30:
                    s = _snap(m, words, cfg)
                    if s:
                        ok.append(_enforce(s, cfg))
            except (KeyError, TypeError, ValueError):
                continue
        return ok

    limited = []
    cands = []
    with ThreadPoolExecutor(max_workers=max(1, int(cfg["claude_parallel"]))) as pool:
        for got in pool.map(work, chunks):
            cands += got
    if limited:   # picks would be incomplete: stop and redo this part on a later run
        raise RuntimeError("CLAUDE_LIMIT: Claude usage limit reached (" + limited[0] + ")")
    if not cands:
        raise RuntimeError("Claude found nothing strong enough to clip in this stream")

    chosen = _dedupe(cands)[: cfg["clips_per_stream"]]
    log(f"picked {len(chosen)} of {len(cands)} candidate moments", "ok")
    cache.write_text(json.dumps(chosen, indent=2))
    (workdir / "candidates.json").write_text(json.dumps(cands, indent=2))
    return chosen
