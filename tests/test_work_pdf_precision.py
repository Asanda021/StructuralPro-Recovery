from copy import deepcopy
import pytest
import pymupdf
from core.reports import exporters

def test_persian_code_repeats_in_each_panel():
    cols=[('کد','کد')] + [(f'amount{i}',f'مبلغ {i}') for i in range(14)]
    rows=[{'کد':'W-001', **{f'amount{i}':'76543.001836602551500' for i in range(14)}}]
    plan=exporters._pdf_column_plan(cols,rows,font=exporters._pdf_font(),usable_width=790)
    assert len(plan)>1 and all(p[0][0]=='کد' for p in plan)
    assert {x[0] for p in plan for x in p}=={x[0] for x in cols}

def test_long_summary_decimal_is_one_full_number(tmp_path):
    value='1234567890'*8+'.123456789012345678901234567890'
    path=exporters.export_pdf([{'item_no':1,'total':'100.00'}],tmp_path/'summary.pdf',
                             title='گزارش دقیق فارسی',summary={'grand_total':value})
    with pymupdf.open(path) as doc:
        text='\n'.join(p.get_text() for p in doc)
        assert value in text

@pytest.mark.parametrize('value',['1.234567890123456789012345678901e+120','-1.234567890123456789e-50'])
def test_scientific_number_is_measured_as_an_indivisible_number(value):
    assert exporters._pdf_is_number(value)

def test_summary_number_too_wide_is_rejected(tmp_path):
    target=tmp_path/'invalid.pdf'
    with pytest.raises(ValueError,match='عدد مالی'):
        exporters.export_pdf([{'item_no':1}],target,summary={'base':'9'*1000})
    assert not target.exists()

def test_unique_later_identity_and_generated_identity_do_not_change_source():
    rows=[{'code':'same','source_id':'physical-1','quantity':'1.0000000000000000001'},
          {'code':'same','source_id':'physical-2','quantity':'2.0000000000000000002'}]
    original=deepcopy(rows);cols=[('code','کد'),('source_id','منبع'),('quantity','مقدار')]
    copied,chosen=exporters._pdf_identity(rows,cols)
    plan=exporters._pdf_column_plan(chosen,copied,font=exporters._pdf_font(),usable_width=790)
    assert plan[0][0][0]=='source_id' and rows==original
    copied,chosen=exporters._pdf_identity(rows,[('quantity','مقدار')])
    assert chosen[0][0]=='_pdf_row_id' and copied[0]['_pdf_row_id']==1 and rows==original

def test_real_persian_all_pages_and_export_precision(tmp_path):
    import csv
    from openpyxl import load_workbook
    value='76543.001836602551500'
    rows=[{'item_no':i,'description':f'بتن و آرماتور طبقه {i%5+1} با منشأ مستند',
           **{f'amount{j}':value for j in range(12)}} for i in range(1,61)]
    cols=[('item_no','ردیف'),('description','شرح فارسی')]+[(f'amount{j}',f'مبلغ دقیق {j}') for j in range(12)]
    original=deepcopy(rows)
    path=exporters.export_pdf(rows,tmp_path/'persian.pdf',title='نمونه مصنوعی — گزارش فارسی چندصفحه‌ای',columns=cols,summary={'grand_total':value})
    with pymupdf.open(path) as pdf:
        assert len(pdf)>2
        for page in pdf:
            words=page.get_text('words')
            assert any(w[4]==value for w in words)
            assert all(-1<=w[0]<w[2]<=page.rect.width+1 and -1<=w[1]<w[3]<=page.rect.height+1 for w in words)
            assert any(w[1]>page.rect.height-30 for w in words) # Real footer on every page.
        assert sum(page.get_text().count(value) for page in pdf)==60*12+1
    csvpath=exporters.export_csv(rows,tmp_path/'persian.csv',columns=cols)
    assert sum(cell==value for row in csv.reader(csvpath.open(encoding='utf-8-sig')) for cell in row)==720
    xlsx=exporters.export_xlsx(rows,tmp_path/'persian.xlsx',columns=cols)
    wb=load_workbook(xlsx);assert wb['ریز متره'].sheet_view.rightToLeft
    assert sum(cell.value==value for row in wb['ریز متره'] for cell in row)==720
    assert rows==original
