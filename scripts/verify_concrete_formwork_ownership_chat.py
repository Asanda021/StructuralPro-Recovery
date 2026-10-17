"""Synthetic repeatable preview of real three-engine concrete/formwork candidates.

Usage from StructuralPro repository root:
  python -m scripts.verify_concrete_formwork_ownership_chat [output_dir]
"""
from __future__ import annotations
import json
from pathlib import Path
import sys

from core.takeoff.shear_wall_bridge_chat import compile_preview as shear
from core.takeoff.stair_bridge_chat import compile_preview as stair
from core.takeoff.bored_pile_bridge_chat import compile_preview as pile
from core.takeoff.concrete_formwork_ownership_preflight_chat import POLICY,request_template,audit


def run(outdir:Path):
    root=Path(__file__).resolve().parents[1]
    def read(name):return json.loads((root/'examples'/name).read_text('utf-8'))
    p={'id':'P','takeoffs':[],'boq':[],'reviewed_aec_systems':{},
       'reviewed_structural_members':{},'beam_detail_register':{}}
    s=read('shear_wall_chat_reference.json')
    t=read('stair_chat_example.json');t['metadata']['project_id']='P'
    b=read('bored_pile_documented_synthetic.json')
    previews={
      'shear_wall':shear(s,p,reviewer='Independent Demo Reviewer',review_reference='SYNTHETIC'),
      'stair':stair(t,p,source_id='STAI-R1',reviewer='Independent Demo Reviewer',ownership_reference='SYNTHETIC'),
      'bored_pile':pile(b,p,independent_reviewer='Independent Demo Reviewer',ownership_reference='SYNTHETIC')}
    template=request_template(previews,p)
    result=audit(previews,p,{'policy':POLICY,'project_id':'P','mappings':[]},{})
    outdir.mkdir(parents=True,exist_ok=True)
    (outdir/'unverified_concrete_formwork_requests.json').write_text(
        json.dumps(template,ensure_ascii=False,sort_keys=True,indent=2)+'\n','utf-8')
    (outdir/'concrete_formwork_blocked_preflight.json').write_text(
        json.dumps(result,ensure_ascii=False,sort_keys=True,indent=2)+'\n','utf-8')
    print(json.dumps({'candidate_count':result['candidate_count'],
                      'operations':result['candidate_count_by_operation'],
                      'documented':result['document_consistent_count'],
                      'commit_allowed':result['commit_allowed']},ensure_ascii=False))
    return result


if __name__=='__main__':
    run(Path(sys.argv[1]) if len(sys.argv)>1 else Path('/tmp/structuralpro_concrete_formwork_preflight'))
