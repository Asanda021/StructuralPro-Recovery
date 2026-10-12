from core.cad.native_dwg_dxf_production_boundary_v1 import (
    CadArtifactRecord,
    build_artifact_fingerprint,
    metadata_from_mapping,
    record_fingerprint,
    round_trip_verify,
)


def _record(payload=b"DXF-EVIDENCE"):
    return CadArtifactRecord(
        project_id="P-01",
        revision="R2",
        source_id="SRC-01",
        discipline="Structural",
        format="DXF",
        version="AC1032",
        external_id="CAD-01",
        artifact_fingerprint=build_artifact_fingerprint(payload),
        metadata=metadata_from_mapping({"layer": "S-1", "units": "mm"}),
    )


def test_artifact_fingerprint_is_deterministic():
    assert build_artifact_fingerprint(b"abc") == build_artifact_fingerprint(b"abc")


def test_record_fingerprint_is_deterministic():
    assert record_fingerprint(_record()) == record_fingerprint(_record())


def test_round_trip_accepts_identical_evidence():
    original = _record()
    returned = _record()
    assert round_trip_verify(original, returned)


def test_round_trip_rejects_changed_artifact_evidence():
    original = _record(b"original")
    returned = _record(b"changed")
    assert not round_trip_verify(original, returned)


def test_round_trip_rejects_external_id_mismatch():
    original = _record()
    returned = _record()
    returned = CadArtifactRecord(
        **{**returned.__dict__, "external_id": "CAD-02"}
    )
    assert not round_trip_verify(original, returned)


def test_unsupported_dxf_version_fails_closed():
    record = CadArtifactRecord(
        project_id="P-01",
        revision="R2",
        source_id="SRC-01",
        discipline="Structural",
        format="DXF",
        version="AC1009",
        external_id="CAD-01",
        artifact_fingerprint="abc",
    )
    assert not round_trip_verify(record, record)


def test_metadata_normalization_is_stable():
    assert metadata_from_mapping({"b": 2, "a": 1}) == (("a", "1"), ("b", "2"))
