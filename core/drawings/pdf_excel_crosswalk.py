"""Fail-closed crosswalk of *normalized* PDF and Excel quantity evidence.

This does NOT parse drawings, infer member identity, assign precedence to Excel,
or approve BOQ/financial rows. The caller must provide independently sourced,
identified measurements. Ambiguities become reviewed questions, not quantities.
"""
from __future__ import annotations

from collections import Counter, defaultdict
from dataclasses import dataclass
from decimal import Decimal, InvalidOperation
import re
from typing import Iterable, Mapping, Any


_DIGITS = str.maketrans('۰۱۲۳۴۵۶۷۸۹٠١٢٣٤٥٦٧٨٩', '01234567890123456789')
_UNITS = {
    'm': 'm', 'متر': 'm', 'cm': 'cm', 'سانتیمتر': 'cm', 'سانتی متر': 'cm',
    'mm': 'mm', 'میلیمتر': 'mm', 'میلی متر': 'mm',
    'm2': 'm2', 'm²': 'm2', 'مترمربع': 'm2', 'متر مربع': 'm2',
    'm3': 'm3', 'm³': 'm3', 'مترمکعب': 'm3', 'متر مکعب': 'm3',
    'kg': 'kg', 'کیلوگرم': 'kg', 'عدد': 'count', 'count': 'count',
}


def _decimal(value: Any) -> Decimal:
    if isinstance(value, bool) or value is None:
        raise ValueError('quantity must be a finite number')
    s = str(value).strip().translate(_DIGITS).replace('٫', '.').replace('٬', '')
    # ASCII commas are ambiguous without an explicit decimal convention.
    if ',' in s:
        raise ValueError('ambiguous number separator')
    try:
        number = Decimal(s)
    except (InvalidOperation, ValueError) as exc:
        raise ValueError('invalid quantity') from exc
    if not number.is_finite() or number < 0:
        raise ValueError('quantity must be finite and non-negative')
    return number


def _unit(value: Any) -> str:
    value = str(value or '').strip().replace('\u200c', ' ')
    value = ' '.join(value.split()).casefold()
    if value not in _UNITS:
        raise ValueError('unit missing or unsupported')
    return _UNITS[value]


def _nonempty(row: Mapping, field: str) -> str:
    v = row.get(field)
    if v is None or not str(v).strip():
        raise ValueError(f'{field} missing')
    return str(v).strip()


def _source_item_code(row: Mapping) -> str:
    """Preserve leading zeroes and fail closed on inconsistent source-code aliases."""
    codes = []
    for field in ('price_code', 'item_code'):
        raw = row.get(field)
        if raw is None:
            continue
        value = str(raw).strip().translate(_DIGITS)
        if not value or not re.fullmatch(r'[0-9A-Za-z_-]{1,32}', value):
            raise ValueError(f'{field} invalid')
        codes.append(value)
    if len(set(codes)) > 1:
        raise ValueError('price_code and item_code conflict in one source')
    return codes[0] if codes else ''


def _validate_factors(row: Mapping, quantity: Decimal) -> None:
    """Optional, independently transcribed arithmetic, NOT an Excel formula parser."""
    if 'factors' not in row:
        return
    factors = row['factors']
    deductions = row.get('deductions', ())
    if not isinstance(factors, (list, tuple)) or not factors:
        raise ValueError('factors must be a nonempty list')
    if not isinstance(deductions, (list, tuple)):
        raise ValueError('deductions must be a list')
    total = Decimal(1)
    for factor in factors:
        total *= _decimal(factor)
    for deduction in deductions:
        total -= _decimal(deduction)
    if total < 0 or abs(total - quantity) > Decimal('0.000001'):
        raise ValueError('explicit factor/deduction arithmetic disagrees with quantity')


