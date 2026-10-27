"""Fail-closed search-to-IFC navigation using the EXISTING reviewed four-way bridge.

No IFC inference: identities must be present in an approved, live source and
a verified project's crosswalk, with independent reviewer evidence.
"""
from __future__ import annotations
from hashlib import sha256
from pathlib import Path


def prepare_verified_controls_view(service, project_id, record_id, parent=None):
    """Focus an exact activity/WBS in the existing guarded controls workspace."""
    from PySide6.QtCore import Qt
    from PySide6.QtWidgets import QTreeWidgetItemIterator
    digest=service.store.current_digest(project_id)
    project=service.open_project(project_id)
    if not isinstance(project,dict) or project.get('id')!=project_id:
        raise ValueError('پروژه معتبر در دسترس نیست.')
    candidates=[(kind,r) for kind in ('project_schedule_tasks','project_wbs')
                for r in project.get(kind,[]) if isinstance(r,dict) and r.get('id')==record_id]
    if not record_id or len(candidates)!=1:
        raise ValueError('شناسه فعالیت یا WBS مفقود یا مبهم است.')
    from app.project_controls_workspace import ProjectControlsWorkspace
    view=ProjectControlsWorkspace(service,project_id,parent)
    try:
        if candidates[0][0]=='project_schedule_tasks':
            view.select_activity(record_id)
            if view.selected_id!=record_id:raise ValueError('فعالیت انتخاب نشد.')
        else:
            iterator=QTreeWidgetItemIterator(view.tree);matches=[]
            while iterator.value():
                item=iterator.value()
                if item.data(0,Qt.ItemDataRole.UserRole)==('wbs',record_id):matches.append(item)
                iterator+=1
            if len(matches)!=1:raise ValueError('گره WBS یکتا نیست.')
            view.tree.setCurrentItem(matches[0]);view.tree.scrollToItem(matches[0])
            view.tree_selected(matches[0])
        view.tabs.setCurrentIndex(0)
        if service.store.current_digest(project_id)!=digest:
            raise RuntimeError('نسخه پروژه هنگام ناوبری تغییر کرد.')
        return view
    except Exception:
        view.close()
        raise


def prepare_verified_drawing_view(service, project_id, document_id, parent=None):
    """Open the exact project record, requiring its explicit hash and revision."""
    from core.projects.project_model import _identity
    if not _identity(document_id) or not _identity(project_id):
        raise ValueError('شناسه سند و پروژه معتبر لازم است.')
    digest=service.store.current_digest(project_id)
    project=service.open_project(project_id)
    if not isinstance(project,dict) or project.get('id')!=project_id:
        raise ValueError('پروژه معتبر در دسترس نیست.')
    records=[]
    for key in ('drawings','documents'):
        container=project.get(key,[])
        if isinstance(container,dict):container=list(container.values())
        if not isinstance(container,list):raise ValueError('فهرست اسناد معتبر نیست.')
        records.extend(r for r in container if isinstance(r,dict) and
                       str(r.get('id',''))==str(document_id))
    if len(records)!=1:raise ValueError('سند فاقد هویت یکتا در پروژه است.')
    record=records[0]
    path=record.get('path') or record.get('source_path')
    expected=record.get('source_sha256') or record.get('sha256')
    revision=record.get('revision')
    if (not isinstance(path,str) or not path.strip() or
            not isinstance(expected,str) or len(expected)!=64 or
            not isinstance(revision,str) or not revision.strip()):
        raise ValueError('مسیر، هش کامل و Revision صریح سند لازم است.')
    source=Path(path)
    if any(part.is_symlink() for part in (source,*source.parents)):
        raise ValueError('مسیر پیوندی سند مجاز نیست.')
    if source.suffix.lower() not in ('.pdf','.dxf','.dwg','.ifc') or not source.is_file():
        raise ValueError('سند نقشه معتبر در دسترس نیست.')
    if sha256(source.read_bytes()).hexdigest()!=expected:
        raise ValueError('هش سند تغییر کرده؛ ناوبری مسدود شد.')
    from app.graphical_takeoff import GraphicalTakeoffDialog
    workspace=GraphicalTakeoffDialog(parent,app_service=service,project_id=project_id)
    try:
        workspace.open_drawing(str(source))
        workspace.ifc_revision.setText(revision)
        if (sha256(source.read_bytes()).hexdigest()!=expected or
                service.store.current_digest(project_id)!=digest):
            raise RuntimeError('سند یا نسخه پروژه هنگام بازکردن تغییر کرد.')
        return workspace
    except Exception:
        workspace.close()
        raise


