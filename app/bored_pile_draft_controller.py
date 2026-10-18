"""Non-Qt control layer for the documented bored-pile DRAFT workflow.

Only explicit evidence, preview and CAS-protected draft persistence. No review,
financial commitment, pricebook or BOQ writes are exposed by this controller.
"""
from __future__ import annotations

from copy import deepcopy
from hashlib import sha256
import json
from pathlib import Path

POLICY = 'bored_pile_reviewed_draft_v1'
MAX_JSON_BYTES = 4 * 1024 * 1024


def _checked_document(path):
    """Load a physical JSON file, rejecting duplicate keys and guessed floats."""
    file = Path(path)
    if not file.is_file():
        raise ValueError('فایل واقعی دیتایل یا مالکیت پیدا نشد')
    size = file.stat().st_size
    if size < 2 or size > MAX_JSON_BYTES:
        raise ValueError('حجم فایل سند خارج از محدوده مجاز است')
    raw = file.read_bytes()
    if len(raw) > MAX_JSON_BYTES:
        raise ValueError('حجم واقعی سند بیش از حد مجاز است')

    def reject_duplicate(items):
        out = {}
        for key, value in items:
            if key in out:
                raise ValueError('کلید تکراری در سند JSON')
            out[key] = value
        return out

    def reject_number(_):
        raise ValueError('مقدار float یا عدد نامتناهی در سند JSON مجاز نیست')

    try:
        obj = json.loads(raw.decode('utf-8-sig'), object_pairs_hook=reject_duplicate,
                         parse_float=reject_number, parse_constant=reject_number)
    except (UnicodeError, json.JSONDecodeError) as exc:
        raise ValueError('سند JSON معتبر نیست') from exc
    if not isinstance(obj, dict):
        raise ValueError('ریشه سند باید شیء JSON باشد')
    return obj, {'path': str(file.resolve()), 'sha256': sha256(raw).hexdigest()}


def _text(value, label):
    if not isinstance(value, str) or not value.strip() or value != value.strip():
        raise ValueError(label + ': مقدار متنی صریح لازم است')
    return value


