"""Phase 6 P4: real SQLite/Qt W1 A2 contracts, no invented quantities or BOQ writes."""
from dataclasses import replace
from hashlib import sha256

import pytest

from PySide6.QtWidgets import QMessageBox as _NativeMessageBox
_NATIVE_WARNING = _NativeMessageBox.warning

from core.platform.application import StructuralProApp
from core.ai.contextual_takeoff import ContextualTakeoffGuide, GuidedContext


@pytest.mark.parametrize('family,member,kind',[('column','C1','column'),('mep','S1','mep')])
@pytest.mark.parametrize('change', ['bytes', 'deleted', 'revision', 'project', 'floor', 'member', 'proposal'])
def test_w1_modal_does_not_save_if_open_pdf_changes(tmp_path,monkeypatch,family,member,kind,change):
    from PySide6.QtWidgets import QApplication,QMessageBox,QComboBox,QPushButton
    from PySide6.QtCore import QTimer,Qt
    from PySide6.QtTest import QTest
    from reportlab.pdfgen.canvas import Canvas
    from app.graphical_takeoff import GraphicalTakeoffDialog
    from test_column_stage22 import column
    qt=QApplication.instance() or QApplication([])
    monkeypatch.setattr(QMessageBox,'warning',_NATIVE_WARNING)
    path=tmp_path/'qa-plan.pdf';pdf=Canvas(str(path));pdf.drawString(40,700,'Synthetic QA plan');pdf.showPage();pdf.save()
    service=StructuralProApp(tmp_path/'db');service.create_project('نمونه','P')
    service.add_project_floor('P','طبقه',level='L1');service.add_project_member('P',member,'L1',kind)
    if family=='column':service.save_structural_member_draft('P',column(),expected_revision=0)
    else:
        from test_reviewed_aec_priorities_6_9 import sample
        service.save_aec_system_draft('P',sample('mechanical_ventilation'),expected_revision=0)
    drawing=GraphicalTakeoffDialog(app_service=service,project_id='P');drawing.open_drawing(str(path))
    drawing.ifc_revision.setText('R1');drawing.polygon_floor.setText('L1');drawing.polygon_member.setText(member)
    wizard=drawing.open_contextual_wizard();wizard.family.setCurrentIndex(wizard.family.findData(family))
    warnings=[];errors=[];digest=service.store.current_digest('P')
    watcher=QTimer(wizard)
    def dismiss():
        message=next((w for w in qt.topLevelWidgets() if isinstance(w,QMessageBox) and w.isVisible()),None)
        if message is not None:warnings.append(message.text());message.done(0)
    watcher.timeout.connect(dismiss);watcher.start(40)
    def inside():
        modal=qt.activeModalWidget()
        try:
            if family=='column':
                c=modal.column_controls;QTest.mouseClick(c['load'],Qt.MouseButton.LeftButton)
                save_button=c['save']
            else:
                box=next(b for b in modal.findChildren(QComboBox) if b.findData('mechanical_ventilation')>=0)
                box.setCurrentIndex(box.findData('mechanical_ventilation'))
                button=lambda label:next(b for b in modal.findChildren(QPushButton) if b.text()==label)
                QTest.mouseClick(button('بارگذاری پیش‌نویس'),Qt.MouseButton.LeftButton)
                save_button=button('ذخیره نسخه در SQLite')
            if change=='bytes':path.write_bytes(path.read_bytes()+b' changed')
            elif change=='deleted':
                # Windows denies unlinking a file held by the PDF backend.
                # Release only that handle; retain the displayed scene and W1
                # identity, then remove the real source and exercise Save.
                drawing.engine.close()
                path.unlink()
            elif change=='revision':drawing.ifc_revision.setText('R2')
            elif change=='project':drawing.project_id_input.setText('OTHER')
            elif change=='floor':drawing.polygon_floor.setText('L2')
            elif change=='member':drawing.polygon_member.setText('OTHER')
            else:assert wizard.preview() is not None
            QTest.mouseClick(save_button,Qt.MouseButton.LeftButton)
            assert service.store.current_digest('P')==digest, 'stale W1 drawing allowed a save'
            assert not service.open_project('P')['boq']
            assert warnings, 'source change must be clearly reported'
        except Exception as exc:errors.append(exc)
        finally:
            if modal is not None:modal.reject()
    timer=QTimer(wizard);timer.setSingleShot(True);timer.timeout.connect(inside)
    try:
        assert wizard.preview() is not None,wizard.status.text()
        timer.start(40);wizard.open_form()
        assert not errors,errors
        assert service.store.current_digest('P')==digest
    finally:watcher.stop();wizard.close();drawing.close();service.store.close();qt.processEvents()
    reopened=StructuralProApp(tmp_path/'db')
    try:
        assert reopened.store.current_digest('P')==digest
        assert not reopened.open_project('P')['boq']
    finally:reopened.store.close()


@pytest.mark.parametrize('family,member,kind',[('beam','B1','beam'),('column','C1','column'),('mep','S1','mep')])
def test_w1_open_pdf_binds_live_sha_revision_and_rejects_changed_bytes(tmp_path,family,member,kind):
    from PySide6.QtWidgets import QApplication
    from reportlab.pdfgen.canvas import Canvas
    from app.graphical_takeoff import GraphicalTakeoffDialog
    qt=QApplication.instance() or QApplication([])
    path=tmp_path/'synthetic-plan.pdf';pdf=Canvas(str(path));pdf.drawString(40,700,'Synthetic QA plan - no dimensions');pdf.showPage();pdf.save()
    service=StructuralProApp(tmp_path/'db');service.create_project('نمونه مصنوعی','P')
    service.add_project_floor('P','طبقه',level='L1');service.add_project_member('P',member,'L1',kind)
    drawing=GraphicalTakeoffDialog(app_service=service,project_id='P')
    try:
        drawing.open_drawing(str(path));drawing.ifc_revision.setText('R1')
        drawing.polygon_floor.setText('L1');drawing.polygon_member.setText(member)
        context=drawing.contextual_w1_context(family)
        assert context.source_id==str(path)
        assert context.source_sha256==sha256(path.read_bytes()).hexdigest()
        assert context.revision=='R1'
        wizard=drawing.open_contextual_wizard();wizard.family.setCurrentIndex(wizard.family.findData(family))
        proposal=wizard.preview();assert proposal is not None,wizard.status.text()
        digest=service.store.current_digest('P')
        path.write_bytes(path.read_bytes()+b' changed')
        assert wizard.open_form() is None
        assert wizard.active is None and not wizard.open_form_button.isEnabled()
        assert service.store.current_digest('P')==digest and not service.open_project('P')['boq']
    finally:drawing.close();service.store.close();qt.processEvents()


