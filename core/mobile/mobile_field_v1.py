"""Offline-first mobile/field contract for AEC quantity workflows."""
from dataclasses import dataclass, asdict
from hashlib import sha256
import json


ALLOWED_STATUSES = {"queued", "synced", "conflict", "rejected"}


@dataclass(frozen=True)
class FieldPacket:
    packet_id: str
    project_id: str
    device_id: str
    revision: str
    source_ids: tuple[str, ...]
    payload_hash: str
    status: str = "queued"


def _canonical(value: object) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def validate_packet(packet: FieldPacket) -> None:
    if not all((packet.packet_id, packet.project_id, packet.device_id, packet.revision, packet.payload_hash)):
        raise ValueError("packet identity, revision and payload hash are required")
    if not packet.source_ids:
        raise ValueError("field packet requires source evidence")
    if packet.status not in ALLOWED_STATUSES:
        raise ValueError("invalid packet status")


def enqueue(packet: FieldPacket) -> FieldPacket:
    validate_packet(packet)
    return FieldPacket(**{**asdict(packet), "status": "queued"})


def mark_synced(packet: FieldPacket) -> FieldPacket:
    validate_packet(packet)
    if packet.status == "conflict":
        raise ValueError("conflicted packet cannot be synced")
    return FieldPacket(**{**asdict(packet), "status": "synced"})


def fingerprint(packet: FieldPacket) -> str:
    validate_packet(packet)
    return sha256(_canonical(asdict(packet)).encode("utf-8")).hexdigest()
