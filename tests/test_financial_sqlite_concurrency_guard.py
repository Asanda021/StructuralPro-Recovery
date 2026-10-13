"""Cost, commitment and receipt ledgers must never erase another SQLite writer."""
import pytest
from core.platform.application import StructuralProApp

ACTIONS = {
    "cost": lambda a: a.add_project_cost("P", "مصالح", 1200, description="synthetic:invoice"),
    "receipt": lambda a: a.add_project_receipt("P", 400, reference="synthetic:receipt"),
    "commitment": lambda a: a.add_project_commitment("P", 900, paid_amount=100,
                                                       reference="synthetic:commitment"),
}
KEYS = {"cost": "cost_entries", "receipt": "receipt_entries", "commitment": "commitment_entries"}

def test_stale_instances_preserve_independent_financial_ledgers(tmp_path):
    a = StructuralProApp(tmp_path); a.create_project("کارگاه آزمایشی", "P")
    b = StructuralProApp(tmp_path); b.open_project("P")
    c = StructuralProApp(tmp_path); c.open_project("P")
    ACTIONS["cost"](a); ACTIONS["receipt"](b); ACTIONS["commitment"](c)
    after = StructuralProApp(tmp_path).open_project("P")
    assert all(len(after[KEYS[k]]) == 1 for k in KEYS)
    assert after["cost_entries"][0]["amount"] == 1200
    assert after["receipt_entries"][0]["amount"] == 400
    assert after["commitment_entries"][0]["paid_amount"] == 100
    assert after["boq"] == []
    for svc in (a,b,c): svc.store.close()

@pytest.mark.parametrize("writer,external", [("cost","receipt"), ("receipt","cost"),
                                              ("commitment","receipt"), ("receipt","commitment")])
def test_mid_write_conflict_rolls_back_only_stale_financial_change(tmp_path,monkeypatch,writer,external):
    first = StructuralProApp(tmp_path); first.create_project("تداخل مالی", "P")
    other = StructuralProApp(tmp_path)
    original = first.store.save
    injected = False
    def interfering_save(pid,project,*,expected_digest=None):
        nonlocal injected
        if not injected:
            injected = True
            ACTIONS[external](other)
        return original(pid,project,expected_digest=expected_digest)
    monkeypatch.setattr(first.store,"save",interfering_save)
    with pytest.raises(RuntimeError, match="changed since write began"):
        ACTIONS[writer](first)
    observed = StructuralProApp(tmp_path).open_project("P")
    assert observed.get(KEYS[writer],[]) == []
    assert len(observed[KEYS[external]]) == 1
    assert observed[KEYS[external]][0]["id"] == 1
    first.store.close(); other.store.close()

@pytest.mark.parametrize("kind", list(ACTIONS))
def test_same_ledger_separate_instances_assign_distinct_persisted_ids(tmp_path,kind):
    a = StructuralProApp(tmp_path); a.create_project("شناسه مالی", "P")
    b = StructuralProApp(tmp_path); b.open_project("P")
    one = ACTIONS[kind](a)
    two = ACTIONS[kind](b)
    assert (one["id"],two["id"]) == (1,2)
    opened = StructuralProApp(tmp_path).open_project("P")
    assert [r["id"] for r in opened[KEYS[kind]]] == [1,2]
    a.store.close(); b.store.close()

@pytest.mark.parametrize("kind",list(ACTIONS))
@pytest.mark.parametrize("amount",[float("nan"),float("inf"),-1])
def test_nonfinite_or_negative_ledger_value_does_not_modify_database(tmp_path,kind,amount):
    app = StructuralProApp(tmp_path); app.create_project("مبلغ نامعتبر", "P")
    snap = app.open_project("P")
    with pytest.raises((TypeError, ValueError, OverflowError)):
        if kind == "cost": app.add_project_cost("P","مصالح",amount)
        elif kind == "receipt": app.add_project_receipt("P",amount)
        else: app.add_project_commitment("P",amount)
    assert app.open_project("P") == snap
    app.store.close()
