"""Independent sample metrics exercised only with invented data."""
import json
from hashlib import sha256

import pytest

from core.drawings.pdf_component_evaluation import evaluate_pdf_component_holdout


def _bytes(document):
    return json.dumps(document, sort_keys=True).encode()


def _digest(content):
    return sha256(content).hexdigest()


def _object(name, operators, family="beam", title=None, box=(2, 2, 9, 9)):
    return {"object_id": name, "bbox_pt": box, "source_operator_ids": operators,
            "family": family, "title_ref": title}


def _fixture():
    source = "a" * 64
    plan = _bytes({"source_sha256": source, "split": "HOLDOUT", "regions": [
        {"review_id": name, "page": page, "bbox_pt": [0, 0, 20, 20]}
        for page, name in enumerate(("positive", "negative", "unknown", "explicit_miss", "empty"), 1)
    ]})
    a, b, c, d, e = (f"test:p{i}:d1:s1" for i in range(1, 6))
    shared = {"source_sha256": source, "plan_sha256": _digest(plan)}
    decisions = {
        "positive": {"decision": "MEMBERS",
                     "objects": [{**_object("true", [a], title="T1"), "title_reviewed": True}]},
        "negative": {"decision": "NON_MEMBER", "objects": []},
        "unknown": {"decision": "NOT_READABLE", "objects": []},
        "explicit_miss": {"decision": "MEMBERS", "objects": [_object("miss", [d], "column")]},
        "empty": {"decision": "NON_MEMBER", "objects": []},
    }
    for name, unit in decisions.items():
        unit["reviews"] = [{"reviewer_id": reviewer, "receipt_sha256": ch * 64, "date": "2026-01-20"}
                           for reviewer, ch in [("fixture-a", "b"), ("fixture-b", "c")]]
        unit["decision_sha256"] = "e" * 64
        unit["disagreement"] = False
    reference = {**shared, "governing_revision": "SYNTHETIC-R1", "units": decisions}
    predictions = {**shared, "engine_commit": "1" * 40, "units": {
        "positive": {"decision": "MEMBER_CANDIDATES", "objects": [
            _object("first", [a], "column", "WRONG"),
            _object("second", [a]),
        ]},
        "negative": {"decision": "MEMBER_CANDIDATES", "objects": [_object("false-member", [b])]},
        "unknown": {"decision": "AMBIGUOUS", "objects": []},
        "explicit_miss": {"decision": "NON_MEMBER", "objects": []},
        "empty": {"decision": "NON_MEMBER", "objects": []},
    }}
    return plan, reference, predictions, {i: [ref] for i, ref in enumerate((a, b, c, d, e), 1)}


def _evaluate(plan, reference, predictions, manifest, *, fixture=True):
    ref_bytes, pred_bytes = _bytes(reference), _bytes(predictions)
    return evaluate_pdf_component_holdout(
        plan, ref_bytes, pred_bytes, manifest, plan_sha256=_digest(plan),
        reference_sha256=_digest(ref_bytes), predictions_sha256=_digest(pred_bytes), fixture=fixture,
    )


def test_component_evaluation_counts_duplicates_conflicts_abstention_and_title_separately():
    result = _evaluate(*_fixture())
    assert result["status"] == "SYNTHETIC_FIXTURE_ONLY"
    assert result["geometry"] == {
        "tp": 1, "fp": 2, "fn": 1, "tn": 1, "precision": 1 / 3, "recall": 0.5, "f1": 0.4
    }
    assert result["family"]["beam"]["tp"] == 1
    assert result["family"]["beam"]["fn"] == 0
    assert result["family"]["beam"]["fp"] == 1
    assert result["family"]["column"]["fn"] == 1
    assert result["family"]["column"]["fp"] == 1
    assert result["title"]["fp"] == result["title"]["fn"] == 1
    assert result["coverage"]["abstained_regions"] == 1
    assert result["coverage"]["undecided_reference_regions"] == 1
    assert result["coverage"]["false_member_objects"] == 1
    assert result["coverage"]["false_non_member_objects"] == 1
    assert result["counts_by_reference"]["decided_regions"] == 4


def test_same_box_with_foreign_ink_is_not_a_match():
    plan, reference, pred, manifest = _fixture()
    other = "test:p1:d2:s1"
    manifest[1].append(other)
    for prediction in pred["units"]["positive"]["objects"]:
        prediction["source_operator_ids"] = [other]
    result = _evaluate(plan, reference, pred, manifest)
    assert result["geometry"]["tp"] == 0
    assert result["geometry"]["fn"] == 2
    assert result["family"]["beam"]["recall"] == 0


@pytest.mark.parametrize("invalid", ["foreign", "missing_scope", "duplicate_reviewer", "absent_adjudication",
                                     "duplicate_prediction", "payable", "digest"])
