"""Run the original probe under the unchanged native-network-denied runner."""
import os
from pathlib import Path

def test_persistent_site_probe():
    from scripts.phase4_site_operations_probe import run
    root=Path(os.environ['STRUCTURALPRO_QA_SCENARIO'])
    result=run(root)
    assert result['prior']['floors']==5 and result['prior']['activities']==15
    assert result['prior']['duration_baseline']==18
    assert result['prior']['duration_current']==20
    assert result['prior']['actual_periods']==['12.500000','45.000000','75.000000']
    assert result['immutable_originals'] and result['reopen_equal']
    assert len(result['exports'])==40
    import fitz
    for kind in ('dashboard','package'):
        with fitz.open(root/(kind+'.pdf')) as document:
            assert len(document)<=15