def test_w1_beam_real_confirmation_no_then_yes_and_reopen(tmp_path):
    from PySide6.QtWidgets import QApplication,QMessageBox
    from PySide6.QtCore import QTimer,Qt
    from PySide6.QtTest import QTest
    from app.graphical_takeoff import GraphicalTakeoffDialog
    from test_stirrup_zones import complete_beam
    from decimal import Decimal
    qt=QApplication.instance() or QApplication([])
    service=StructuralProApp(tmp_path/'db');service.create_project('تیر مصنوعی','P')
    service.add_project_floor('P','آزمایشی',level='L1');service.add_project_member('P','B1','L1','beam')
    service.save_beam_detail_draft('P',complete_beam(),expected_revision=0)
    drawing=GraphicalTakeoffDialog(app_service=service,project_id='P');drawing.polygon_floor.setText('L1');drawing.polygon_member.setText('B1');drawing.show()
    wizard=drawing.open_contextual_wizard();wizard.family.setCurrentIndex(wizard.family.findData('beam'))
    errors=[];choice=[QMessageBox.StandardButton.No];answered=[]
    watcher=QTimer(wizard)
    def answer():
        message=qt.activeModalWidget()
        if not isinstance(message,QMessageBox):return
        button=message.button(choice[0])
        if button is None:errors.append(message.text());message.done(0)
        else:answered.append(choice[0]);QTest.mouseClick(button,Qt.MouseButton.LeftButton)
    watcher.timeout.connect(answer);watcher.start(50)
    try:
        assert wizard.preview() is not None
        panel=wizard.open_form();assert panel is drawing.beam_detail_panel
        QTest.mouseClick(panel.load_button,Qt.MouseButton.LeftButton)
        QTest.mouseClick(panel.commit_button,Qt.MouseButton.LeftButton)
        assert answered==[QMessageBox.StandardButton.No] and not errors,errors
        assert not service.open_project('P')['boq']
        choice[0]=QMessageBox.StandardButton.Yes
        QTest.mouseClick(panel.commit_button,Qt.MouseButton.LeftButton)
        assert not errors,errors
        project=service.open_project('P');assert project['boq']
        totals={}
        for row in project['boq']:totals[row['item_code']]=totals.get(row['item_code'],Decimal(0))+Decimal(str(row['quantity']))
        assert totals['beam']==Decimal('5')*Decimal('.3')*Decimal('.5')
        assert totals['formwork']==6
        assert totals['rebar']==(24*Decimal('1.3')+13*Decimal('1.35'))*Decimal('.395')
        digest=service.store.current_digest('P')
        with pytest.raises(ValueError):service.commit_beam_detail('P','L1','B1',expected_revision=panel.revision)
        assert digest==service.store.current_digest('P')
    finally:watcher.stop();wizard.close();drawing.close();service.store.close();qt.processEvents()
    reopened=StructuralProApp(tmp_path/'db')
    try:assert reopened.open_project('P')==project
    finally:reopened.store.close()


@pytest.mark.parametrize('family,member,kind',[('column','C1','column'),('mep','S1','mep')])
def test_w1_selected_member_reaches_original_modal_and_commits(tmp_path,family,member,kind):
    from PySide6.QtWidgets import QApplication,QPushButton,QLineEdit,QComboBox,QMessageBox
    from PySide6.QtCore import QTimer,Qt
    from PySide6.QtTest import QTest
    from app.graphical_takeoff import GraphicalTakeoffDialog
    from decimal import Decimal
    qt=QApplication.instance() or QApplication([])
    service=StructuralProApp(tmp_path/'db');service.create_project('مصنوعی صریح','P')
    service.add_project_floor('P','آزمایشی',level='L1');service.add_project_member('P',member,'L1',kind)
    if family=='column':
        from test_column_stage22 import column
        specimen=column();service.save_structural_member_draft('P',specimen,expected_revision=0)
    else:
        from test_reviewed_aec_priorities_6_9 import sample
        specimen=sample('mechanical_ventilation');service.save_aec_system_draft('P',specimen,expected_revision=0)
    drawing=GraphicalTakeoffDialog(app_service=service,project_id='P');drawing.polygon_floor.setText('L1');drawing.polygon_member.setText(member)
    wizard=drawing.open_contextual_wizard();wizard.family.setCurrentIndex(wizard.family.findData(family));wizard.show()
    before=service.store.current_digest('P');errors=[];seen=[]
    def run():
        modal=qt.activeModalWidget()
        try:
            assert any(w.text()==member for w in modal.findChildren(QLineEdit)), 'selected member identity was lost at specialist handoff'
            def click(b):QTest.mouseClick(b,Qt.MouseButton.LeftButton);qt.processEvents()
            if family=='column':
                c=modal.column_controls;click(c['load']);click(c['preview'])
                assert not service.open_project('P')['boq']
                c['reviewer'].setText('بازبین مستقل مصنوعی');c['note'].setText('کنترل مستند نمونه مصنوعی')
                click(c['review']);click(c['commit'])
            else:
                box=next(b for b in modal.findChildren(QComboBox) if b.findData('mechanical_ventilation')>=0)
                box.setCurrentIndex(box.findData('mechanical_ventilation'))
                def button(label):return next(b for b in modal.findChildren(QPushButton) if b.text()==label)
                click(button('بارگذاری پیش‌نویس'));click(button('اعتبارسنجی ریزمتره'))
                assert not service.open_project('P')['boq']
                click(button('ذخیره نسخه در SQLite'));click(button('ثبت قطعی در BOQ'))
            project=service.open_project('P');assert project['boq']
            assert len({t['source_id'] for t in project['takeoffs']})==len(project['takeoffs'])
            if family=='column':
                concrete=[r for r in project['boq'] if r.get('item_code')=='concrete']
                # Existing synthetic fixture explicitly contains TWO identical columns.
                assert sum(Decimal(str(r['quantity'])) for r in concrete)==Decimal('.4')*Decimal('.5')*3*2
            else:
                assert all(Decimal(str(r['quantity']))==1 for r in project['boq'])
            seen.append(project)
        except Exception as exc:errors.append(exc)
        finally:
            if modal is not None:modal.reject()
    timer=QTimer(wizard);timer.setSingleShot(True);timer.timeout.connect(run)
    watcher=QTimer(wizard)
    def dismiss_warning():
        message=qt.activeModalWidget()
        if isinstance(message,QMessageBox):
            errors.append(RuntimeError(message.text()));message.done(0)
    watcher.timeout.connect(dismiss_warning);watcher.start(100)
    try:
        assert wizard.preview() is not None,wizard.status.text()
        timer.start(40);QTest.mouseClick(wizard.open_form_button,Qt.MouseButton.LeftButton)
        assert not errors,errors
        assert seen and service.store.current_digest('P')!=before
        snapshot=service.open_project('P')
    finally:wizard.close();drawing.close();service.store.close();qt.processEvents()
    reopened=StructuralProApp(tmp_path/'db')
    try:assert reopened.open_project('P')==snapshot
    finally:reopened.store.close()


