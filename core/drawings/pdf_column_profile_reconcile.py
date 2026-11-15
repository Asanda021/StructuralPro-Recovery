"""Column steel-piece takeoff *candidate* corroboration, never BOQ acceptance.

Input: independently normalized and provenanced plan glyphs, a section
component specification (e.g. 2 IPE16 per location), and a reference rize
metre/Excel row. The section's piece multiplier MUST come from the drawing;
it is NEVER inferred from a reference number or from floor-plan count.

This module does not extract the section annotation, infer source revision,
determine the levels where columns exist, validate per-member identity or
approve financial rows. All results remain review candidates.
"""
from __future__ import annotations

from collections import Counter, defaultdict
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP
from typing import Iterable, Mapping
import re

_DIGITS = str.maketrans('۰۱۲۳۴۵۶۷۸۹٠١٢٣٤٥٦٧٨٩', '01234567890123456789')


def _decimal(value, *, zero_allowed=False):
    if isinstance(value, bool) or value is None:
        raise ValueError('decimal quantity missing')
    string = str(value).strip().translate(_DIGITS).replace('٫', '.')
    if not re.fullmatch(r'\+?\d+(?:\.\d+)?', string):
        raise ValueError('unverified decimal convention')
    try:
        value = Decimal(string)
    except (InvalidOperation, ValueError) as exc:
        raise ValueError('invalid decimal') from exc
    if not value.is_finite() or value < 0 or (not zero_allowed and value == 0):
        raise ValueError('positive finite decimal expected')
    return value


def _source_ref(row: Mapping) -> dict:
    doc = str(row.get('document_id') or '').strip()
    page = row.get('page')
    if not doc or type(page) is not int or page < 1:
        raise ValueError('a valid document_id and page are mandatory')
    return {'document_id':doc, 'page':page}


def _tag(row: Mapping) -> str:
    import re
    value = str(row.get('tag') or '').strip().upper().replace('-', '')
    if not re.fullmatch(r'C[1-9][0-9]{0,2}', value):
        raise ValueError('only explicit numbered C-column types are supported')
    return value


def _spec(row: Mapping) -> dict:
    src = _source_ref(row)
    tag = _tag(row)
    per = row.get('profiles_per_symbol')
    if type(per) is not int or not 1 <= per <= 16:
        raise ValueError('explicit positive section profile count required')
    profile = str(row.get('profile') or '').strip().upper().replace(' ', '')
    if not profile or len(profile) > 30 or not profile.isalnum():
        raise ValueError('explicit section profile required')
    kind = str(row.get('evidence_kind') or '').strip()
    if kind not in ('SOURCE_VERIFIED_VECTOR_DETAIL', 'VISUALLY_REVIEWED_PDF_DETAIL'):
        raise ValueError('detail component witness missing')
    return {**src, 'tag':tag,'profile':profile,'profiles_per_symbol':per,
            'length_m':_decimal(row.get('length_m')), 'evidence_kind':kind}


def _reference(row: Mapping) -> dict:
    src=_source_ref(row)
    tag=_tag(row)
    pieces=row.get('profile_piece_count')
    if type(pieces) is not int or pieces < 1:
        raise ValueError('positive integer reference profile pieces required')
    profile=str(row.get('profile') or '').strip().upper().replace(' ','')
    if not profile or not profile.isalnum():
        raise ValueError('reference profile missing')
    mass=_decimal(row.get('unit_mass_kg_per_m'))
    length=_decimal(row.get('length_m'))
    total=_decimal(row.get('reported_mass_kg'))
    return {**src,'tag':tag,'profile':profile,'profile_piece_count':pieces,
            'length_m':length, 'unit_mass_kg_per_m':mass,
            'reported_mass_kg':total,
            'workbook_anchor':str(row.get('workbook_anchor') or '')}


