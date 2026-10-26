"""W1/A2: actual SQLite CAS, reviewed assembly, no AI-made quantities or prices."""
from copy import deepcopy
from hashlib import sha256

import pytest

from core.ai.contextual_takeoff_p6 import GovernedTakeoffAssistant, SPECIALIST_ONLY
from core.platform.application import StructuralProApp
from core.collaboration.workspace import User

SLAB = {"count":"1","length":"5","width":"4",
        "thickness":"0.2","openings":"0"}
ROOF_BLOCK = {"count":"1","length":"5","width":"4",
        "topping_thickness":"0.05","joist_spacing":"0.5",
        "joist_width":"0.1","joist_depth":"0.25","joist_count":"9",
        "block_length":"0.5","block_width":"0.4","block_height":"0.25",
        "block_count":"80"}


def case(tmp_path, *, has_member=True):
    service=StructuralProApp(tmp_path/"app")
    service.create_project("ساختمان پنج‌طبقه", "P")
    service.add_project_floor("P","طبقه اول",level="F1")
    if has_member:
        service.add_project_member("P","SL1","F1","slab")
    service.collaboration.add_user(User("owner","مدیر پروژه","owner"))
    service.collaboration.add_user(User("editor","کارشناس متره","editor"))
    return service


def assistant(service, *, member="SL1", **options):
    return GovernedTakeoffAssistant(service,"P",floor_id="F1",
                                    member_id=member,**options)


def test_template_missing_inputs_concrete_no_defaults_no_data_changes(tmp_path):
    svc=case(tmp_path)
    original=deepcopy(svc.open_project("P"))
    digest=svc.store.current_digest("P")
    w=assistant(svc)
    p=w.preview("concrete_slab",{"length":"5"},measurement_source="zone/A")
    assert not p.ready_to_review
    assert "count" in p.missing and "openings" in p.missing
    assert p.components==()
    assert p.financial_approved is False
    assert "floor_screed" in {x["code"] for x in p.companions}
    assert svc.store.current_digest("P")==digest
    assert svc.open_project("P")==original
    svc.store.close()


def test_joist_block_real_schedule_never_invents_counts_ribs_mesh_or_pricing(tmp_path):
    svc=case(tmp_path)
    w=assistant(svc)
    for code,inputs in (("joist_block_roof_assembly",ROOF_BLOCK),
                        ("joist_foam_roof_assembly",{
                          **{k:v for k,v in ROOF_BLOCK.items()
                             if not k.startswith("block_")},
                          "foam_length":"0.5","foam_width":"0.4","foam_height":"0.25",
                          "foam_count":"80"})):
        p=w.preview(code,inputs,measurement_source="roof/A")
        assert p.ready_to_review
        assert {x["code"] for x in p.components}==(
            {"concrete","joist","block"} if "block_" in code else
            {"concrete","joist","foam"})
        assert all(x.get("quantity") is not None for x in p.components)
        assert all("price" not in x for x in p.components)
        assert "reinforcement_mesh" not in {x["code"] for x in p.components}
    svc.store.close()


def test_wall_openings_and_finishes_ask_first_no_fake_zero(tmp_path):
    svc=case(tmp_path)
    w=assistant(svc)
    p=w.preview("block_wall",{"length":"7","height":"3","thickness":"0.1"},
                measurement_source="wall/F1")
    assert "openings" in p.missing
    assert "block_length" in p.missing
    assert any(x["code"]=="wall_paint" for x in p.companions)
    assert not p.ready_to_review
    svc.store.close()


@pytest.mark.parametrize("code",sorted(SPECIALIST_ONLY))
def test_unsupported_specialist_geometry_never_gets_placeholder_assembly(tmp_path,code):
    svc=case(tmp_path)
    p=assistant(svc).preview(code,measurement_source="zone/Z1")
    assert p.blockers and p.components==() and not p.ready_to_review
    assert svc.open_project("P")["boq"]==[]
    svc.store.close()


