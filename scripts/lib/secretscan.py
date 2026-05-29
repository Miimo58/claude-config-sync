"""Scan file contents for likely secrets before pushing."""
import os
import re

_PATTERNS: list[tuple[str, re.Pattern[str]]] = [
    ("openai-style key", re.compile(r"sk-[A-Za-z0-9]{16,}")),
    ("github token", re.compile(r"gh[pousr]_[A-Za-z0-9]{20,}")),
    ("aws access key id", re.compile(r"AKIA[0-9A-Z]{12,}")),
    ("private key header", re.compile(r"-----BEGIN [A-Z ]*PRIVATE KEY-----")),
    ("secret-valued key", re.compile(
        r'"[^"]*(?:token|secret|password|apikey|api_key)[^"]*"\s*:\s*"[^"]{16,}"',
        re.IGNORECASE)),
]

MAX_SCAN_BYTES = 1 * 1024 * 1024  # skip files larger than 1 MB


def scan_text(text: str) -> list[str]:
    """Return a list of human-readable finding labels (empty if clean)."""
    found = []
    for label, pattern in _PATTERNS:
        if pattern.search(text):
            found.append(label)
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
