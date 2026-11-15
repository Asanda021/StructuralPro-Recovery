"""Loss-aware, non-financial PDF sheet/region coverage inventory.

Every supplied drawing page is partitioned into stable page-coordinate zones.
These zones are CANDIDATE search regions, NOT automatically segmented details
and NOT proof that all engineering content was interpreted. Titles, vector
content, text and images are recorded separately. No region can disappear
without EXAMINED/UNRESOLVED/BLOCKED disposition.
"""
from __future__ import annotations

from collections import Counter
from math import isfinite
import re
import unicodedata
from typing import Iterable, Mapping

_DEFAULT_ROWS = 4
_DEFAULT_COLS = 4
_MAX_PATHS = 30000
_MAX_BLOCKS = 30000
_MAX_PAGES = 600
_MARKS = re.compile(r'(?<![A-Za-z0-9])(?:SC|SW|C|B|F|T|W|S|P)\s*[-–]?\s*[1-9][0-9]{0,2}(?![A-Za-z0-9])',re.I)
_DETAIL_TERMS = ('جزئیات', 'جزییات', 'اتصال', 'مقطع', 'برش', 'detail', 'connection', 'section')
_COMPONENT_TERMS = {
    'beam': ('تیر', 'پل', 'beam', 'girder'),
    'column': ('ستون', 'column'),
    'foundation': ('پی', 'فنداسیون', 'foundation', 'footing'),
    'slab_roof': ('سقف', 'دال', 'بام', 'roof', 'slab'),
    'wall_opening': ('دیوار', 'بازشو', 'پنجره', 'wall', 'opening'),
    'stair_ramp': ('پله', 'رمپ', 'stair', 'ramp'),
    'reinforcement_connection': ('آرماتور', 'خاموت', 'میلگرد', 'اتصال', 'rebar', 'connection'),
    'mechanical': ('مکانیک', 'لوله', 'کانال', 'mechanical', 'pipe', 'duct'),
    'electrical': ('برق', 'کابل', 'electrical', 'cable'),
}


def _norm(text: str) -> str:
    t = unicodedata.normalize('NFKC', str(text or '')).casefold()
    t = t.translate(str.maketrans({'ي':'ی','ى':'ی','ك':'ک','ة':'ه'}))
    return t.replace('ـ','').replace('\u200c','')


def _compact(t: str) -> str:
    return ''.join(x for x in _norm(t) if x.isalnum())


def _rect(obj) -> tuple[float,float,float,float] | None:
    try:
        a = [float(obj[i]) for i in range(4)]
        return tuple(a) if all(isfinite(x) for x in a) and a[2] >= a[0] and a[3] >= a[1] else None
    except (TypeError, ValueError, IndexError, KeyError):
        return None


def _overlaps(a, b) -> bool:
    return min(a[2],b[2]) > max(a[0],b[0]) and min(a[3],b[3]) > max(a[1],b[1])


def _source_title_candidates(blocks: Iterable[tuple], document_id: str, page_number: int) -> list[dict]:
    out=[]
    for idx, block in enumerate(blocks):
        if len(block) < 7 or block[6] != 0:
            continue
        raw = str(block[4])
        compact = _compact(raw)
        terms=[term for term in _DETAIL_TERMS if _compact(term) in compact]
        if not terms:
            continue
        box = _rect(block)
        if box is None:
            continue
        out.append({'anchor_id': f'{document_id}:p{page_number}:title{idx+1}',
                    'document_id':document_id,'page':page_number,
                    'bbox_pt':list(map(lambda x:round(x,2),box)),
                    'title_preview':raw.strip()[:96],
                    'explicit_terms':terms,
                    'status':'UNRESOLVED',
                    'reason':'Explicit detail/section label found, but its drawing boundary and linked instances are not verified',
                    'financially_payable':False})
    return out