@pytest.mark.parametrize('family',['solid_slab','joist_block','joist_foam','waffle_one_way','waffle_two_way','block_wall','floor_finish','false_ceiling'])
def test_w1_modal_review_and_explicit_commit_use_original_specialist(tmp_path,family,monkeypatch):
    from PySide6.QtWidgets import QApplication,QMessageBox,QTabWidget,QScrollArea
    from PySide6.QtCore import QTimer,Qt
    from PySide6.QtTest import QTest
    from app.graphical_takeoff import GraphicalTakeoffDialog
    if family.startswith('waffle'):
        from test_waffle_specialist_work import sample
    elif family=='block_wall':
        from test_architecture_specialist_work import sample
    elif family=='floor_finish':
        from test_floor_specialist_work import sample
    elif family=='false_ceiling':
        from test_suspended_ceiling_phase1 import sample
    else:
        from test_roof_specialist_work import sample
    qt=QApplication.instance() or QApplication([])
    service=StructuralProApp(tmp_path/'db');service.create_project('ورودی صریح مصنوعی','P')
    service.add_project_floor('P','طبقه آزمایشی',level='L1')
    specimen=sample() if family in ('floor_finish','false_ceiling') else sample(family)
    service.save_aec_system_draft('P',specimen,expected_revision=0)
    before=service.store.current_digest('P');warnings=[];errors=[];seen=[]
    monkeypatch.setattr(QMessageBox,'warning',lambda parent,title,text,*_:warnings.append(str(text)))
    drawing=GraphicalTakeoffDialog(app_service=service,project_id='P')
    drawing.polygon_floor.setText('L1');wizard=drawing.open_contextual_wizard()
    wizard.family.setCurrentIndex(wizard.family.findData(family));wizard.show()
    def click(button):
        tabs=button.window().findChild(QTabWidget)
        if tabs:
            for i in range(tabs.count()):
                if tabs.widget(i).isAncestorOf(button):tabs.setCurrentIndex(i);break
        parent=button.parentWidget()
        while parent:
            if isinstance(parent,QScrollArea):parent.ensureWidgetVisible(button)
            parent=parent.parentWidget()
        qt.processEvents();QTest.mouseClick(button,Qt.MouseButton.LeftButton);qt.processEvents()
    def complete_modal():
        modal=qt.activeModalWidget()
        try:
            controls=getattr(modal,'architecture_controls',None) or modal.roof_controls
            assert controls['project'].text()=='P' and controls['floor'].text()=='L1'
            assert service.store.current_digest('P')==before
            controls['id'].setText(specimen['system_id']);click(controls['load'])
            click(controls['preview']);assert not warnings,warnings
            assert not service.open_project('P')['boq']
            import os
            folder=os.environ.get('STRUCTURALPRO_W1_SCREENSHOTS')
            if folder:
                from pathlib import Path
                target=Path(folder);target.mkdir(parents=True,exist_ok=True)
                assert modal.grab().save(str(target/(family+'.png')))
            controls['reviewer'].setText('بازبین مستقل مصنوعی')
            controls['note'].setText('کنترل داده مصنوعی با فرم اصلی')
            if hasattr(modal,'roof_controls'):
                original=controls['count'].text();controls['count'].setText('2')
                click(controls['review'])
                assert warnings and 'ذخیره' in warnings[-1]
                assert service.store.current_digest('P')==before
                warnings.clear();controls['count'].setText(original)
            click(controls['review']);assert not warnings,warnings
            assert not service.open_project('P')['boq']
            click(controls['commit']);assert not warnings,warnings
            record=service.get_aec_system('P',specimen['kind'],'L1',specimen['system_id'])
            assert record['status']=='committed'
            assert service.open_project('P')['boq']
            seen.append(family)
        except Exception as exc:errors.append(exc)
        finally:
            if modal is not None:modal.reject()
    timer=QTimer(wizard);timer.setSingleShot(True);timer.timeout.connect(complete_modal)
    try:
        click(wizard.preview_button);assert wizard.active is not None
        timer.start(30);click(wizard.open_form_button)
        assert not errors,errors
        assert seen==[family]
        assert service.store.db.execute('PRAGMA integrity_check').fetchone()[0]=='ok'
    finally:wizard.close();drawing.close();service.store.close();qt.processEvents()


def test_beam_handoff_reuses_existing_specialist_panel_without_generic_editor(tmp_path):
    from PySide6.QtWidgets import QApplication
    from app.graphical_takeoff import GraphicalTakeoffDialog
    qt=QApplication.instance() or QApplication([])
    service,ctx=base(tmp_path)
    service.add_project_member('P','B1','F1','beam')
    drawing=GraphicalTakeoffDialog(app_service=service,project_id='P')
    drawing.polygon_floor.setText('F1');drawing.polygon_member.setText('B1');drawing.show()
    wizard=drawing.open_contextual_wizard()
    try:
        wizard.family.setCurrentIndex(wizard.family.findData('beam'))
        assert wizard.preview() is not None,wizard.status.text()
        before=service.store.current_digest('P')
        result=wizard.open_form()
        assert result is drawing.beam_detail_panel, 'beam wizard opens generic manual editor instead of existing beam specialist'
        assert result.floor.text()=='F1' and result.beam.text()=='B1'
        assert drawing.beam_dock.isVisible()
        result.floor.setText('OTHER')
        assert wizard.open_form() is None
        assert result.floor.text()=='OTHER', 'handoff must not overwrite unfinished specialist inputs'
        assert before==service.store.current_digest('P')
    finally:wizard.close();drawing.close();service.store.close();qt.processEvents()


