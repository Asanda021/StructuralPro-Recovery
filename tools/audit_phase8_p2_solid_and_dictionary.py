"""Read-only, SHA-pinned private-source P2 audit. Not an approval of 3D UI or finance."""
from __future__ import annotations

import argparse
from hashlib import sha256
import json
from pathlib import Path

from core.drawings.dwg_source_display_integrity import (
    source_solid_3d_preview_manifest,
    converted_dxf_solid_3d_diagnostic,
    audit_named_dictionary_links,
)

HANDLES = ('6C2CD','6C2D4','6C2F1','6C2F3','6C2F9','6C5D9','6C5DF')


def audit(dwg_path: str, dxf_path: str, source_sha256: str, dxf_sha256: str) -> dict:
    import ezdxf
    import ezdwg
    from importlib import metadata
    dwg, dxf = Path(dwg_path), Path(dxf_path)
    if not dwg.is_file() or not dxf.is_file() or dwg.suffix.lower()!='.dwg' or dxf.suffix.lower()!='.dxf':
        raise ValueError('Expected original DWG and diagnostic DXF files')
    if dwg.is_symlink() or dxf.is_symlink() or not 6 < dwg.stat().st_size <= 50*1024*1024 or not 100 < dxf.stat().st_size <= 300*1024*1024:
        raise ValueError('Source file is symlinked or size out of range')
    if sha256(dwg.read_bytes()).hexdigest()!=source_sha256 or sha256(dxf.read_bytes()).hexdigest()!=dxf_sha256:
        raise ValueError('Source SHA mismatch')
    if metadata.version('ezdwg')!='0.17.0':
        raise ValueError('Pinned independent reader unavailable')
    native=ezdwg.read(str(dwg))
    converted=ezdxf.readfile(str(dxf))
    if native.version!=dwg.read_bytes()[:6].decode('ascii'):
        raise ValueError('DWG signature mismatch')
    found={}
    wanted={int(h,16) for h in HANDLES}
    for entity in native.modelspace().iter_entities(types='SOLID',include_styles=False):
        h=int(entity.handle)
        if h in wanted:
            if h in found:raise ValueError('Duplicate original source SOLID')
            found[h]=entity
    if set(found)!=wanted:raise ValueError('Missing source SOLIDs')
    records=[]
    for h in HANDLES:
        source=found[int(h,16)];target=converted.entitydb.get(h)
        if target is None:raise ValueError('Missing diagnostic DXF SOLID')
        orig=source_solid_3d_preview_manifest(source.dxf.get('points'),source.dxf.get('extrusion',(0,0,1)))
        diagnostic=converted_dxf_solid_3d_diagnostic(target)
        if diagnostic['status']!='GROUP38_ELEVATION_RECONSTRUCTED_DIAGNOSTIC_ONLY':
            raise ValueError('Expected legacy group-38 SOLID representation changed')
        a=orig['native_source_vertices_3d']; b=diagnostic['diagnostic_wcs_vertices_3d']
        if len(a)!=len(b) or any(abs(x-y)>1e-7 for av,bv in zip(a,b) for x,y in zip(av,bv)):
            raise ValueError('Diagnostic group-38 positions disagree with original DWG')
        records.append({'source_handle':h,'status':diagnostic['status'],
                        'source_z':a[0][2],'diagnostic_dxf_z':b[0][2],
                        'reconstructed_wcs_equals_native_xyz':True,
                        'actual_structuralpro_cad_3d_ui_render_verified':False,
                        'financial_quantity_approved':False})
    integrity=audit_named_dictionary_links(converted)
    if integrity['dangling_or_invalid_count']!=3:
        raise ValueError('Expected three open dangling targets changed; refresh evidence')
    if sha256(dwg.read_bytes()).hexdigest()!=source_sha256 or sha256(dxf.read_bytes()).hexdigest()!=dxf_sha256:
        raise ValueError('Source mutated during inspection')
    return {'policy':'p8p2_source_backed_solid_3d_dictionary_v1', 'original_dwg_sha256':source_sha256,
            'diagnostic_dxf_sha256':dxf_sha256,
            'decoder':'ezdwg==0.17.0 independent original vs LibreDWG DXF interpreted by ezdxf',
            'source_solid_7_diagnostic_agree_count':len(records), 'solid_records':records,
            'dxf_dictionary_link_audit':integrity,
            'actual_cad_3d_gui_render_verified':False,
            'read_only_native_cad_preview_is_2d':True,
            'opaque_map_aec_payloads_decoded':False,
            'source_units_verified':False,
            'financial_quantity_rows_approved':0,'status':'PARTIAL_NO_GO'}


def main() -> int:
    p=argparse.ArgumentParser()
    p.add_argument('--dwg',required=True);p.add_argument('--dxf',required=True)
    p.add_argument('--dwg-sha',required=True);p.add_argument('--dxf-sha',required=True)
    p.add_argument('--output',required=True)
    a=p.parse_args()
    result=audit(a.dwg,a.dxf,a.dwg_sha,a.dxf_sha)
    out=Path(a.output);out.parent.mkdir(parents=True,exist_ok=True)
    out.write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    print('PARTIAL_NO_GO',result['source_solid_7_diagnostic_agree_count'],result['dxf_dictionary_link_audit']['dangling_or_invalid_count'])
    return 0

if __name__=='__main__':raise SystemExit(main())