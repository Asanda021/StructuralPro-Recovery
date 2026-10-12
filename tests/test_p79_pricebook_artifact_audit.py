from core.estimate.pricebook_artifact_audit_v1 import audit

def test_audit_records_hash_and_size(tmp_path):
    p=tmp_path/"a.bin"; p.write_bytes(b"pricebook")
    a=audit(p)
    assert a.bytes==9
    assert len(a.sha256)==64
    assert a.archive is False
