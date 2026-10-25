def test_extended_five_floor_site_operations(tmp_path):
    from scripts.phase4_site_operations_probe import run
    result=run(tmp_path/'site')
    assert result['prior']['actual_periods']==['12.500000','45.000000','75.000000']
    assert result['prior']['duration_baseline']==18 and result['prior']['duration_current']==20
    assert result['immutable_originals'] and result['reopen_equal']
    check_layout(tmp_path/'site')

def check_layout(root):
    import fitz
    for kind,limit in [('dashboard',15),('package',15)]:
        with fitz.open(root/(kind+'.pdf')) as document:
            assert len(document)<=limit, f'{kind}: raw payload dump produced {len(document)} pages'
