"""Pinned public SAN IFC4 numerical audit; no model contents/coordinates uploaded."""
from __future__ import annotations
import argparse
from decimal import Decimal, localcontext
import hashlib
import json
from pathlib import Path
import re
import tempfile
from scripts.diagnostics.p6_g2_heating_sanitary_original_ui import fetch_pinned, EXTRA_MODELS
from scripts.diagnostics.p6_independent_ifc_public_reference import REV


def audit(path: Path, name: str) -> dict:
    import ifcopenshell
    from core.drawings.bim_adapter import BIMAdapter
    raw = path.read_bytes()
    spec = EXTRA_MODELS[name]
    assert len(raw) == spec['size']
    assert hashlib.sha1(b'blob '+str(len(raw)).encode()+b'\0'+raw).hexdigest() == spec['git_blob_sha1']
    model = ifcopenshell.open(str(path))
    text = raw.decode('utf-8-sig')
    literals = {int(sid): [Decimal(v.strip()) for v in values.split(',')]
                for sid, values in re.findall(r'#(\d+)\s*=\s*IFCDIRECTION\s*\(\s*\(([^)]+)\)\s*\)', text, re.I)}
    problems = []
    max_parser_dot_difference = Decimal(0)
    max_final_orthogonality_error = Decimal(0)
    depths = []
    with localcontext() as c:
        c.prec = 80
        for pl in model.by_type('IfcLocalPlacement'):
            r = pl.RelativePlacement
            if not r.is_a('IfcAxis2Placement3D'):
                raise ValueError('UNSUPPORTED_RELATIVE_PLACEMENT')
            assert bool(r.Axis) == bool(r.RefDirection), 'INCOMPLETE_AXIS_PAIR'
            x = [Decimal(str(v)) for v in r.RefDirection.DirectionRatios] if r.RefDirection else list(map(Decimal,(1,0,0)))
            z = [Decimal(str(v)) for v in r.Axis.DirectionRatios] if r.Axis else list(map(Decimal,(0,0,1)))
            def unit(v):
                n = sum(a*a for a in v).sqrt()
                assert n > 0
                return [a/n for a in v]
            x, z = unit(x), unit(z)
            dot = sum(a*b for a,b in zip(x,z))
            projected = [a-dot*b for a,b in zip(x,z)]
            length = sum(a*a for a in projected).sqrt()
            assert length > Decimal('1e-12'), 'ILL_CONDITIONED_AXIS_PAIR'
            xp = unit(projected)
            final_error = abs(sum(a*b for a,b in zip(xp,z)))
            max_final_orthogonality_error = max(max_final_orthogonality_error,final_error)
            if abs(dot)>Decimal('1e-12'):
                lx, lz = unit(literals[r.RefDirection.id()]),unit(literals[r.Axis.id()])
                literal_dot = sum(a*b for a,b in zip(lx,lz))
                delta = abs(literal_dot-dot)
                max_parser_dot_difference = max(max_parser_dot_difference,delta)
                problems.append({'local_placement_step_id':pl.id(), 'axis_placement_step_id':r.id(),
                    'normalized_dot_parser':str(dot),'normalized_dot_step_literal':str(literal_dot),
                    'parser_vs_literal_difference':str(delta), 'projected_x_norm':str(length),
                    'derived_x_dot_z':str(final_error)})
            visited=set(); p=pl
            while p is not None:
                assert p.id() not in visited,'PLACEMENT_CYCLE'
                visited.add(p.id());p=p.PlacementRelTo
            depths.append(len(visited))
        report={'model':name,'source_commit':REV,'source_path':spec['path'],
            'source_git_blob_sha1':spec['git_blob_sha1'],'source_sha256':hashlib.sha256(raw).hexdigest(),
            'schema':model.schema,'element_count':len(model.by_type('IfcElement')),
            'local_placement_count':len(depths),'max_parent_depth':max(depths),
            'above_old_input_dot_guard_count':len(problems),'all_above_guard_placements':problems,
            'max_parser_vs_literal_dot_difference':str(max_parser_dot_difference),
            'max_derived_orthogonality_error':str(max_final_orthogonality_error),
            'source_axis_pair_validity':'NONZERO_NONCOLLINEAR_BOTH_PROVIDED_OR_BOTH_DEFAULT',
            'raw_model_uploaded':False,'quantity_authority':False}
    document=BIMAdapter().read_document(path,revision='SAN-BUILD-AXES-AUDIT')
    assert len(document['elements'])==len(model.by_type('IfcElement'))
    assert document['source_sha256']==report['source_sha256']
    report['engineering_read']='PASS_ALL_SOURCE_ELEMENTS_RETAINED'
    return report


def main():
    parser=argparse.ArgumentParser();parser.add_argument('--output',default='p6-san-audit');parser.add_argument('--source-dir');args=parser.parse_args()
    output=Path(args.output);output.mkdir(parents=True,exist_ok=True)
    with tempfile.TemporaryDirectory() as t:
        rows=[]
        for name in ('sanitary_v1','sanitary'):
            path=Path(args.source_dir or t)/(name+'.ifc')
            if not args.source_dir:fetch_pinned(name,path)
            rows.append(audit(path,name))
        (output/'san-placement-numerical.json').write_text(json.dumps(rows,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
        print(json.dumps([{k:r[k] for k in ('model','element_count','local_placement_count','above_old_input_dot_guard_count','max_derived_orthogonality_error','engineering_read')} for r in rows]))

if __name__=='__main__': main()
