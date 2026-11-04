"""Read-only native original DWG vs converter DXF comparison.

Safety: An equality of selected modelspace attributes is NOT native object-graph
coverage, SHX glyph correctness, source revision identity or payable quantity
approval. All outputs always remain PARTIAL_NO_GO.
"""
from __future__ import annotations
import argparse
from collections import Counter, defaultdict
from hashlib import sha256
from importlib import metadata
import json
import math
from pathlib import Path

SUPPORTED_TYPES = frozenset({'LINE','ARC','CIRCLE','LWPOLYLINE','SOLID','POINT','SPLINE','INSERT'})
MAX_SIZE_DWG = 50 * 1024 * 1024
MAX_SIZE_DXF = 300 * 1024 * 1024
MAX_MODELSPACE = 1_000_000

def _close(x, y):
    return math.isclose(float(x), float(y), rel_tol=1e-12, abs_tol=1e-7)

def _vec(a, b):
    aa=list(a);bb=list(b)
    if len(aa)!=len(bb):
        if len(aa)==2 and len(bb)==3 and _close(bb[2],0): bb=bb[:2]
        elif len(bb)==2 and len(aa)==3 and _close(aa[2],0): aa=aa[:2]
        else:return False
    return all(_close(x,y) for x,y in zip(aa,bb))

def _angle(a,b):
    return abs((float(a)-float(b)+180)%360-180)<1e-7

def classify_geometry_pair(source, converted, source_layer: str | None) -> list[str]:
    """Classify checked attributes only; never assert semantic equivalence."""
    t=str(source.dxftype)
    if converted.dxftype()!=t:
        return ['TYPE_CHANGED']
    s=source.dxf; d=converted.dxf
    issues=[]
    if source_layer!=str(d.layer):issues.append('LAYER_CHANGED')
    if t=='LINE':
        if not _vec(s['start'],d.start) or not _vec(s['end'],d.end):issues.append('LINE_3D_COORD_CHANGED')
    elif t in ('ARC','CIRCLE'):
        if not _vec(s['center'],d.center) or not _close(s['radius'],d.radius):issues.append('CIRCLE_ARC_GEOMETRY_CHANGED')
        if t=='ARC' and (not _angle(s['start_angle'],d.start_angle) or not _angle(s['end_angle'],d.end_angle)):
            issues.append('ARC_ANGLE_CHANGED')
    elif t=='LWPOLYLINE':
        a=list(s['points']);b=list(converted.get_points('xyb'));bulges=list(s['bulges'])
        if len(a)!=len(b) or len(a)!=len(bulges) or bool(s['closed'])!=bool(converted.closed):
            issues.append('POLYLINE_TOPOLOGY_CHANGED')
        elif any(not _vec(u[:2],v[:2]) or not _close(bl,v[2]) for u,v,bl in zip(a,b,bulges)):
            issues.append('POLYLINE_XY_BULGE_CHANGED')
    elif t=='SOLID':
        a=list(s['points']);b=[getattr(d,'vtx'+str(i)) for i in range(4)]
        if len(a)!=len(b):issues.append('SOLID_VERTEX_COUNT_CHANGED')
        elif any(not _vec(u,v) for u,v in zip(a,b)):
            if all(_vec(list(u)[:2],list(v)[:2]) for u,v in zip(a,b)) and any(not _close(u[2],v[2]) for u,v in zip(a,b)):
                issues.append('SOLID_Z_CHANGED')
            else:issues.append('SOLID_GEOMETRY_CHANGED')
    elif t=='POINT':
        if not _vec(s['location'],d.location):issues.append('POINT_3D_COORD_CHANGED')
    elif t=='SPLINE':
        if int(s['degree'])!=int(d.degree) or len(s['control_points'])!=len(converted.control_points) or len(s['knots'])!=len(converted.knots):issues.append('SPLINE_STRUCTURE_CHANGED')
        elif (any(not _vec(a,b) for a,b in zip(s['control_points'],converted.control_points))
              or any(not _close(a,b) for a,b in zip(s['knots'],converted.knots))):issues.append('SPLINE_GEOMETRY_CHANGED')
    elif t=='INSERT':
        if not _vec(s['insert'],d.insert):issues.append('INSERT_3D_POSITION_CHANGED')
        if any(not _close(s.get(k,1 if k.endswith('scale') else 0), getattr(d,k)) for k in ('xscale','yscale','zscale','rotation')):
            issues.append('INSERT_TRANSFORM_CHANGED')
        if str(s['name'])!=str(d.name):issues.append('INSERT_BLOCK_NAME_CHANGED')
    return issues

