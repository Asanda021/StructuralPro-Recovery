from core.verification.real_input_validation_v1 import InputEvidence,assess_inputs,validate_inputs
H="a"*64
def e(k="pdf",sid="s1"): return InputEvidence("p1",sid,k,H,"2026-10-04T00:00:00Z")
def test_supported_inputs(): assert assess_inputs((e("pdf"),e("dwg","s2"),e("dxf","s3"),e("ifc","s4"))).source_count==4
def test_deterministic(): assert assess_inputs((e(),)).fingerprint==assess_inputs((e(),)).fingerprint
def test_empty_fails_closed():
    try: validate_inputs(())
    except ValueError: pass
    else: raise AssertionError
def test_bad_hash_fails():
    try: validate_inputs((InputEvidence("p","s","pdf","bad","t"),))
    except ValueError: pass
    else: raise AssertionError
def test_unsupported_fails():
    try: validate_inputs((e("xlsx"),))
    except ValueError: pass
    else: raise AssertionError
