"""Service-backed, fail-closed read-only cross-view selection for IFC and BOQ.

The trusted input is the *persisted* project, its SQLite CAS digest, independently
reviewed IFC identity records, and actual BOQ source receipts. An inferred
GlobalId/MemberID match, a BOQ item number or a price code is never an approval.
"""
from __future__ import annotations

from hashlib import sha256
import json
from pathlib import Path

from core.drawings.verified_selection import VerifiedSelectionCrosswalk
from core.drawings.ifc_pipeline import _binding


def _required(value, label):
    if not isinstance(value, str) or not value.strip() or value != value.strip():
        raise ValueError(f"شناسه معتبر {label} موجود نیست.")
    return value


def _boq_snapshot_key(project_id, digest, index, source_ids):
    """Ephemeral display key, bound to a version; NOT a persistent BOQ identifier."""
    encoded=json.dumps([project_id,digest,index,sorted(source_ids)],
                       ensure_ascii=False,separators=(",",":"))
    return "boq-view:"+sha256(encoded.encode()).hexdigest()


class VerifiedProjectSelection:
    """Read-only verified crosswalk tied to one immutable CAS+IFC revision."""

    def __init__(self, service, project_id, *, source_sha256, revision, real_global_ids):
        if service is None or not callable(getattr(service, "open_project", None)):
            raise ValueError("نمای چهارسویه نیازمند سرویس واقعی پروژه است.")
        self.service = service
        self.project_id = _required(project_id, "پروژه")
        self.source_sha256 = _required(source_sha256, "هش IFC")
        self.revision = _required(revision, "Revision مدل")
        self.digest = service.store.current_digest(project_id)
        if not isinstance(self.digest, str) or not self.digest:
            raise ValueError("CAS پروژه برای نمایش معتبر نیست.")
        project = service.open_project(project_id)
        if not isinstance(project, dict) or project.get("id") != project_id:
            raise ValueError("داده پروژه واقعی پیدا نشد.")
        self.project_version = (project.get("_meta") or {}).get("version")
        if not isinstance(self.project_version, int):
            raise ValueError("نسخه واقعی پروژه مشخص نیست.")
        real_global_ids = set(real_global_ids)
        if not real_global_ids:
            raise ValueError("شناسه‌های واقعی هندسه IFC در دسترس نیستند.")
        all_members = project.get("members", [])
        all_boq = project.get("boq", [])
        reviews = project.get("ifc_identity_reviews", [])
        if not all(isinstance(x,list) for x in (all_members,all_boq,reviews)):
            raise ValueError("دفتر عضو/BOQ/بازبینی پروژه ساختار نامعتبر دارد.")
        member_ids = set()
        self.member_floor_ids = {}
        for m in all_members:
            if not isinstance(m,dict) or not isinstance(m.get("id"),str):
                raise ValueError("شناسه درخت عضو واقعی نامعتبر است.")
            if m["id"] in member_ids:
                raise ValueError("درخت اعضا شناسه تکراری دارد.")
            member_ids.add(m["id"])
            self.member_floor_ids[m["id"]] = m.get("floor_id")
        approved, trusted, by_proposal = [], set(), {}
        self.review_proofs = []
        for review in reviews:
            if not isinstance(review,dict) or review.get("status")!="approved":
                raise ValueError("دفتر بازبینی هویت IFC نامعتبر است.")
            document = review.get("document")
            if not isinstance(document,dict):
                raise ValueError("سند IFC بازبینی موجود نیست.")
            if (document.get("source_sha256") != source_sha256 or
                    document.get("revision") != revision):
                continue  # other model revisions never navigate this viewer
            if review.get("global_id") not in real_global_ids:
                raise ValueError("هویت تأییدشده در مدل IFC بازشده موجود نیست.")
            # Validates source file, immutable evidence SHA, revisions, actual
            # floor/member, supersession/lineage. Never trust 'approved' alone.
            decision, element = _binding(project, review.get("proposal_id"))
            if decision != review or element["global_id"] != review["global_id"]:
                raise ValueError("مدرک بازبینی IFC با پروژه تطبیق ندارد.")
            proof = review.get("review") or {}
            reviewer = proof.get("user_id")
            if (not reviewer or reviewer == proof.get("author") or
                    reviewer != review.get("review",{}).get("user_id")):
                raise ValueError("بازبین مستقل IFC معتبر نیست.")
            collab = service.collaboration
            user = collab.users.get(reviewer)
            if user is None or not collab.roles[user.role].allows("review"):
                raise PermissionError("نقش بازبین IFC دیگر مجاز نیست.")
            evidence_ref = review.get("event_id")
            if not isinstance(evidence_ref,str) or not evidence_ref:
                raise ValueError("رویداد ممیزی بازبینی IFC موجود نیست.")
            if review["proposal_id"] in by_proposal:
                raise ValueError("تطبیق IFC دوباره ثبت شده است.")
            by_proposal[review["proposal_id"]] = review
            trusted.add((evidence_ref, reviewer))
            self.review_proofs.append((
                proof.get("evidence_path"),proof.get("evidence_sha256"),reviewer))
            approved.append(dict(
                project_id=project_id,source_sha256=source_sha256,revision=revision,
                global_id=review["global_id"],member_id=review["member_id"],
                shape_id=None,boq_row_id=None,
                evidence_ref=evidence_ref,reviewer_id=reviewer,review_status="approved"))
        # Stable persisted receipts link a BOQ snapshot row to a reviewed IFC
        # proposal only when its *exact* source ID belongs to a real takeoff.
        # The BOQ row itself may be an aggregation; never arbitrarily select one.
        takeoffs = project.get("takeoffs", [])
        if not isinstance(takeoffs,list):
            raise ValueError("دفتر متره پروژه نامعتبر است.")
        source_receipts = {}
        for t in takeoffs:
            if not isinstance(t,dict):
                raise ValueError("رسید متره ذخیره‌شده نامعتبر است.")
            sid = t.get("source_id")
            if not isinstance(sid,str) or not sid.strip():
                continue
            if sid in source_receipts:
                raise ValueError("شناسه منبع متره تکراری است؛ انتخاب BOQ مسدود شد.")
            provenance=t.get("provenance") or {}
            params=t.get("params") or {}
            if not isinstance(provenance,dict) or not isinstance(params,dict):
                raise ValueError("منشأ متره نامعتبر است.")
            # A takeoff's writable parameters are NOT a trusted identity
            # receipt. Only the canonical committed provenance can carry a
            # reviewed IFC source into BOQ navigation.
            meta = provenance.get("ifc_identity")
            if meta is not None and not isinstance(meta,dict):
                raise ValueError("هویت IFC در رسید BOQ نامعتبر است.")
            if params.get("ifc_identity") and not meta:
                # Unreviewed manual metadata must never establish a link.
                proposal_id = None
            else:
                proposal_id = meta.get("proposal_id") if meta else None
            source_receipts[sid] = proposal_id
        boq_labels = {}
        self.boq_readback = {}
        for pos, row in enumerate(all_boq):
            if not isinstance(row,dict):
                raise ValueError("ردیف BOQ واقعی نامعتبر است.")
            ids = row.get("source_ids")
            if not isinstance(ids,list) or not ids or not all(
                isinstance(x,str) and x and x==x.strip() for x in ids):
                # A row with no audited source can be displayed as unlinked,
                # but it must never navigate an IFC member.
                ids=[]
            key = _boq_snapshot_key(project_id,self.digest,pos,ids)
            if key in boq_labels:
                raise ValueError("شناسه نسخه‌ای BOQ تکراری است.")
            boq_labels[key] = f"ردیف {pos+1} | {row.get('description','بدون شرح')}"
            # Only persisted values. This display NEVER recalculates, rounds
            # or suggests quantities/prices.
            self.boq_readback[key] = {
                "label": boq_labels[key],
                "quantity": row.get("quantity"),
                "unit": row.get("unit"),
                "source_ids": tuple(ids),
            }
            for proposal_id in {source_receipts.get(sid) for sid in ids} - {None}:
                review = by_proposal.get(proposal_id)
                if review is None:
                    continue  # unapproved/stale IFC does not navigate
                approved.append(dict(
                    project_id=project_id,source_sha256=source_sha256,revision=revision,
                    global_id=review["global_id"],member_id=review["member_id"],
                    shape_id=None,boq_row_id=key,
                    evidence_ref=review["event_id"],reviewer_id=review["review"]["user_id"],
                    review_status="approved"))
        # Empty approved index is permitted: the UI displays actual members
        # and BOQ rows as unlinked, without inventing a mapping.
        self.index = VerifiedSelectionCrosswalk(
            project_id=project_id,source_sha256=source_sha256,revision=revision,
            real_global_ids=real_global_ids,real_member_ids=member_ids,
            real_boq_row_ids=set(boq_labels),approved_records=approved,
            trusted_review_pairs=frozenset(trusted) if trusted else frozenset({("__none__","__none__")}))
        self.boq_labels = boq_labels
        self.document_paths = frozenset(
            x["document"]["source_path"] for x in reviews
            if isinstance(x,dict) and isinstance(x.get("document"),dict)
            and x["document"].get("source_sha256")==source_sha256)

    def assert_current(self, *, source_sha256, revision):
        if source_sha256 != self.source_sha256 or revision != self.revision:
            raise RuntimeError("هش یا نسخه IFC تغییر کرده است؛ پیوند قبلی معتبر نیست.")
        if self.service.store.current_digest(self.project_id) != self.digest:
            raise RuntimeError("نسخه پروژه در SQLite تغییر کرده است؛ پیوندها باید دوباره خوانده شوند.")
        project = self.service.open_project(self.project_id)
        if not isinstance(project,dict) or (project.get("_meta") or {}).get("version") != self.project_version:
            raise RuntimeError("نسخه ثبت‌شده پروژه تغییر کرده است.")
        for evidence_path, expected_sha, reviewer in self.review_proofs:
            if not isinstance(evidence_path,str) or not isinstance(expected_sha,str):
                raise RuntimeError("مدرک بازبینی IFC معتبر نیست.")
            proof_path=Path(evidence_path)
            if not proof_path.is_file():
                raise RuntimeError("مدرک بازبینی IFC مفقود شده است.")
            digest=sha256()
            with proof_path.open("rb") as evidence_file:
                for part in iter(lambda:evidence_file.read(1024*1024),b""):
                    digest.update(part)
            if digest.hexdigest()!=expected_sha:
                raise RuntimeError("مدرک بازبینی IFC پس از تأیید تغییر کرده است.")
            user=self.service.collaboration.users.get(reviewer)
            if user is None or not self.service.collaboration.roles[user.role].allows("review"):
                raise PermissionError("مجوز بازبین IFC باطل شده است.")
        for source in self.document_paths:
            # Any in-place IFC change invalidates a previously reviewed link.
            doc = Path(source)
            if not doc.is_file():
                raise RuntimeError("منبع IFC حذف شده است.")
            h = sha256()
            with doc.open("rb") as f:
                for chunk in iter(lambda: f.read(1024*1024), b""):
                    h.update(chunk)
            if h.hexdigest() != self.source_sha256:
                raise RuntimeError("محتوای IFC تغییر کرده است.")
        return True

    def resolve(self, *, origin, identifier, source_sha256, revision):
        self.assert_current(source_sha256=source_sha256,revision=revision)
        return self.index.resolve(origin=origin,identifier=identifier,
            project_id=self.project_id,source_sha256=self.source_sha256,
            revision=self.revision)

    def inspector_text(self, result):
        """Persian live inspector from verified, unchanged SQLite BOQ values."""
        self.assert_current(source_sha256=self.source_sha256,revision=self.revision)
        if result.status != "linked":
            return "فاقد پیوند مستند؛ مقدار یا هندسه فرضی ایجاد نشده است."
        names = ", ".join(result.member_ids) or "فاقد عضو"
        floors = ", ".join(sorted({str(self.member_floor_ids[m])
            for m in result.member_ids if self.member_floor_ids.get(m) is not None})) or "نامشخص"
        lines = [
            "پروژه: " + self.project_id + " | طبقه: " + floors,
            "عضو: " + names + " | IFC GlobalId: " + ", ".join(result.global_ids),
            "نسخه: " + self.revision + " | SHA-256: " + self.source_sha256,
            "متره و ردیف‌ها فقط از نسخه ذخیره‌شده پروژه؛ بدون محاسبه جدید:",
        ]
        for key in result.boq_row_ids[:8]:
            row = self.boq_readback[key]
            amount = "نامشخص" if row["quantity"] is None else str(row["quantity"])
            unit = str(row["unit"]) if row["unit"] else "نامشخص"
            lines.append(row["label"] + " | مقدار ثبت‌شده: " + amount + " " + unit)
        if len(result.boq_row_ids)>8:
            lines.append(str(len(result.boq_row_ids)-8) +
                         " ردیف دیگر: برای مشاهده به جدول BOQ مراجعه کنید.")
        if not result.boq_row_ids:
            lines.append("هیچ ردیف BOQ تأییدشده برای این عضو وجود ندارد.")
        lines.append("نمای فقط‌خواندنی؛ این پنل تأیید یا انتقال مالی صادر نمی‌کند.")
        return "\n".join(lines)
