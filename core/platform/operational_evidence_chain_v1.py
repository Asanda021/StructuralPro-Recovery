"""P371-P380 deterministic operational-evidence archive-chain boundary."""
from __future__ import annotations

import hashlib
import json
from typing import Any, Mapping, Sequence

from .operational_evidence_archive_v1 import verify_archive

SCHEMA_VERSION = "v1"
REQUIRED_KEYS = frozenset({"schema_version", "sequence", "archives", "chain_sha256"})


def _canonical(payload: Mapping[str, Any]) -> bytes:
    return json.dumps(dict(payload), ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")


def chain_from_archives(archives: Sequence[Mapping[str, Any]]) -> dict[str, Any]:
    normalized = [dict(a) for a in archives]
    if any(not verify_archive(a) for a in normalized):
        raise ValueError("all archives must be valid")
    payload = {
        "schema_version": SCHEMA_VERSION,
        "sequence": list(range(len(normalized))),
        "archives": normalized,
    }
    payload["chain_sha256"] = hashlib.sha256(_canonical(payload)).hexdigest()
    return payload


def validate_chain(chain: Mapping[str, Any]) -> list[str]:
    errors: list[str] = []
    if not isinstance(chain, Mapping):
        return ["chain must be a mapping"]
    missing = sorted(REQUIRED_KEYS - set(chain))
    if missing:
        errors.append(f"missing keys: {','.join(missing)}")
    if chain.get("schema_version") != SCHEMA_VERSION:
        errors.append("unsupported schema_version")
    seq = chain.get("sequence")
    archives = chain.get("archives")
    if not isinstance(seq, list) or any(not isinstance(x, int) for x in seq):
        errors.append("sequence must be a list of ints")
    if not isinstance(archives, list):
        errors.append("archives must be a list")
    else:
        for i, archive in enumerate(archives):
            if not verify_archive(archive):
                errors.append(f"archives[{i}] integrity verification failed")
    if isinstance(seq, list) and isinstance(archives, list) and seq != list(range(len(archives))):
        errors.append("sequence does not match archive order")
    digest = chain.get("chain_sha256")
    if not isinstance(digest, str) or len(digest) != 64:
        errors.append("invalid chain_sha256")
    return errors


def verify_chain(chain: Mapping[str, Any]) -> bool:
    if validate_chain(chain):
        return False
    payload = {k: chain[k] for k in chain if k != "chain_sha256"}
    return chain["chain_sha256"] == hashlib.sha256(_canonical(payload)).hexdigest()


def serialize_chain(chain: Mapping[str, Any]) -> str:
    if not verify_chain(chain):
        raise ValueError("cannot serialize invalid chain")
    return json.dumps(dict(chain), ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def restore_chain(serialized: str) -> dict[str, Any]:
    try:
        value = json.loads(serialized)
    except (TypeError, json.JSONDecodeError) as exc:
        raise ValueError("invalid chain JSON") from exc
    if not verify_chain(value):
        raise ValueError("chain integrity verification failed")
    return dict(value)


def replay_chain(chain: Mapping[str, Any], archives: Sequence[Mapping[str, Any]]) -> bool:
    if not verify_chain(chain):
        return False
    expected = chain_from_archives(archives)
    return expected == dict(chain)
