"""Synthetic source membership and standard reachability regressions."""
import pytest

from core.drawings.dwg_line_ownership_graph import summarize_line_ownership


def evidence():
    def record(handle, **fields):
        return {"handle": [0, 1, handle], **fields}

    def ref(handle):
        return [0, 1, handle, handle]

    rows = [
        record(1, object="BLOCK_HEADER", entities=[ref(20), ref(40)]),
        record(2, object="BLOCK_HEADER", entities=[ref(21)]),
        record(3, object="BLOCK_HEADER", name="*A1", entities=[ref(22), ref(41)]),
        record(4, object="BLOCK_HEADER", entities=[ref(23), ref(42)]),
        record(5, object="BLOCK_HEADER", entities=[ref(24)]),
        record(20, entity="LINE", entmode=2),
        record(21, entity="LINE", entmode=1),
        record(22, entity="LINE", entmode=0, ownerhandle=ref(3)),
        record(23, entity="LINE", entmode=0, ownerhandle=ref(4)),
        record(24, entity="LINE", entmode=0, ownerhandle=ref(5)),
        record(40, entity="INSERT", entmode=2, block_header=ref(3)),
        record(41, entity="DIMENSION_LINEAR", entmode=0, ownerhandle=ref(3), block=ref(4)),
        record(42, entity="INSERT", entmode=0, ownerhandle=ref(4), block_header=ref(3)),
    ]
    return rows, {1: "model", 2: "paper"}, {20: None, 21: None, 22: 3, 23: 4, 24: 5}, {40: 3, 41: 4, 42: 3}


def test_layout_membership_nested_cycle_and_unreferenced_definition():
    result = summarize_line_ownership(*evidence())
    assert result["line_membership"] == {
        "DIRECT_MODELSPACE_VERIFIED": 1, "DIRECT_PAPERSPACE_VERIFIED": 1,
        "BLOCK_DEFINITION_VERIFIED": 3,
    }
    assert result["standard_reachable_line_count"] == 2
    assert result["standard_reachable_block_count"] == 2
    assert result["geometry_approved_for_financial_takeoff"] is False
    assert result["financial_quantity_rows_approved"] == 0


@pytest.mark.parametrize("change, expected", [
    ("moved", "CONFLICTING_OWNERSHIP"),
    ("ambiguous", "CONFLICTING_OWNERSHIP"),
    ("missing", "OWNER_OR_REACHABILITY_UNVERIFIED"),
    ("wrong_paper", "CONFLICTING_OWNERSHIP"),
])
def test_owner_evidence_cannot_be_replaced_by_count(change, expected):
    rows, scopes, owners, refs = evidence()
    if change == "moved":
        owners[20] = 3
    elif change == "ambiguous":
        rows[2]["entities"].append(rows[0]["entities"][0])
    elif change == "missing":
        owners[22] = None
    else:
        rows[5]["entmode"] = 1
    result = summarize_line_ownership(rows, scopes, owners, refs)
    assert result["line_membership"][expected] == 1
    assert sum(result["line_membership"].values()) == 5


def test_dangling_or_disagreeing_reference_cannot_establish_reachability():
    rows, scopes, owners, refs = evidence()
    refs[40] = 999
    result = summarize_line_ownership(rows, scopes, owners, refs)
    assert result["standard_reachable_line_count"] == 0
    assert result["unverified_standard_reference_count"] == 1


def test_duplicate_object_id_rejected():
    rows, scopes, owners, refs = evidence()
    with pytest.raises(ValueError, match="Duplicate"):
        summarize_line_ownership([*rows, rows[0]], scopes, owners, refs)


def test_duplicate_membership_within_one_block_fails_closed():
    rows, scopes, owners, refs = evidence()
    rows[0]["entities"].append(rows[0]["entities"][0])
    with pytest.raises(ValueError, match="Duplicate entity"):
        summarize_line_ownership(rows, scopes, owners, refs)


def test_absent_independent_line_record_does_not_verify_implicit_owner():
    rows, scopes, owners, refs = evidence()
    del owners[20]
    result = summarize_line_ownership(rows, scopes, owners, refs)
    assert result["line_membership"]["OWNER_OR_REACHABILITY_UNVERIFIED"] == 1
    assert "DIRECT_MODELSPACE_VERIFIED" not in result["line_membership"]


@pytest.mark.parametrize("change", ["wrong_sha", "mid_audit"])
def test_private_audit_rejects_bad_or_changing_source(tmp_path, monkeypatch, change):
    import hashlib
    import json
    import sys
    from types import SimpleNamespace

    from core.drawings import dwg_line_ownership_graph as audit

    dwg = tmp_path / "public.dwg"
    decoded = tmp_path / "synthetic.json"
    dwg.write_bytes(b"AC1018 synthetic")
    rows, _, owners, _ = evidence()
    rows.extend([
        {"handle": [0, 1, 60], "object": "LAYOUT", "block_header": [0, 1, 1]},
        {"handle": [0, 1, 61], "object": "LAYOUT", "block_header": [0, 1, 2]},
    ])
    decoded.write_text(json.dumps({"OBJECTS": rows}))

    def read_owners(_):
        decoded.write_bytes(decoded.read_bytes() + b" ")
        return list(owners.items())

    raw = SimpleNamespace(
        detect_version=lambda _: "AC1018",
        decode_line_owner_handles=read_owners,
        decode_insert_write_properties=lambda _: [(40, (), 3), (42, (), 3)],
        decode_dimension_entities=lambda _: [("linear", (41, *([None] * 9), (0, 4)))],
    )
    reader = SimpleNamespace(raw=raw, read=lambda _: SimpleNamespace(layouts=lambda: {
        "model": {"handle": 60, "block_record_handle": 1, "model": True},
        "paper": {"handle": 61, "block_record_handle": 2, "model": False},
    }))
    monkeypatch.setitem(sys.modules, "ezdwg", reader)
    monkeypatch.setattr(audit, "version", lambda _: "0.17.0")
    expected = hashlib.sha256(decoded.read_bytes()).hexdigest()
    with pytest.raises(ValueError, match="SHA mismatch"):
        audit.audit_original_line_ownership(
            dwg, decoded, dwg_sha256=hashlib.sha256(dwg.read_bytes()).hexdigest(),
            native_json_sha256=expected if change == "mid_audit" else "0" * 64,
        )
    assert (hashlib.sha256(decoded.read_bytes()).hexdigest() != expected) == (change == "mid_audit")
