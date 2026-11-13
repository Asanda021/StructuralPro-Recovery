"""Private CLI tests. Synthetic AC1032-signature placeholder only, never actual CAD."""
import json
import os
from pathlib import Path
import pytest
import hashlib
import re
import subprocess
import ezdxf


def _sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _icacls(path, *args):
    assert os.name == "nt"
    result = subprocess.run(["icacls", str(path), *args],
                            capture_output=True, text=True, timeout=25)
    assert result.returncode == 0, "Cannot establish synthetic NTFS test ACL"


def _restrict_native(path, *, directory=False):
    from core.platform.windows_private_acl import (
        current_user_sid, verify_private_dacl,
    )
    user_sid = current_user_sid()
    rights = "(OI)(CI)F" if directory else "F"
    _icacls(path, "/setowner", f"*{user_sid}")
    _icacls(path, "/inheritance:r")
    _icacls(path, "/grant:r",
            f"*{user_sid}:{rights}", f"*S-1-5-18:{rights}")
    assert verify_private_dacl(path, directory=directory)


def _make_public_native(path):
    _icacls(path, "/grant", "*S-1-1-0:R")


def setup_files(tmp_path):
    src = tmp_path / "synthetic.dwg"
    src.write_bytes(b"AC1032" + bytes(128))
    results = []
    for name in ("independent.dxf", "candidate.dxf"):
        drawing = ezdxf.new("R2013")
        poly = drawing.modelspace().add_polyline2d([(0, 0), (3, 0), (3, 2)], close=True)
        list(poly.vertices)[0].dxf.bulge = 0.5
        out = tmp_path / name
        drawing.saveas(out)
        text = out.read_text()
        for vertex in ezdxf.readfile(out).entitydb.values():
            if vertex is not None and vertex.dxftype() == 'VERTEX':
                pattern = (rf"(\n  0\nVERTEX\n  5\n{vertex.dxf.handle}\n330\n)"
                           r"([0-9A-F]+)(\n)")
                match = re.search(pattern, text)
                assert match is not None
                text = text[:match.start(2)] + str(vertex.dxf.owner) + text[match.end(2):]
        out.write_text(text)
        results.append(out)
    return src, *results

from tools.audit_phase8_p2_ac1032_vertex_bulge import main


def make_config(tmp_path, **changes):
    src, ref, cand = setup_files(tmp_path)
    private = tmp_path / "private"
    private.mkdir(mode=0o700)
    if os.name != "nt":
        private.chmod(0o700)
    doc = {
        "original_dwg": str(src), "reference_dxf": str(ref), "candidate_dxf": str(cand),
        "original_sha256": _sha(src), "reference_sha256": _sha(ref),
        "candidate_sha256": _sha(cand), "output_json": str(private / "audit.json"),
    }
    doc.update(changes)
    config = private / "config.json"
    config.write_text(json.dumps(doc), encoding="utf-8")
    if os.name != "nt":
        config.chmod(0o600)
    else:
        # All test files are synthetic, but native Windows input protection
        # must be real; chmod(0600) cannot replace a protected NTFS DACL.
        _restrict_native(private, directory=True)
        for item in (src, ref, cand, config):
            _restrict_native(item)
    return config, doc


def test_private_cli_writes_0600_non_payable_receipt(tmp_path, capsys):
    config, doc = make_config(tmp_path)
    assert main(["--private-config", str(config)]) == 0
    p = Path(doc['output_json'])
    report = json.loads(p.read_text())
    assert report['financial_quantity_rows_approved'] == 0
    assert report['original_dwg_vertex_field_truth_verified'] is False
    if os.name == "nt":
        from core.platform.windows_private_acl import verify_private_dacl
        assert verify_private_dacl(p, directory=False)
    else:
        assert p.stat().st_mode & 0o077 == 0
    output = capsys.readouterr().out
    assert doc['original_sha256'] not in output
    assert doc['original_dwg'] not in output
    assert doc['output_json'] not in output


def test_private_cli_wrong_hash_fails_without_leaking(tmp_path, capsys):
    config, doc = make_config(tmp_path, original_sha256='0'*64)
    assert main(["--private-config", str(config)]) == 2
    assert not Path(doc['output_json']).exists()
    assert doc['original_dwg'] not in capsys.readouterr().out


def test_insecure_config_rejected(tmp_path):
    config, doc = make_config(tmp_path)
    if os.name == "nt":
        _make_public_native(config)
    else:
        config.chmod(0o644)
    assert main(["--private-config", str(config)]) == 2
    assert not Path(doc['output_json']).exists()


def test_existing_output_never_overwritten(tmp_path):
    config, doc = make_config(tmp_path)
    output = Path(doc['output_json'])
    output.write_text('ORIGINAL')
    assert main(["--private-config", str(config)]) == 2
    assert output.read_text() == 'ORIGINAL'


def test_windows_is_explicitly_fail_closed(tmp_path):
    # A world-readable Windows config must remain blocked even if the
    # directory and all native inputs were previously secured.
    config, doc = make_config(tmp_path)
    if os.name == 'nt':
        _make_public_native(config)
        assert main(["--private-config", str(config)]) == 2
        assert not Path(doc['output_json']).exists()
    else:
        assert config.is_file()


def test_private_native_mode_explicitly_uses_original_source_oracle(tmp_path, monkeypatch, capsys):
    config, doc = make_config(tmp_path)
    from core.drawings import dwg_ac1032_native_vertex_oracle as native
    calls = []
    def oracle(*args, **kwargs):
        calls.append((args, kwargs))
        return {
            "status": "NATIVE_SOURCE_VS_DXF_FIELD_DISCREPANCY_NO_GO",
            "native_2d_vertex_observations_verified_by_reader": 6,
            "reference_dxf": {"bulge_difference_count": 0},
            "candidate_dxf": {"bulge_difference_count": 3,
                              "native_nonzero_bulge_zeroed_in_dxf_count": 3},
            "financial_quantity_rows_approved": 0,
        }
    monkeypatch.setattr(native, "audit_ac1032_native_2d_vertex_sources", oracle)
    assert main(["--private-config", str(config), "--original-native-vertex-oracle"]) == 0
    assert len(calls) == 1
    assert Path(doc["output_json"]).is_file()
    message = capsys.readouterr().out
    assert "candidate missing curvature: 3" in message
    for key in ("original_sha256", "reference_sha256", "candidate_sha256",
                "original_dwg", "reference_dxf", "candidate_dxf"):
        assert doc[key] not in message


def test_private_native_reader_failure_leaves_no_report(tmp_path, monkeypatch, capsys):
    config, doc = make_config(tmp_path)
    from core.drawings import dwg_ac1032_native_vertex_oracle as native
    def broken(*args, **kwargs):
        raise ValueError("PRIVATE_VALUE_MUST_NOT_BE_PRINTED")
    monkeypatch.setattr(native, "audit_ac1032_native_2d_vertex_sources", broken)
    assert main(["--private-config", str(config), "--original-native-vertex-oracle"]) == 2
    assert not Path(doc["output_json"]).exists()
    message = capsys.readouterr().out
    assert "PRIVATE_VALUE_MUST_NOT_BE_PRINTED" not in message
    assert "BLOCKED_PRIVATE_VERTEX_AUDIT:" in message
