from core.platform.updates import validate_artifact,validate_update,verify_bytes,canonical_manifest
def artifact(v="1.2.4",channel="stable",data=b"abc"):
 import hashlib
 return {"version":v,"channel":channel,"sha256":hashlib.sha256(data).hexdigest(),"size":len(data)}
def test_valid_update_and_artifact():
 a=artifact(); assert validate_artifact(a)==[] and validate_update("1.2.3",a)==[]
def test_downgrade_same_version_and_channel_rejected():
 assert validate_update("1.2.4",artifact("1.2.4"))
 assert validate_update("1.3.0",artifact("1.2.4"))
 assert validate_update("1.2.3",artifact(channel="beta"))
def test_artifact_integrity():
 a=artifact(); assert verify_bytes(b"abc",a["sha256"],3) and not verify_bytes(b"abd",a["sha256"],3)
def test_invalid_manifest_fails_closed():
 assert validate_artifact({"version":"x","channel":"stable","sha256":"bad","size":-1})
def test_manifest_deterministic():
 assert canonical_manifest({"version":"1.0.0","channel":"stable","size":1})==canonical_manifest({"size":1,"channel":"stable","version":"1.0.0"})