@dataclass(frozen=True)
class Evidence:
    side: str
    member_id: str
    scope_id: str
    trade: str
    measure: str
    unit: str
    quantity: Decimal
    source_ref: str
    revision: str
    locator: str
    formula_checked: bool
    source_item_code: str = ''

    @property
    def key(self) -> tuple[str, str, str, str, str]:
        return (self.member_id.casefold(), self.scope_id.casefold(),
                self.trade.casefold(), self.measure.casefold(), self.unit)

    def public(self) -> dict:
        return {'side': self.side, 'member_id': self.member_id,
                'scope_id': self.scope_id, 'trade': self.trade,
                'measure': self.measure, 'unit': self.unit,
                'quantity': str(self.quantity), 'source_ref': self.source_ref,
                'revision': self.revision, 'locator': self.locator,
                'formula_checked': self.formula_checked,
                **({'source_item_code': self.source_item_code} if self.source_item_code else {})}


def _evidence(row: Mapping, side: str) -> Evidence:
    if not isinstance(row, Mapping):
        raise ValueError('evidence must be a mapping')
    member = _nonempty(row, 'member_id')
    scope = _nonempty(row, 'scope_id')
    trade = _nonempty(row, 'trade')
    measure = _nonempty(row, 'measure')
    unit = _unit(row.get('unit'))
    quantity = _decimal(row.get('quantity'))
    source = _nonempty(row, 'source_ref')
    if side == 'pdf':
        page = row.get('page')
        if type(page) is not int or page <= 0:
            raise ValueError('PDF page missing/invalid')
        locator = f'p{page}' + (f":{row['view']}" if row.get('view') else '')
    else:
        sheet = _nonempty(row, 'sheet')
        cell = _nonempty(row, 'cell').upper()
        if not re.fullmatch(r'[A-Z]{1,3}[1-9][0-9]*', cell):
            raise ValueError('Excel cell address invalid')
        locator = f'{sheet}!{cell}'
    _validate_factors(row, quantity)
    return Evidence(side, member, scope, trade, measure, unit, quantity,
                    source, str(row.get('revision') or '').strip(), locator,
                    'factors' in row, _source_item_code(row))


