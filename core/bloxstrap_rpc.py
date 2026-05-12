"""Rich Presence biome extraction — tolerant of real Bloxstrap / Fishstrap log output.

F9 console can mirror RPC; logs under ``%LOCALAPPDATA%\\Roblox\\logs`` may use slightly
different JSON shape than the old ``}}}`` slice in MultiScope-V1.
"""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

_REPO_MULTISCOPE_BIOMES = (
    Path(__file__).resolve().parent.parent / "reference" / "multiscope" / "assets" / "biomes.json"
)

# Line may be "[BloxstrapRPC] {...}" or prefixed with timestamps
_BLOX_MARKER = re.compile(r"\[?\s*BloxstrapRPC\s*\]?", re.IGNORECASE)

# Grab hoverText without full JSON parse (escape-aware)
_HOVER_TEXT_RE = re.compile(
    r'"hoverText"\s*:\s*"((?:\\.|[^"\\])*)"',
    re.MULTILINE | re.DOTALL,
)

_LARGE_KEY_RE = re.compile(
    r'"largeImage"\s*:\s*(\{[^}]*"hoverText"\s*:\s*"((?:\\.|[^"\\])*)"[^}]*\})',
    re.MULTILINE | re.DOTALL,
)

_AURA_FROM_HOVER_PATTERNS = [
    re.compile(r"\baura\s*[:\-]\s*(?P<aura>[A-Za-z0-9 _'\-]{2,64})", re.IGNORECASE),
    re.compile(r"\bequipped\s*[:\-]?\s*(?P<aura>[A-Za-z0-9 _'\-]{2,64})\s+aura\b", re.IGNORECASE),
    re.compile(r"\baura\s+equipped\s*[:\-]?\s*(?P<aura>[A-Za-z0-9 _'\-]{2,64})", re.IGNORECASE),
]
_AURA_FROM_STATE_PATTERNS = [
    re.compile(r"^\s*equipped\s+_?none_?\s*$", re.IGNORECASE),
    re.compile(r"^\s*in\s+main\s+menu\s*$", re.IGNORECASE),
]


def _load_hover_to_slug() -> dict[str, str]:
    aliases: dict[str, str] = {}
    if _REPO_MULTISCOPE_BIOMES.exists():
        try:
            data = json.loads(_REPO_MULTISCOPE_BIOMES.read_text(encoding="utf-8"))
            for key in data:
                if isinstance(key, str) and key.startswith("_"):
                    continue
                ku = key.strip().upper()
                ks = " ".join(key.strip().lower().replace("_", " ").split())
                aliases[ku] = ks
        except (OSError, json.JSONDecodeError):
            pass
    fallback = (
        ("WINDY", "windy"), ("RAINY", "rainy"), ("SNOWY", "snowy"), ("HEAVEN", "heaven"),
        ("HELL", "hell"), ("STARFALL", "starfall"), ("CORRUPTION", "corruption"),
        ("SAND STORM", "sand storm"), ("NULL", "null"), ("GLITCHED", "glitched"),
        ("DREAMSPACE", "dreamspace"), ("CYBERSPACE", "cyberspace"), ("NORMAL", "normal"),
        ("EGGLAND", "eggland"), ("EGGLAN", "eggland"), ("AURORA", "aurora"),
    )
    for k, v in fallback:
        aliases.setdefault(k, v)
    return aliases


_HOVER_SLUG = _load_hover_to_slug()


def _strip_game_title_suffix(hover_text: str) -> str:
    """Discord often shows ``Rainy • Sol's RNG`` or ``|`` variants."""
    s = hover_text.strip()
    for sep in ("•", "·", "|", "—", "–", " - "):
        if sep in s:
            s = s.split(sep)[0].strip()
    return s


def _balanced_json_from(text: str, start_idx: int) -> str | None:
    """Slice one JSON object beginning at ``text[start_idx] == '{'``."""
    if start_idx < 0 or start_idx >= len(text) or text[start_idx] != "{":
        return None
    depth = 0
    in_string = False
    escape = False
    for i in range(start_idx, len(text)):
        ch = text[i]
        if in_string:
            if escape:
                escape = False
            elif ch == "\\":
                escape = True
            elif ch == '"':
                in_string = False
            continue
        if ch == '"':
            in_string = True
            continue
        if ch == "{":
            depth += 1
        elif ch == "}":
            depth -= 1
            if depth == 0:
                return text[start_idx : i + 1]
    return None


def _last_marker_slice(log_text: str) -> str | None:
    """Text from the **last** BloxstrapRPC marker onward (whole tail chunk)."""
    if not log_text:
        return None
    best = -1
    for m in _BLOX_MARKER.finditer(log_text):
        best = max(best, m.start())
    if best == -1:
        return None
    return log_text[best : max(best + 1, len(log_text))]


def _hover_from_json_obj(data: dict[str, Any]) -> str | None:
    stack: list[Any] = [data]
    while stack:
        obj = stack.pop()
        if isinstance(obj, dict):
            for key in ("largeImage", "smallImage"):
                li = obj.get(key)
                if isinstance(li, dict):
                    h = li.get("hoverText")
                    if isinstance(h, str) and h.strip():
                        return h.strip()
            stack.extend(obj.values())
        elif isinstance(obj, list):
            stack.extend(obj)
    return None