def test_evaluator_fails_closed_on_ineligible_source_authority(invalid):
    plan, reference, pred, manifest = _fixture()
    if invalid == "foreign":
        pred["units"]["positive"]["objects"][0]["source_operator_ids"] = ["test:p2:d1:s1"]
    elif invalid == "missing_scope":
        del pred["units"]["empty"]
    elif invalid == "duplicate_reviewer":
        reference["units"]["positive"]["reviews"][1]["reviewer_id"] = "fixture-a"
    elif invalid == "absent_adjudication":
        reference["units"]["positive"]["disagreement"] = True
    elif invalid == "duplicate_prediction":
        pred["units"]["positive"]["objects"][1]["object_id"] = "first"
    elif invalid == "payable":
        pred["units"]["positive"]["objects"][0]["financially_payable"] = True
    else:
        reference["source_sha256"] = "d" * 64
    with pytest.raises(ValueError):
        _evaluate(plan, reference, pred, manifest)


def test_zero_denominator_is_na_and_real_insufficient_support_withholds_scores():
    plan, reference, pred, manifest = _fixture()
    pred["units"]["positive"] = {"decision": "UNCLASSIFIED", "objects": []}
    pred["units"]["negative"] = {"decision": "UNCLASSIFIED", "objects": []}
    assert _evaluate(plan, reference, pred, manifest)["geometry"]["precision"] is None
    ref_bytes, pred_bytes = _bytes(reference), _bytes(pred)
    verified = []

    def test_authenticator(*args):
        verified.append(args)
        return True

    frozen_operators = {row["review_id"]: manifest[row["page"]] for row in json.loads(plan)["regions"]}
    result = evaluate_pdf_component_holdout(
        plan, ref_bytes, pred_bytes, manifest, plan_sha256=_digest(plan),
        reference_sha256=_digest(ref_bytes), predictions_sha256=_digest(pred_bytes),
        verify_reference=test_authenticator, operators_by_region=frozen_operators,
    )
    assert verified == [("a" * 64, _digest(plan), "SYNTHETIC-R1", _digest(ref_bytes))]
    assert result["status"] == "METRICS_NOT_MEASURABLE"
    assert result["geometry"]["fn"] == 2
    assert result["geometry"]["recall"] is None
    assert result["family"]["beam"]["estimate_status"] == "NOT_ESTIMABLE"


def test_another_region_cannot_supply_source_operators():
    plan, reference, pred, manifest = _fixture()
    refs = {row["review_id"]: manifest[row["page"]].copy() for row in json.loads(plan)["regions"]}
    same_page_elsewhere = "test:p1:d88:s1"
    manifest[1].append(same_page_elsewhere)
    pred["units"]["positive"]["objects"][0]["source_operator_ids"] = [same_page_elsewhere]
    ref_bytes, pred_bytes = _bytes(reference), _bytes(pred)
    with pytest.raises(ValueError, match="out-of-region PDF object"):
        evaluate_pdf_component_holdout(
            plan, ref_bytes, pred_bytes, manifest, plan_sha256=_digest(plan),
            reference_sha256=_digest(ref_bytes), predictions_sha256=_digest(pred_bytes),
            verify_reference=lambda *_: True, operators_by_region=refs,
        )


def test_duplicate_keys_rejected_even_if_the_bytes_are_pinned():
    plan, reference, pred, manifest = _fixture()
    pred_bytes = _bytes(pred).replace(b'"engine_commit": ', b'"engine_commit": "other", "engine_commit": ', 1)
    ref_bytes = _bytes(reference)
    with pytest.raises(ValueError, match="Duplicate key"):
        evaluate_pdf_component_holdout(
            plan, ref_bytes, pred_bytes, manifest, plan_sha256=_digest(plan),
            reference_sha256=_digest(ref_bytes), predictions_sha256=_digest(pred_bytes), fixture=True,
        )


def test_unverified_receipt_hashes_never_produce_real_metrics():
    plan, reference, predictions, manifest = _fixture()
    result = _evaluate(plan, reference, predictions, manifest, fixture=False)
    assert result["status"] == "METRICS_NOT_MEASURABLE"
    assert result["reference_status"] == "GOLD_PENDING_INDEPENDENT_REVIEW"
    assert result["geometry"]["tp"] is None and result["coverage"]["abstention_rate"] is None


def test_family_matching_does_not_prefer_unrelated_prediction_id():
    plan, reference, predictions, manifest = _fixture()
    a = _evaluate(plan, reference, predictions, manifest)
    guesses = predictions["units"]["positive"]["objects"]
    guesses[0]["object_id"], guesses[1]["object_id"] = guesses[1]["object_id"], guesses[0]["object_id"]
    b = _evaluate(plan, reference, predictions, manifest)
    assert a["geometry"] == b["geometry"]
    assert a["family"] == b["family"]
    assert a["family"]["beam"]["tp"] == 1