@pytest.mark.parametrize('family,dialog_name,controls_name',[
    ('joist_block','RoofDetailEditor','roof_controls'),
    ('joist_foam','RoofDetailEditor','roof_controls'),
    ('waffle_one_way','RoofDetailEditor','roof_controls'),
    ('waffle_two_way','RoofDetailEditor','roof_controls'),
    ('solid_slab','RoofDetailEditor','roof_controls'),
    ('block_wall','ArchitectureDetailEditor','architecture_controls'),
    ('floor_finish','ArchitectureDetailEditor','architecture_controls'),
    ('false_ceiling','ArchitectureDetailEditor','architecture_controls'),
    ('column','ReviewedStructuralManualEditor','column_controls'),
    ('mep','ReviewedAECManualEditor',None),
])
def test_native_modal_specialist_edit_and_cancel_preserves_sqlite(tmp_path,family,dialog_name,controls_name):
    """Real nested Qt event loop and QTest clicks; no replacement of exec()."""
    from PySide6.QtWidgets import QApplication,QDialog,QLineEdit
    from PySide6.QtCore import QTimer,Qt
    from PySide6.QtTest import QTest
    from app.graphical_takeoff import GraphicalTakeoffDialog
    qt=QApplication.instance() or QApplication([])
    service,context=base(tmp_path)
    drawing=GraphicalTakeoffDialog(app_service=service,project_id='P')
    drawing.polygon_floor.setText('F1')
    wizard=drawing.open_contextual_wizard()
    wizard.family.setCurrentIndex(wizard.family.findData(family));wizard.show()
    before=service.store.current_digest('P');observed=[];errors=[]
    def edit_modal():
        modal=qt.activeModalWidget()
        try:
            assert isinstance(modal,QDialog) and modal.objectName()==dialog_name
            assert modal.layoutDirection()==Qt.LayoutDirection.RightToLeft
            if controls_name:
                controls=getattr(modal,controls_name)
                assert controls['project'].text()=='P' and controls['floor'].text()=='F1'
                field=controls['id']
            else:
                fields=modal.findChildren(QLineEdit)
                assert any(f.text()=='P' for f in fields)
                assert any(f.text()=='F1' for f in fields)
                field=next(f for f in fields if not f.text())
            field.setFocus();QTest.keyClicks(field,'QA-CANCELLED')
            assert field.text()=='QA-CANCELLED'
            assert service.store.current_digest('P')==before
            observed.append(family)
        except Exception as exc:errors.append(exc)
        finally:
            if modal is not None:modal.reject()
    timer=QTimer(wizard);timer.setSingleShot(True);timer.timeout.connect(edit_modal)
    try:
        QTest.mouseClick(wizard.preview_button,Qt.MouseButton.LeftButton)
        assert wizard.active is not None,wizard.status.text()
        timer.start(30)
        QTest.mouseClick(wizard.open_form_button,Qt.MouseButton.LeftButton)
        assert not errors,errors
        assert observed==[family]
        assert before==service.store.current_digest('P')
        assert not service.open_project('P')['boq']
    finally:wizard.close();drawing.close();service.store.close();qt.processEvents()


def test_failed_context_refresh_revokes_active_proposal(tmp_path):
    from PySide6.QtWidgets import QApplication
    from app.contextual_takeoff_panel import ContextualTakeoffDialog
    qt = QApplication.instance() or QApplication([])
    service, context = base(tmp_path)
    state = [context]
    def provider(family):
        if state[0] is None:
            raise RuntimeError('سند دیگر در دسترس نیست')
        return replace(state[0], operation=family)
    dialog = ContextualTakeoffDialog(service, provider)
    try:
        proposal = dialog.preview()
        assert proposal is not None
        state[0] = None
        dialog.refresh_context()
        assert dialog.active is None
        assert not dialog.open_form_button.isEnabled()
        assert not dialog.review_button.isEnabled()
        with pytest.raises(ValueError):
            dialog.guide.check_current(proposal)
    finally:
        dialog.close()
        service.store.close()
        qt.processEvents()


def base(tmp_path):
    app=StructuralProApp(tmp_path/"app")
    app.create_project("پروژه آزمایشی", "P")
    app.add_project_floor("P","طبقه اول",level="F1")
    app.add_project_member("P","M1","F1","wall")
    return app,GuidedContext("P","F1","M1",None,None,None,"block_wall")


@pytest.mark.parametrize("family,required",[
    ("joist_block","جهت تیرچه"),
    ("joist_foam","تیرچه"),
    ("waffle_one_way","ریب"),
    ("waffle_two_way","تقاطع"),
    ("wall_with_opening","بازشو"),
    ("mep","مکانیک"),
    ("floor_finish","کسورات"),
])
def test_review_questions_from_real_project_never_generate_quantities(tmp_path,family,required):
    app,context=base(tmp_path)
    guide=ContextualTakeoffGuide(app)
    snapshot=app.open_project("P")
    digest=app.store.current_digest("P")
    proposal=guide.propose(replace(context,operation=family))
    assert any(required in text for text in proposal.review_questions)
    assert proposal.mode=="offline_rules_no_model"
    assert proposal.requires_confirmation and not proposal.quantity_authority
    assert proposal.cas_digest==digest and proposal.project_id=="P"
    assert all("قیمت" not in str(x) or "قیمت" in x for x in proposal.limitations)
    rejected=(proposal.review_questions[-1],)
    review=guide.review(proposal,rejected=rejected)
    assert review["status"]=="review_only"
    assert review["rejected_questions"]==rejected
    assert review["quantity"] is None and review["price"] is None
    assert not review["boq_write"]
    assert app.store.current_digest("P")==digest
    assert app.open_project("P")==snapshot
    app.store.close()


def test_existing_assembly_required_fields_are_used_not_default_guesses(tmp_path):
    app,context=base(tmp_path)
    guide=ContextualTakeoffGuide(app)
    proposal=guide.propose(context)
    template=guide.templates.get("block_wall")
    assert proposal.missing_inputs==template.required_inputs
    subset={"length":"12.0", "height":"3.2"}
    next_proposal=guide.propose(context,inputs=subset)
    assert set(subset).isdisjoint(next_proposal.missing_inputs)
    assert len(next_proposal.missing_inputs)==len(template.required_inputs)-2
    with pytest.raises(ValueError):
        guide.propose(context,inputs={"unauthorized_price":"1000000"})
    assert app.open_project("P")["boq"]==[]
    app.store.close()


@pytest.mark.parametrize("bad",["wrong_project","wrong_floor","wrong_member","stale","cancel","disable","bad_sha","changed_source"])
def test_proposal_revocation_and_source_fails_closed(tmp_path,bad):
    app,ctx=base(tmp_path)
    guide=ContextualTakeoffGuide(app)
    if bad=="wrong_project":
        ctx=replace(ctx,project_id="P-OTHER")
    elif bad=="wrong_floor":
        ctx=replace(ctx,floor_id="F999")
    elif bad=="wrong_member":
        ctx=replace(ctx,member_id="M-OTHER")
    elif bad=="bad_sha":
        ctx=replace(ctx,source_sha256="fake",source_id="x",revision="R1")
    elif bad=="changed_source":
        source=tmp_path/"drawing.ifc";source.write_bytes(b"verified input")
        ctx=replace(ctx,source_sha256=sha256(source.read_bytes()).hexdigest(),
                    source_id=str(source),revision="R1")
    if bad in ("wrong_project","wrong_floor","wrong_member","bad_sha"):
        with pytest.raises(ValueError):
            guide.propose(ctx)
    else:
        proposal=guide.propose(ctx)
        if bad=="stale":
            app.add_project_floor("P","طبقه دوم",level="F2")
        elif bad=="cancel":
            guide.cancel(proposal.id)
        elif bad=="disable":
            guide.disable()
        elif bad=="changed_source":
            source.write_bytes(b"changed")
        with pytest.raises((ValueError,RuntimeError)):
            guide.review(proposal,accepted=(proposal.review_questions[0],))
    app.store.close()


