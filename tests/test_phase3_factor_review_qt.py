import hashlib,json
from PySide6.QtWidgets import QApplication,QLineEdit,QPushButton,QLabel
from PySide6.QtTest import QTest
from PySide6.QtCore import Qt
from core.platform.application import StructuralProApp


def test_real_factor_review_click_persists_document(tmp_path):
    from app.financial_factor_review import FactorReviewDialog
    qt=QApplication.instance() or QApplication([])
    service=StructuralProApp(tmp_path/'app');service.create_project('fixture','P')
    p=tmp_path/'p.csv';p.write_text('code,description,unit,unit_price\nA,test,m,1\n')
    service.import_project_pricebook('P',p,year=1405,approved_by='reviewer',currency='IRR')
    doc=tmp_path/'f.json';doc.write_text(json.dumps({'version':'R1','year':1405,'currency':'IRR','effective_date':'2026-10-23','basis':'sequential_compound','factors':[{'name':'overhead','rate':'0.1'}]}))
    dialog=FactorReviewDialog(service,'P');dialog.show();qt.processEvents()
    for name,value in [('FactorEvidencePath',str(doc)),('FactorEvidenceSHA256',hashlib.sha256(doc.read_bytes()).hexdigest()),('FactorAuthor','author'),('FactorReviewer','reviewer')]:
        dialog.findChild(QLineEdit,name).setText(value)
    QTest.mouseClick(dialog.findChild(QPushButton,'ApproveFactors'),Qt.MouseButton.LeftButton)
    assert service.open_project('P')['factor_review']['reviewer']=='reviewer'
    assert 'ثبت شد' in dialog.findChild(QLabel,'FactorReviewStatus').text()
    before=service.store.current_digest('P');doc.write_text('{}')
    QTest.mouseClick(dialog.findChild(QPushButton,'ApproveFactors'),Qt.MouseButton.LeftButton)
    assert service.store.current_digest('P')==before
    assert 'نامعتبر' in dialog.findChild(QLabel,'FactorReviewStatus').text()
    dialog.close();service.store.close()
