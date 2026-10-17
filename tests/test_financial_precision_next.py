"""Independent Decimal references; legacy SQLite payloads remain readable."""
from decimal import Decimal
import pytest
from core.platform.application import StructuralProApp
from core.commercial.progress import build_progress
from test_statement_amendment_workflow import fixture,version

@pytest.mark.parametrize('method',['add_project_cost','add_project_receipt','add_project_commitment'])
def test_long_amount_saved_and_summed_exactly(tmp_path,method):
    a=StructuralProApp(tmp_path/'db');a.create_project('مصنوعی','P');value='123456789012345678901234567890.123456789'
    fn=getattr(a,method)
    args=('P','مصالح',value) if method=='add_project_cost' else ('P',value)
    fn(*args);fn(*args);a.store.close();a=StructuralProApp(tmp_path/'db')
    key,summary={'add_project_cost':('actual_cost',a.project_cost_summary),'add_project_receipt':('total_received',a.project_receipt_summary),'add_project_commitment':('committed_total',a.project_commitment_summary)}[method]
    with __import__('decimal').localcontext() as ctx:
        ctx.prec=128;assert Decimal(str(summary('P')[key]))==Decimal(value)*2
    a.store.close()

@pytest.mark.parametrize('value',[True,None,'NaN','Infinity','-1'])
@pytest.mark.parametrize('method',['add_project_cost','add_project_receipt','add_project_commitment'])
def test_invalid_amount_rejected_without_mutation(tmp_path,method,value):
    a=StructuralProApp(tmp_path/'db');a.create_project('مصنوعی','P');before=a.open_project('P')
    args=('P','مصالح',value) if method=='add_project_cost' else ('P',value)
    with pytest.raises(ValueError):getattr(a,method)(*args)
    assert a.open_project('P')==before;a.store.close()

def test_progress_product_and_deductions_use_decimal():
    q='0.12345678901234567890123456789';price='987654321098765432109876543.21'
    with __import__('decimal').localcontext() as ctx:
        ctx.prec=128;expected=Decimal(q)*Decimal(price)-Decimal('0.1')-Decimal('0.2')
    r=build_progress([{'code':'X','contract_quantity':'1','previous_quantity':'0','current_quantity':q,'unit_price':price}],deductions=['0.1','0.2'])
    assert Decimal(str(r['payable_current']))==expected

def test_issued_and_amendment_money_share_policy(tmp_path):
    a,docs,_,_=fixture(tmp_path)
    issued=a.statement_periods('P')[0];snapshot=a.statement_amendment_summary('P',1)
    assert Decimal(str(issued['payable_current']))==Decimal(snapshot['original']['payable_current'])
    assert issued['money_policy']==a.open_project('P')['statement_amendment_policy']['money'];a.store.close()

def test_exact_boq_estimate_factors_and_exports(tmp_path):
    from core.takeoff.estimate import build_estimate
    from core.reports import exporters
    from openpyxl import load_workbook
    q='0.12345678901234567890123456789';price='987654321098765432109876543.21';factor='0.12345678901234567890123456789'
    row={'source_id':'independent','description':'مصنوعی','item_code':'X','price_code':'X','unit':'m2','quantity':q,'unit_price':price}
    with __import__('decimal').localcontext() as ctx:
        ctx.prec=512;expected=Decimal(q)*Decimal(price)*(1+Decimal(factor))
    result=build_estimate([row],factors={'مصوب مصنوعی':factor})
    assert Decimal(str(result['cost']['grand_total']))==expected
    value=str(result['cost']['grand_total']);rows=[{'code':'X','amount':value}]
    path=exporters.export_xlsx(rows,tmp_path/'exact.xlsx');wb=load_workbook(path)
    assert any(cell.value==value for row in wb['ریز متره'] for cell in row)

def test_real_dashboard_keeps_fractional_money_text(tmp_path):
    from PySide6.QtWidgets import QApplication
    from app.dashboard import DashboardPage
    from core.pricing.catalog import PriceCatalog
    global _qt_lifetime
    _qt_lifetime=QApplication.instance() or QApplication([])
    qt=_qt_lifetime
    a,docs,_,_=fixture(tmp_path);a.add_project_receipt('P','0.12345678901234567890123456789')
    a.add_project_cost('P','مصالح','0.12345678901234567890123456789')
    widget=DashboardPage(a,PriceCatalog())
    widget.project_selector.setCurrentIndex(widget.project_selector.findData('P'));qt.processEvents()
    widget._refresh_selected_project()
    assert '0.12345678901234567890123456789' in widget.financial_summary.text()
    widget.close();widget.deleteLater()
    from PySide6.QtCore import QCoreApplication,QEvent
    QCoreApplication.sendPostedEvents(None,QEvent.DeferredDelete);qt.processEvents()
    a.store.close()

def test_payment_allocation_and_summary_preserve_large_exact_amount(tmp_path):
    a=StructuralProApp(tmp_path/'db');a.create_project('مصنوعی','P')
    value='123456789012345678901234567890.123456789'
    p=a.add_project_payment('P',value)
    a.allocate_project_payment('P',p['id'],'document',1,value)
    summary=a.project_payment_summary('P')
    assert Decimal(str(summary['payment_total']))==Decimal(value)
    assert Decimal(str(summary['allocated_total']))==Decimal(value) and summary['unallocated_total']==0
    before=a.open_project('P')
    with pytest.raises(ValueError):a.allocate_project_payment('P',p['id'],'document',1,'0.000000001')
    assert a.open_project('P')==before;a.store.close()
