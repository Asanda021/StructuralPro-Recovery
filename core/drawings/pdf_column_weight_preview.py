"""Explicit, nonfinancial steel-weight *scenarios* for PDF column grid candidates.

The length schedule is source-observed, but occurrence, profile multiplicity,
unit mass and plates are independent assumptions. None are approved BOQ inputs.
"""
from __future__ import annotations

import csv
from decimal import Decimal, InvalidOperation
import json
import re
from pathlib import Path
from typing import Mapping


def _decimal(value, field: str, *, positive: bool = False) -> Decimal:
    if value is None or isinstance(value, bool):
        raise ValueError(f'{field} requires a numeric scenario value')
    raw = str(value).strip().translate(str.maketrans('۰۱۲۳۴۵۶۷۸۹٠١٢٣٤٥٦٧٨٩', '01234567890123456789')).replace('٫', '.')
    if not re.fullmatch(r'\d+(?:\.\d+)?', raw):
        raise ValueError(f'{field} must be an unambiguous decimal without separators or exponents')
    try:
        n = Decimal(raw)
    except InvalidOperation as exc:
        raise ValueError(f'{field} must be a decimal') from exc
    if not n.is_finite() or n < 0 or n > Decimal('1000000000000') or (positive and n == 0):
        raise ValueError(f'{field} must be {"positive" if positive else "nonnegative"} and finite')
    return n


def _integer(value, field: str) -> int:
    n = _decimal(value, field)
    if n != n.to_integral_value() or n > 100000:
        raise ValueError(f'{field} must be a reasonable whole number')
    return int(n)


def draft_component_weight_preview(schedule: Mapping, scenarios: Mapping) -> dict:
    """User-specified profile/plate assumptions; never claim extracted steel mass.

    Each type scenario: ``profile_count``; ``profile_unit_mass_kg_m``;
    optional ``profile_name``; ``plate_count`` and dimensions in millimetres.
    Density defaults to an **explicit engineering assumption** of 7850 kg/m³.
    Missing input blocks that type instead of silently assuming a zero weight.
    """
    if schedule.get('status') not in ('DRAFT_COMPLETE_GRID_EVIDENCE', 'PARTIAL_WITH_BLOCKED_GRID_NODES'):
        raise ValueError('Source-backed draft column schedule is required')
    if not isinstance(scenarios, Mapping):
        raise ValueError('Scenario must be a type-to-input mapping')
    groups = schedule.get('groups', ())
    if not groups:
        raise ValueError('There are no source-backed column lengths')
    known = {g['type_tag'] for g in groups}
    if set(scenarios) - known:
        raise ValueError('Scenario contains an unknown column type')
    results = []
    total_profiles = total_plates = Decimal('0')
    for g in groups:
        tag = g['type_tag']
        raw = scenarios.get(tag)
        result = {'type_tag': tag, 'grid_location_candidates': g['grid_location_candidates'],
                  'printed_type_length_m': g['printed_type_length_m'],
                  'draft_extended_length_m': g['draft_extended_length_m'],
                  'status': 'BLOCKED_MISSING_USER_SCENARIO', 'profile_mass_kg': None,
                  'plate_mass_kg': None, 'estimated_total_kg': None,
                  'approved': False, 'financially_payable': False}
        if raw is None:
            results.append(result)
            continue
        if not isinstance(raw, Mapping):
            raise ValueError(f'{tag}: scenario must be a mapping')
        count = _integer(raw.get('profile_count'), f'{tag}.profile_count')
        if count == 0:
            raise ValueError(f'{tag}: at least one longitudinal profile is needed')
        kg_per_m = _decimal(raw.get('profile_unit_mass_kg_m'), f'{tag}.profile_unit_mass_kg_m', positive=True)
        plate_count = _integer(raw.get('plate_count', 0), f'{tag}.plate_count')
        density = _decimal(raw.get('steel_density_kg_m3', '7850'), f'{tag}.steel_density_kg_m3', positive=True)
        profile_length = _decimal(g['draft_extended_length_m'], f'{tag}.draft_extended_length_m') * count
        profile_mass = profile_length * kg_per_m
        plate_mass = Decimal('0')
        if plate_count:
            length = _decimal(raw.get('plate_length_mm'), f'{tag}.plate_length_mm', positive=True)
            width = _decimal(raw.get('plate_width_mm'), f'{tag}.plate_width_mm', positive=True)
            thick = _decimal(raw.get('plate_thickness_mm'), f'{tag}.plate_thickness_mm', positive=True)
            plate_mass = Decimal(g['grid_location_candidates']) * plate_count * length * width * thick * density / Decimal('1000000000')
        result.update({
            'status':'DRAFT_USER_WEIGHT_SCENARIO_NOT_APPROVED',
            'profile_name':str(raw.get('profile_name') or 'UNVERIFIED_PROFILE').strip(),
            'profile_count_per_location':count,
            'profile_unit_mass_kg_m':str(kg_per_m),
            'profile_total_length_m':str(profile_length),
            'profile_mass_kg':str(profile_mass),
            'plate_count_per_location':plate_count,
            'plate_mass_kg':str(plate_mass),
            'estimated_total_kg':str(profile_mass+plate_mass),
            'plate_dimensions_mm':[str(raw[x]) for x in ('plate_length_mm','plate_width_mm','plate_thickness_mm')] if plate_count else None,
            'steel_density_kg_m3':str(density),
            'scenario_source':'USER_EDITABLE_ASSUMPTION_NOT_FROM_PDF',
        })
        total_profiles += profile_mass
        total_plates += plate_mass
        results.append(result)
    complete = schedule.get('status') == 'DRAFT_COMPLETE_GRID_EVIDENCE' and len(results) == len(groups) and all(r['status']=='DRAFT_USER_WEIGHT_SCENARIO_NOT_APPROVED' for r in results)
    return {'status':'DRAFT_SCENARIO_COMPLETE' if complete else 'DRAFT_SCENARIO_PARTIAL',
            'document_sha256':schedule['document_sha256'], 'source_plan_page':schedule['plan_page'],
            'source_grid_location_candidates':schedule['grid_node_count'],
            'source_draft_extended_length_m':schedule['draft_extended_length_total_m'],
            'groups':results, 'profile_mass_total_kg':str(total_profiles),
            'plate_mass_total_kg':str(total_plates),
            'draft_weight_total_kg':str(total_profiles+total_plates),
            'omitted_components':['welds','bolts','splice allowances','cutting waste','other reinforcement plates unless individually entered'],
            'revision_status':'NOT_VERIFIED', 'physical_member_approved':False,
            'approved':False, 'financially_payable':False}


