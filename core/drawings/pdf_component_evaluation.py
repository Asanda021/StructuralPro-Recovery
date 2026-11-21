"""Score a locked, independently reviewed PDF holdout outside the intake engine.

Geometry uses both the region IoU and the Jaccard overlap of the original
operator sets. Convex hulls do not replace reviewed ink. A negative unit is
an explicitly adjudicated region, so arbitrary empty sheet space adds no TN.
Scoring real data requires an external verifier of the signed reference.
"""
from collections import Counter, defaultdict
from datetime import date
from hashlib import sha256
from math import isfinite
import json
import re


_ABSTENTIONS = {"AMBIGUOUS", "BLOCKED", "UNCLASSIFIED"}
_REF_STATES = {"MEMBERS", "NON_MEMBER", "NOT_READABLE"}
_PRED_STATES = _ABSTENTIONS | {"MEMBER_CANDIDATES", "NON_MEMBER"}
_FAMILY_SUPPORT = 10
_MIN_GLOBAL_SUPPORT = (40, 20, 10)
_IOU_THRESHOLD = 0.5
_PRECISION_TARGET, _RECALL_TARGET = 0.95, 0.90
_COUNTS = ("tp", "fp", "fn", "tn")


def _is_sha(value, size=64):
    return isinstance(value, str) and re.fullmatch(rf"[0-9a-f]{{{size}}}", value) is not None


def _read_locked(content, expected):
    if not isinstance(content, bytes) or sha256(content).hexdigest() != expected:
        raise ValueError("Holdout artefact digest mismatch")
    def unique(pairs):
        record = dict(pairs)
        if len(record) != len(pairs):
            raise ValueError("Duplicate key in locked PDF holdout")
        return record

    record = json.loads(content, object_pairs_hook=unique)
    if not isinstance(record, dict):
        raise ValueError("Holdout artefact must be a JSON object")
    return record


def _box(values):
    if (not isinstance(values, (tuple, list)) or len(values) != 4
            or not all(type(value) in {int, float} and isfinite(value) for value in values)
            or values[0] >= values[2] or values[1] >= values[3]):
        raise ValueError("Invalid reviewed PDF rectangle")
    return tuple(values)


def _region_iou(left, right):
    a, b, c, d = left
    x, y, u, v = right
    intersection = max(0, min(c, u) - max(a, x)) * max(0, min(d, v) - max(b, y))
    return intersection / ((c - a) * (d - b) + (u - x) * (v - y) - intersection)


def _reviewer_id(record):
    if not isinstance(record, dict):
        raise ValueError("Malformed independent review receipt")
    signer = record.get("reviewer_id")
    if not isinstance(signer, str) or not signer.strip() or not _is_sha(record.get("receipt_sha256")):
        raise ValueError("Missing independent reviewer provenance")
    try:
        date.fromisoformat(record.get("date"))
    except (TypeError, ValueError) as exc:
        raise ValueError("Missing independent review date") from exc
    return signer.strip().casefold()


def _check_review(unit):
    reviews = unit.get("reviews", ())
    if not isinstance(reviews, list) or len(reviews) != 2 or not _is_sha(unit.get("decision_sha256")):
        raise ValueError("Every reference unit needs two signed reviews and a locked decision")
    signers = {_reviewer_id(row) for row in reviews}
    if len(signers) != 2 or reviews[0]["receipt_sha256"] == reviews[1]["receipt_sha256"]:
        raise ValueError("Reference reviews must be independent")
    if type(unit.get("disagreement")) is not bool:
        raise ValueError("Reviewer agreement must be explicit")
    if unit["disagreement"]:
        adjudicator = unit.get("adjudicator") or {}
        if (_reviewer_id(adjudicator) in signers
                or adjudicator["receipt_sha256"] in {row["receipt_sha256"] for row in reviews}):
            raise ValueError("Disagreement needs independent adjudication")