def inventory_pdf_page_regions(page, *, document_id: str, page_number: int,
                               sheet_kind: str | None = None,
                               rows: int = _DEFAULT_ROWS, columns: int = _DEFAULT_COLS,
                               max_paths: int = _MAX_PATHS) -> dict:
    """Inventory every grid tile of one PDF sheet with source provenance.

    EXAMINED means content was indexed; it does NOT mean a measurement was
    approved. UNRESOLVED means semantics of the visual region aren't known.
    A BLOCKED tile means evidence extraction was incomplete, not empty.
    """
    if not isinstance(document_id,str) or not document_id.strip() or type(page_number) is not int or page_number < 1:
        raise ValueError('A stable document ID and positive page number are required')
    if type(rows) is not int or type(columns) is not int or not 2 <= rows <= 8 or not 2 <= columns <= 8:
        raise ValueError('Region tiling must be bounded between 2 and 8')
    if type(max_paths) is not int or not 1 <= max_paths <= 100000:
        raise ValueError('Positive bounded path budget required')
    bounds=_rect(page.rect)
    if bounds is None or bounds[2]-bounds[0] <= 1 or bounds[3]-bounds[1] <= 1:
        raise ValueError('Invalid PDF page dimensions')
    extraction_errors=[]
    blocks=[]
    paths=[]
    try:
        blocks=list(page.get_text('blocks'))
        if len(blocks)>_MAX_BLOCKS:
            extraction_errors.append('BLOCKED_EXCESSIVE_TEXT_BLOCKS')
            blocks=[]
    except (RuntimeError,ValueError,MemoryError):
        extraction_errors.append('BLOCKED_TEXT_EXTRACTION')
    try:
        paths=list(page.get_drawings())
        if len(paths)>max_paths:
            extraction_errors.append('BLOCKED_EXCESSIVE_VECTOR_PATHS')
            paths=[]
    except (RuntimeError,ValueError,MemoryError):
        extraction_errors.append('BLOCKED_VECTOR_EXTRACTION')
    title_anchors=_source_title_candidates(blocks,document_id,page_number)
    box_data=[]
    for block in blocks:
        if len(block)<7:continue
        box=_rect(block)
        if box:
            box_data.append((box,block[6],str(block[4]) if block[6]==0 else ''))
        else:
            extraction_errors.append('BLOCKED_INVALID_TEXT_BLOCK_BBOX')
    path_boxes=[]
    for path in paths:
        box=_rect(path.get('rect'))
        if box and box[2]>box[0] and box[3]>box[1]:path_boxes.append(box)
        elif box is None:
            extraction_errors.append('BLOCKED_INVALID_VECTOR_PATH_BBOX')
    blocked=bool(extraction_errors)
    x0,y0,x1,y1=bounds
    dx=(x1-x0)/columns;dy=(y1-y0)/rows
    zones=[]
    for r in range(rows):
        for c in range(columns):
            tile=(x0+c*dx,y0+r*dy,x0+(c+1)*dx,y0+(r+1)*dy)
            text_items=[v for v in box_data if v[1]==0 and _overlaps(tile,v[0])]
            images=sum(v[1]!=0 and _overlaps(tile,v[0]) for v in box_data)
            vectors=sum(_overlaps(tile,box) for box in path_boxes)
            titles=[v['anchor_id'] for v in title_anchors if _overlaps(tile,v['bbox_pt'])]
            raw=' '.join(v[2] for v in text_items)
            marks=sorted(set(m.group().upper().replace('-','').replace(' ','') for m in _MARKS.finditer(raw)))[:100]
            has_ink=bool(text_items or images or vectors)
            if blocked:
                status='BLOCKED'
                reason='Source evidence extraction incomplete; tile cannot be certified empty'
            elif images:
                status='UNRESOLVED'
                reason='Raster content requires independent semantic review'
            elif vectors:
                status='UNRESOLVED'
                reason='Vector drawing region indexed, member/detail meaning not yet established'
            elif titles:
                status='UNRESOLVED'
                reason='Explicit detail title with unverified attached drawing'
            else:
                status='EXAMINED'
                reason='Indexed text-only or blank tile, no vector/raster geometry detected'
            zones.append({'region_id':f'{document_id}:p{page_number}:r{r+1}:c{c+1}',
              'document_id':document_id,'page':page_number,
              'tile_row':r+1,'tile_column':c+1,
              'bbox_pt':[round(v,3) for v in tile],
              'status':status,'reason':reason,'text_block_count':len(text_items),
              'vector_path_count':vectors,'image_block_count':images,
              'has_visible_evidence':has_ink,'explicit_detail_title_ids':titles,
              'searchable_member_marks':marks,
              'role':'PAGE_EVIDENCE_ZONE_NOT_SEGMENTED_DETAIL',
              'physical_member_verified':False,'financially_payable':False})
    # Only a classified sheet kind or an explicit detail TITLE can suggest
    # disciplines. Arbitrary text and short Persian syllables are too noisy.
    classification=sheet_kind or 'UNKNOWN_SHEET_KIND'
    known_kind = {
        'column_type_plan': ['column'], 'column_detail': ['column'],
        'beam_layout_plan': ['beam'], 'foundation_plan': ['foundation'],
        'roof_drainage_plan': ['slab_roof'],
        'formwork_plan': ['slab_roof'],
    }
    family_candidates=set(known_kind.get(classification, ()))
    for anchor in title_anchors:
        anchor_text = _compact(anchor['title_preview'])
        for family, phrases in _COMPONENT_TERMS.items():
            if any(_compact(term) in anchor_text and len(_compact(term)) >= 3
                   for term in phrases):
                family_candidates.add(family)
    family_candidates=sorted(family_candidates)
    status_count=Counter(x['status'] for x in zones)
    return {'document_id':document_id,'page':page_number,
      'sheet_kind':classification,'discipline_candidates':family_candidates,
      'source_bbox_pt':[round(v,2) for v in bounds],
      'regions':zones,'region_count':len(zones),'expected_region_count':rows*columns,
      'detail_title_anchors':title_anchors,
      'explicit_detail_anchor_count':len(title_anchors),
      'searchable_text_block_count':sum(v[1]==0 for v in box_data),
      'vector_path_count':len(paths),'image_block_count':sum(v[1]!=0 for v in box_data),
      'extraction_errors':sorted(set(extraction_errors)),
      'coverage_status':'BLOCKED' if blocked else ('UNRESOLVED' if status_count['UNRESOLVED'] else 'EXAMINED'),
      'status_counts':dict(sorted(status_count.items())),
      'detail_geometry_interpreted':False,
      'all_regions_indexed':len(zones)==rows*columns,
      'financially_payable':False}


