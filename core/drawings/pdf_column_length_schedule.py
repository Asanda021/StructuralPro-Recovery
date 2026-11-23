"""Source-traceable *draft* column type length schedule from one PDF.

This is a nonfinancial takeoff preview. A grid intersection is a location
candidate, not proof of built member or repeated-floor placement. Type-detail
L dimensions are not field measurements; no BOQ/statement writes occur.
"""
from __future__ import annotations

import argparse
from collections import Counter
import csv
from decimal import Decimal
from hashlib import sha256
import json
from pathlib import Path

from core.drawings.pdf_grid_instances import detect_vector_grid_positions
from core.drawings.pdf_vector_symbol_witness import compact_symbol_witness
from core.drawings.pdf_vector_type_labels import vector_column_type_labels
from core.drawings.pdf_sheet_scope_registration import classify_sheet_title
from core.drawings.pdf_auto_intake import _parse_pdf_lines, _score_pair


def _collect_dimensions(doc):
    by_type = {}
    for index, page in enumerate(doc):
        kind = classify_sheet_title(page.get_text())
        if kind.get('status') != 'EXPLICIT_SHEET_TITLE' or kind.get('sheet_kind') != 'column_detail':
            continue
        marks, dims = _parse_pdf_lines(page)
        for mark in marks:
            matches = [(score, d) for d in dims
                       if d['quantity_kind'] == 'length'
                       if (score := _score_pair(mark, d)) is not None]
            if not matches:
                continue
            matches.sort(key=lambda x: x[0])
            closest = matches[0]
            # Equal-quality but conflicting alternatives cannot be resolved.
            if any(abs(s - closest[0]) < 5 and d['quantity_m'] != closest[1]['quantity_m']
                   for s, d in matches[1:]):
                by_type.setdefault(mark['tag'], []).append({'status':'BLOCKED_CONFLICTING_DIMENSIONS'})
                continue
            by_type.setdefault(mark['tag'], []).append({
                'status':'EXPLICIT_PRINTED_DIMENSION',
                'length_m':closest[1]['quantity_m'],
                'page':index+1,
                'tag_bbox_pt':mark['bbox'],
                'dimension_bbox_pt':closest[1]['bbox'],
                'dimension_text':closest[1]['printed'],
            })
    indexed = {}
    for tag, evidence in by_type.items():
        values = {e.get('length_m') for e in evidence if e['status'] == 'EXPLICIT_PRINTED_DIMENSION'}
        if len(values) != 1 or any(e['status'] != 'EXPLICIT_PRINTED_DIMENSION' for e in evidence):
            indexed[tag] = {'status':'BLOCKED_CONFLICTING_OR_MISSING_DETAIL', 'evidence':evidence}
        else:
            indexed[tag] = {'status':'EXPLICIT_PRINTED_DIMENSION', 'length_m':next(iter(values)),
                            'evidence':evidence}
    return indexed