def _objects(unit, region, allowed_refs, seen, *, reference):
    expected = _REF_STATES if reference else _PRED_STATES
    rows = unit.get("objects")
    if (unit.get("decision") not in expected or not isinstance(rows, list)
            or bool(rows) != (unit["decision"] in {"MEMBERS", "MEMBER_CANDIDATES"}) or len(rows) > 128):
        raise ValueError("Invalid holdout disposition or object budget")
    result = []
    for row in rows:
        box = _box(row.get("bbox_pt"))
        ref_list = row.get("source_operator_ids", ())
        ident, family, title = row.get("object_id"), row.get("family"), row.get("title_ref")
        if (not isinstance(ident, str) or not ident.strip() or ident in seen
                or not isinstance(ref_list, (list, tuple)) or not ref_list
                or any(not isinstance(ref, str) for ref in ref_list)
                or len(set(ref_list)) != len(ref_list) or not set(ref_list) <= allowed_refs
                or not (region[0] <= box[0] < box[2] <= region[2] and region[1] <= box[1] < box[3] <= region[3])
                or (family is None and reference)
                or (family is not None and (not isinstance(family, str) or not family.strip()))
                or (title is not None and (not isinstance(title, str) or not title.strip()))
                or (reference and title is not None and row.get("title_reviewed") is not True)
                or row.get("financially_payable", False) is not False):
            raise ValueError("Foreign, duplicated, unauthorized or out-of-region PDF object")
        seen.add(ident)
        result.append({**row, "family": family, "box": box, "refs": frozenset(ref_list)})
    return result


def _match(truths, guesses, *, match_family=False):
    """Maximum cardinality at fixed thresholds, with deterministic IoU tie ordering."""
    choices = []
    for truth in truths:
        candidates = []
        for j, guess in enumerate(guesses):
            if match_family and truth["family"] != guess["family"]:
                continue
            area = _region_iou(truth["box"], guess["box"])
            common = len(truth["refs"] & guess["refs"]) / len(truth["refs"] | guess["refs"])
            if min(area, common) >= _IOU_THRESHOLD:
                candidates.append((min(area, common), guess["object_id"], j))
        choices.append([j for _, _, j in sorted(candidates, key=lambda c: (-c[0], c[1]))])
    matched = {}

    def claim(i, tried):
        for j in choices[i]:
            if j not in tried:
                tried.add(j)
                if j not in matched or claim(matched[j], tried):
                    matched[j] = i
                    return True
        return False

    for i in sorted(range(len(truths)), key=lambda i: (len(choices[i]), truths[i]["object_id"])):
        claim(i, set())
    return {i: j for j, i in matched.items()}


def _score(counts, measurable):
    tp, fp, fn, _ = (counts[key] for key in _COUNTS)
    return {**{key: counts[key] for key in _COUNTS},
            "precision": tp / (tp + fp) if measurable and tp + fp else None,
            "recall": tp / (tp + fn) if measurable and tp + fn else None,
            "f1": 2 * tp / (2 * tp + fp + fn) if measurable and 2 * tp + fp + fn else None}


def _title_pair(truth, guess, counts):
    if truth.get("title_reviewed") is not True:
        return
    expected = truth.get("title_ref")
    actual = guess.get("title_ref") if guess else None
    if expected == actual:
        if expected:
            counts["tp"] += 1
        elif guess:
            counts["tn"] += 1
        return
    counts["fp"] += actual is not None
    counts["fn"] += expected is not None