def reconcile_column_profile_components(
    plan_nodes: Iterable[Mapping], section_specs: Iterable[Mapping],
    reference_rows: Iterable[Mapping],
) -> dict:
    """Explain type-level profile count/weight parity without approving anything.

    Do not use this output to assert a physical member is unique across floors,
    and do not multiply detected glyphs by the number of architectural floors.
    """
    found=defaultdict(list)
    invalid=[]
    used_ids=set()
    plan_sheet_keys=set()
    for i,node in enumerate(plan_nodes):
        try:
            if not isinstance(node, Mapping):
                raise ValueError('node must be a mapping')
            tag = _tag({'tag':node.get('suggested_type')})
            src = _source_ref(node)
            cid = str(node.get('candidate_id') or '').strip()
            if not cid or cid in used_ids:
                raise ValueError('duplicate/missing grid position identity')
            label=node.get('vector_type_label_evidence')
            axis=node.get('independent_axis_grid_witness')
            detail=node.get('cross_sheet_type_reference')
            if not isinstance(label,Mapping) or not isinstance(axis,Mapping) or not isinstance(detail,Mapping):
                raise ValueError('independent glyph/axis/type-detail witness missing')
            if label.get('tag') != tag or detail.get('tag') != tag:
                raise ValueError('plan glyph and type-detail disagree')
            if axis.get('status') != 'PROPOSED_INDEPENDENT_GRID_REGISTRATION':
                raise ValueError('grid was not independently registered')
            if (axis.get('axis_document_id') != src['document_id'] or
                type(axis.get('axis_page')) is not int or
                axis['axis_page'] < 1 or axis['axis_page'] == src['page']):
                raise ValueError('axis witness must come from a distinct sheet of the same document')
            if node.get('financially_payable') is True or node.get('type_verified') is True:
                # Never treat a prior approval flag as source engineering evidence.
                raise ValueError('untrusted prior member/finance approval flag')
            used_ids.add(cid)
            plan_sheet_keys.add((src['document_id'],src['page']))
            found[tag].append({'id':cid,'source':src,'type_reference':detail})
        except (ValueError,TypeError) as exc:
            invalid.append({'index':i,'status':'BLOCKED_INVALID_PLAN_WITNESS','reason':str(exc)})

    spec_groups=defaultdict(list)
    for i,row in enumerate(section_specs):
        try:spec_groups[_tag(row)].append(_spec(row))
        except (ValueError,TypeError) as exc:
            invalid.append({'side':'section','index':i,'status':'BLOCKED_INVALID_SECTION_SPEC','reason':str(exc)})
    ref_groups=defaultdict(list)
    for i,row in enumerate(reference_rows):
        try:ref_groups[_tag(row)].append(_reference(row))
        except (ValueError,TypeError) as exc:
            invalid.append({'side':'reference','index':i,'status':'BLOCKED_INVALID_REFERENCE','reason':str(exc)})

    results=[]
    # Multiple column sheets could be identical revisions or different levels;
    # never silently aggregate them as separate physical member placements.
    unique_plan_sheet=len(plan_sheet_keys)==1
    for tag in sorted(set(found)|set(spec_groups)|set(ref_groups)):
        plan=found.get(tag,[])
        specs=spec_groups.get(tag,[])
        refs=ref_groups.get(tag,[])
        result={'tag':tag,'plan_symbol_candidates':len(plan),
                'source_position_ids':[v['id'] for v in plan],
                'section_sources':[{k:s[k] for k in ('document_id','page','evidence_kind')} for s in specs],
                'reference_sources':[{k:r[k] for k in ('document_id','page','workbook_anchor')} for r in refs],
                'section_piece_multiplier':None,
                'expected_piece_count':None,'independent_arithmetic_kg':None,
                'status':'BLOCKED_MISSING_EVIDENCE',
                'member_identity_approved':False,'financially_payable':False,
                'approved':False}
        if not unique_plan_sheet:
            result.update(status='BLOCKED_MULTIPLE_OR_MISSING_COLUMN_PLAN_SHEETS',
                          reason='Cannot infer unique physical instances from multiple/empty plans.')
        elif not plan or len(specs)!=1 or len(refs)!=1:
            result['reason']='One unambiguous source-backed detail, reference row, and plan glyph set are required.'
        else:
            spec,ref=specs[0],refs[0]
            result['section_piece_multiplier']=spec['profiles_per_symbol']
            # Every glyph must be tied to the same uniquely documented type detail.
            spec_ref=(spec['document_id'],spec['page'])
            try:
                consistent_all=all(
                    len(node['type_reference'].get('details', ())) == 1 and
                    all((d.get('document_id'),d.get('page')) == spec_ref and
                        d.get('dimension_kind') == 'length' and
                        _decimal(d.get('dimension_m')) == spec['length_m']
                        for d in node['type_reference']['details'])
                    for node in plan
                )
                consistent_all = consistent_all and all(
                    node['source']['document_id'] == spec['document_id'] and
                    node['source']['page'] != spec['page'] for node in plan
                )
            except (ValueError,TypeError):
                consistent_all=False
            expected_pieces=len(plan)*spec['profiles_per_symbol']
            result['expected_piece_count']=expected_pieces
            if not consistent_all:
                result.update(status='BLOCKED_DETAIL_IDENTITY_OR_LENGTH',
                              reason='Column mark type detail does not match the independent section evidence.')
            elif spec['profile']!=ref['profile'] or spec['length_m']!=ref['length_m']:
                result.update(status='BLOCKED_REFERENCE_PROFILE_OR_LENGTH',
                              reason='Source section profile or length disagrees with reference.')
            elif expected_pieces!=ref['profile_piece_count']:
                result.update(status='BLOCKED_PROFILE_PIECE_COUNT',
                              reason='Number of profiles is inconsistent with plan marks x section multiplier.')
            else:
                mass=(Decimal(expected_pieces)*spec['length_m']*ref['unit_mass_kg_per_m'])\
                     .quantize(Decimal('0.01'),rounding=ROUND_HALF_UP)
                result['independent_arithmetic_kg']=str(mass)
                result['reference_mass_kg']=str(ref['reported_mass_kg'])
                result['unit_mass_from_reference_kg_per_m']=str(ref['unit_mass_kg_per_m'])
                if mass!=ref['reported_mass_kg']:
                    result.update(status='BLOCKED_PROFILE_WEIGHT_MISMATCH',
                                  reason='Component formula disagrees with the reference reported mass.')
                else:
                    result.update(status='DOCUMENT_COMPONENT_ARITHMETIC_MATCH_UNVERIFIED',
                                  reason=('One plan + section count agrees with reference component arithmetic. '
                                          'Unit mass comes from reference; member revisions, installed levels '
                                          'and financial evidence are NOT independently verified.'))
        results.append(result)
    return {'rows':results,'invalid':invalid,
            'summary':dict(sorted(Counter(row['status'] for row in results).items())),
            'matched_component_type_rows':sum(r['status']=='DOCUMENT_COMPONENT_ARITHMETIC_MATCH_UNVERIFIED' for r in results),
            'approved_financial_rows':0,'physical_member_count':None,
            'floor_repetition_multiplier':None,'complete':False,'acceptance':'PARTIAL_NO_GO'}