def write_weight_preview(preview: Mapping, *, json_path: str | Path, csv_path: str | Path):
    Path(json_path).write_text(json.dumps(preview,ensure_ascii=False,indent=2),encoding='utf-8')
    columns = ('type_tag','grid_location_candidates','printed_type_length_m','draft_extended_length_m',
               'status','profile_name','profile_count_per_location','profile_unit_mass_kg_m',
               'profile_total_length_m','profile_mass_kg','plate_count_per_location',
               'plate_mass_kg','estimated_total_kg','approved','financially_payable')
    with Path(csv_path).open('w',encoding='utf-8-sig',newline='') as f:
        writer=csv.DictWriter(f,fieldnames=columns)
        writer.writeheader()
        for row in preview['groups']:
            writer.writerow({x:row.get(x) for x in columns})


def export_weight_preview_xlsx(schedule: Mapping, preview: Mapping, path: str | Path):
    """Standalone readable workbook, no BOQ/snapshot/price changes."""
    from openpyxl import Workbook
    from openpyxl.styles import Font, Alignment, PatternFill
    from openpyxl.utils import get_column_letter
    book=Workbook()
    overview=book.active;overview.title='Preview'
    lines=[('StructuralPro | DRAFT NONFINANCIAL STEEL SCENARIO',),
           ('Source SHA256',schedule['document_sha256']),
           ('Plan page',schedule['plan_page']), ('Revision status','NOT_VERIFIED'),
           ('Engineering approved','NO'),('Financially payable','NO'),
           ('Source grid positions',schedule['grid_node_count']),
           ('Draft type lengths total m',schedule['draft_extended_length_total_m']),
           ('Scenario profile mass kg',preview['profile_mass_total_kg']),
           ('Scenario plate mass kg',preview['plate_mass_total_kg']),
           ('Scenario total mass kg',preview['draft_weight_total_kg']),
           ('Excluded','Welds, bolts, splices, waste, unentered reinforcement'),
           ('WARNING','Assumptions are user-entered; NOT measured or approved steel quantity')]
    for line in lines:overview.append(list(line))
    details=book.create_sheet('Types')
    headers=['Type','Grid candidates','Printed length m','Draft total length m','Profiles/column','Unit mass kg/m',
             'Profile length m','Profile mass kg','Plates/column','Plate mass kg','Scenario total kg','Status']
    details.append(headers)
    for r in preview['groups']:
        details.append([r.get('type_tag'),r.get('grid_location_candidates'),r.get('printed_type_length_m'),
                        r.get('draft_extended_length_m'),r.get('profile_count_per_location'),
                        r.get('profile_unit_mass_kg_m'),r.get('profile_total_length_m'),
                        r.get('profile_mass_kg'),r.get('plate_count_per_location'),
                        r.get('plate_mass_kg'),r.get('estimated_total_kg'),r.get('status')])
    positions=book.create_sheet('PDF positions')
    ph=['Candidate ID','Row','Column','Plan page','Type','X pt','Y pt','Length m','Status','Source path indices']
    positions.append(ph)
    for r in schedule.get('rows',[]):
        positions.append([r.get('candidate_id'),r.get('grid_row'),r.get('grid_column'),r.get('plan_page'),
                          r.get('type_tag'),r.get('x_pt'),r.get('y_pt'),r.get('printed_length_m'),
                          r.get('status'),json.dumps(r.get('label_path_indices',[]))])
    for sheet in book:
        sheet.sheet_view.rightToLeft=True
        sheet.freeze_panes='A2'
        for cell in sheet[1]:
            cell.fill=PatternFill('solid',fgColor='23384C')
            cell.font=Font(color='FFFFFF',bold=True)
            cell.alignment=Alignment(horizontal='center')
        for col in sheet.columns:
            letter=get_column_letter(col[0].column)
            sheet.column_dimensions[letter].width=min(54,max(14,max(len(str(c.value or '')) for c in col)+2))
    overview['A13'].font=Font(color='AA0000',bold=True)
    book.save(str(path))