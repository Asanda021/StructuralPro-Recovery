"""Read-only verified crosswalk for 2D / 3D / project tree / BOQ selection.

This index never equates IFC GlobalId with a project MemberID or a BOQ row by
string similarity. It only resolves explicit, independently reviewed links
against identities from the current source and the actual project snapshots.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any


def _ident(value: Any, *, what: str) -> str:
    if not isinstance(value, str) or not value or value != value.strip():
        raise ValueError(f"شناسه مستند {what} نامعتبر است.")
    return value


@dataclass(frozen=True)
class SelectionLink:
    global_id: str
    member_id: str | None
    shape_id: str | None
    boq_row_id: str | None
    evidence_ref: str
    reviewer_id: str


@dataclass(frozen=True)
class SelectionResult:
    status: str
    origin: str
    identifier: str
    global_ids: tuple[str, ...] = ()
    member_ids: tuple[str, ...] = ()
    shape_ids: tuple[str, ...] = ()
    boq_row_ids: tuple[str, ...] = ()


class VerifiedSelectionCrosswalk:
    """Immutable evidence-authorized lookup: selection cannot write to project."""

    _ORIGINS = {"2d": "global_id", "3d": "global_id",
                "tree": "member_id", "boq": "boq_row_id"}

    def __init__(
        self, *,
        project_id: str, source_sha256: str, revision: str,
        real_global_ids: set[str], real_member_ids: set[str],
        real_boq_row_ids: set[str], approved_records: list[dict],
        trusted_review_pairs: frozenset[tuple[str, str]],
    ):
        self.project_id = _ident(project_id, what="پروژه")
        self.revision = _ident(revision, what="نسخه")
        if (not isinstance(source_sha256, str) or len(source_sha256) != 64 or
            any(c not in "0123456789abcdef" for c in source_sha256)):
            raise ValueError("هش مستند IFC برای ناوبری نامعتبر است.")
        self.source_sha256 = source_sha256
        self.allowed = {
            "global_id": frozenset(real_global_ids),
            "member_id": frozenset(real_member_ids),
            "boq_row_id": frozenset(real_boq_row_ids),
        }
        for category, identifiers in self.allowed.items():
            if not all(isinstance(x, str) and x.strip() == x and x for x in identifiers):
                raise ValueError(f"شناسه‌های مرجع {category} معتبر نیستند.")
        if not isinstance(trusted_review_pairs, frozenset) or not trusted_review_pairs:
            raise ValueError('ثبت مستقل تأیید پیوندها در سرویس معتبر یافت نشد.')
        if not isinstance(approved_records, list):
            raise ValueError("جدول پیوند مستند موجود نیست.")
        keys = set()
        records = []
        for row in approved_records:
            if not isinstance(row, dict):
                raise ValueError("سطر ارتباط هویت معتبر نیست.")
            if (row.get("project_id") != project_id or
                row.get("source_sha256") != source_sha256 or
                row.get("revision") != revision or
                row.get("review_status") != "approved"):
                raise ValueError("پیوند فاقد تأیید مستقل، منشأ یا نسخه معتبر است.")
            global_id = _ident(row.get("global_id"), what="IFC")
            if global_id not in self.allowed["global_id"]:
                raise ValueError("GlobalId پیوند در IFC واقعی وجود ندارد.")
            member_id = row.get("member_id")
            shape_id = row.get("shape_id")
            boq = row.get("boq_row_id")
            if member_id is not None and _ident(member_id, what="عضو") not in self.allowed["member_id"]:
                raise ValueError("عضو پیوند در درخت واقعی وجود ندارد.")
            if boq is not None and _ident(boq, what="BOQ") not in self.allowed["boq_row_id"]:
                raise ValueError("ردیف BOQ در اطلاعات واقعی پروژه وجود ندارد.")
            if shape_id is not None:
                _ident(shape_id, what="هندسه")
            if member_id is None and boq is None and shape_id is None:
                raise ValueError("پیوند فاقد هویت مقصد است.")
            evidence = _ident(row.get("evidence_ref"), what="مدرک پیوند")
            reviewer = _ident(row.get("reviewer_id"), what="بازبین")
            if (evidence, reviewer) not in trusted_review_pairs:
                raise ValueError('تأیید مستقل مدرک و هویت بازبین معتبر نیست.')
            key = (global_id, member_id, shape_id, boq)
            if key in keys:
                raise ValueError("پیوند مستند تکراری است.")
            keys.add(key)
            records.append(SelectionLink(global_id, member_id, shape_id,
                                         boq, evidence, reviewer))
        self.links = tuple(records)

    def resolve(self, *, origin: str, identifier: str,
                project_id: str, source_sha256: str, revision: str) -> SelectionResult:
        if (project_id != self.project_id or source_sha256 != self.source_sha256 or
            revision != self.revision):
            raise ValueError("منبع یا پروژه تغییر کرده؛ انتخاب به نسخه قدیمی وصل نمی‌شود.")
        if origin not in self._ORIGINS:
            raise ValueError("نمای انتخاب مبدأ ناشناخته است.")
        identifier = _ident(identifier, what="انتخاب")
        category = self._ORIGINS[origin]
        if identifier not in self.allowed[category]:
            return SelectionResult("unverified", origin, identifier)
        matches = [x for x in self.links if getattr(x, category) == identifier]
        if not matches:
            return SelectionResult("unlinked", origin, identifier)
        return SelectionResult(
            "linked", origin, identifier,
            tuple(sorted({r.global_id for r in matches})),
            tuple(sorted({r.member_id for r in matches if r.member_id is not None})),
            tuple(sorted({r.shape_id for r in matches if r.shape_id is not None})),
            tuple(sorted({r.boq_row_id for r in matches if r.boq_row_id is not None})),
        )