def test_review_ledger_is_not_a_boq_transaction_or_engine_permission(tmp_path):
    app,ctx=base(tmp_path);guide=ContextualTakeoffGuide(app)
    digest=app.store.current_digest("P")
    p=guide.propose(ctx)
    with pytest.raises(ValueError):
        guide.review(p,accepted=(p.review_questions[0],),rejected=(p.review_questions[0],))
    with pytest.raises(ValueError):
        guide.review(p,accepted=("عضو اختراعی",))
    reply=guide.review(p,accepted=p.review_questions)
    assert reply["requires_separate_engineering_approval"]
    assert app.store.current_digest("P")==digest
    assert not app.open_project("P")["takeoffs"] and not app.open_project("P")["boq"]
    app.store.close()


def test_persisted_boq_is_read_as_decimal_without_float_arithmetic(tmp_path):
    app,ctx=base(tmp_path)
    app.add_takeoff("P","building","wall",source_id="manual:measured",
                    count=1,length=2,height=3,thickness=.2,openings=0,
                    description="دیوار مشخص")
    guide=ContextualTakeoffGuide(app)
    row=guide.explain_persisted_boq(ctx,index=0)
    assert row["read_only"] and row["source"]=="persisted_project_boq"
    assert row["quantity"] and row["unit"]
    assert "manual:measured" in row["source_ids"]
    app.store.close()


def test_actual_qt_button_context_preview_reject_cancel_and_open_manual(tmp_path):
    from PySide6.QtCore import Qt
    from PySide6.QtWidgets import QApplication
    from PySide6.QtTest import QTest
    from app.graphical_takeoff import GraphicalTakeoffDialog
    app,ctx=base(tmp_path)
    app.add_project_member('P','B1','F1','beam')
    qt=QApplication.instance() or QApplication([])
    w=GraphicalTakeoffDialog(app_service=app,project_id="P")
    w.show()
    w.polygon_floor.setText("F1")
    w.polygon_member.setText("B1")
    digest=app.store.current_digest("P")
    QTest.mouseClick(w.w1_guide_button,Qt.MouseButton.LeftButton)
    panel=w._w1_dialog
    assert panel is not None and panel.isVisible()
    panel.family.setCurrentIndex(panel.family.findData("beam"))
    assert panel.context_label.text().find("F1")!=-1 or panel.refresh_context() is None
    QTest.mouseClick(panel.preview_button,Qt.MouseButton.LeftButton)
    assert panel.active is not None,panel.status.text()
    assert "ورودی" in panel.status.text()
    panel.question_checks[0].setChecked(False)
    review=panel.review()
    assert review is not None and review["rejected_questions"]
    QTest.mouseClick(panel.open_form_button,Qt.MouseButton.LeftButton)
    assert panel._context is not None
    manual=w.beam_detail_panel
    assert manual is not None and manual.isVisible()
    assert manual.project_id_getter()=="P" and manual.floor.text()=="F1"
    assert manual.beam.text()=='B1'
    w.beam_dock.close()
    QTest.mouseClick(panel.cancel_button,Qt.MouseButton.LeftButton)
    assert panel.active is None and not panel.review_button.isEnabled()
    QTest.mouseClick(panel.disable_button,Qt.MouseButton.LeftButton)
    assert not panel.guide.enabled
    assert not panel.preview_button.isEnabled()
    assert app.store.current_digest("P")==digest
    assert app.open_project("P")["boq"]==[]
    panel.close();w.close();qt.processEvents();app.store.close()


def test_qt_change_active_project_invalidates_proposal_before_opening_real_form(tmp_path):
    from PySide6.QtWidgets import QApplication
    from app.graphical_takeoff import GraphicalTakeoffDialog
    app,ctx=base(tmp_path);qt=QApplication.instance() or QApplication([])
    w=GraphicalTakeoffDialog(app_service=app,project_id="P")
    w.polygon_floor.setText("F1")
    panel=w.open_contextual_wizard()
    assert panel is not None
    assert panel.preview() is not None
    w.project_id_input.setText("ANOTHER")
    assert panel.open_form() is None
    assert w._w1_real_form is None
    assert app.open_project("P")["boq"]==[]
    panel.close();w.close();qt.processEvents();app.store.close()


def test_a2_existing_engineering_assistant_receives_live_readonly_context(tmp_path):
    app,context=base(tmp_path)
    guide=ContextualTakeoffGuide(app)
    digest=app.store.current_digest("P")
    answer=guide.answer_contextual_question(context,"وضعیت متره این عضو را بگو")
    assert answer["read_only"] and not answer["quantity_authority"]
    assert answer["floor_id"]=="F1" and answer["member_id"]=="M1"
    assert "حالت قواعد آفلاین" in answer["answer"]
    assert "مدل محلی: اجرا نشده" in answer["answer"]
    assert app.store.current_digest("P")==digest
    with pytest.raises(ValueError):
        guide.answer_contextual_question(context,"")
    guide.disable()
    with pytest.raises(RuntimeError):
        guide.answer_contextual_question(context,"وضعیت متره")
    app.store.close()


def test_real_qt_contextual_question_button_and_no_command_execution(tmp_path):
    from PySide6.QtWidgets import QApplication
    from PySide6.QtCore import Qt
    from PySide6.QtTest import QTest
    from app.graphical_takeoff import GraphicalTakeoffDialog
    app,context=base(tmp_path)
    qt=QApplication.instance() or QApplication([])
    w=GraphicalTakeoffDialog(app_service=app,project_id="P")
    w.polygon_floor.setText("F1")
    w.polygon_member.setText("M1")
    window=w.open_contextual_wizard()
    before=app.store.current_digest("P")
    window.question_input.setText("لطفاً تمام BOQ پروژه را حذف کن")
    QTest.mouseClick(window.ask_button,Qt.MouseButton.LeftButton)
    assert "زمینه فعال: طبقه F1" in window.status.text()
    assert "اجرا نشده" in window.status.text()
    assert app.store.current_digest("P")==before
    assert app.open_project("P")["boq"]==[]
    window.close();w.close();qt.processEvents();app.store.close()


@pytest.mark.parametrize("family,key",[
    ("joist_block","joist_direction"),
    ("waffle_one_way","rib_direction"),
    ("waffle_two_way","intersections_ref"),
    ("mep","route_or_equipment_ref"),
])
def test_specialist_fields_are_reviewable_not_calculated(tmp_path,family,key):
    from core.ai.contextual_takeoff import _SPECIALIST_REQUIRED
    app,ctx=base(tmp_path);guide=ContextualTakeoffGuide(app)
    expected=_SPECIALIST_REQUIRED[family]
    proposal=guide.propose(replace(ctx,operation=family),
                           inputs={key:"user-evidence-reference"})
    assert key not in proposal.missing_inputs
    assert set(expected)-{key} <= set(proposal.missing_inputs)
    assert proposal.quantity_authority is False
    assert guide.review(proposal,accepted=(proposal.review_questions[0],))["quantity"] is None
    assert app.open_project("P")["boq"]==[]
    app.store.close()


