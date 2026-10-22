"""Native IFC controls delegate to canonical formula/column amendment journals."""
from decimal import Decimal
from hashlib import sha256
from pathlib import Path
from PySide6.QtWidgets import QComboBox, QLineEdit, QLabel, QPushButton, QFileDialog


def install_ifc_amendment_controls(dialog, layout, service, project_id, document,
                                   selected, author, reviewers, note, outcome):
    from core.takeoff import manual_formula_register as register
    from core.takeoff import manual_formula_amendments as journal
    from core.drawings.ifc_pipeline import quantity_formula_data, column_detail_data, ifc_amendment_source_identity
    from core.platform.concurrency import assert_unchanged

    rows=QComboBox(); rows.setObjectName('ifc_amend_row')
    reason=QLineEdit(); reason.setObjectName('ifc_amend_reason')
    reason.setPlaceholderText('علت اصلاح و مرجع مدرک نسخه جدید؛ اصل قطعی محفوظ می‌ماند')
    detail=QLineEdit();detail.setObjectName('ifc_amend_detail')
    detail.setPlaceholderText('فقط ستون: فایل JSON دیتایل کامل مستقل نسخه جدید')
    browse=QPushButton('انتخاب مدرک دیتایل اصلاحی ستون')
    browse.clicked.connect(lambda:detail.setText(QFileDialog.getOpenFileName(dialog,'دیتایل مستقل IFC')[0]))
    summary=QLabel('اصلاحیه: برداشت قطعی و عضو نسخه جدید را انتخاب و پیش‌نمایش کنید')
    summary.setWordWrap(True); summary.setObjectName('ifc_amend_summary')
    for widget in (rows,reason,detail,browse,summary):layout.addWidget(widget)
    state={}
    for key,row in register.load(service,project_id).items():
        if row['status']=='committed' and row['data'].get('ifc_evidence'):
            rows.addItem(key+' | '+row['data']['member']+' | '+str(row['quantity'])+' '+row['data']['unit'],('formula',key))
    for record in service.open_project(project_id).get('reviewed_structural_members',{}).values():
        data=record['data']
        if data.get('kind')=='column' and record['status']=='committed' and data.get('source',{}).get('ifc_identity'):
            rows.addItem('ستون | '+data['floor_id']+' | '+data['member_id'],('column',[data['floor_id'],data['member_id']]))

    def preview_column(data):
        from core.takeoff.reviewed_structural import preview_member
        report=preview_member(data,service.takeoff)
        if not report['ready']:raise ValueError('دیتایل ستون ناقص است: '+'؛ '.join(report['blockers']))
        return {r['unit']:Decimal(str(r['quantity'])) for r in report['rows']}

    def action(step):
        try:
            if not rows.currentData(): raise ValueError('برداشت قطعی IFC یافت نشد')
            kind,key=rows.currentData()
            if step=='preview':
                if 'element' not in selected: raise ValueError('عضو IFC نسخه جدید را انتخاب کنید')
                current=service.open_project(project_id)
                proposal=next((x for x in current.get('ifc_identity_proposals',[])
                    if x['global_id']==selected['element']['global_id']
                    and x['document']['source_sha256']==document['source_sha256']
                    and x['document']['revision']==document['revision']),None)
                if proposal is None: raise ValueError('هویت نسخه جدید باید مستقل تأیید شده باشد')
                if kind=='formula':
                    old=register.load(service,project_id)[key]
                    data=quantity_formula_data(service,project_id,proposal['id'],old['data']['ifc_evidence']['quantity_name'],author=author.text())
                    if proposal['id']==old['data']['ifc_evidence']['proposal_id']:
                        raise ValueError('برای اصلاحیه IFC منبع نسخه جدید و مدرک تغییر لازم است')
                    before={data['unit']:Decimal(str(old['quantity']))};after={data['unit']:Decimal(data['variables']['Q'])}
                    history=[a['id']+' | '+a['status'] for a in current.get('manual_formula_amendments',{}).values() if a.get('row_id')==key]
                elif kind=='column':
                    floor,member=key
                    old=service.get_structural_member(project_id,'column',floor,member)
                    path=Path(detail.text())
                    data=column_detail_data(service,project_id,proposal_id=proposal['id'],detail_path=str(path),detail_sha256=sha256(path.read_bytes()).hexdigest(),author=author.text(),reviewer=reviewers.currentData())
                    if not ifc_amendment_source_identity(current,old['data'],data):raise ValueError('نسخه جدید باید جانشین بازبینی‌شده همان ستون باشد')
                    before=preview_column(old['data']);after=preview_column(data)
                    history=[a['id']+' | '+a['status'] for a in current.get('beam_amendments',{}).values() if a.get('proposal',{}).get('member_id')==member]
                else:raise ValueError('نوع اصلاحیه IFC پشتیبانی نمی‌شود')
                state.clear();state.update(kind=kind,key=key,revision=old['revision'],data=data,
                    base_digest=service.store.current_digest(project_id))
                summary.setText('\n'.join(f'{unit}: مقدار قبلی {before.get(unit,0)}؛ پیشنهادی {after.get(unit,0)}؛ اختلاف {after.get(unit,0)-before.get(unit,0)}' for unit in sorted(set(before)|set(after)))+'\nمنبع: '+document['source_sha256']+' | '+document['revision']+'\nتاریخچه: '+('؛ '.join(history) or 'بدون اصلاحیه'))
                return
            if state.get('key')!=key or state.get('kind')!=kind: raise ValueError('ابتدا پیش‌نمایش همین برداشت را بررسی کنید')
            current=service.open_project(project_id)
            assert_unchanged({k:v for k,v in current.items() if k!='_meta'},state['base_digest'])
            if step=='create':
                if kind=='formula':a=journal.proposal(service,project_id,key,state['data'],expected_revision=state['revision'],created_by=author.text(),reason=reason.text())
                else:a=service.create_column_amendment(project_id,*key,state['data'],expected_revision=state['revision'],created_by=author.text(),reason=reason.text())
                state['amendment_id']=a['id'];outcome.setText('درخواست اصلاحیه ثبت شد؛ اصل متره و BOQ تغییر نکرد')
            else:
                aid=state.get('amendment_id')
                if not aid: raise ValueError('ابتدا درخواست اصلاحیه را ثبت کنید')
                if step=='review':
                    if kind=='formula':journal.review(service,project_id,aid,expected_revision=1,reviewer=reviewers.currentData(),note=note.text())
                    else:service.review_beam_amendment(project_id,aid,expected_revision=1,reviewer=reviewers.currentData(),note=note.text())
                    outcome.setText('اصلاحیه با بازبین مستقل و کنترل منبع بازبینی شد')
                elif step=='apply':
                    if kind=='formula':
                        journal.apply(service,project_id,aid,expected_revision=1)
                        effective=register.load(service,project_id)[key]
                        result=str(effective['quantity'])+' '+effective['data']['unit']
                    else:
                        service.apply_beam_amendment(project_id,aid,expected_revision=1)
                        result=str(preview_column(service.get_structural_member(project_id,'column',*key)['data']))
                    summary.setText(summary.text()+'\nمقدار مؤثر BOQ: '+result+'؛ اصل قطعی محفوظ است'+'\nتاریخچه: '+aid+' | اعمال‌شده')
                    outcome.setText('اصلاحیه از دفتر نسخه‌دار موجود اعمال شد؛ قیمت ایجاد نشد')
            state['base_digest']=service.store.current_digest(project_id)
        except Exception as exc:
            outcome.setText('اصلاحیه IFC انجام نشد: '+str(exc))
    for step,label in [('preview','پیش‌نمایش مقدار قبلی، جدید و اختلاف'),('create','ثبت درخواست اصلاحیه IFC'),('review','بازبینی مستقل اصلاحیه IFC'),('apply','اعمال اصلاحیه مجاز و نمایش BOQ مؤثر')]:
        button=QPushButton(label);button.setObjectName('ifc_amend_'+step)
        button.clicked.connect(lambda checked=False,step=step:action(step));layout.addWidget(button)
