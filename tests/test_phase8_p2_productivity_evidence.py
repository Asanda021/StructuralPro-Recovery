"""Calibration uses real source-backed observations, never universal fake rates."""
import pytest
from core.projects.productivity_evidence import (
    calibrate_productivity,validate_calibration,calibrated_duration,
)


def _observations(tmp_path):
    records=[]
    for i,(quantity,days,crews) in enumerate(((20,2,1),(40,2,2),(60,2,3)),1):
        doc=tmp_path/f"crew-report-{i}.txt"
        doc.write_text(f"site output {i} {quantity} m2 {days} shifts {crews} crews",encoding="utf-8")
        records.append({
            "observed_on":f"1405/08/{i+1:02d}",
            "quantity":quantity,"unit":"مترمربع",
            "workdays":days,"crews":crews,
            "source_path":str(doc),
        })
    return records


def test_site_calibration_three_distinct_source_hashed_outputs(tmp_path):
    samples=_observations(tmp_path)
    result=calibrate_productivity("block_wall",samples,reviewer="ناظر",
                                  project_id="PROJECT-1")
    assert result["observation_count"]==3
    assert result["median_per_crew_day"]=="10"
    assert result["status"]=="PROJECT_OBSERVED_REVIEW_ONLY"
    assert len(result["source_documents"])==3
    assert validate_calibration(result,"block_wall","PROJECT-1")==result
    days=calibrated_duration(result,100,crews=2)
    assert days["expected_workdays"]==5
    assert days["status"]=="PROJECT_OBSERVED_REQUIRES_BASELINE_APPROVAL"
    with pytest.raises(ValueError,match="پروژه"):
        validate_calibration(result,"block_wall","OTHER")
    samples[0]["source_path"] and __import__("pathlib").Path(samples[0]["source_path"]).write_text("CHANGED",encoding="utf-8")
    with pytest.raises(ValueError,match="تغییر"):
        validate_calibration(result,"block_wall","PROJECT-1")


def test_calibration_needs_real_independent_field_observations(tmp_path):
    records=_observations(tmp_path)
    with pytest.raises(ValueError,match="۳"):
        calibrate_productivity("block_wall",records[:2],reviewer="ناظر",project_id="P")
    records[1]["observed_on"]=records[0]["observed_on"]
    with pytest.raises(ValueError,match="تاریخ"):
        calibrate_productivity("block_wall",records,reviewer="ناظر",project_id="P")
    records[1]["observed_on"]="1405/08/02"
    records[1]["unit"]="kg"
    with pytest.raises(ValueError,match="واحد"):
        calibrate_productivity("block_wall",records,reviewer="ناظر",project_id="P")



def test_verified_project_rates_link_to_actual_measured_wall_and_detect_tamper(tmp_path):
    from types import SimpleNamespace
    from core.drawings.workflow_planning import (
        new_workflow_plan,register_project_productivity_calibration,sync_measured_items
    )
    records=_observations(tmp_path)
    evidence=calibrate_productivity("block_wall",records,reviewer="ناظر",
                                   project_id="P-1")
    plan=new_workflow_plan(drawing_source="plan.dwg",source_sha256="sha",
        project_id="P-1",structure="concrete",disciplines=["architecture"])
    plan=register_project_productivity_calibration(plan,evidence)
    item=SimpleNamespace(id="1",label="دیوار بلوکی",takeoff_code="",
        cad_evidence=None,quantity=96,unit="m2",source_ref="source-1")
    sync_measured_items(plan,[item])
    task=next(t for t in plan["tasks"] if t["id"]=="block_wall")
    assert task["duration_days"]==5
    assert task["duration_status"]=="PROJECT_OBSERVED_REQUIRES_BASELINE_APPROVAL"
    assert task["rate_source"]=="PROJECT_FIELD_OBSERVATION_SHA_VERIFIED"
    records[0] and __import__("pathlib").Path(records[0]["source_path"]).write_text(
        "TAMPER",encoding="utf-8"
    )
    with pytest.raises(ValueError,match="تغییر"):
        sync_measured_items(plan,[item])


def test_project_calibration_cannot_transfer_to_different_project(tmp_path):
    from core.drawings.workflow_planning import (
        new_workflow_plan,register_project_productivity_calibration
    )
    evidence=calibrate_productivity("block_wall",_observations(tmp_path),
        reviewer="بازبین",project_id="A")
    plan=new_workflow_plan(drawing_source="p.dxf",source_sha256="sha",
        project_id="B",structure="concrete",disciplines=["architecture"])
    with pytest.raises(ValueError,match="پروژه"):
        register_project_productivity_calibration(plan,evidence)