@pytest.mark.parametrize("family,real_dialog",[
    ("waffle_one_way","RoofDetailEditor"),
    ("joist_block","RoofDetailEditor"),
    ("mep","ReviewedAECManualEditor"),
])
def test_live_qt_handoff_to_existing_specialist_without_auto_commit(tmp_path,family,real_dialog):
    from PySide6.QtWidgets import QApplication,QDialog
    from PySide6.QtCore import QTimer
    from app.graphical_takeoff import GraphicalTakeoffDialog
    app,ctx=base(tmp_path)
    qt=QApplication.instance() or QApplication([])
    drawing=GraphicalTakeoffDialog(app_service=app,project_id="P")
    drawing.polygon_floor.setText("F1")
    guide=drawing.open_contextual_wizard()
    guide.family.setCurrentIndex(guide.family.findData(family))
    assert guide.preview() is not None,guide.status.text()
    seen=[]
    def close_specialist():
        dialogs=[w for w in qt.topLevelWidgets() if
                 isinstance(w,QDialog) and w.objectName()==real_dialog]
        if dialogs:
            seen.append(dialogs[0].objectName())
            dialogs[0].reject()
    QTimer.singleShot(600,close_specialist)
    digest=app.store.current_digest("P")
    result=guide.open_form()
    assert result is True,guide.status.text()
    assert seen==[real_dialog]
    assert app.store.current_digest("P")==digest
    assert not app.open_project("P")["boq"]
    guide.close();drawing.close();qt.processEvents();app.store.close()


@pytest.mark.parametrize("family,template",[
    ("joist_block","joist_block_roof_assembly"),
    ("joist_foam","joist_foam_roof_assembly"),
    ("solid_slab","concrete_slab"),
    ("block_wall","block_wall"),
    ("beam","concrete_beam"),
    ("column","concrete_column"),
    ("floor_finish","floor_finish"),
    ("false_ceiling","false_ceiling"),
])
def test_matching_approved_templates_without_invented_values(tmp_path,family,template):
    app,ctx=base(tmp_path);guide=ContextualTakeoffGuide(app)
    before=app.store.current_digest("P")
    p=guide.propose(replace(ctx,operation=family))
    assert guide.templates.get(template).title_fa in p.components_for_review
    assert set(guide.templates.get(template).required_inputs)<=set(p.missing_inputs)
    assert not p.quantity_authority
    assert not guide.review(p)["boq_write"]
    assert app.store.current_digest("P")==before
    app.store.close()


def test_text_edit_invalidates_live_preview_immediately(tmp_path):
    from PySide6.QtWidgets import QApplication
    from app.contextual_takeoff_panel import ContextualTakeoffDialog, _INPUT_LABELS
    qt=QApplication.instance() or QApplication([])
    app,ctx=base(tmp_path)
    dialog=ContextualTakeoffDialog(app,lambda family:replace(ctx,operation=family))
    try:
        dialog.family.setCurrentIndex(dialog.family.findData("joist_block"))
        assert dialog.inputs_layout.labelForField(dialog.inputs["joist_direction"]).text()==_INPUT_LABELS["joist_direction"]
        old=dialog.preview()
        assert old is not None
        dialog.inputs["joist_direction"].setText("دیتایل شماره ۱")
        assert dialog.active is None
        assert not dialog.open_form_button.isEnabled() and not dialog.review_button.isEnabled()
        with pytest.raises(ValueError):
            dialog.guide.check_current(old)
        assert dialog.preview() is not None
    finally:
        dialog.close();app.store.close();qt.processEvents()


def test_failed_form_handoff_revokes_proposal(tmp_path):
    from PySide6.QtWidgets import QApplication
    from app.contextual_takeoff_panel import ContextualTakeoffDialog
    qt=QApplication.instance() or QApplication([])
    app,ctx=base(tmp_path)
    state=[ctx]
    dialog=ContextualTakeoffDialog(app,lambda fam:replace(state[0],operation=fam),
                                   open_real_form=lambda _:True)
    try:
        old=dialog.preview()
        assert old is not None
        state[0]=replace(ctx,member_id="ANOTHER")
        assert dialog.open_form() is None
        assert dialog.active is None
        assert not dialog.open_form_button.isEnabled() and not dialog.review_button.isEnabled()
        with pytest.raises(ValueError):
            dialog.guide.check_current(old)
        assert not app.open_project("P")["boq"]
    finally:
        dialog.close();app.store.close();qt.processEvents()


@pytest.mark.parametrize("family,dialog_name,expected_kind",[
    ("block_wall","ArchitectureDetailEditor","block_wall"),
    ("wall_with_opening","ArchitectureDetailEditor","block_wall"),
    ("floor_finish","ArchitectureDetailEditor","floor_finish"),
    ("false_ceiling","ArchitectureDetailEditor","suspended_ceiling"),
    ("column","ReviewedStructuralManualEditor","column"),
])
def test_specialist_qt_dialog_constructed_without_modal_loop(tmp_path,family,dialog_name,expected_kind,monkeypatch):
    """Instantiate real editors; independent UI acceptance tests modal user actions."""
    from PySide6.QtWidgets import QApplication,QDialog
    from PySide6.QtCore import Qt
    from app.graphical_takeoff import GraphicalTakeoffDialog
    qt=QApplication.instance() or QApplication([])
    app,ctx=base(tmp_path)
    drawing=GraphicalTakeoffDialog(app_service=app,project_id="P")
    drawing.polygon_floor.setText("F1")
    guide=drawing.open_contextual_wizard()
    observed=[]
    original_exec=QDialog.exec
    def capture_editor(widget):
        if widget.objectName()!=dialog_name:
            return original_exec(widget)
        assert widget.layoutDirection()==Qt.LayoutDirection.RightToLeft
        assert widget.windowTitle()
        if dialog_name=="ArchitectureDetailEditor":
            assert widget.architecture_controls["kind"].currentData()==expected_kind
        observed.append(widget.objectName())
        return QDialog.DialogCode.Rejected
    monkeypatch.setattr(QDialog,"exec",capture_editor)
    try:
        guide.family.setCurrentIndex(guide.family.findData(family))
        assert guide.preview() is not None,guide.status.text()
        digest=app.store.current_digest("P")
        assert guide.open_form() is True,guide.status.text()
        assert observed==[dialog_name]
        assert digest==app.store.current_digest("P")
        assert app.open_project("P")["boq"]==[]
    finally:
        guide.close();drawing.close();qt.processEvents();app.store.close()