def test_a2_offline_only_from_scoped_current_project_and_numeric_refusal(tmp_path):
    svc=case(tmp_path)
    w=assistant(svc)
    result=w.advise("مقدار بتن چقدر است؟",code="concrete_slab",
                    inputs={"length":"4"},measurement_source="zone/A")
    assert result["offline"] and result["deterministic"]
    assert "عدد" in result["text"] and "openings" in result["text"]
    assert not result["commit_allowed"] and result["requires_confirmation"]
    assert result["project_id"]=="P" and result["member_id"]=="SL1"
    svc.store.close()


def test_real_cas_assembly_commit_only_after_approval_and_no_double_billing(tmp_path):
    svc=case(tmp_path)
    w=assistant(svc)
    before=svc.store.current_digest("P")
    p=w.preview("concrete_slab",SLAB,measurement_source="measurement-checked-01")
    assert p.ready_to_review
    assert svc.store.current_digest("P")==before
    with pytest.raises(PermissionError):
        w.commit(code="concrete_slab",inputs=SLAB,measurement_source="measurement-checked-01",
                 approver="editor",expected_digest=p.project_digest)
    committed=w.commit(code="concrete_slab",inputs=SLAB,measurement_source="measurement-checked-01",
                       approver="owner",expected_digest=p.project_digest)
    assert committed["assembly"]["approved_by"]=="owner"
    assert len(committed["rows"])==len(p.components)
    project=svc.open_project("P")
    assert len(project.get("takeoff_assemblies",[]))==1
    assert project["boq"] and project["takeoffs"]
    assert svc.store.current_digest("P")!=before
    with pytest.raises(RuntimeError):
        w.commit(code="concrete_slab",inputs=SLAB,measurement_source="measurement-checked-01",
                 approver="owner",expected_digest=p.project_digest)
    duplicate=w.preview("concrete_slab",SLAB,measurement_source="measurement-checked-01")
    assert not duplicate.ready_to_review and duplicate.blockers
    svc.store.close()


def test_stale_project_cas_cancel_and_disable_are_fail_closed(tmp_path):
    svc=case(tmp_path)
    w=assistant(svc)
    ready=w.preview("concrete_slab",SLAB,measurement_source="measurement-02")
    svc.add_project_floor("P","طبقه جدید",level="F2")
    with pytest.raises(RuntimeError):
        w.commit(code="concrete_slab",inputs=SLAB,measurement_source="measurement-02",
                 approver="owner",expected_digest=ready.project_digest)
    assert not svc.open_project("P")["boq"]
    w.cancel()
    with pytest.raises(RuntimeError):
        w.preview("concrete_slab",SLAB,measurement_source="measurement-02")
    w.reset()
    w.disable()
    with pytest.raises(RuntimeError):
        w.advise("متره")
    svc.store.close()


def test_verified_file_source_hash_and_revision_guard(tmp_path):
    svc=case(tmp_path)
    source=tmp_path/"source.ifc";source.write_bytes(b"real IFC source fixture bytes")
    digest=sha256(source.read_bytes()).hexdigest()
    w=assistant(svc,document_path=str(source),
                document_sha256=digest,revision="R1",global_id="A-GlobalID")
    assert w.preview("concrete_slab",SLAB,measurement_source="A").ready_to_review
    source.write_bytes(b"changed")
    with pytest.raises(RuntimeError):
        w.preview("concrete_slab",SLAB,measurement_source="A")
    with pytest.raises(ValueError):
        assistant(svc,document_path=str(source),document_sha256=digest,
                  revision="R1")
    svc.store.close()


def test_changed_input_blocks_old_preview_and_duplicate_project_ids_refused(tmp_path):
    svc=case(tmp_path)
    w=assistant(svc)
    p=w.preview("concrete_slab",SLAB,measurement_source="measurement-03")
    with pytest.raises(RuntimeError):
        w.commit(code="concrete_slab",inputs={**SLAB,"thickness":"0.3"},
                 measurement_source="measurement-03",approver="owner",
                 expected_digest=p.project_digest)
    assert not svc.open_project("P")["boq"]
    with pytest.raises(KeyError):
        GovernedTakeoffAssistant(svc,"OTHER",floor_id="F1")
    with pytest.raises(ValueError):
        assistant(svc,member="NONEXISTENT")
    svc.store.close()