def audit(original_path: str | Path, converted_path: str | Path, expected_original_sha256: str) -> dict:
    """Audit selected fields on one original DWG and one existing converted DXF."""
    original=Path(original_path);converted=Path(converted_path)
    if len(expected_original_sha256)!=64 or any(ch not in '0123456789abcdef' for ch in expected_original_sha256.lower()):
        raise ValueError('Expected original SHA256 must be a 64-digit hex digest')
    if not original.is_file() or original.suffix.lower()!='.dwg' or not 6<original.stat().st_size<=MAX_SIZE_DWG:
        raise ValueError('Original DWG is unavailable or too large')
    if not converted.is_file() or converted.suffix.lower()!='.dxf' or not 1<converted.stat().st_size<=MAX_SIZE_DXF:
        raise ValueError('Converted DXF is unavailable or too large')
    sh_before=sha256(original.read_bytes()).hexdigest(); dxf_before=sha256(converted.read_bytes()).hexdigest()
    if sh_before!=expected_original_sha256.lower():raise ValueError('Original DWG SHA mismatch: no comparison')
    if metadata.version('ezdwg')!='0.17.0':raise ValueError('Only pinned ezdwg==0.17.0 is authorized')
    import ezdwg,ezdxf
    n=ezdwg.read(str(original)); x=ezdxf.readfile(str(converted))
    if n.version!=original.read_bytes()[:6].decode('ascii'):raise ValueError('Native DWG signature mismatch')
    orig={};target={};orig_types=Counter();dxf_types=Counter()
    for e in n.modelspace().iter_entities():
        if len(orig)>=MAX_MODELSPACE:raise ValueError('Native modelspace over entity cap')
        h=int(e.handle)
        if h in orig:raise ValueError('Duplicate native handle')
        orig[h]=e;orig_types[str(e.dxftype)]+=1
    for e in x.modelspace():
        if len(target)>=MAX_MODELSPACE:raise ValueError('DXF modelspace over entity cap')
        h=int(e.dxf.handle,16)
        if h in target:raise ValueError('Duplicate DXF handle')
        target[h]=e;dxf_types[e.dxftype()]+=1
    types_orig={(h,str(e.dxftype)) for h,e in orig.items()}
    types_dxf={(h,e.dxftype()) for h,e in target.items()}
    only_orig=sorted(types_orig-types_dxf);only_dxf=sorted(types_dxf-types_orig)
    layers={int(l.handle):str(l.name) for l in n.layers}
    checked=Counter();equal=Counter();mismatches=Counter();examples=defaultdict(list)
    for h,e in orig.items():
        t=str(e.dxftype)
        if t not in SUPPORTED_TYPES or h not in target or target[h].dxftype()!=t:continue
        checked[t]+=1
        try:
            issues=classify_geometry_pair(e,target[h],layers.get(int(e.dxf.get('layer_handle',0))))
        except (KeyError,ValueError,TypeError,AttributeError,OverflowError):
            issues=['UNREADABLE_COMPARISON']
        if not issues:equal[t]+=1
        for problem in issues:
            mismatches[problem]+=1
            if len(examples[problem])<20:examples[problem].append(format(h,'X'))
    if sh_before!=sha256(original.read_bytes()).hexdigest() or dxf_before!=sha256(converted.read_bytes()).hexdigest():
        raise ValueError('Source DWG or DXF changed during comparison')
    return {
        'policy':'structuralpro_p8p2_pinned_independent_dwg_dxf_v1',
        'source_sha256':sh_before,'diagnostic_dxf_sha256':dxf_before,
        'reader':'ezdwg==0.17.0 original DWG vs ezdxf parsed DXF',
        'native_dwg_version':n.version,'native_dwg_units':n.units,
        'converted_dxf_units_code':int(x.header.get('$INSUNITS',0) or 0),
        'native_modelspace_count':len(orig),'dxf_modelspace_count':len(target),
        'source_by_type':dict(sorted(orig_types.items())),'dxf_by_type':dict(sorted(dxf_types.items())),
        'missing_from_dxf_count':len(only_orig),'missing_from_dxf_examples':[[format(h,'X'),t] for h,t in only_orig[:25]],
        'unmatched_dxf_count':len(only_dxf),'unmatched_dxf_examples':[[format(h,'X'),t] for h,t in only_dxf[:25]],
        'selected_type_checked_count':dict(sorted(checked.items())),'selected_type_equal_count':dict(sorted(equal.items())),
        'selected_field_discrepancies':dict(sorted(mismatches.items())),'discrepancy_handle_examples':dict(sorted(examples.items())),
        'opaque_payloads_verified':False,'shx_glyphs_verified':False,'source_revision_verified':False,
        'quantity_approved':0,'geometry_approved_for_financial_takeoff':False,'status':'PARTIAL_NO_GO',
        'limitations':'Only specified fields are compared; block-definition semantics, HATCH paths, some entity attributes, unknown objects, SHX glyphs and source revision are unverified.'}

def main():
    p=argparse.ArgumentParser(description='Read-only pinned independent DWG-to-DXF comparison; always NO-GO for payable quantities')
    p.add_argument('original_dwg');p.add_argument('diagnostic_dxf');p.add_argument('report_json');p.add_argument('--expected-source-sha256',required=True)
    a=p.parse_args()
    try:
        r=audit(a.original_dwg,a.diagnostic_dxf,a.expected_source_sha256)
    except Exception as exc:
        # Fail closed without laundering tool exceptions into positive comparison.
        print('BLOCKED_NO_INDEPENDENT_COMPARISON',type(exc).__name__,str(exc)[:200]);return 2
    out=Path(a.report_json);out.parent.mkdir(parents=True,exist_ok=True)
    out.write_text(json.dumps(r,ensure_ascii=False,indent=2)+'\n',encoding='utf8')
    print('PARTIAL_NO_GO','source',r['native_modelspace_count'],'dxf',r['dxf_modelspace_count'],r['selected_field_discrepancies']);return 0
if __name__=='__main__':raise SystemExit(main())