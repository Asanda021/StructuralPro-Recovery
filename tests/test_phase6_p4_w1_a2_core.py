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
    p=w.preview("concrete_slab",SLAB,measurement_source="A")
    assert not p.ready_to_review and any("IFC" in x for x in p.blockers)
    assert svc.open_project("P")["boq"]==[]
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


def test_unapproved_visual_ifc_global_id_must_not_become_financial_owner(tmp_path):
    svc=case(tmp_path)
    source=tmp_path/"document.ifc"
    source.write_bytes(b"synthetic IFC bytes without reviewed mapping")
    digest=sha256(source.read_bytes()).hexdigest()
    w=assistant(svc,document_path=str(source),document_sha256=digest,
                revision="R1",global_id="NOT-REVIEWED")
    p=w.preview("concrete_slab",SLAB,measurement_source="document:frame01")
    assert not p.ready_to_review and p.components and p.blockers
    with pytest.raises(RuntimeError):
        w.commit(code="concrete_slab",inputs=SLAB,
                 measurement_source="document:frame01",approver="owner",
                 expected_digest=p.project_digest)
    assert svc.open_project("P")["boq"]==[]
    svc.store.close()


def test_roof_same_owner_rejects_incompatible_joist_or_slab_double_count(tmp_path):
    svc=case(tmp_path)
    w=assistant(svc)
    p=w.preview("concrete_slab",SLAB,measurement_source="real-roof-Z")
    assert p.ready_to_review
    w.commit(code="concrete_slab",inputs=SLAB,measurement_source="real-roof-Z",
             approver="owner",expected_digest=p.project_digest)
    other=w.preview("joist_block_roof_assembly",ROOF_BLOCK,
                    measurement_source="real-roof-Z")
    assert not other.ready_to_review
    assert any("دوباره‌شماری" in x for x in other.blockers)
    assert len(svc.open_project("P").get("takeoff_assemblies",[]))==1
    svc.store.close()


def test_real_ifc_identity_review_allows_only_matched_member_for_w1(tmp_path):
    from test_phase2_priority5_closure import identity_case
    from core.ai.contextual_takeoff_p6 import GovernedTakeoffAssistant
    app,path,proof,proposal,args=identity_case(tmp_path)
    app.review_ifc_identity("P",**args)
    app.collaboration.add_user(User("owner","مدیر پروژه","owner"))
    doc_hash=sha256(path.read_bytes()).hexdigest()
    guide=GovernedTakeoffAssistant(app,"P",floor_id="F1",member_id="B1",
        document_path=str(path),document_sha256=doc_hash,revision="R1",
        global_id=proposal["global_id"])
    beam={"count":"1","length":"4","width":"0.3","depth":"0.5"}
    p=guide.preview("concrete_beam",beam,measurement_source="source:beam1")
    assert p.ready_to_review
    assert not p.financial_approved
    assert len(p.components)==1
    wrong=GovernedTakeoffAssistant(app,"P",floor_id="F1",member_id="B1",
        document_path=str(path),document_sha256=doc_hash,revision="R2",
        global_id=proposal["global_id"])
    stale=wrong.preview("concrete_beam",beam,measurement_source="source:beam1")
    assert not stale.ready_to_review and stale.blockers
    app.store.close()


def test_a2_only_exact_persisted_active_boq_row_via_decimal_and_digest(tmp_path):
    svc=case(tmp_path)
    w=assistant(svc)
    p=w.preview("concrete_slab",SLAB,measurement_source="slab-number-01")
    w.commit(code="concrete_slab",inputs=SLAB,
             measurement_source="slab-number-01",approver="owner",
             expected_digest=p.project_digest)
    fresh=svc.store.current_digest("P")
    real=w.exact_boq_row(0,expected_digest=fresh)
    assert real["quantity"] and real["unit"] and real["source_ids"]
    response=w.advise("مقدار دقیق ردیف انتخاب‌شده چقدر است؟",
                      boq_row_index=0,boq_digest=fresh)
    assert real["quantity"] in response["text"]
    assert "منبع:" in response["text"]
    assert response["commit_allowed"] is False
    svc.add_project_floor("P","طبقه دوم",level="F2")
    with pytest.raises(RuntimeError):
        w.exact_boq_row(0,expected_digest=fresh)
    assert len(svc.open_project("P").get("takeoff_assemblies",[]))==1
    svc.store.close()


def test_real_roof_checklist_requires_joist_direction_and_thermal_rebar_review(tmp_path):
    svc=case(tmp_path)
    w=assistant(svc)
    p=w.preview("joist_block_roof_assembly",ROOF_BLOCK,
                measurement_source="real:roof03")
    assert any("جهت تیرچه" in q for q in p.review_questions)
    assert any("میلگرد حرارتی" in q for q in p.review_questions)
    assert any("دوباره" in q or "بتن" in q for q in p.review_questions)
    assert "مش" in w.advise("چه اقلام وابسته‌ای لازم است؟",
            code="joist_block_roof_assembly",inputs=ROOF_BLOCK,
            measurement_source="real:roof03")["text"]
    assert svc.open_project("P")["boq"]==[]
    svc.store.close()


def test_a2_mep_and_specialist_waffle_evidence_without_fictional_quantities(tmp_path):
    svc=case(tmp_path)
    w=assistant(svc)
    for code,needle in (("mep_pipe","لوله"),("mep_electrical","کابل"),
                        ("waffle_one_way","ریب"),("waffle_two_way","تقاطع"),
                        ("hollowcore","قطعه")):
        preview=w.preview(code,measurement_source="source:no-calculation")
        assert not preview.ready_to_review and preview.components==()
        assert any(needle in q for q in preview.review_questions)
        answer=w.advise("چه چیزهایی نیاز است؟",code=code)
        assert "بدون مقدار" not in answer["text"] or not answer["commit_allowed"]
        assert answer["member_id"]=="SL1" and answer["project_id"]=="P"
    assert not svc.open_project("P")["boq"]
    svc.store.close()
