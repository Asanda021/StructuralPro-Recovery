from core.bim.quantity_integrity_v1 import BIMQuantityEvidence,normalize_quantities,fingerprint
import pytest
def test_valid_and_deterministic():
 r=[BIMQuantityEvidence("g1","ifc:x:g1","BIM-BEAM-VOL",2,"m3")]
 assert fingerprint(r)==fingerprint(r); assert normalize_quantities(r)[0].quantity==2
def test_negative_fails():
 with pytest.raises(ValueError): BIMQuantityEvidence("g","s","i",-1,"m3").validate()
def test_missing_identity_fails():
 with pytest.raises(ValueError): BIMQuantityEvidence("","","i",1,"m3").validate()
def test_duplicate_global_id_fails():
 e=BIMQuantityEvidence("g","s","i",1,"m3")
 with pytest.raises(ValueError): normalize_quantities([e,e])