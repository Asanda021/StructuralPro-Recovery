import hashlib
import json
import pytest
from core.ai.gguf_runtime_v1 import GGUFProductionRuntime

def write_manifest(tmp_path, model_name="model.gguf", digest=""):
    payload={"schema_version":2,"runtime":"llama.cpp-compatible","format":"GGUF","offline_required":True,"internet_required":False,"api_key_required":False,
             "model_files":[{"name":"StructuralPro Test Model","path":model_name,"sha256":digest,"license":"test-license","commercial_use":True,"architecture":"test"}]}
    path=tmp_path/"model_manifest.json"; path.write_text(json.dumps(payload),encoding="utf-8"); return path

def test_valid_artifact_is_verified(tmp_path):
    artifact=tmp_path/"model.gguf"; artifact.write_bytes(b"deterministic-gguf-fixture")
    digest=hashlib.sha256(artifact.read_bytes()).hexdigest()
    result=GGUFProductionRuntime(write_manifest(tmp_path,digest=digest)).verify_artifact()
    assert result.ready is True and result.reason=="verified" and result.actual_sha256==digest

def test_missing_artifact_fails_closed(tmp_path):
    result=GGUFProductionRuntime(write_manifest(tmp_path,digest="a"*64)).verify_artifact()
    assert result.ready is False and result.reason=="model_artifact_missing"

def test_changed_artifact_fails_closed(tmp_path):
    artifact=tmp_path/"model.gguf"; artifact.write_bytes(b"original")
    digest=hashlib.sha256(artifact.read_bytes()).hexdigest()
    runtime=GGUFProductionRuntime(write_manifest(tmp_path,digest=digest)); artifact.write_bytes(b"tampered")
    result=runtime.verify_artifact()
    assert result.ready is False and result.reason=="model_sha256_mismatch"

def test_manifest_rejects_multiple_models(tmp_path):
    manifest=json.loads(write_manifest(tmp_path,digest="a"*64).read_text()); manifest["model_files"].append(dict(manifest["model_files"][0]))
    path=tmp_path/"model_manifest.json"; path.write_text(json.dumps(manifest),encoding="utf-8")
    with pytest.raises(ValueError,match="exactly one"): GGUFProductionRuntime(path).load_manifest()

def test_manifest_requires_offline_operation(tmp_path):
    manifest=json.loads(write_manifest(tmp_path,digest="a"*64).read_text()); manifest["internet_required"]=True
    path=tmp_path/"model_manifest.json"; path.write_text(json.dumps(manifest),encoding="utf-8")
    with pytest.raises(ValueError,match="internet"): GGUFProductionRuntime(path).load_manifest()

def test_noncommercial_artifact_is_not_production_ready(tmp_path):
    artifact=tmp_path/"model.gguf"; artifact.write_bytes(b"fixture")
    digest=hashlib.sha256(artifact.read_bytes()).hexdigest()
    manifest=json.loads(write_manifest(tmp_path,digest=digest).read_text()); manifest["model_files"][0]["commercial_use"]=False
    path=tmp_path/"model_manifest.json"; path.write_text(json.dumps(manifest),encoding="utf-8")
    result=GGUFProductionRuntime(path).verify_artifact()
    assert result.ready is False and result.reason=="commercial_use_not_verified"
