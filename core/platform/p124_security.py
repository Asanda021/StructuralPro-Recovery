"""P124 security boundaries: safe paths, redaction and non-reversible secret fingerprints."""
from __future__ import annotations
from hashlib import sha256
from pathlib import PurePosixPath
import re

_SECRET = re.compile(r"(?i)(token|password|secret|api[_-]?key)\s*[:=]\s*[^,\s;]+")

def safe_relative_path(value: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ValueError("path is required")
    p = PurePosixPath(value.replace("\\", "/"))
    if p.is_absolute() or ".." in p.parts:
        raise ValueError("path traversal is not allowed")
    if p.parts and ":" in p.parts[0]:
        raise ValueError("drive-qualified path is not allowed")
    return "/".join(p.parts)

def redact(text: str) -> str:
    return _SECRET.sub(lambda m: m.group(0).split("=")[0].split(":")[0] + "=<redacted>", text)

def secret_fingerprint(secret: str) -> str:
    if not secret:
        raise ValueError("secret is required")
    return sha256(secret.encode()).hexdigest()

def safe_filename(name: str) -> str:
    cleaned = re.sub(r"[^A-Za-z0-9._-]+", "_", str(name)).strip("._")
    if not cleaned:
        raise ValueError("filename is empty")
    return cleaned[:120]