class PileDraftController:
    """Stateful adapter for real StructuralProApp APIs; Qt uses this directly."""

    def __init__(self, service, project_id):
        self.service = service
        self.project_id = _text(project_id, 'شناسه پروژه')
        if service.open_project(self.project_id) is None:
            raise ValueError('پروژه موجود نیست')
        self.data = None
        self.revision = 0
        self.saved_data = None

    def _set(self, data, revision):
        self.data = deepcopy(data)
        self.saved_data = deepcopy(data)
        self.revision = revision
        return deepcopy(self.data)

    def new(self, floor_id, group_id):
        from core.takeoff.bored_pile_detail import new_detail
        data = new_detail(_text(floor_id, 'طبقه'), _text(group_id, 'گروه شمع'))
        self.data = deepcopy(data)
        self.saved_data = None
        self.revision = 0
        return deepcopy(self.data)

    def load(self, floor_id, group_id):
        floor_id, group_id = _text(floor_id, 'طبقه'), _text(group_id, 'گروه شمع')
        record = self.service.get_structural_member(self.project_id, 'bored_pile',floor_id,group_id)
        if record is None:
            raise ValueError('گروه شمع در پروژه پیدا نشد')
        data = record['data']
        if data.get('measurement_policy') != POLICY:
            raise ValueError('تبدیل خاموش رکورد تاریخی یا عمومی شمع ممنوع است')
        return self._set(data, record['revision'])

    def attach_input(self, path, *, source):
        """Caller supplies the explicit real source descriptor; never invent mode."""
        if self.data is None:
            raise ValueError('ابتدا گروه شمع را ایجاد یا بازگشایی کنید')
        if not isinstance(source, dict) or source.get('mode') not in ('manual', 'drawing'):
            raise ValueError('نوع منبع متره باید صریحاً انتخاب شود')
        document, evidence = _checked_document(path)
        if any(document.get(k) != v for k, v in (
            ('project_id', self.project_id),
            ('floor_id', self.data['floor_id']),
            ('group_id', self.data['member_id']))):
            raise ValueError('شناسه سند با پروژه، طبقه یا گروه شمع مغایرت دارد')
        src = document.get('source')
        if not isinstance(src, dict) or any(source.get(key) != src.get(other) for key,other in (
            ('source_id','source_id'),('approved_by','approved_by'),('measurement_ref','source_ref'))):
            raise ValueError('مشخصات منبع متره با دیتایل مستند برابر نیست')
        from core.takeoff.bored_pile_specialist_chat import compile_piles
        compile_piles(document)
        candidate = deepcopy(self.data)
        candidate['source'] = deepcopy(source)
        dt = candidate['pile_detail']
        # A new document necessarily invalidates the old ownership allocation.
        dt['input'] = document
        dt['input_document'] = {**evidence, 'reference': _text(src['source_ref'], 'مرجع دیتایل')}
        dt['ownership_document'] = {'path': '', 'sha256': '', 'reference': ''}
        dt['joint_document'] = {'path': '', 'sha256': '', 'reference': ''}
        self.data = candidate
        return deepcopy(self.data)

    def attach_ownership(self, path, *, reference):
        if self.data is None or not self.data['pile_detail'].get('input_document',{}).get('path'):
            raise ValueError('ابتدا دیتایل موتور شمع را بارگذاری کنید')
        reference = _text(reference, 'مرجع سند مالکیت')
        evidence, file = _checked_document(path)
        from core.takeoff.bored_pile_specialist_chat import compile_piles
        from core.takeoff.bored_pile_ownership_preflight import audit
        compiled = compile_piles(self.data['pile_detail']['input'])
        result = audit(self.data['pile_detail']['input'], compiled, evidence)
        if result['commit_allowed'] or result['ready_for_boq']:
            raise ValueError('گیت مالی مالکیت نباید باز شود')
        candidate = deepcopy(self.data)
        candidate['pile_detail']['ownership_document'] = {**file, 'reference': reference}
        candidate['pile_detail']['joint_document'] = {'path': '', 'sha256': '', 'reference': ''}
        self.data = candidate
        return deepcopy(result)

    def attach_joint(self, path, *, reference):
        """Attach a documented cross-member joint *audit*, never payment permission."""
        if self.data is None:
            raise ValueError('ابتدا گروه شمع را ایجاد یا بازگشایی کنید')
        dt = self.data['pile_detail']
        own = dt.get('ownership_document', {})
        if not own.get('path') or not dt.get('input_document', {}).get('path'):
            raise ValueError('ابتدا دیتایل و مالکیت مستقل شمع باید مستند شوند')
        reference = _text(reference, 'مرجع هندسه و مالکیت مشترک')
        # Re-read signed documents at the moment of attachment. Neither a
        # cached JSON object nor a previous audit can substitute current bytes.
        from core.takeoff.bored_pile_detail import validated
        from core.takeoff.bored_pile_specialist_chat import compile_piles
        from core.takeoff.bored_pile_ownership_preflight import read_evidence
        from core.takeoff.bored_pile_joint_crosswalk import audit_joint_contract
        validated(self.data, self.project_id)
        data = dt['input']
        compiled = compile_piles(data)
        owner = read_evidence(own['path'], own['sha256'])
        joint, file = _checked_document(path)
        report = audit_joint_contract(data, compiled, owner, own['sha256'],
                                      joint, self.service.open_project(self.project_id))
        if report['commit_allowed'] or report['ready_for_boq'] or report.get('rows'):
            raise ValueError('ممیزی مشترک نباید مجوز مالی یا ردیف BOQ صادر کند')
        candidate = deepcopy(self.data)
        candidate['pile_detail']['joint_document'] = {**file, 'reference': reference}
        self.data = candidate
        return deepcopy(report)

    def amend_input(self, path, *, reason):
        """Revise documented pile geometry through the existing CAS journal only.

        Physical pile identities and primary source cannot change in place.
        Changed input revokes ownership/joint audits. A new financial lifecycle
        is *not* created here; the amended member remains a draft.
        """
        reason = _text(reason, 'علت اصلاحیه پیش‌نویس')
        if self.data is None or self.saved_data is None or self.revision < 1:
            raise ValueError('اصلاحیه فقط روی پیش‌نویس ذخیره‌شده معتبر است')
        if self.dirty:
            raise ValueError('ابتدا تغییرات ذخیره‌نشده را تعیین تکلیف کنید')
        previous = deepcopy(self.data)
        old = previous['pile_detail']
        input_doc = old['input_document']
        # Verify the old immutable evidence against its stored SHA first.
        current, current_ref = _checked_document(input_doc['path'])
        if current_ref['sha256'] != input_doc['sha256'] or current != old['input']:
            raise ValueError('مدرک قبلی شمع تغییر کرده یا از نسخه ذخیره‌شده جدا شده است')
        incoming, new_ref = _checked_document(path)
        if new_ref['sha256'] == input_doc['sha256'] or incoming == current:
            raise ValueError('اصلاحیه بدون تغییر واقعی دیتایل پذیرفته نیست')
        if any(incoming.get(key) != current.get(key)
               for key in ('project_id', 'floor_id', 'group_id', 'source', 'datum')):
            raise ValueError('اصلاح هویت پروژه، منبع یا مبنای مختصات نیازمند گردش مستقل است')
        from core.takeoff.bored_pile_specialist_chat import compile_piles
        compiled_incoming = compile_piles(incoming)
        def physical_ids(document):
            return {(pile['id'], pile['physical_id']) for pile in document['piles']}
        if physical_ids(incoming) != physical_ids(current):
            raise ValueError('تغییر تعداد یا هویت فیزیکی شمع‌ها نیازمند پرونده مستقل است')
        if compiled_incoming['source_sha256'] == compile_piles(current)['source_sha256']:
            raise ValueError('اصلاحیه فاقد تغییر محاسباتی یا دیتایل معتبر است')
        try:
            self.attach_input(path, source=deepcopy(previous['source']))
            # Existing ReviewedStructuralWorkflow.save_draft writes previous
            # version + reason into structural_member_history under SQLite CAS.
            return self.save(reason='اصلاحیه پیش‌نویس شمع: ' + reason)
        except Exception:
            # No local half-revision survives a rejected journal/CAS write.
            self.data = previous
            raise

    def set_preflight(self, *, reviewer, ownership_reference):
        if self.data is None:
            raise ValueError('گروه شمع بارگذاری نشده است')
        self.data['pile_detail']['preflight'] = {
            'reviewer': _text(reviewer, 'بازبین پیش‌نمایش'),
            'ownership_reference_claim': _text(ownership_reference, 'مرجع ممیزی مالکیت')}

    def preview(self):
        if self.data is None:
            raise ValueError('گروه شمع بارگذاری نشده است')
        from core.takeoff.bored_pile_detail import preview
        # This does not persist an unsaved edit and never moves an item to BOQ.
        result = preview(deepcopy(self.data), project_id=self.project_id,
                         project=self.service.open_project(self.project_id))
        if result.get('commit_allowed') or result.get('ready') or result.get('rows'):
            raise ValueError('پیش‌نمایش شمع نباید مجوز ثبت قطعی یا مالی داشته باشد')
        return result

    def save(self, *, reason=None):
        if self.data is None:
            raise ValueError('پیش‌نویس شمع موجود نیست')
        kwargs = {} if reason is None else {'reason': _text(reason, 'علت نسخه')}
        record = self.service.save_structural_member_draft(
            self.project_id, deepcopy(self.data), expected_revision=self.revision, **kwargs)
        if record.get('data',{}).get('measurement_policy') != POLICY:
            raise ValueError('پاسخ ذخیره با قرارداد شمع سازگار نیست')
        return self._set(record['data'],record['revision'])

    @property
    def dirty(self):
        return self.data is not None and self.data != self.saved_data
