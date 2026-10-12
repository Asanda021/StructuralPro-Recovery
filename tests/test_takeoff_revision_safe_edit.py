import pytest

from core.platform.application import StructuralProApp


def test_persisted_takeoff_revision_updates_quantity_and_preserves_history(tmp_path):
    app = StructuralProApp(tmp_path)
    app.create_project("پروژه نسخه متره", "rev-takeoff")
    initial = app.add_takeoff(
        "rev-takeoff", "building", "column", source_id="manual-row-1",
        description="ستون C1", system="طبقه ۱",
        count=2, width=0.4, depth=0.4, height=3,
    )
    assert initial["revision"] == 1
    assert initial["params"]["width"] == 0.4
    assert initial["quantities"][0]["amount"] == pytest.approx(0.96)

    revised = app.revise_takeoff(
        "rev-takeoff", "manual-row-1", expected_revision=1,
        domain="building", item="column", description="ستون C1 اصلاح‌شده",
        system="طبقه ۱", count=2, width=0.5, depth=0.5, height=3,
    )
    assert revised["revision"] == 2
    assert revised["quantities"][0]["amount"] == pytest.approx(1.5)

    project = app.open_project("rev-takeoff")
    assert len(project["takeoff_revision_history"]) == 1
    history = project["takeoff_revision_history"][0]
    assert history["from_revision"] == 1 and history["to_revision"] == 2
    assert history["previous_row"]["quantities"][0]["amount"] == pytest.approx(0.96)
    assert project["takeoffs"][0]["quantities"][0]["amount"] == pytest.approx(1.5)
    assert project["boq"][0]["quantity"] == pytest.approx(1.5)


def test_stale_takeoff_revision_is_rejected_without_mutating_current_row(tmp_path):
    app = StructuralProApp(tmp_path)
    app.create_project("پروژه تعارض نسخه", "rev-conflict")
    app.add_takeoff(
        "rev-conflict", "building", "column", source_id="manual-row-2",
        description="ستون C2", count=1, width=0.4, depth=0.4, height=3,
    )
    app.revise_takeoff(
        "rev-conflict", "manual-row-2", expected_revision=1,
        domain="building", item="column", description="ستون C2 v2",
        count=1, width=0.5, depth=0.5, height=3,
    )
    with pytest.raises(RuntimeError, match="تعارض نسخه"):
        app.revise_takeoff(
            "rev-conflict", "manual-row-2", expected_revision=1,
            domain="building", item="column", description="تلاش قدیمی",
            count=1, width=0.8, depth=0.8, height=3,
        )
    project = app.open_project("rev-conflict")
    assert project["takeoffs"][0]["revision"] == 2
    assert project["takeoffs"][0]["quantities"][0]["amount"] == pytest.approx(0.75)
    assert len(project["takeoff_revision_history"]) == 1


def test_revision_rejects_missing_or_ambiguous_source_id(tmp_path):
    app = StructuralProApp(tmp_path)
    app.create_project("پروژه منبع", "rev-source")
    with pytest.raises(KeyError):
        app.revise_takeoff("rev-source", "missing", expected_revision=1,
                           domain="building", item="column", count=1,
                           width=0.4, depth=0.4, height=3)
    with pytest.raises(ValueError):
        app.revise_takeoff("rev-source", "", expected_revision=1,
                           domain="building", item="column", count=1,
                           width=0.4, depth=0.4, height=3)