def assemble_pdf_detail_inventory(page_summaries: Iterable[Mapping],
                                  documents: Iterable[Mapping]) -> dict:
    """Refuse 'complete' claims unless each input page has every zone indexed."""
    pages=list(page_summaries)
    docs=list(documents)
    expected={(d['document_id'],n) for d in docs for n in range(1,int(d['page_count'])+1)}
    actual=[(p.get('document_id'),p.get('page')) for p in pages]
    if len(set(actual))!=len(actual):
        raise ValueError('Duplicate page would invalidate a full-sheet inventory')
    if set(actual)!=expected:
        raise ValueError('Missing or foreign PDF pages invalidate full-sheet inventory')
    errors=[]
    all_regions=[]
    all_anchors=[]
    summary=[]
    for page in pages:
        regs=page.get('regions',())
        if not page.get('all_regions_indexed') or len(regs)!=page.get('expected_region_count'):
            errors.append(f"INCOMPLETE_PAGE_REGIONS:{page['document_id']}:p{page['page']}")
        expected_ids={r['region_id'] for r in regs}
        if len(expected_ids)!=len(regs):
            errors.append(f"DUPLICATE_REGION:{page['document_id']}:p{page['page']}")
        all_regions.extend(regs)
        all_anchors.extend(page.get('detail_title_anchors',()))
        summary.append({'document_id':page['document_id'],'page':page['page'],
          'sheet_kind':page['sheet_kind'],'coverage_status':page['coverage_status'],
          'region_count':len(regs),'detail_anchor_count':page['explicit_detail_anchor_count'],
          'discipline_candidates':page['discipline_candidates'],
          'vector_path_count':page['vector_path_count'],
          'image_block_count':page['image_block_count'],
          'errors':page['extraction_errors']})
    counts=Counter(r['status'] for r in all_regions)
    pages_count=Counter(s['coverage_status'] for s in summary)
    return {'documents':docs,'page_count':len(pages),
      'sheet_inventory':summary,'detail_title_anchors':all_anchors,
      'region_inventory':all_regions,
      'region_count':len(all_regions),'expected_region_count':sum(p['expected_region_count'] for p in pages),
      'region_status_counts':dict(sorted(counts.items())),
      'page_status_counts':dict(sorted(pages_count.items())),
      'all_input_pages_indexed':not errors and set(actual)==expected,
      'errors':errors,
      'semantic_details_fully_interpreted':False,
      'quantity_approval_count':0,
      'complete':False,
      'acceptance':'PARTIAL_NO_GO',
      'source_type':'PDF_ONLY'}