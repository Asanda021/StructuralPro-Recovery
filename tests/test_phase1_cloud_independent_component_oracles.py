"""Independent arithmetic for 15 bounded MEP routes, not design acceptance.

All inputs below are explicit synthetic test data: three 0.125 m lengths,
three enumerated devices, or a 0.125 x 0.375 m duct of length 2.25 m.
No network layout, fitting allowance, capacity or engineer approval is inferred.
Only input-document builders are reused; expected quantities never call an engine.
"""
from copy import deepcopy
from decimal import Decimal

import pytest

from core.platform.application import StructuralProApp
from test_chat_package4_five_mechanical_generic_gates import MECH, engine_document as mechanical
from test_chat_package4_five_electrical_generic_gates import ENGINE as ELECTRICAL, engine_document as electrical
from test_chat_package4_five_service_specialty_gates import ENGINE as SPECIALTY, with_engine


CASES = (
    [(case[0], case[1], mechanical(case)) for case in MECH]
    + [(case[0], case[1], electrical(case)) for case in ELECTRICAL]
    + [(case[0], case[1], with_engine(case)) for case in SPECIALTY]
)


@pytest.mark.parametrize("family,component,template", CASES, ids=[case[0] for case in CASES])
def test_explicit_component_oracle_sqlite_cas_and_existing_boq(tmp_path, family, component, template):
    document = deepcopy(template)
    item = document["components"][component]["items"][0]
    route = item["item"]
    if route in {"pipe", "cable"}:
        item["params"] = {"count": "3", "length": "0.125"}
        expected, unit = Decimal("3") * Decimal("0.125"), "m"
    elif route == "duct_area":
        item["params"] = {"width": "0.125", "height": "0.375", "length": "2.25"}
        expected = Decimal("2") * (Decimal("0.125") + Decimal("0.375")) * Decimal("2.25")
        unit = "m2"
    else:
        assert route in {"equipment", "light", "panel"}
        item["params"] = {"count": "3"}
        expected, unit = Decimal("3"), "عدد"

    app = StructuralProApp(tmp_path)
    try:
        app.create_project("Synthetic bounded component oracle", "P")
        # Populate a BOQ through the real supported service before the audit.
        app.add_takeoff("P", "building", "column", source_id="SYNTHETIC:BOQ-SENTINEL",
                        system="OTHER", manual_location_id="UNRELATED-COLUMN",
                        count=1, width=0.4, depth=0.4, height=3)
        before = app.open_project("P")
        assert before["boq"] and before["takeoffs"]
        app.save_aec_system_draft("P", document, expected_revision=0)
    finally:
        app.store.close()

    reopened = StructuralProApp(tmp_path)
    try:
        assert reopened.get_aec_system("P", family, "L1", document["system_id"])["data"] == document
        digest = reopened.store.current_digest("P")
        result = reopened.preview_aec_system("P", family, "L1", document["system_id"])
        assert result["ready"], result["blockers"]
        row, = [row for row in result["rows"] if row["component"] == component]
        assert Decimal(str(row["quantity"])) == expected
        assert row["unit"] == unit
        with pytest.raises(RuntimeError):
            reopened.save_aec_system_draft("P", document, expected_revision=0)
        assert reopened.store.current_digest("P") == digest
        for field in ("boq", "takeoffs"):
            assert reopened.open_project("P")[field] == before[field]
        assert reopened.store.db.execute("PRAGMA integrity_check").fetchone()[0] == "ok"
    finally:
        reopened.store.close()