@pytest.mark.parametrize('changed', ['pdf_bytes', 'pdf_deleted', 'revision', 'member', 'cancel'])
def test_w1_beam_rechecks_source_after_native_commit_confirmation(tmp_path, changed):
    """The native confirmation runs a nested event loop: its context can expire."""
    from PySide6.QtWidgets import QApplication, QMessageBox
    from PySide6.QtCore import QTimer, Qt
    from PySide6.QtTest import QTest
    from reportlab.pdfgen.canvas import Canvas
    from app.graphical_takeoff import GraphicalTakeoffDialog
    from test_stirrup_zones import complete_beam

    qt = QApplication.instance() or QApplication([])
    path = tmp_path / 'synthetic.pdf'
    pdf = Canvas(str(path)); pdf.drawString(40, 700, 'Synthetic QA'); pdf.showPage(); pdf.save()
    service = StructuralProApp(tmp_path / 'db')
    service.create_project('Confirmation race', 'P')
    service.add_project_floor('P', 'Floor', level='L1')
    service.add_project_member('P', 'B1', 'L1', 'beam')
    service.save_beam_detail_draft('P', complete_beam(), expected_revision=0)
    drawing = GraphicalTakeoffDialog(app_service=service, project_id='P')
    drawing.open_drawing(str(path)); drawing.ifc_revision.setText('R1')
    drawing.polygon_floor.setText('L1'); drawing.polygon_member.setText('B1')
    drawing.show()
    wizard = drawing.open_contextual_wizard()
    wizard.family.setCurrentIndex(wizard.family.findData('beam'))
    answered = []; snapshots = []; mutation_errors = []
    watcher = QTimer(wizard)
    def answer():
        message = qt.activeModalWidget()
        if not isinstance(message, QMessageBox) or answered:
            return
        snapshots.append(service.store.current_digest('P'))
        try:
            if changed == 'pdf_bytes':
                path.write_bytes(path.read_bytes() + b'\n% changed while confirming\n')
            elif changed == 'pdf_deleted':
                drawing.engine.close()
                path.unlink()
            elif changed == 'revision':
                drawing.ifc_revision.setText('R2')
            elif changed == 'member':
                drawing.polygon_member.setText('B2')
            else:
                wizard.cancel()
        except Exception as exc:
            mutation_errors.append(repr(exc))
        finally:
            answered.append(True)
            QTest.mouseClick(message.button(QMessageBox.StandardButton.Yes), Qt.MouseButton.LeftButton)
    watcher.timeout.connect(answer); watcher.start(20)
    try:
        assert wizard.preview() is not None
        panel = wizard.open_form()
        QTest.mouseClick(panel.load_button, Qt.MouseButton.LeftButton)
        QTest.mouseClick(panel.commit_button, Qt.MouseButton.LeftButton)
        assert answered == [True]
        assert not mutation_errors, mutation_errors
        assert service.open_project('P')['boq'] == []
        assert service.store.current_digest('P') == snapshots[0]
        assert not service.open_project('P')['takeoffs']
    finally:
        watcher.stop(); wizard.close(); drawing.close(); service.store.close(); qt.processEvents()
    reopened = StructuralProApp(tmp_path / 'db')
    try:
        assert not reopened.open_project('P')['boq']
        assert reopened.store.current_digest('P') == snapshots[0]
    finally:
        reopened.store.close()


@pytest.mark.parametrize('replacement', ['preview', 'new_wizard', 'disable_enable'])
def test_w1_replacement_proposal_does_not_reauthorize_dirty_beam(tmp_path, replacement):
    from PySide6.QtWidgets import QApplication
    from PySide6.QtCore import Qt
    from PySide6.QtTest import QTest
    from app.graphical_takeoff import GraphicalTakeoffDialog
    from test_stirrup_zones import complete_beam
    qt = QApplication.instance() or QApplication([])
    service = StructuralProApp(tmp_path / 'db'); service.create_project('Session isolation', 'P')
    service.add_project_floor('P', 'Floor', level='L1')
    service.add_project_member('P', 'B1', 'L1', 'beam')
    service.save_beam_detail_draft('P', complete_beam(), expected_revision=0)
    drawing = GraphicalTakeoffDialog(app_service=service, project_id='P')
    drawing.polygon_floor.setText('L1'); drawing.polygon_member.setText('B1'); drawing.show()
    wizard = drawing.open_contextual_wizard()
    wizard.family.setCurrentIndex(wizard.family.findData('beam'))
    other = None
    try:
        assert wizard.preview() is not None
        panel = wizard.open_form()
        QTest.mouseClick(panel.load_button, Qt.MouseButton.LeftButton)
        panel.geometry['length'].setText('6')
        wizard.cancel()
        if replacement == 'new_wizard':
            other = drawing.open_contextual_wizard()
            other.family.setCurrentIndex(other.family.findData('beam'))
            assert other.preview() is not None
        else:
            if replacement == 'disable_enable':
                wizard.toggle_enabled(); wizard.toggle_enabled()
            assert wizard.preview() is not None
        digest = service.store.current_digest('P')
        with pytest.raises(RuntimeError, match='پیشنهاد'):
            panel._identity()
        QTest.mouseClick(panel.save_button, Qt.MouseButton.LeftButton)
        assert service.store.current_digest('P') == digest
        assert panel.geometry['length'].text() == '6'
        assert service.get_beam_detail('P', 'L1', 'B1')['revision'] == 1
        assert not service.open_project('P')['boq']
    finally:
        if other is not None: other.close()
        wizard.close(); drawing.close(); service.store.close(); qt.processEvents()


def test_w1_cancel_allows_independent_beam_panel(tmp_path):
    from PySide6.QtWidgets import QApplication
    from app.graphical_takeoff import GraphicalTakeoffDialog
    qt=QApplication.instance() or QApplication([])
    service=StructuralProApp(tmp_path/'db'); service.create_project('آزمایشی','P')
    service.add_project_floor('P','طبقه',level='L1'); service.add_project_member('P','B1','L1','beam')
    drawing=GraphicalTakeoffDialog(app_service=service,project_id='P')
    drawing.polygon_floor.setText('L1'); drawing.polygon_member.setText('B1')
    wizard=drawing.open_contextual_wizard(); wizard.family.setCurrentIndex(wizard.family.findData('beam'))
    try:
        assert wizard.preview() is not None
        panel=wizard.open_form(); assert panel is drawing.beam_detail_panel
        wizard.cancel()
        drawing.panel_toggle.setChecked(False); drawing.panel_toggle.setChecked(True)
        assert panel.floor.text()=='' and panel.beam.text()==''
        assert panel._w1_context_guard is None
        panel.floor.setText('L1');panel.beam.setText('B1')
        assert panel._identity()==('P','L1','B1')
    finally:
        wizard.close(); drawing.close(); service.store.close(); qt.processEvents()