def hover_text_from_fragment(fragment: str) -> str | None:
    """Best-effort hoverText from RPC tail (JSON + regex fallbacks)."""
    # 1) Balanced brace parse from first '{'
    brace = fragment.find("{")
    if brace != -1:
        chunk = _balanced_json_from(fragment, brace)
        if chunk:
            try:
                parsed = json.loads(chunk)
                h = _hover_from_json_obj(parsed)
                if h:
                    return h
            except json.JSONDecodeError:
                pass

    # 2) Regex hoverText captures (take last plausible match — closest to newest RPC)
    hovers = _HOVER_TEXT_RE.findall(fragment)
    if hovers:
        raw = hovers[-1].replace(r"\"", '"').strip()
        if raw:
            try:
                raw = raw.encode("utf-8", "surrogateescape").decode("unicode_escape")
            except (UnicodeDecodeError, UnicodeEncodeError):
                pass
            if raw.strip():
                return raw.strip()

    lm = list(_LARGE_KEY_RE.finditer(fragment))
    if lm:
        raw = lm[-1].group(2).strip()
        if raw:
            return raw
    return None


def state_text_from_fragment(fragment: str) -> str | None:
    # Prefer JSON parse first
    brace = fragment.find("{")
    if brace != -1:
        chunk = _balanced_json_from(fragment, brace)
        if chunk:
            try:
                parsed = json.loads(chunk)
                state = parsed.get("data", {}).get("state")
                if isinstance(state, str) and state.strip():
                    return state.strip()
            except json.JSONDecodeError:
                pass
            except Exception:
                pass

    # Regex fallback
    m = re.findall(r'"state"\s*:\s*"((?:\\.|[^"\\])*)"', fragment, re.MULTILINE | re.DOTALL)
    if m:
        raw = m[-1].replace(r"\"", '"').strip()
        if raw:
            try:
                raw = raw.encode("utf-8", "surrogateescape").decode("unicode_escape")
            except (UnicodeDecodeError, UnicodeEncodeError):
                pass
            if raw.strip():
                return raw.strip()
    return None


def extract_rpc_block(log_tail: str) -> str | None:
    frag = _last_marker_slice(log_tail)
    return frag


def hover_text_from_rpc(rpc_fragment: str) -> str | None:
    return hover_text_from_fragment(rpc_fragment)


def biome_slug_from_hover(hover_text: str) -> str | None:
    base = _strip_game_title_suffix(hover_text)
    collapsed = " ".join(base.strip().upper().replace("_", " ").split())
    if collapsed in _HOVER_SLUG:
        return _HOVER_SLUG[collapsed]
    without_biome_suffix = collapsed[: -len(" BIOME")] if collapsed.endswith(" BIOME") else None
    if without_biome_suffix and without_biome_suffix in _HOVER_SLUG:
        return _HOVER_SLUG[without_biome_suffix]
    lc = collapsed.lower()
    for slug in sorted(set(_HOVER_SLUG.values()), key=len, reverse=True):
        su = slug.upper()
        if su == collapsed or collapsed.startswith(su + " ") or collapsed.endswith(" " + su):
            return slug
        if lc == slug:
            return slug
    return None


def biome_from_log_tail(log_tail: str) -> tuple[str | None, str | None]:
    frag = extract_rpc_block(log_tail)
    if not frag:
        return None, None
    hover = hover_text_from_fragment(frag)
    if not hover:
        return None, None
    slug = biome_slug_from_hover(hover)
    return slug, hover


def aura_from_hover(hover_text: str | None) -> str | None:
    if not hover_text:
        return None
    text = " ".join(hover_text.split())
    for pat in _AURA_FROM_HOVER_PATTERNS:
        m = pat.search(text)
        if not m:
            continue
        aura = " ".join((m.group("aura") or "").split()).strip(" .,:;!-[](){}")
        if aura and len(aura) >= 2:
            return aura

    # Common RPC format: "Aegis Equipped" or "Equipped: Aegis"
    if "equipped" in text.lower():
        cleaned = re.sub(r"\bequipped\b", "", text, flags=re.IGNORECASE).strip(" .,:;!-[](){}")
        cleaned = " ".join(cleaned.split())
        if cleaned and len(cleaned) >= 2 and len(cleaned) <= 64:
            return cleaned
    return None


def aura_from_state(state_text: str | None) -> str | None:
    if not state_text:
        return None
    state = " ".join(state_text.split())
    for deny in _AURA_FROM_STATE_PATTERNS:
        if deny.match(state):
            return None

    # fishSol-style state tends to be aura name directly, sometimes wrapped/escaped.
    cleaned = state.replace('\\"', '"').strip(" .,:;!-[](){}")
    if cleaned.lower().startswith("equipped "):
        cleaned = cleaned[len("equipped "):].strip(" .,:;!-[](){}")
    if cleaned.lower().startswith("equipped:"):
        cleaned = cleaned[len("equipped:"):].strip(" .,:;!-[](){}")
    if cleaned.lower().startswith("aura equipped:"):
        cleaned = cleaned[len("aura equipped:"):].strip(" .,:;!-[](){}")
    if cleaned.startswith('"') and cleaned.endswith('"') and len(cleaned) > 1:
        cleaned = cleaned[1:-1].strip()
    if cleaned:
        return cleaned[:64]
    return None


def aura_from_log_tail(log_tail: str) -> str | None:
    frag = extract_rpc_block(log_tail)
    if not frag:
        return None
    state = state_text_from_fragment(frag)
    aura_from_rpc_state = aura_from_state(state)
    if aura_from_rpc_state:
        return aura_from_rpc_state
    hover = hover_text_from_fragment(frag)
    return aura_from_hover(hover)


def biome_from_any_log_text(text: str) -> tuple[str | None, str | None]:
    """Scan arbitrarily large snippet; uses last RPC region."""
    return biome_from_log_tail(text)
