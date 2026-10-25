"""BOQ display identity survives JSON dictionary sorting; values remain guarded."""
from copy import deepcopy
from decimal import Decimal
from pathlib import Path
from hashlib import sha256
import json,pytest
from core.platform.application import StructuralProApp
from core.takeoff.commit_guards import rebuild_project_boq
from test_slope_integrated_work import sample,commit

def test_rebuild_preserves_existing_order_without_trusting_quantities():
 def row(s,q):return dict(source_id=s,domain='building',quantities=[dict(code='fill',title='مصنوعی '+s,amount=q,unit='m3',role='work',price_code=None,unit_price=None)])
 p={'takeoffs':[row('A','1'),row('B','2')]};_,initial=rebuild_project_boq(p,p['takeoffs']);p['boq']=initial
 _,actual=rebuild_project_boq(p,list(reversed(p['takeoffs']))+[row('C','3')])
 assert [r['source_id'] for r in actual]==['A','B','C']
 p['boq'][0]['quantity']=999
 _,actual=rebuild_project_boq(p,p['takeoffs']);assert Decimal(str(actual[0]['quantity']))==1

def test_aggregated_sources_retain_validated_order_after_replay():
 def row(s,q):return dict(source_id=s,domain='building',quantities=[dict(code='fill',title='عملیات تجمیعی مصنوعی',amount=q,unit='m3',role='work',price_code=None,unit_price=None)])
 p={'takeoffs':[row('A','1'),row('B','2')]};_,p['boq']=rebuild_project_boq(p,p['takeoffs'])
 _,actual=rebuild_project_boq(p,list(reversed(p['takeoffs'])))
 assert actual==p['boq']
 p['boq'][0]['quantity']=999
 _,actual=rebuild_project_boq(p,p['takeoffs']);assert Decimal(str(actual[0]['quantity']))==3

def test_reopen_multiple_amendments_then_save_draft_preserves_boq(tmp_path):
 a=StructuralProApp(tmp_path/'db');a.create_project('مصنوعی','P')
 for sid in ('A','B'):
  d=sample(tmp_path);d['system_id']=sid;d['source']['source_id']=sid;g=d['architecture_detail']['geometry'];g['physical_region_id']=sid
  for name in ('zones','openings'):
   for v in d['architecture_detail'][name]:v['physical_key']=sid+v['physical_key']
  a.save_aec_system_draft('P',d,expected_revision=0);a.review_roof_system('P','floor_finish','L1',sid,expected_revision=1,reviewer='مستقل',note='مصنوعی');a.commit_aec_system('P','floor_finish','L1',sid,expected_revision=2)
  revised=deepcopy(a.get_aec_system('P','floor_finish','L1',sid)['data']);revised.pop('roof_review');revised['architecture_detail']['zones'][0]['thickness_00_m']='.21';f=tmp_path/(sid+'.txt');f.write_text('EXPLICIT SYNTHETIC revised corner thickness')
  am=a.create_roof_amendment('P','floor_finish','L1',sid,revised,expected_revision=2,created_by='سازنده',reason='مصنوعی',evidence=dict(evidence_path=str(f),evidence_sha256=sha256(f.read_bytes()).hexdigest(),evidence_reference='مصنوعی'));a.review_beam_amendment('P',am['id'],expected_revision=1,reviewer='بازبین',note='مصنوعی');a.apply_beam_amendment('P',am['id'],expected_revision=1)
 p=a.open_project('P');before=deepcopy(p['boq'])
 # Simulate canonical JSON map ordering differing from amendment application order.
 p['beam_amendment_applied']=dict(reversed(list(p['beam_amendment_applied'].items())))
 encoded=json.dumps(p,ensure_ascii=False)
 # Reorder a committed fixture snapshot consistently in both representations.
 # Leaving only projects changed would model a torn write, now rejected at startup.
 a.store.db.execute('update projects set payload=? where id=?',(encoded,'P'))
 a.store.db.execute('update revisions set payload=? where project_id=? and version=?',(encoded,'P',p['_meta']['version']))
 a.store.db.commit()
 from core.recovery.recovery import require_project_history_consistency
 require_project_history_consistency(a.store.db)
 a.store.close();a=StructuralProApp(tmp_path/'db')
 d=sample(tmp_path);d['system_id']='NEW';d['source']['source_id']='NEW';g=d['architecture_detail']['geometry'];g['physical_region_id']='NEW'
 for name in ('zones','openings'):
  for v in d['architecture_detail'][name]:v['physical_key']='NEW'+v['physical_key']
 a.save_aec_system_draft('P',d,expected_revision=0);assert a.open_project('P')['boq']==before
 bad=a.open_project('P');bad['boq'][0]['quantity']=999
 with pytest.raises(ValueError):a.store.save('P',bad)
 a.store.close()
