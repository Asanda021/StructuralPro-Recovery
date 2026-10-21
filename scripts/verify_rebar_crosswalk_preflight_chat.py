"""Emit exact, unverified nine-row rebar crosswalk requests; no commits/writes."""
from __future__ import annotations
import json
from pathlib import Path
import sys
ROOT=Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:sys.path.insert(0,str(ROOT))
from scripts.verify_structural_four_package_preflight_chat import read
from core.takeoff.shear_wall_bridge_chat import compile_preview as shear
from core.takeoff.stair_bridge_chat import compile_preview as stair
from core.takeoff.bored_pile_bridge_chat import compile_preview as pile
from core.takeoff.shared_rebar_ownership_chat import reconcile
from core.takeoff.rebar_crosswalk_preflight_chat import POLICY, template, audit

def verify():
    project={'id':'P','takeoffs':[],'boq':[],'reviewed_aec_systems':{},
             'reviewed_structural_members':{},'beam_detail_register':{}}
    w=read('shear_wall_chat_reference.json')
    t=read('stair_chat_example.json');t['metadata']['project_id']='P'
    b=read('bored_pile_documented_synthetic.json')
    previews={'shear_wall':shear(w,project,reviewer='Independent Audit',review_reference='synthetic'),
              'stair':stair(t,project,source_id='STAI-R1',reviewer='Independent Audit',ownership_reference='synthetic'),
              'bored_pile':pile(b,project,independent_reviewer='Independent Audit',ownership_reference='synthetic')}
    ownership=reconcile(read('rebar_shared_synthetic.json'),project)
    requests=template(previews,project['id'])
    crosswalk={'policy':POLICY,'project_id':project['id'],
               'owner_source_fingerprint_sha256':ownership['source_fingerprint_sha256'],
               'mappings':[]}
    result=audit(previews,ownership,crosswalk,{},project_id=project['id'])
    return {'sample_kind':'SYNTHETIC_ONLY_NOT_REAL_ENGINEERING',
            'crosswalk_request_template':requests,'audit':result}

if __name__=='__main__':
    print(json.dumps(verify(),ensure_ascii=False,indent=2))
