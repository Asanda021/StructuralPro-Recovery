"""Static release security checks for source and packaging surfaces."""
from __future__ import annotations
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SCAN_DIRS = ("core", "app", "packaging", ".github")
SECRET_PATTERNS = (
    re.compile(r"(?i)(private[_-]?key|secret[_-]?key)\s*[:=]\s*[A-Za-z0-9+/=_-]{16,}"),
    re.compile(r"(?i)(api[_-]?key|token|password)\s*[:=]\s*['\"][^'\"]{12,}['\"]"),
)

def iter_source_files():
    for directory in SCAN_DIRS:
        root = ROOT / directory
        if not root.exists():
            continue
        for path in root.rglob("*"):
            if path.is_file() and path.suffix.lower() in {".py",".ps1",".iss",".yml",".yaml",".json",".toml"}:
                yield path

def find_embedded_secret_candidates():
    findings = []
    for path in iter_source_files():
        text = path.read_text(encoding="utf-8", errors="ignore")
        for pattern in SECRET_PATTERNS:
            if pattern.search(text):
                findings.append(path.relative_to(ROOT).as_posix())
                break
    return sorted(set(findings))
