from scripts.phase2_priority3_closure_probe import run

def test_two_islands_to_specialist_boq_revised_opening_and_reports(tmp_path):
 r=run(tmp_path/'acceptance');assert r['effective_revision']==3 and r['sqlite_integrity']=='ok'
 assert r['reopened_snapshot_equal'] and len(r['negative_checks'])==3