def evaluate_pdf_component_holdout(plan_json, reference_json, predictions_json, operators_by_page, *,
                                  plan_sha256, reference_sha256, predictions_sha256, fixture=False,
                                  verify_reference=None, operators_by_region=None):
    """Compare immutable partitions and return metrics, without modifying a review or BOQ.

    Every frozen region must occur in both files. No prediction on a positive
    region is a miss, including explicit abstention. An unreadable reference
    remains in coverage and out of the confusion denominators. `None` is N/A.

    For real data, the caller provides a trusted verifier outside these JSON
    files. It must authenticate the signed reference (two qualified reviewers
    and a third for disagreements) and governing revision against the four
    supplied identifiers. A receipt hash inside the reference is insufficient.
    Region operator sets come from the frozen, prediction-free source index.
    """
    plan = _read_locked(plan_json, plan_sha256)
    reference = _read_locked(reference_json, reference_sha256)
    predictions = _read_locked(predictions_json, predictions_sha256)
    source = plan.get("source_sha256")
    revision = reference.get("governing_revision")
    if (not _is_sha(source) or plan.get("split") != "HOLDOUT" or reference_sha256 == predictions_sha256
            or not isinstance(revision, str) or not revision.strip() or revision.strip().upper() == "UNKNOWN"
            or not _is_sha(predictions.get("engine_commit"), 40)
            or any(row.get("source_sha256") != source or row.get("plan_sha256") != plan_sha256
                   for row in (reference, predictions))):
        raise ValueError("Holdout source, revision or partition mismatch")
    regions = plan.get("regions", ())
    if not isinstance(regions, list) or not regions or len(regions) > 2500:
        raise ValueError("Holdout region budget exceeded or missing")
    ids = [region["review_id"] for region in regions]
    truth_units, prediction_units = reference.get("units"), predictions.get("units")
    if (not isinstance(truth_units, dict) or not isinstance(prediction_units, dict)
            or len(set(ids)) != len(ids) or set(ids) != truth_units.keys() or set(ids) != prediction_units.keys()):
        raise ValueError("Holdout records differ from the frozen region list")
    provenance = {"source_sha256": source, "governing_revision": revision,
                  "engine_commit": predictions["engine_commit"], "plan_sha256": plan_sha256,
                  "reference_sha256": reference_sha256, "predictions_sha256": predictions_sha256}
    if not fixture and (verify_reference is None or
                        verify_reference(source, plan_sha256, revision, reference_sha256) is not True):
        unknown = dict.fromkeys((*_COUNTS, "precision", "recall", "f1"))
        return {**provenance, "status": "METRICS_NOT_MEASURABLE", "thresholds_met": False,
                "reference_status": "GOLD_PENDING_INDEPENDENT_REVIEW",
                "geometry": unknown, "title": unknown.copy(), "family_micro": unknown.copy(),
                "family": {}, "family_macro": dict.fromkeys(("precision", "recall", "f1")),
                "counts_by_reference": {"authenticated_regions": 0},
                "coverage": {"total_regions": len(regions), "abstention_rate": None}}
    if not fixture and (operators_by_region is None or operators_by_region.keys() != set(ids)):
        raise ValueError("A verified holdout needs the frozen per-region source operators")
    allow = {page: frozenset(refs) for page, refs in operators_by_page.items()}
    boundaries, titles, families = Counter(), Counter(), defaultdict(Counter)
    coverage = Counter({key: 0 for key in (
        "abstained_regions", "undecided_reference_regions", "predictions_in_undecided_reference",
        "false_member_objects", "false_non_member_objects", "untyped_matched_objects",
    )})
    support, decided_pages = Counter(), set()
    seen_truth, seen_guesses = set(), set()
    work = 0
    for region in regions:
        ident, page = region["review_id"], region["page"]
        if type(page) is not int or not isinstance(ident, str) or not ident or page not in allow:
            raise ValueError("Foreign holdout region")
        truth_unit, guess_unit = truth_units[ident], prediction_units[ident]
        _check_review(truth_unit)
        box = _box(region["bbox_pt"])
        permitted = allow[page]
        if operators_by_region is not None:
            local_refs = frozenset(operators_by_region[ident])
            if local_refs - permitted:
                raise ValueError("Foreign operator in frozen PDF holdout region")
            permitted = local_refs
        truths = _objects(truth_unit, box, permitted, seen_truth, reference=True)
        guesses = _objects(guess_unit, box, permitted, seen_guesses, reference=False)
        work += 2 * len(truths) * len(guesses)
        if work > 300_000:
            raise ValueError("Holdout matching budget exhausted")
        coverage["abstained_regions"] += guess_unit["decision"] in _ABSTENTIONS
        if truth_unit["decision"] == "NOT_READABLE":
            coverage["undecided_reference_regions"] += 1
            coverage["predictions_in_undecided_reference"] += len(guesses)
            continue
        decided_pages.add(page)
        support["decided_regions"] += 1
        if not truths:
            support["negative_regions"] += 1
            boundaries["tn"] += guess_unit["decision"] == "NON_MEMBER"
            coverage["false_member_objects"] += len(guesses)
        coverage["false_non_member_objects"] += len(truths) if guess_unit["decision"] == "NON_MEMBER" else 0
        support["positive_objects"] += len(truths)
        support["reviewed_title_links"] += sum(row.get("title_reviewed") is True and row.get("title_ref") is not None
                                               for row in truths)
        matches = _match(truths, guesses)
        family_matches = _match(truths, guesses, match_family=True)
        family_guess_indices = set(family_matches.values())
        boundaries.update(tp=len(matches), fn=len(truths) - len(matches), fp=len(guesses) - len(matches))
        for i, truth in enumerate(truths):
            guess = guesses[matches[i]] if i in matches else None
            actual = guess["family"] if guess else None
            expected = truth["family"]
            families[expected]["tp" if i in family_matches else "fn"] += 1
            if guess and actual is None:
                coverage["untyped_matched_objects"] += 1
            _title_pair(truth, guess, titles)
        matched_guesses = set(matches.values())
        for j, guess in enumerate(guesses):
            if j not in family_guess_indices and guess["family"] is not None:
                families[guess["family"]]["fp"] += 1
            if j not in matched_guesses:
                titles["fp"] += guess.get("title_ref") is not None

    support["decided_sheets"] = len(decided_pages)
    enough = all(support[key] >= floor for key, floor in
                 zip(("positive_objects", "negative_regions", "decided_sheets"), _MIN_GLOBAL_SUPPORT, strict=True))
    for family in families.values():
        family["tn"] = boundaries["tn"]
    per_family = {}
    for name, counts in sorted(families.items()):
        positives = counts["tp"] + counts["fn"]
        estimable = fixture or (enough and positives >= _FAMILY_SUPPORT)
        per_family[name] = {**_score(counts, estimable), "support": positives,
                            "estimate_status": "ESTIMABLE" if estimable else "NOT_ESTIMABLE"}
    micro_counts = {key: sum(f[key] for f in families.values()) for key in _COUNTS}
    micro = _score(micro_counts, fixture or enough)
    macro = {}
    for key in ("precision", "recall", "f1"):
        valid = [row[key] for row in per_family.values() if row[key] is not None]
        macro[key] = sum(valid) / len(valid) if valid else None
    status = "SYNTHETIC_FIXTURE_ONLY" if fixture else "HOLDOUT_MEASURED" if enough else "METRICS_NOT_MEASURABLE"
    threshold_met = (not fixture and enough and micro["precision"] is not None and micro["recall"] is not None
                     and micro["precision"] >= _PRECISION_TARGET and micro["recall"] >= _RECALL_TARGET)
    return {
        **provenance, "status": status, "thresholds_met": threshold_met,
        "reference_status": "SYNTHETIC_FIXTURE" if fixture else "INDEPENDENT_REFERENCE_VERIFIED",
        "geometry": _score(boundaries, fixture or enough),
        "family": per_family, "family_micro": micro, "family_macro": macro,
        "title": _score(titles, fixture or (enough and support["reviewed_title_links"] >= _FAMILY_SUPPORT)),
        "counts_by_reference": dict(support), "coverage": {**coverage, "total_regions": len(regions),
            "abstention_rate": coverage["abstained_regions"] / len(regions)},
    }