def reviewed_member_source(service, project_id, member_id):
    from core.projects.project_model import _identity
    if not all(isinstance(x,str) and _identity(x) for x in (project_id,member_id)):
        raise ValueError("شناسه پروژه و عضو معتبر لازم است")
    digest=service.store.current_digest(project_id)
    project=service.open_project(project_id)
    if not isinstance(project,dict) or project.get("id")!=project_id:
        raise ValueError("پروژه معتبر در دسترس نیست")
    if len([m for m in project.get("members",[]) if m.get("id")==member_id])!=1:
        raise ValueError("شناسه عضو موجود یا یکتا نیست")
    reviews=project.get("ifc_identity_reviews",[])
    if not isinstance(reviews,list):raise ValueError("بازبینی IFC معتبر نیست")
    candidates={}
    for review in reviews:
        if not isinstance(review,dict) or review.get("member_id")!=member_id or review.get("status")!="approved":
            continue
        doc=review.get("document")
        if not isinstance(doc,dict):raise ValueError("مدرک IFC ناقص است")
        signature=(doc.get("source_path"),doc.get("source_sha256"),doc.get("revision"))
        if any(not isinstance(s,str) or not s.strip() for s in signature):
            raise ValueError("هویت سند و Revision ناقص است")
        candidates[signature]=True
    if len(candidates)!=1:
        raise ValueError("عضو فاقد منبع IFC تأییدشده یکتا است")
    path,expected_sha,revision=next(iter(candidates))
    source=Path(path)
    if not source.is_file():raise ValueError("سند IFC تأییدشده در دسترس نیست")
    if (len(expected_sha)!=64 or
            sha256(source.read_bytes()).hexdigest()!=expected_sha):
        raise ValueError("هش IFC با مدرک تأییدشده همخوان نیست")
    if service.store.current_digest(project_id)!=digest:
        raise RuntimeError("پروژه هنگام اعتبارسنجی سند تغییر کرد")
    return dict(path=str(source),sha=expected_sha,revision=revision,project_id=project_id,
                member_id=member_id,digest=digest)


def prepare_verified_member_view(service, project_id, member_id, parent=None):
    """Return a *real* Qt drawing viewer or raise before exposing a guessed match."""
    entry=reviewed_member_source(service,project_id,member_id)
    from app.graphical_takeoff import GraphicalTakeoffDialog
    workspace=GraphicalTakeoffDialog(parent,app_service=service,project_id=project_id)
    try:
        workspace.open_drawing(entry["path"])
        workspace.ifc_revision.setText(entry["revision"])
        if workspace.viewer.kind!="ifc" or workspace.viewer.ifc_document is None:
            raise ValueError("منبع تصویری IFC معتبر باز نشد")
        if workspace.viewer.ifc_document.source_sha256!=entry["sha"]:
            raise RuntimeError("مدل IFC در زمان بارگذاری تغییر کرد")
        panel=workspace.open_verified_crossview()
        if panel is None:raise ValueError("کنترل مستقل چهارطرفه معتبر نشد: "+workspace.status.text())
        bridge=workspace._verified_project_selection
        resolved=bridge.resolve(origin="tree",identifier=member_id,
                                source_sha256=entry["sha"],revision=entry["revision"])
        if resolved.status!="linked" or len(resolved.global_ids)!=1:
            raise ValueError("عضو فاقد لینک هندسی تأییدشده یکتا است")
        if service.store.current_digest(project_id)!=entry["digest"]:
            raise RuntimeError("نسخه پروژه هنگام بازکردن مدل تغییر کرد")
        workspace._check_live_four_way_context(bridge)
        workspace._select_from_verified_project(resolved.global_ids[0])
        if workspace._ifc_selected_global_id!=resolved.global_ids[0]:
            raise RuntimeError("نمای دوبعدی نتوانست عضو مستند را انتخاب کند")
        workspace.show()
        return workspace
    except Exception:
        workspace.close()
        raise
