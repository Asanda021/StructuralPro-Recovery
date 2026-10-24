"""Regression for untranslated operational values observed in real exports."""
from copy import deepcopy
import pytest
from core.reports.site_operations import compact_rows

@pytest.mark.parametrize('status,label',[('open','باز'),('resolved','رفع‌شده')])
def test_office_report_localizes_status_without_rewriting_record(status,label):
    records=[{'id':'OBS-open-1','title':'مانع آزمایشی','status':status,'date':'2026-03-16','owner':'planner','activity_id':'S1'}]
    before=deepcopy(records)
    rows=compact_rows('obstacles',records,{})
    assert 'وضعیت: '+label in rows[0]['مقدار و وضعیت']
    assert 'وضعیت: '+status not in rows[0]['مقدار و وضعیت']
    assert rows[0]['شناسه سند']=='OBS-open-1' and records==before

@pytest.mark.parametrize('kind,label',[('opening','افتتاحیه'),('receipt','رسید'),('consume','مصرف'),('reserve','رزرو'),('return','برگشت'),('correct','اصلاح')])
def test_inventory_report_localizes_operation_without_rewriting_identity(kind,label):
    project={'project_materials':[{'schema':'site_material_v1','id':'receipt-1','material_code':'CON','kind':kind,'date':'2026-03-16','quantity':'1','unit':'m3'}]}
    before=deepcopy(project)
    rows=compact_rows('materials',{'requirements':[]},project)
    assert rows[0]['شرح و محل']=='CON | '+label
    assert rows[0]['شناسه سند']=='receipt-1' and project==before

@pytest.mark.parametrize('current,label',[(True,'بله'),(False,'خیر')])
def test_package_report_localizes_current_basis_flag(current,label):
    packages=[{'id':'W4','title':'بسته آزمایشی','date':'2026-03-16','status':'issued','current':current,'reference':'PKG-1','template':'site-office','template_version':'1','documents':[]}]
    rows=compact_rows('package',packages,{})
    assert 'مبنای جاری: '+label in rows[0]['مقدار و وضعیت']
