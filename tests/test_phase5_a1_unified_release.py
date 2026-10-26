"""A1/Unified: no tier gate, no model without hashes and release approval."""
import hashlib
import json
import socket
from pathlib import Path
import pytest
from core.ai.release_gate import inspect_ai_release_assets
from core.ai.local_engine import LocalAIEngine
from core.platform.product import ProductEdition, FEATURES, product_profile, packaged_edition, validate_packaged_edition_features


def _manifest(root):
    assets=[]
    for kind,name in (("model","model.gguf"),("mmproj","projector.gguf"),("runtime_text","llama-cli.exe"),("runtime_vision","llama-mtmd-cli.exe")):
        raw=("fixture:"+name).encode()
        (root/name).write_bytes(raw)
        license_name=name+".LICENSE.txt"
        license_bytes=("synthetic-licensing-evidence:"+name).encode()
        (root/license_name).write_bytes(license_bytes)
        assets.append({
            "kind":kind,"name":name,"path":name,"sha256":hashlib.sha256(raw).hexdigest(),
            "version":"test-1","architecture":"x86_64",
            "source_url":"https://example.invalid/test-fixture",
            "license_id":"SYNTHETIC_TEST_LICENSE",
            "license_evidence":license_name,
            "license_evidence_sha256":hashlib.sha256(license_bytes).hexdigest(),
            "commercial_use_allowed":True,"redistribution_allowed":True,
            "legal_review_approved":True,
        })
    manifest={"schema_version":1,"product":"StructuralPro","edition":"unified",
              "offline_required":True,"external_api_required":False,
              "owner_release_approval":True,"assets":assets}
    path=root/"release_manifest.json"
    path.write_text(json.dumps(manifest),encoding="utf-8")
    return path,manifest


def test_unified_profile_all_features_but_no_automatic_model(tmp_path):
    (tmp_path/"EDITION").write_text("unified\n")
    assert packaged_edition(tmp_path,fail_closed=True) is ProductEdition.UNIFIED
    assert product_profile(ProductEdition.UNIFIED).features==frozenset(FEATURES)
    assert validate_packaged_edition_features(tmp_path,FEATURES)
    engine=LocalAIEngine(model_dir=tmp_path)
    assert engine.edition=="unified" and engine.tier.value=="takeoff"
    assert not engine.has_llm_model and not engine.has_vision_model


def test_rejects_unlicensed_missing_model_corrupt_runtime_and_projector(tmp_path):
    path,data=_manifest(tmp_path)
    assert inspect_ai_release_assets(path,tmp_path).ready
    data["assets"][1]["redistribution_allowed"]=False
    path.write_text(json.dumps(data))
    result=inspect_ai_release_assets(path,tmp_path)
    assert not result.ready and any("mmproj:unverified" in x for x in result.blockers)
    data["assets"][1]["redistribution_allowed"]=True
    data["owner_release_approval"]=False
    path.write_text(json.dumps(data))
    assert "missing_owner_release_approval" in inspect_ai_release_assets(path,tmp_path).blockers
    data["owner_release_approval"]=True
    path.write_text(json.dumps(data))
    (tmp_path/"llama-cli.exe").write_bytes(b"tampered")
    assert "runtime_text:sha256_mismatch" in inspect_ai_release_assets(path,tmp_path).blockers
    (tmp_path/"model.gguf.LICENSE.txt").write_bytes(b"forged-license-terms")
    assert "model:license_evidence_hash_mismatch" in inspect_ai_release_assets(path,tmp_path).blockers
    (tmp_path/"projector.gguf").unlink()
    assert "mmproj:unsafe_or_missing" in inspect_ai_release_assets(path,tmp_path).blockers


def test_rejects_symlinks_path_escape_omission_and_tiered_release(tmp_path):
    path,data=_manifest(tmp_path)
    external=tmp_path.parent/"outside-asset.gguf"
    external.write_bytes(b"external")
    (tmp_path/"model.gguf").unlink()
    (tmp_path/"model.gguf").symlink_to(external)
    assert "model:unsafe_or_missing" in inspect_ai_release_assets(path,tmp_path).blockers
    data["edition"]="pro"
    path.write_text(json.dumps(data))
    assert "tiered_edition_not_allowed" in inspect_ai_release_assets(path,tmp_path).blockers
    data["assets"][0]["path"]="../outside-asset.gguf"
    data["edition"]="unified"
    path.write_text(json.dumps(data))
    assert "model:unsafe_or_missing" in inspect_ai_release_assets(path,tmp_path).blockers


def test_a1_never_uses_network_even_when_manifest_malicious(tmp_path,monkeypatch):
    path,data=_manifest(tmp_path)
    data["assets"][0]["source_url"]="https://malicious.invalid/should-not-fetch"
    path.write_text(json.dumps(data))
    called=[]
    def deny(*args,**kwargs):
        called.append(True)
        raise AssertionError("network forbidden")
    monkeypatch.setattr(socket.socket,"connect",deny)
    assert inspect_ai_release_assets(path,tmp_path).ready
    assert not called


def test_unified_engine_blocked_without_license_even_if_model_present(tmp_path):
    engine=LocalAIEngine(model_dir=tmp_path,edition="unified")
    from core.ai.edition_models import MODEL_SPECS, AITier
    spec=MODEL_SPECS[AITier.TAKEOFF]
    model=tmp_path/spec.model_filename
    model.write_bytes(b"fake-model")
    engine.model_path=model
    assert not engine.has_llm_model
    assert engine.answer("آفلاین کار می‌کند؟").quantity_authority is False


def test_single_shipped_edition_ignores_environment_and_legacy_engine_override(tmp_path,monkeypatch):
    from core.platform import product
    import core.ai.local_engine as engine_module
    (tmp_path/"EDITION").write_text("unified\n")
    monkeypatch.setenv("STRUCTURALPRO_EDITION","light")
    assert product.packaged_edition(tmp_path,fail_closed=True) is ProductEdition.UNIFIED
    monkeypatch.setattr(engine_module,"packaged_edition",lambda *a,**kw:ProductEdition.UNIFIED)
    engine=engine_module.LocalAIEngine(model_dir=tmp_path,edition="pro")
    assert engine.edition=="unified"
    assert not engine.has_llm_model


def test_manifest_of_other_valid_files_cannot_authorize_actual_runtime(tmp_path,monkeypatch):
    path,_=_manifest(tmp_path)
    # Manifest contains valid test bytes, but it does not describe the assets
    # that the AI engine selected for invocation.
    (tmp_path/"AI_RELEASE_MANIFEST.json").write_bytes(path.read_bytes())
    root=tmp_path/"models"
    root.mkdir()
    engine=LocalAIEngine(model_dir=root,edition="unified")
    engine.bundle_dir=tmp_path
    from core.ai.edition_models import AITier,MODEL_SPECS
    selected=root/MODEL_SPECS[AITier.TAKEOFF].model_filename
    selected.write_bytes(b"different unapproved model")
    engine.model_path=selected
    engine.mmproj_path=root/MODEL_SPECS[AITier.TAKEOFF].mmproj_filename
    engine.mmproj_path.write_bytes(b"different projector")
    engine.runtime_dir=tmp_path
    for name in ("llama-cli", "llama-mtmd-cli"):
        runtime=tmp_path/name
        runtime.write_bytes(b"unapproved runnable")
        runtime.chmod(0o755)
    assert inspect_ai_release_assets(path,tmp_path).ready
    assert not engine.has_llm_model
