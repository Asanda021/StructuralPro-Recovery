"""RTL review of the existing IFC lineage and canonical correction journals."""
from hashlib import sha256
from pathlib import Path
from PySide6.QtWidgets import QComboBox,QLineEdit,QLabel,QPushButton,QTableWidget,QTableWidgetItem,QFileDialog


def install_ifc_lineage_controls(dialog,layout,viewer,service,pid,author,reviewers,outcome):
    from core.takeoff.manual_formula_amendments import IFC_TRANSFER,ifc_transfer_head
    lineages=QComboBox();lineages.setObjectName('ifc_group_lineage')
    allocation=QLineEdit();allocation.setObjectName('ifc_group_allocation');allocation.setPlaceholderText('فایل مدرک جدول تخصیص مقدار و طبقه‌بندی ناخالص/خالص')
    choose=QPushButton('انتخاب مدرک تخصیص');choose.clicked.connect(lambda:allocation.setText(QFileDialog.getOpenFileName(dialog,'مدرک تخصیص IFC')[0]))
    table=QTableWidget(0,6);table.setObjectName('ifc_group_quantities');table.setHorizontalHeaderLabels(['نسخه','طبقه / عضو','GlobalId','مقدار','واحد / مبنا','SHA-256 منبع'])
    summary=QLabel('گروه Split/Merge را برای بررسی تاریخچه و مالکیت انتخاب کنید');summary.setObjectName('ifc_group_summary');summary.setWordWrap(True)
    preview=QPushButton('پیش‌نمایش آشتی مستقل مقدار');preview.setObjectName('ifc_group_preview')
    confirm=QPushButton('تأیید صریح بازبین مستقل برای انتقال / مهاجرت');confirm.setCheckable(True);confirm.setObjectName('ifc_group_confirm')
    apply=QPushButton('اعمال یکپارچه انتقال مالکیت در دفتر اصلاحیه');apply.setObjectName('ifc_group_apply')
    reject=QPushButton('رد درخواست / لغو تأیید');reject.setObjectName('ifc_group_reject')
    document=QLineEdit();document.setObjectName('ifc_group_crosswalk_document');document.setPlaceholderText('فایل مدرک گروهی ارتباط‌های قبلی و جاری Crosswalk')
    choose_link=QPushButton('انتخاب مدرک مهاجرت');choose_link.clicked.connect(lambda:document.setText(QFileDialog.getOpenFileName(dialog,'مدرک مهاجرت Crosswalk')[0]))
    migrate=QPushButton('بازبینی مستقل و مهاجرت گروهی Crosswalk');migrate.setObjectName('ifc_group_migrate')
    links=QComboBox();links.setObjectName('ifc_group_links')
    open_link=QPushButton('انتخاب مدل نسخه مرتبط و نمایش عضو دوبعدی');open_link.setObjectName('ifc_group_open_link')
    history_action=QComboBox();history_action.setObjectName('ifc_history_action')
    history_action.addItem('واگرد مالکیت با ثبت اصلاحیه معکوس','undo');history_action.addItem('تکرار انتقال مالکیت با نسخه تازه','redo')
    history_reason=QLineEdit();history_reason.setObjectName('ifc_history_reason');history_reason.setPlaceholderText('علت صریح واگرد یا تکرار مالکیت')
    history_preview=QPushButton('پیش‌نمایش مالک‌های قبل و بعد واگرد / تکرار');history_preview.setObjectName('ifc_history_preview')
    history_apply=QPushButton('اعمال نسخه تازه تاریخچه پس از تأیید مستقل');history_apply.setObjectName('ifc_history_apply')
    state={}
    def history_context():
        return viewer.project_id_input.text().strip(),str(viewer.viewer.path),viewer.ifc_revision.text().strip()
    history_origin=history_context()
    def refresh():
        project=service.open_project(pid);chosen=lineages.currentData();lineages.blockSignals(True);lineages.clear()
        for event in project.get('ifc_identity_lineages',[]):lineages.addItem(event['mode']+' | '+event['id'],event['id'])
        if chosen:lineages.setCurrentIndex(max(0,lineages.findData(chosen)))
        lineages.blockSignals(False);links.clear()
        event=next((x for x in project.get('ifc_identity_lineages',[]) if x['id']==lineages.currentData()),None)
        if event:
            for link in project.get('ifc_2d_crosswalks',[]):
                if link['proposal_id'] in event['previous_proposal_ids']+event['current_proposal_ids']:
                    stage='تاریخی' if link['proposal_id'] in event['previous_proposal_ids'] else 'جاری'
                    links.addItem(stage+' | '+link['ifc_document']['revision']+' | '+link['member_id']+' | '+link['drawing']['source_sha256'],link['id'])
            applied=next((x for x in project.get('manual_formula_amendments',{}).values() if x.get('kind')==IFC_TRANSFER and not x.get('transfer_root') and x.get('lineage_id')==event['id']),None)
            if not applied:summary.setText('مالکیت گروه هنوز منتقل نشده است؛ مدرک و بازبینی مستقل لازم است')
            if applied:
                _,head=ifc_transfer_head(project,applied['id'])
                summary.setText('نسخه مالکیت '+str(head['group_revision'])+' | '+head.get('history_action','apply')+' | '+head['previous_total']+' → '+head['current_total']+' '+head['unit']+' | '+applied['id'])
    def run(action):
        try:
            if action in ('preview','apply','migrate','history_preview','history_apply') and (history_origin[0]!=pid or history_context()!=history_origin):
                raise ValueError('پروژه یا نسخه منبع نمایش‌داده‌شده تغییر کرده؛ فرم بازبینی را دوباره باز کنید')
            if action=='preview':
                path=Path(allocation.text());token=service.store.current_digest(pid)
                args=dict(lineage_id=lineages.currentData(),evidence_path=str(path),evidence_sha256=sha256(path.read_bytes()).hexdigest(),author=author.text(),reviewer=reviewers.currentData(),expected_digest=token)
                result=service.assess_ifc_lineage_quantities(pid,**args);state.clear();state.update(args=args)
                table.setRowCount(0)
                for group in ('previous','current'):
                    for row in result[group]:
                        n=table.rowCount();table.insertRow(n)
                        for col,text in enumerate([row['revision'],row['floor_id']+' / '+row['member_id'],row['global_id'],row['quantity'],row['unit']+' / '+row['classification'],row['source_sha256']]):
                            cell=QTableWidgetItem(str(text));from PySide6.QtCore import Qt
                            cell.setFlags(cell.flags() & ~Qt.ItemIsEditable);table.setItem(n,col,cell)
                summary.setText('اولیه '+result['previous_total']+' | پیشنهادی '+result['current_total']+' | اختلاف '+result['delta']+' '+result['unit']+' | SHA مدرک '+args['evidence_sha256'])
                confirm.setChecked(False)
            elif action=='apply':
                if not confirm.isChecked() or 'args' not in state:raise ValueError('پیش‌نمایش و تأیید صریح مستقل لازم است')
                args=state['args']
                if args['author']!=author.text() or args['reviewer']!=reviewers.currentData() or args['lineage_id']!=lineages.currentData() or args['evidence_path']!=allocation.text():raise ValueError('ورودی بازبینی تغییر کرده است؛ پیش‌نمایش تازه لازم است')
                service.apply_ifc_quantity_transfer(pid,**args);refresh();state.clear()
            elif action=='migrate':
                if not confirm.isChecked():raise ValueError('تأیید صریح بازبین مستقل لازم است')
                path=Path(document.text());service.migrate_ifc_crosswalk_group(pid,lineage_id=lineages.currentData(),evidence_path=str(path),evidence_sha256=sha256(path.read_bytes()).hexdigest(),author=author.text(),reviewer=reviewers.currentData(),expected_digest=service.store.current_digest(pid));refresh()
            elif action=='history_preview':
                # Previous evidence/consent belongs to its original CAS token.
                # A failed or concurrently invalidated preview must not leave
                # a previously confirmed inverse transfer actionable.
                state.clear()
                confirm.setChecked(False)
                table.setRowCount(0)
                token=service.store.current_digest(pid)
                project=service.open_project(pid)
                if service.store.current_digest(pid)!=token:
                    raise RuntimeError('نسخه پروژه هنگام خواندن تاریخچه مالکیت تغییر کرد؛ پیش‌نمایش دوباره لازم است')
                roots=[x for x in project.get('manual_formula_amendments',{}).values()
                    if x.get('kind')==IFC_TRANSFER and not x.get('transfer_root') and x.get('lineage_id')==lineages.currentData()]
                if len(roots)!=1:raise ValueError('انتقال اصلی یکتا برای واگرد موجود نیست')
                root,head=ifc_transfer_head(project,roots[0]['id'])
                args=dict(transfer_id=root['id'],action=history_action.currentData(),expected_revision=head['group_revision'],
                    expected_digest=token,author=author.text(),reviewer=reviewers.currentData(),reason=history_reason.text())
                result=service.preview_ifc_quantity_transfer_step(pid,**args)
                state.clear();state.update(history_args=args,history_lineage=lineages.currentData())
                table.setRowCount(0)
                for stage in ('previous','current'):
                    for row in result[stage]:
                        n=table.rowCount();table.insertRow(n)
                        for col,value in enumerate([row['revision'],row['floor_id']+' / '+row['member_id'],row['global_id'],row['quantity'],row['unit']+' / '+row['classification'],row['source_sha256']]):
                            cell=QTableWidgetItem(str(value));from PySide6.QtCore import Qt
                            cell.setFlags(cell.flags() & ~Qt.ItemIsEditable);table.setItem(n,col,cell)
                summary.setText('پیش‌نمایش '+args['action']+' | نسخه '+str(result['group_revision'])+' | '+result['previous_total']+' → '+result['current_total']+' '+result['unit'])
                confirm.setChecked(False)
            elif action=='history_apply':
                if not confirm.isChecked() or 'history_args' not in state:raise ValueError('پیش‌نمایش و تأیید صریح مستقل لازم است')
                args=dict(state['history_args'])
                if (args['action']!=history_action.currentData() or args['author']!=author.text() or
                        args['reviewer']!=reviewers.currentData() or args['reason']!=history_reason.text() or
                        state['history_lineage']!=lineages.currentData()):
                    raise ValueError('زمینه واگرد تغییر کرده؛ پیش‌نمایش تازه لازم است')
                step=args.pop('action')
                getattr(service,step+'_ifc_quantity_transfer')(pid,**args)
                state.clear();confirm.setChecked(False);refresh()
            elif action=='open':
                project=service.open_project(pid);link=next(x for x in project['ifc_2d_crosswalks'] if x['id']==links.currentData())
                if viewer.viewer.kind!='ifc' or viewer.viewer.ifc_document.source_sha256!=link['ifc_document']['source_sha256']:
                    viewer.open_drawing(link['ifc_document']['source_path']);viewer.ifc_revision.setText(link['ifc_document']['revision'])
                viewer.open_ifc_crosswalk(link['id'])
            outcome.setText('عملیات گروهی انجام شد؛ ثبت مالی فقط از دفتر اصلاحیه بازبینی‌شده مجاز است')
        except Exception as exc:outcome.setText('عملیات گروهی انجام نشد: '+str(exc))
    def cancel():
        state.clear();confirm.setChecked(False);outcome.setText('درخواست محلی رد شد؛ داده قطعی تغییر نکرد')
    lineages.currentIndexChanged.connect(lambda:refresh())
    preview.clicked.connect(lambda:run('preview'));apply.clicked.connect(lambda:run('apply'));migrate.clicked.connect(lambda:run('migrate'));open_link.clicked.connect(lambda:run('open'));reject.clicked.connect(cancel)
    history_preview.clicked.connect(lambda:run('history_preview'));history_apply.clicked.connect(lambda:run('history_apply'))
    history_action.currentIndexChanged.connect(cancel)
    for widget in (lineages,allocation,choose,table,summary,preview,confirm,apply,reject,history_action,history_reason,history_preview,history_apply,document,choose_link,migrate,links,open_link):layout.addWidget(widget)
    refresh()