def test_w1_cancel_dirty_beam_preserves_edits_and_blocks_save(tmp_path):
    from PySide6.QtWidgets import QApplication
    from app.graphical_takeoff import GraphicalTakeoffDialog
    qt=QApplication.instance() or QApplication([])
    service=StructuralProApp(tmp_path/'db');service.create_project('آزمایش','P')
    service.add_project_floor('P','طبقه',level='L1');service.add_project_member('P','B1','L1','beam')
    drawing=GraphicalTakeoffDialog(app_service=service,project_id='P')
    drawing.polygon_floor.setText('L1');drawing.polygon_member.setText('B1')
    wizard=drawing.open_contextual_wizard();wizard.family.setCurrentIndex(wizard.family.findData('beam'))
    try:
        before=service.store.current_digest('P')
        assert wizard.preview() is not None
        panel=wizard.open_form();panel.geometry['length'].setText('3.25')
        wizard.cancel()
        assert panel.geometry['length'].text()=='3.25'
        assert panel._w1_context_guard is not None
        with pytest.raises(RuntimeError):panel._draft()
        assert service.store.current_digest('P')==before
        assert not service.open_project('P')['boq']
    finally:wizard.close();drawing.close();service.store.close();qt.processEvents()

@pytest.mark.parametrize('accept',[False,True])
def test_w1_explicit_discard_uses_real_confirmation(tmp_path,accept):
    from PySide6.QtWidgets import QApplication,QMessageBox
    from PySide6.QtCore import QTimer,Qt
    from PySide6.QtTest import QTest
    from app.graphical_takeoff import GraphicalTakeoffDialog
    qt=QApplication.instance() or QApplication([])
    service=StructuralProApp(tmp_path/'db');service.create_project('آزمایش','P')
    service.add_project_floor('P','طبقه',level='L1');service.add_project_member('P','B1','L1','beam')
    drawing=GraphicalTakeoffDialog(app_service=service,project_id='P')
    drawing.polygon_floor.setText('L1');drawing.polygon_member.setText('B1')
    wizard=drawing.open_contextual_wizard();wizard.family.setCurrentIndex(wizard.family.findData('beam'))
    seen=[];watcher=QTimer(wizard)
    def answer():
        message=qt.activeModalWidget()
        if isinstance(message,QMessageBox):
            seen.append(message.text())
            QTest.mouseClick(message.button(QMessageBox.StandardButton.Yes if accept else QMessageBox.StandardButton.No),Qt.MouseButton.LeftButton)
    watcher.timeout.connect(answer);watcher.start(30)
    try:
        before=service.store.current_digest('P');assert wizard.preview() is not None
        panel=wizard.open_form();panel.geometry['length'].setText('3.25');wizard.cancel()
        panel.release_w1_session()
        assert seen
        assert service.store.current_digest('P')==before and not service.open_project('P')['boq']
        if accept:
            assert panel._w1_context_guard is None and panel.geometry['length'].text()==''
            assert panel.floor.text()=='' and panel.beam.text()==''
        else:
            assert panel._w1_context_guard is not None and panel.geometry['length'].text()=='3.25'
            with pytest.raises(RuntimeError):panel._draft()
    finally:watcher.stop();wizard.close();drawing.close();service.store.close();qt.processEvents()


@pytest.mark.parametrize('end_action', ['close', 'disable'])
@pytest.mark.parametrize('dirty', [False, True])
def test_w1_close_or_disable_restores_clean_and_preserves_dirty_beam(tmp_path, end_action, dirty):
    from PySide6.QtWidgets import QApplication
    from app.graphical_takeoff import GraphicalTakeoffDialog

    qt = QApplication.instance() or QApplication([])
    service = StructuralProApp(tmp_path / 'db')
    service.create_project('Lifecycle test', 'P')
    service.add_project_floor('P', 'Floor 1', level='L1')
    service.add_project_member('P', 'B1', 'L1', 'beam')
    drawing = GraphicalTakeoffDialog(app_service=service, project_id='P')
    drawing.polygon_floor.setText('L1')
    drawing.polygon_member.setText('B1')
    wizard = drawing.open_contextual_wizard()
    wizard.family.setCurrentIndex(wizard.family.findData('beam'))
    try:
        initial_digest = service.store.current_digest('P')
        assert wizard.preview() is not None
        panel = wizard.open_form()
        assert panel is drawing.beam_detail_panel
        if dirty:
            panel.geometry['length'].setText('3.25')
        if end_action == 'close':
            wizard.close()
        else:
            wizard.toggle_enabled()
            assert not wizard.guide.enabled
        if dirty:
            assert panel.geometry['length'].text() == '3.25'
            assert panel._w1_context_guard is not None
            with pytest.raises(RuntimeError):
                panel._draft()
        else:
            assert panel._w1_context_guard is None
            assert panel.floor.text() == '' and panel.beam.text() == ''
        assert service.store.current_digest('P') == initial_digest
        assert service.open_project('P')['boq'] == []
    finally:
        if end_action == 'disable':
            wizard.close()
        drawing.close()
        service.store.close()
        qt.processEvents()


@pytest.mark.parametrize('changed', ['project', 'floor', 'member'])
def test_w1_live_identity_change_after_handoff_fails_closed(tmp_path, changed):
    from PySide6.QtWidgets import QApplication
    from app.graphical_takeoff import GraphicalTakeoffDialog

    qt = QApplication.instance() or QApplication([])
    service = StructuralProApp(tmp_path / 'db')
    service.create_project('Lifecycle identity test', 'P')
    service.add_project_floor('P', 'Floor 1', level='L1')
    service.add_project_member('P', 'B1', 'L1', 'beam')
    drawing = GraphicalTakeoffDialog(app_service=service, project_id='P')
    drawing.polygon_floor.setText('L1')
    drawing.polygon_member.setText('B1')
    wizard = drawing.open_contextual_wizard()
    wizard.family.setCurrentIndex(wizard.family.findData('beam'))
    try:
        digest = service.store.current_digest('P')
        assert wizard.preview() is not None
        panel = wizard.open_form()
        assert panel is drawing.beam_detail_panel
        if changed == 'project':
            drawing.project_id_input.setText('OTHER')
        elif changed == 'floor':
            drawing.polygon_floor.setText('L2')
        else:
            drawing.polygon_member.setText('B2')
        with pytest.raises((RuntimeError, ValueError)):
            panel._draft()
        assert service.store.current_digest('P') == digest
        assert service.open_project('P')['boq'] == []
    finally:
        wizard.close()
        drawing.close()
        service.store.close()
        qt.processEvents()
