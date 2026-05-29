"""Scan file contents for likely secrets before pushing."""
import os
import re

# Precise, high-confidence patterns: a match is almost certainly a real secret,
# so these fire regardless of the surrounding key name or placeholder wording.
_PATTERNS: list[tuple[str, re.Pattern[str]]] = [
    ("openai-style key", re.compile(r"sk-[A-Za-z0-9]{16,}")),
    ("github token", re.compile(r"gh[pousr]_[A-Za-z0-9]{20,}")),
    ("aws access key id", re.compile(r"AKIA[0-9A-Z]{12,}")),
    ("private key header", re.compile(r"-----BEGIN [A-Z ]*PRIVATE KEY-----")),
]

# Loose heuristic: a JSON key whose name hints at a credential, paired with a
# long-ish value. This catches secrets the precise patterns miss, but it also
# matches config *templates* that ship placeholder values, so the captured value
# is run through _looks_like_placeholder before reporting.
_SECRET_KEY_PATTERN = re.compile(
    r'"[^"]*(?:token|secret|password|apikey|api_key)[^"]*"\s*:\s*"([^"]{16,})"',
    re.IGNORECASE)
_SECRET_KEY_LABEL = "secret-valued key"

# Words/shapes that mark a value as an unfilled placeholder rather than a secret.
_PLACEHOLDER_MARKERS = re.compile(
    r"your[_-]|[_-]here\b|\byour\b|change[_-]?me|placeholder|example|dummy"
    r"|\breplace\b|redacted|<[^>]+>",
    re.IGNORECASE)

MAX_SCAN_BYTES = 1 * 1024 * 1024  # skip files larger than 1 MB


def _looks_like_placeholder(value: str) -> bool:
    """True if a credential-shaped value is clearly an unfilled placeholder."""
    v = value.strip()
    if v.startswith("<") and v.endswith(">"):
        return True
    if v.startswith("$"):  # ${ENV_VAR} or $ENV_VAR reference, not a literal secret
        return True
    if len(v) >= 8 and len(set(v)) <= 2:  # runs like xxxxxxxx or ********
        return True
    return bool(_PLACEHOLDER_MARKERS.search(v))


def scan_text(text: str) -> list[str]:
    """Return a list of human-readable finding labels (empty if clean)."""
    found = []
    for label, pattern in _PATTERNS:
        if pattern.search(text):
            found.append(label)
    for match in _SECRET_KEY_PATTERN.finditer(text):
        if not _looks_like_placeholder(match.group(1)):
            found.append(_SECRET_KEY_LABEL)
            break
    return found


def scan_file(path: str) -> list[str]:
    try:
        if os.path.getsize(path) > MAX_SCAN_BYTES:
            return []
        with open(path, "r", errors="ignore", encoding="utf-8") as fh:
            return scan_text(fh.read())
    except OSError:
        return []


def scan_paths(paths: list[str]) -> dict[str, list[str]]:
    """Return {path: [labels]} for every path with findings."""
    results: dict[str, list[str]] = {}
    for path in paths:
        if not os.path.isfile(path):
            continue
        hits = scan_file(path)
        if hits:
            results[path] = hits
    return results