def draft_column_length_schedule(pdf_path: str | Path, *, expected_sha256: str | None = None) -> dict:
    """Extract a draft length schedule without approving physical or financial takeoff."""
    import pymupdf

    path = Path(pdf_path)
    if not path.is_file() or path.suffix.lower() != '.pdf':
        raise ValueError('Expected a readable PDF source')
    content = path.read_bytes()
    digest = sha256(content).hexdigest()
    if expected_sha256 and expected_sha256.lower() != digest:
        raise ValueError('PDF SHA256 does not match the reviewed source')
    with pymupdf.open(stream=content, filetype='pdf') as doc:
        if not doc or doc.needs_pass or doc.is_repaired:
            raise ValueError('Encrypted, repaired or empty PDF blocked')
        plans = [(i, page) for i, page in enumerate(doc)
                 if (classification := classify_sheet_title(page.get_text())).get('status') == 'EXPLICIT_SHEET_TITLE'
                 and classification.get('sheet_kind') == 'column_type_plan']
        if len(plans) != 1:
            return {'status':'BLOCKED_NON_UNIQUE_COLUMN_TYPE_PLAN', 'document_sha256':digest,
                    'plan_sheet_candidates':[i+1 for i,_ in plans], 'rows':[],
                    'financially_payable':False, 'approved':False}
        index, page = plans[0]
        grid = detect_vector_grid_positions(page,document_id='PDF001',page_number=index+1)
        if grid['status'] != 'VECTOR_GRID_LOCATION_CANDIDATES' or not grid['nodes']:
            return {'status':'BLOCKED_NO_COLUMN_GRID', 'document_sha256':digest,
                    'plan_page':index+1, 'rows':[], 'financially_payable':False, 'approved':False}
        symbols = compact_symbol_witness(page,grid['nodes'])
        recognized = vector_column_type_labels(page,symbols['nodes'])
        details = _collect_dimensions(doc)
        rows=[]
        for node in recognized['nodes']:
            tag=node.get('suggested_type')
            glyph=node.get('vector_type_label_evidence')
            dim=details.get(tag,{}) if tag else {}
            valid=(node.get('status') == 'GRID_LOCATION_VECTOR_TYPE_CANDIDATE'
                   and isinstance(glyph, dict) and glyph.get('tag') == tag
                   and dim.get('status') == 'EXPLICIT_PRINTED_DIMENSION')
            row={'candidate_id':node['candidate_id'], 'grid_row':node['row'],
                 'grid_column':node['column'], 'x_pt':node['x_pt'], 'y_pt':node['y_pt'],
                 'plan_page':index+1, 'type_tag':tag, 'status':
                 'DRAFT_TYPE_LENGTH_CANDIDATE' if valid else 'BLOCKED_MISSING_TYPE_OR_DETAIL',
                 'label_path_indices':list(glyph.get('path_indices',())) if isinstance(glyph,dict) else [],
                 'label_bbox_pt':list(glyph.get('bbox_pt',())) if isinstance(glyph,dict) else [],
                 'detail_page':dim['evidence'][0]['page'] if valid else None,
                 'printed_length_m':dim['length_m'] if valid else None,
                 'printed_length_bbox_pt':list(dim['evidence'][0]['dimension_bbox_pt']) if valid else [],
                 'approved':False, 'financially_payable':False}
            rows.append(row)
        tally=Counter(r['type_tag'] for r in rows if r['status'] == 'DRAFT_TYPE_LENGTH_CANDIDATE')
        groups=[]
        for tag,count in sorted(tally.items()):
            d=details[tag];length=Decimal(d['length_m'])
            groups.append({'type_tag':tag, 'grid_location_candidates':count,
                           'printed_type_length_m':str(length),
                           'draft_extended_length_m':str(length*count),
                           'formula':f'{count} x {length} m',
                           'status':'DRAFT_NONFINANCIAL_NOT_REVISION_APPROVED'})
        total=sum((Decimal(r['draft_extended_length_m']) for r in groups), Decimal('0'))
        complete=bool(rows) and len(rows)==len(grid['nodes']) and len(tally)==len(details) and all(
            r['status']=='DRAFT_TYPE_LENGTH_CANDIDATE' for r in rows)
        return {'status':'DRAFT_COMPLETE_GRID_EVIDENCE' if complete else 'PARTIAL_WITH_BLOCKED_GRID_NODES',
                'document_sha256':digest, 'document_name':path.name,
                'page_count':len(doc), 'plan_page':index+1,
                'grid_node_count':len(grid['nodes']), 'labeled_node_count':recognized['attached'],
                'draft_node_count':sum(tally.values()), 'blocked_node_count':len(rows)-sum(tally.values()),
                'groups':groups, 'rows':rows,
                'draft_extended_length_total_m':str(total),
                'measurement_meaning':'Sum of printed type-detail lengths across labeled plan grid points, one hypothetical occurrence per point; NOT floor-by-floor quantity',
                'revision_status':'NOT_VERIFIED', 'physical_member_approved':False,
                'approved':False, 'financially_payable':False}


def write_schedule(result: dict, *, json_path: str | Path, csv_path: str | Path):
    Path(json_path).write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding='utf-8')
    columns=('candidate_id','grid_row','grid_column','x_pt','y_pt','plan_page',
             'type_tag','status','detail_page','printed_length_m', 'label_path_indices','label_bbox_pt',
             'printed_length_bbox_pt','approved','financially_payable')
    with Path(csv_path).open('w',encoding='utf-8-sig',newline='') as f:
        w=csv.DictWriter(f,fieldnames=columns)
        w.writeheader()
        for row in result.get('rows',()):
            w.writerow({k:json.dumps(row[k],ensure_ascii=False) if isinstance(row.get(k),list)
                        else row.get(k) for k in columns})


def main():
    parser=argparse.ArgumentParser(description='Draft, nonfinancial PDF column length schedule')
    parser.add_argument('pdf')
    parser.add_argument('--sha256')
    parser.add_argument('--json',dest='out_json',required=True)
    parser.add_argument('--csv',dest='out_csv',required=True)
    args=parser.parse_args()
    r=draft_column_length_schedule(args.pdf,expected_sha256=args.sha256)
    write_schedule(r,json_path=args.out_json,csv_path=args.out_csv)
    print(json.dumps({'status':r['status'],'grid_nodes':r.get('grid_node_count'),
                      'draft_length_m':r.get('draft_extended_length_total_m')},ensure_ascii=False))


if __name__=='__main__':
    main()