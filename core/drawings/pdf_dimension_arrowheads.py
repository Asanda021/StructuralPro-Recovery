"""Recognize a narrow vector annotation pattern without taking its context ink."""
from collections import defaultdict
from dataclasses import dataclass
from itertools import pairwise


@dataclass(frozen=True)
class _Arrowhead:
    axis: int
    base: float
    tip: tuple[float, float]
    width: float

    @property
    def length(self):
        return abs(self.tip[self.axis] - self.base)


def _filled_head(path):
    if len(path) != 3 or any(op["paint"] != "f" or op["operator"] != "l" for op in path):
        return None
    segments = [tuple(map(tuple, op["points_pt"])) for op in sorted(path, key=lambda op: op["operator_index"])]
    vertices = tuple(segment[0] for segment in segments)
    if len(set(vertices)) != 3 or tuple(segment[1] for segment in segments) != vertices[1:] + vertices[:1]:
        return None
    for first, second, tip in zip(vertices, vertices[1:] + vertices[:1], vertices[2:] + vertices[:2], strict=True):
        for axis in (0, 1):
            across = 1 - axis
            if first[axis] != second[axis]:
                continue
            width = abs(first[across] - second[across])
            mid = (first[across] + second[across]) / 2
            head = _Arrowhead(axis, first[axis], tip, width)
            if .15 * head.length <= width <= .50 * head.length and abs(tip[across] - mid) <= .25 * width:
                return head
    return None


def _ordered_outward_pair(first, second):
    if first.axis != second.axis:
        return None
    axis = first.axis
    left, right = sorted((first, second), key=lambda head: head.base)
    if (left.tip[axis] < left.base < right.base < right.tip[axis]
            and left.tip[1 - axis] == right.tip[1 - axis]
            and right.base - left.base >= 3 * max(left.length, right.length)
            and min(left.width, right.width) >= .75 * max(left.width, right.width)
            and min(left.length, right.length) >= .75 * max(left.length, right.length)):
        return left, right
    return None


def _straight_stroke(op):
    return op["operator"] == "l" and op["paint"] == "s"


def paired_dimension_arrowhead_witnesses(operators, paint_sequences, *, max_checks):
    """Return owned heads plus supporting IDs, or ``None`` on comparison exhaustion.

    Both complete fills must immediately follow the painted connecting stroke,
    with matching perpendicular extensions at their tips. Extensions may
    end at the tips when adjacent pairs corroborate the same dimension chain.
    Identical overpainted extensions keep their IDs. Distinct competing
    intervals abstain. Spines and extensions stay in boundary review.
    """
    paths = defaultdict(list)
    for op in operators:
        paths[op["path_index"]].append(op)
    heads = {i: head for i, path in paths.items() if (head := _filled_head(path)) is not None}
    if not heads:
        return ()

    extensions = defaultdict(lambda: defaultdict(list))
    for path in paths.values():
        for op in path:
            if not _straight_stroke(op):
                continue
            a, b = op["points_pt"]
            for axis in (0, 1):
                if a[axis] == b[axis]:
                    interval = tuple(sorted((a[1 - axis], b[1 - axis])))
                    extensions[axis, a[axis]][interval].append(op["source_id"])

    checks, matches = 0, []
    chain_candidates = []
    starts, ends = defaultdict(list), defaultdict(list)
    for i, first in sorted(heads.items()):
        if i <= 1 or i + 1 not in heads or i - 1 not in paths:
            continue
        sequence = paint_sequences[i-2:i+1]
        if len(sequence) != 3 or any(type(value) is not int for value in sequence):
            continue
        if any(next_value != value + 1 for value, next_value in pairwise(sequence)):
            continue
        pair = _ordered_outward_pair(first, heads[i + 1])
        if pair is None:
            continue
        left, right = pair
        axis, cross = left.axis, left.tip[1 - left.axis]
        left_ext = extensions.get((axis, left.tip[axis]), {})
        right_ext = extensions.get((axis, right.tip[axis]), {})
        checks += len(paths[i-1]) + min(len(left_ext), len(right_ext))
        if checks > max_checks:
            return None

        def between_bases(op):
            if not _straight_stroke(op):
                return False
            a, b = op["points_pt"]
            return (a[1-axis] == b[1-axis] == cross
                    and sorted((a[axis], b[axis])) == [left.base, right.base])

        spines = [op["source_id"] for op in paths[i-1] if between_bases(op)]
        clearance = max(left.width, right.width) / 2
        span_limit = 6 * max(left.length, right.length)
        if len(spines) != 1:
            continue
        shared_intervals = left_ext.keys() & right_ext.keys()
        crossing = [(a, b) for a, b in shared_intervals
                    if cross - a >= clearance and b - cross >= clearance and b - a <= span_limit]
        if len(crossing) > 1:
            continue
        owned = tuple(op["source_id"] for op in (*paths[i], *paths[i+1]))

        if crossing:
            interval, = crossing
            matches.append((owned, (*spines, *sorted(left_ext[interval]), *sorted(right_ext[interval]))))
            continue

        # A single one-sided pair can still be non-dimension geometry.
        # Require a repeated span with a common tip and the same extension.
        # One-sided extensions can run to the drawing itself. Bound their
        # length by the witnessed span while requiring exact chain repetition.
        span = right.tip[axis] - left.tip[axis]
        one_sided = [(a, b) for a, b in shared_intervals
                     if cross in (a, b) and clearance <= b - a <= span]
        if len(one_sided) == 1:
            interval, = one_sided
            start_key = (axis, left.tip)
            end_key = (axis, right.tip)
            supporting = (*spines, *sorted(left_ext[interval]), *sorted(right_ext[interval]))
            index = len(chain_candidates)
            starts[start_key].append(index)
            ends[end_key].append(index)
            chain_candidates.append((start_key, end_key, interval, owned, supporting))

    eligible = {index for index, (start, end, _, _, _) in enumerate(chain_candidates)
                if len(starts[start]) == len(ends[end]) == 1
                and len(ends[start]) <= 1 and len(starts[end]) <= 1}
    for index, (start, end, interval, owned, supporting) in enumerate(chain_candidates):
        if index not in eligible:
            continue
        corroborating = []
        for neighbor in (*ends[start], *starts[end]):
            _, _, neighbor_interval, neighbor_heads, neighbor_support = chain_candidates[neighbor]
            if neighbor in eligible and interval == neighbor_interval:
                corroborating.extend((*neighbor_heads, *neighbor_support))
        if corroborating:
            matches.append((owned, tuple(dict.fromkeys((*supporting, *corroborating)))))
    return matches