def reconcile_pdf_excel(
    pdf_rows: Iterable[Mapping], excel_rows: Iterable[Mapping]
) -> dict:
    """Compare independently normalized evidence by *exact physical identity*.

    Does not take an approval parameter. Every output is a non-financial draft.
    Workbook data is never taken as inherently more authoritative than PDF.
    """
    groups: dict[tuple, dict[str, list[Evidence]]] = defaultdict(
        lambda: {'pdf': [], 'excel': []})
    invalid: list[dict] = []
    for side, items in (('pdf', pdf_rows), ('excel', excel_rows)):
        for index, row in enumerate(items):
            try:
                ev = _evidence(row, side)
            except (ValueError, TypeError) as exc:
                invalid.append({'side': side, 'index': index,
                                'status': 'BLOCKED_INVALID_EVIDENCE',
                                'reason': str(exc)})
                continue
            groups[ev.key][side].append(ev)

    results = []
    questions = []
    for key in sorted(groups):
        source = groups[key]
        pdf, excel = source['pdf'], source['excel']
        refs = [x.public() for x in pdf + excel]
        if len(pdf) != 1 or len(excel) != 1:
            if len(pdf) > 1 or len(excel) > 1:
                status, reason = 'BLOCKED_MULTIPLE_CANDIDATES', 'Multiple rows share one physical identity; duplicate/typical-sheet ownership unknown.'
            else:
                status, reason = 'BLOCKED_MISSING_COUNTERPART', 'Evidence is missing from PDF or Excel.'
            proposed = None
        elif ((pdf[0].source_item_code or excel[0].source_item_code)
              and pdf[0].source_item_code != excel[0].source_item_code):
            status = 'BLOCKED_SOURCE_CODE_CONFLICT'
            reason = 'Price/item source codes differ or one source code is missing; no automatic code correction or finance.'
            proposed = None
        elif pdf[0].quantity != excel[0].quantity:
            status, reason = 'BLOCKED_QUANTITY_CONFLICT', 'PDF and Excel quantities disagree; source precedence unverified.'
            proposed = {'quantity': str(excel[0].quantity),
                        'unit': excel[0].unit, 'source': excel[0].source_ref,
                        'locator': excel[0].locator,
                        'status': 'PROPOSED_UNVERIFIED',
                        'reason': 'Excel reference candidate; not automatically authoritative.'}
        elif pdf[0].revision and excel[0].revision and pdf[0].revision != excel[0].revision:
            status, reason = 'BLOCKED_REVISION_CONFLICT', 'Matching quantity but conflicting document revisions.'
            proposed = None
        else:
            status, reason, proposed = 'AGREED_CANDIDATE', 'Numeric and identity agreement; engineering approval is still required.', None
        result = {'identity': {'member_id': key[0], 'scope_id': key[1],
                              'trade': key[2], 'measure': key[3], 'unit': key[4]},
                  'status': status, 'reason': reason, 'evidence': refs,
                  'suggestion': proposed, 'approved': False, 'financially_payable': False}
        results.append(result)
        if status != 'AGREED_CANDIDATE':
            questions.append({'identity': result['identity'], 'status': status,
                              'question': 'Which source/version governs this physical item?',
                              'reason': reason, 'evidence': refs,
                              'suggestion': proposed,
                              'options': ['confirm_suggestion', 'correct', 'request_document']})
    counts = Counter(x['status'] for x in results)
    counts.update(x['status'] for x in invalid)
    return {'rows': results, 'invalid': invalid, 'questions': questions,
            'summary': dict(sorted(counts.items())),
            'approved_financial_rows': 0,
            'complete': False,  # No proof of exhaustive source-sheet/member coverage.
            'input_pairs_reconciled': bool(results) and not invalid and not questions,
            'acceptance': 'NOT_VERIFIED'}


def compare_pdf_printed_quantity(pdf_printed: str, excel_exact: Any) -> dict:
    """Compare Excel's exact number at the *verified PDF display precision*.

    The printed decimal places determine the rounding step. This confirms only
    a document-row transcription, never physical member identity or finance.
    """
    from decimal import ROUND_HALF_UP

    if not isinstance(pdf_printed, str):
        raise ValueError('printed PDF value must preserve its literal precision')
    literal = pdf_printed.strip().translate(_DIGITS).replace('٫', '.')
    if not re.fullmatch(r'[+-]?\d+(?:\.\d+)?', literal):
        raise ValueError('printed PDF value must be an unambiguous decimal')
    printed = Decimal(literal)  # Signed deductions are legal *document rows*.
    if isinstance(excel_exact, bool) or excel_exact is None:
        raise ValueError('invalid Excel document value')
    excel_text = str(excel_exact).strip().translate(_DIGITS).replace('٫', '.')
    if not re.fullmatch(r'[+-]?\d+(?:\.\d+)?', excel_text):
        raise ValueError('Excel document value must be unambiguous')
    exact = Decimal(excel_text)
    quantum = Decimal(1).scaleb(printed.as_tuple().exponent)
    try:
        rounded = exact.quantize(quantum, rounding=ROUND_HALF_UP)
    except InvalidOperation as exc:
        raise ValueError('rounding precision unsupported') from exc
    agrees = rounded == printed
    return {'status': 'AGREED_DISPLAY_CANDIDATE' if agrees else 'BLOCKED_DOCUMENT_MISMATCH',
            'pdf_printed': str(printed), 'excel_exact': str(exact),
            'excel_at_pdf_precision': str(rounded),
            'pdf_minus_excel_exact': str(printed - exact),
            'rounding_mode': 'ROUND_HALF_UP',
            'approved': False, 'member_identity_verified': False,
            'financially_payable': False}