"""Read-only, source-neutral controls for historical PDF/XLS finance transcriptions.

Never resolves ambiguous pricebook identifiers, chooses a governing document,
constructs approved members, or pays BOQ rows. Inputs must be independently
transcribed; functions do not open private files or mutate project state.
Duplicate source codes require independent occurrence ownership proof.
"""
from __future__ import annotations

from collections import Counter
from decimal import Decimal, InvalidOperation
import re
from typing import Iterable, Mapping, Any

_DIGITS = str.maketrans('۰۱۲۳۴۵۶۷۸۹٠١٢٣٤٥٦٧٨٩', '01234567890123456789')


def _code(value: Any) -> str:
    s = str(value or '').strip().translate(_DIGITS)
    if not re.fullmatch(r'[0-9]{6}', s):
        raise ValueError('item code must be six digits; preserve leading zeros')
    return s


def _money(value: Any) -> Decimal:
    if value is None or isinstance(value, bool):
        raise ValueError('monetary amount missing or invalid')
    s = str(value).strip().translate(_DIGITS)
    if not re.fullmatch(r'\d+(?:\.\d+)?', s):
        raise ValueError('monetary amount must be finite nonnegative unambiguous decimal')
    try:
        n = Decimal(s)
    except (ValueError, InvalidOperation) as exc:
        raise ValueError('invalid monetary amount') from exc
    if not n.is_finite():
        raise ValueError('nonfinite monetary amount')
    return n


def audit_historical_financial_rows(rows: Iterable[Mapping]) -> dict:
    """Compare document amounts only. Never infer physical identity or finance.

    Rows require code, pdf_amount, excel_amount and two source locators.
    Duplicate codes remain blocked even when amounts agree because pairing
    occurrences by spreadsheet row order is not independent ownership proof.
    """
    source = list(rows)
    counts = Counter()
    for row in source:
        if isinstance(row, Mapping):
            try:
                counts[_code(row.get('code'))] += 1
            except ValueError:
                pass
    inspected = []
    for idx, row in enumerate(source):
        evidence = {'index': idx, 'status': 'BLOCKED_INVALID_EVIDENCE',
                    'approved': False, 'financially_payable': False}
        try:
            if not isinstance(row, Mapping):
                raise ValueError('row is not a mapping')
            code = _code(row.get('code'))
            pdf = _money(row.get('pdf_amount'))
            xls = _money(row.get('excel_amount'))
            pdf_locator = str(row.get('pdf_locator') or '').strip()
            excel_locator = str(row.get('excel_locator') or '').strip()
            if not pdf_locator or not excel_locator:
                raise ValueError('both document source locators are required')
            evidence.update({'code': code, 'pdf_amount': str(pdf),
                             'excel_amount': str(xls), 'delta_excel_minus_pdf': str(xls - pdf),
                             'pdf_locator': pdf_locator, 'excel_locator': excel_locator})
            if counts[code] > 1:
                evidence['status'] = 'BLOCKED_DUPLICATE_SOURCE_CODE'
            elif pdf != xls:
                evidence['status'] = 'BLOCKED_AMOUNT_CONFLICT'
            else:
                evidence['status'] = 'MATCHED_DOCUMENT_AMOUNT_ONLY'
            evidence['reason'] = {
                'BLOCKED_DUPLICATE_SOURCE_CODE': 'Same code occurs more than once; independent occurrence identity absent.',
                'BLOCKED_AMOUNT_CONFLICT': 'Document amounts disagree; governing revision unknown.',
                'MATCHED_DOCUMENT_AMOUNT_ONLY': 'Amounts match, but physical identity and financial approval unverified.',
            }[evidence['status']]
        except (TypeError, ValueError) as exc:
            evidence['reason'] = str(exc)
        inspected.append(evidence)
    statuses = Counter(x['status'] for x in inspected)
    return {'rows': inspected, 'summary': dict(sorted(statuses.items())),
            'total_rows': len(inspected),
            'matched_document_amount_only': statuses['MATCHED_DOCUMENT_AMOUNT_ONLY'],
            'approved_financial_rows': 0, 'financially_payable_rows': 0,
            'acceptance': 'NOT_ENGINEERING_OR_FINANCIAL_APPROVAL'}


def audit_legacy_code_labels(rows: Iterable[Mapping]) -> dict:
    """Compare item/chapter label against context, never rewrite source codes.

    Chapter label correction is presentation-only. An apparent item-code typo
    still requires governing evidence before any financial remapping.
    """
    issues = []
    for idx, row in enumerate(rows):
        item = {'index': idx, 'status': 'BLOCKED_INVALID_EVIDENCE', 'approved': False}
        try:
            if not isinstance(row, Mapping):
                raise ValueError('row is not a mapping')
            kind = str(row.get('kind') or '').strip()
            if kind == 'chapter':
                declared = str(row.get('declared') or '').strip().translate(_DIGITS)
                expected = str(row.get('context_chapter') or '').strip().translate(_DIGITS)
                if not re.fullmatch(r'\d{1,2}', declared) or not re.fullmatch(r'\d{1,2}', expected):
                    raise ValueError('invalid chapter label')
                status = 'PRESENTATION_LABEL_CORRECTION_CANDIDATE' if declared != expected else 'MATCHED_CHAPTER_LABEL'
            elif kind == 'code':
                declared, expected = _code(row.get('declared')), _code(row.get('context_code'))
                status = 'BLOCKED_SOURCE_CODE_CONFLICT' if declared != expected else 'MATCHED_SOURCE_CODE'
            else:
                raise ValueError('unknown kind')
            item.update({'kind': kind, 'declared': declared, 'context': expected,
                         'source_locator': str(row.get('source_locator') or '').strip(),
                         'status': status})
            if not item['source_locator']:
                raise ValueError('source locator required')
        except (TypeError, ValueError) as exc:
            item['status'] = 'BLOCKED_INVALID_EVIDENCE'
            item['reason'] = str(exc)
        issues.append(item)
    return {'rows': issues,
            'summary': dict(sorted(Counter(i['status'] for i in issues).items())),
            'approved_code_remappings': 0, 'source_mutations': 0}
