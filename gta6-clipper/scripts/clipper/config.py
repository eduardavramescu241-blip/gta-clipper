"""Settings. Defaults below; override any of them in ~/gta6-clips/config.json."""

import json
from pathlib import Path

import os
HOME = Path(os.environ["GTA6CLIP_HOME"]) if os.environ.get("GTA6CLIP_HOME") else Path.home() / "gta6-clips"

DEFAULTS = {
    # --- finding streams ---
    "game": "Grand Theft Auto VI",   # Twitch category name (official API only)
    "search": "GTA 6",               # YouTube search words
    "title_words": ["gta"],          # a watchlist VOD must have one of these in its title
    "max_age_hours": 36,             # ignore watchlist VODs older than this

    # --- download ---
    "max_height": 1080,

    # --- listening to the stream ---
    "scan_model": "tiny",            # fast pass over the whole stream (what Claude reads)
    "caption_model": "base",         # careful pass over each chosen clip (the captions)
    "language": "en",                # English captions only (campaign rule)
    "scan_block_minutes": 20,        # audio is decoded in blocks, so 10-hour streams fit in memory
    "loud_db": 6.0,                  # louder than the last 2 minutes by this much = a spike
    "chat": True,                    # YouTube replays: count chat messages per 5 s
    "chat_timeout": 420,

    # --- picking moments ---
    "clips_per_stream": 3,
    "min_duration": 20,
    "max_duration": 35,
    "chunk_minutes": 12,             # transcript window per Claude call
    "claude_parallel": 4,            # Claude calls at the same time (more = faster, more usage)
    "claude_model": None,            # None = your Claude Code default, or "sonnet" / "opus"

    # --- campaign (Lacy GTA 6 marathon clipping program) ---
    "max_new_hours": 0,              # --new-only: at most this many hours of new stream per run (0 = all)
    "max_silence": 4.5,              # longest pause without speech inside a clip (s)
    "no_swearing": True,             # mask swear words in captions/titles and mute them in the audio
    "must_mention": "",              # name that must appear in the hook bar and the caption ("" = off)
    "must_hashtags": [],             # hashtags every caption must carry
    "avoid_titles": [],              # hooks already made: pick different moments and ideas
    "game_max_x": None,              # stream layout: keep gameplay left of this fraction of the width (cuts a chat overlay on the right)
    "campaign_rules": "",           # filled per streamer in config.json; see CAMPAIGN_TEMPLATE
    "_unused_template": (
        "This clip is for {NAME}'s official clipping campaign for their GTA 6 streams. Follow these rules strictly:\n"
        "- LACY must be the main focus of the WHOLE clip (their voice, reaction or face), not just the start. "
        "Skip moments where someone else (a guest, a video, an NPC) carries the clip.\n"
        "- Prefer, in this order: funny moments, memorable quotes from LACY, other strong reactions or memorable moments.\n"
        "- NEVER portray LACY in a negative light. No clips of them angry at chat, insulting people, drama, "
        "embarrassing personal moments, or anything that could build a negative or false narrative (no hate farming).\n"
        "- hook_text and caption MUST contain the word LACY. hashtags MUST include #LACY.\n"
        "- Write hook_text and caption in English only.\n"
        "- kind may also be quote: a memorable line LACY says.\n"
    ),

    # --- framing ---
    "layout": "auto",                # auto | stream | face | fit
    "output_width": 1080,
    "output_height": 1920,
    "cam_height": 760,               # stream layout: height of the facecam panel on top
    "fit_aspect": 1.7778,            # fit layout: 1.7778 keeps the whole 16:9 frame (cams sit on edges)
    "track_smoothing": 5,

    # --- hook (the title bar) ---
    "hook_font_file": "auto",         # auto = Arial Bold from the system; or a path to any .ttf
    "hook_font_size": 54,
    "hook_y": 0.09,
    "hook_margin_x": 150,

    # --- captions ---
    "font": "Arial Black",
    "font_size": 82,
    "words_per_group": 4,
    "uppercase": True,
    "text_color": "FFFFFF",
    "highlight_color": "FFE13B",
    "outline_width": 6,
    "caption_y": 0.72,
    "word_pop": True,

    # --- encoding ---
    "encoder": "libx264",            # or h264_videotoolbox (Mac) / h264_nvenc, h264_qsv, h264_amf (Windows)
    "crf": 20,
    "preset": "medium",
    "audio_bitrate": "192k",
    "loudnorm": True,
}


def load(overrides=None):
    cfg = dict(DEFAULTS)
    path = HOME / "config.json"
    if path.exists():
        try:
            cfg.update(json.loads(path.read_text(encoding="utf-8-sig")))
        except json.JSONDecodeError as exc:
            raise SystemExit(f"{path} is not valid JSON: {exc}")
    for key, value in (overrides or {}).items():
        if value is not None:
            cfg[key] = value
    return cfg


CAMPAIGN_TEMPLATE = DEFAULTS.pop("_unused_template")


def campaign_text(cfg):
    """Campaign rules for the prompt, with the streamer's name filled in."""
    name = (cfg.get("must_mention") or "").strip()
    text = cfg.get("campaign_rules") or (CAMPAIGN_TEMPLATE if name else "")
    text = text.replace("{NAME}", name or "the streamer")
    if name:
        tags = cfg.get("must_hashtags") or []
        tags = tags if isinstance(tags, str) else " ".join(tags)
        text = text.replace("LACY", name).replace("#" + name, tags or "#" + name.replace(" ", ""))
    avoid = cfg.get("avoid_titles") or []
    avoid = [avoid] if isinstance(avoid, str) else avoid
    avoid = [t for t in avoid if t][-40:]
    if avoid:
        text += ("- These clips were ALREADY made. Pick different moments and avoid repeating "
                 "the same idea or wording: " + " | ".join(avoid) + "\n")
    return text
