import re
from typing import List, Dict, Optional
from wordfreq import zipf_frequency

TOKEN_RE = re.compile(r"^[A-Z0-9]{1,8}$", re.IGNORECASE)
ENGLISH_ZIPF_THRESHOLD = 2.0

STOPWORDS = {
    # ... (same as your previous list)
    "LG", "ELECTRONICS", "INC", "COPYRIGHT", "ALL", "RIGHTS", "RESERVED", "LGE",
    "TRAINING", "SERVICE", "PURPOSES", "ONLY", "INTERNAL", "USE",
    "2015","2016","2017","2018","2019","2020","2021","2022","2014",
    "LAN","GENDER","WHITE","BLACK",
    "EXPLODED","VIEW","IMPORTANT","SAFETY","NOTICE","MANY","ELECTRICAL",
    "MECHANICAL","PARTS","IN","THIS","CHASSIS","HAVE","RELATED",
    "CHARACTERISTICS","THESE","ARE","IDENTIFIED","BY","IT","IS","ESSENTIAL",
    "SPECIAL","SHOULD","BE","REPLACED","WITH","SAME","COMPONENTS","AS",
    "RECOMMENDED","MANUAL","PREVENT","FIRE","OR","OTHER","HAZARDS","DO",
    "NOT","MODIFY","THE","ORIGINAL","DESIGN","WITHOUT","PERMISSION","OF",
    "MANUFACTURER","SHOCK","THAT","TO","MRC","MODULE","REPAIR","CENTER",
    "OPTICAL","SHEET","ITEM","LOCATION","STATUS","UNDER",
    "PANEL","ASS'Y","POL","REAR","FRONT","COF","SOURCE","PCB",
    "LEFT","RIGHT","ASS","FOR","SIDE","STAND","SCREW","BOARD"
}

def _is_common_english_word(token: str) -> bool:
    if any(ch.isdigit() for ch in token):
        return False
    return zipf_frequency(token.lower(), "en") >= ENGLISH_ZIPF_THRESHOLD

def _leading_zero_shift_numeric(s: str) -> Optional[str]:
    if not s.isdigit():
        return None
    leading = len(s) - len(s.lstrip("0"))
    stripped = s.lstrip("0")
    if stripped == "":
        return None
    return stripped + ("0" * leading)

def _normalize_token(raw: str) -> Optional[str]:
    if raw is None:
        return None
    t = raw.strip().upper()
    if t.isdigit():
        mapped = _leading_zero_shift_numeric(t)
        if mapped is None:
            return None
        t = mapped
    if t.startswith("N") and len(t) >= 3:
        if t[-2] == "O":
            t = t[:-2] + "0" + t[-1]
    return t

def extract_part_boxes(words: List[Dict], bom_refs: set) -> List[Dict]:
    """
    Returns a list of dicts for each detected part number:
    {
        'token': str,
        'x': float,
        'y': float,
        'w': float,
        'h': float,
        'color': 'green' or 'red'
    }
    Only part numbers (not noise) are included.
    """
    candidates = []
    for w in words:
        raw = (w.get("text") or "").strip()
        if raw == "":
            continue
        token = re.sub(r"^[^A-Za-z0-9]+|[^A-Za-z0-9]+$", "", raw)
        if token == "":
            continue
        if not TOKEN_RE.match(token):
            continue
        candidates.append({
            "raw": token,
            "y": float(w.get("y", 0)),
            "meta": w
        })

    # Exclude bottom-most pure-numeric token (likely page number)
    page_candidate_index = None
    max_y = -1.0
    for idx, c in enumerate(candidates):
        raw = c["raw"]
        if re.fullmatch(r"\d{1,2}", raw):
            if c["y"] > max_y:
                max_y = c["y"]
                page_candidate_index = idx

    found = []
    for idx, c in enumerate(candidates):
        if page_candidate_index is not None and idx == page_candidate_index:
            continue
        raw = c["raw"].upper()
        token = _normalize_token(raw)
        if not token:
            continue
        if token.isdigit():
            if len(token) < 1 or len(token) > 4:
                continue
            # Do NOT filter numeric tokens by stopwords or English word
        else:
            if raw in STOPWORDS:
                continue
            if _is_common_english_word(raw):
                continue
            if len(token) < 2 or len(token) > 8:
                continue

        color = "green" if token in bom_refs else "red"
        box = c["meta"].copy()
        box.update({"token": token, "color": color})
        found.append(box)

    # Sort: numeric first, then alphanumeric
    def _sort_key(x: Dict):
        t = x["token"]
        return (0, int(t)) if t.isdigit() else (1, t)
    return sorted(found, key=_sort_key)