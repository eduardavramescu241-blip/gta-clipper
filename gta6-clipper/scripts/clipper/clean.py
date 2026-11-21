"""No swearing: mask swear words in captions and titles, mute them in the audio."""

import re

# Stems; matched at the start of a word ("fucking", "shitty", "bitches", "motherfucker").
_STEMS = [
    "fuck", "fuk", "fck", "fuq", "motherf", "muthaf", "shit", "sh1t", "bullshit", "bitch",
    "asshole", "arsehole", "dumbass", "jackass", "bastard", "cunt", "dick", "cock", "pussy",
    "whore", "slut", "nigg", "fag", "retard", "wank", "twat", "prick", "goddamn", "damn",
]
_EXACT = {"ass", "arse", "asses", "wtf", "stfu", "af", "lmfao", "mf", "mfs", "hoe", "hoes", "tits"}
_SAFE = {"dickens", "cocktail", "cockpit", "peacock", "shitake", "assess", "assassin", "class"}

_WORD = re.compile(r"[A-Za-z0-9']+")


def is_swear(word):
    w = re.sub(r"[^a-z0-9]", "", word.lower())
    if not w or w in _SAFE:
        return False
    return w in _EXACT or any(w.startswith(s) for s in _STEMS)


def mask_word(word):
    """'Fucking!' -> 'F******!' (first letter kept, punctuation kept)."""
    def sub(m):
        t = m.group(0)
        return t[0] + "*" * (len(t) - 1) if is_swear(t) else t
    return _WORD.sub(sub, word)


def mask_text(text):
    return mask_word(text or "")


def clean_words(words, pad=0.08):
    """Mask swear words in caption words; return (words, [(start, end), ...] to mute)."""
    out, mute = [], []
    for w in words:
        if any(is_swear(t) for t in _WORD.findall(w["w"])):
            mute.append((max(0.0, w["s"] - pad), w["e"] + pad))
            w = dict(w, w=mask_word(w["w"]))
        out.append(w)
    merged = []
    for s, e in sorted(mute):
        if merged and s <= merged[-1][1]:
            merged[-1] = (merged[-1][0], max(merged[-1][1], e))
        else:
            merged.append((s, e))
    return out, merged


def mute_filter(spans):
    """ffmpeg audio filter that silences the given spans ('' when none)."""
    if not spans:
        return ""
    cond = "+".join(f"between(t,{s:.2f},{e:.2f})" for s, e in spans)
    return f"volume=0:enable='{cond}'"
