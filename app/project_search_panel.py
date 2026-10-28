"""E4 searchable, project-bound Qt record navigator over original search."""
import json
from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QDialog,QVBoxLayout,QHBoxLayout,QLabel,QLineEdit,QPushButton,
    QListWidget,QListWidgetItem,QPlainTextEdit
)
from core.search.global_search import search_project


def display_verified_boq_row(project, row_id, table):
    """Read-only presentation of an exact stored BOQ row; no pricing recalc."""
    from PySide6.QtWidgets import QTableWidgetItem
    from core.projects.project_model import _identity
    if not isinstance(project,dict):raise ValueError("پروژه معتبر لازم است")
    rows=project.get("boq",[])
    if not isinstance(rows,list):raise ValueError("BOQ معتبر نیست")
    def rid(r):
        return next((r.get(k) for k in ("row_id","id","item_id")
                     if r.get(k) not in (None,"")),None)
    selected=[i for i,r in enumerate(rows)
              if isinstance(r,dict) and _identity(rid(r))==_identity(row_id)]
    if not _identity(row_id) or len(selected)!=1:
        raise ValueError("هویت ردیف BOQ مبهم یا مفقود است؛ ناوبری مسدود شد")
    # Render the existing project rows before selection: never call estimate
    # recalculation as a side effect of search.
    prepared=[]
    for i,row in enumerate(rows):
        if not isinstance(row,dict):raise ValueError("ردیف BOQ معتبر نیست")
        prepared.append([
            row.get("item_no",i+1),row.get("description",""),
            row.get("quantity","نامشخص"),row.get("unit",""),
            row.get("price_code",""),row.get("total","بدون مبلغ مصوب")])
    table.setRowCount(len(prepared))
    for i,values in enumerate(prepared):
        for j,value in enumerate(values):
            table.setItem(i,j,QTableWidgetItem(str(value)))
    from PySide6.QtCore import QItemSelectionModel
    table.setCurrentCell(selected[0],0,
        QItemSelectionModel.SelectionFlag.ClearAndSelect | QItemSelectionModel.SelectionFlag.Rows)
    table.scrollToItem(table.item(selected[0],0))
    return selected[0]


class ProjectSearchDialog(QDialog):
    def __init__(self, service, project_id, *, parent=None, initial_query="", on_navigate=None, on_open_model=None):
        super().__init__(parent)
        self.service=service
        self.pid=str(project_id).strip()
        self.on_navigate=on_navigate
        self.on_open_model=on_open_model
        self.results=[]
        self.digest=None
        self.setObjectName("E4GlobalProjectSearch")
        self.setWindowTitle("جست‌وجوی سراسری در پروژه فعال")
        self.setLayoutDirection(Qt.LayoutDirection.RightToLeft)
        self.resize(850,650)
        layout=QVBoxLayout(self)
        self.scope=QLabel("جست‌وجو فقط در پروژه مجاز: "+self.pid)
        layout.addWidget(self.scope)
        row=QHBoxLayout();layout.addLayout(row)
        self.query=QLineEdit(initial_query);self.query.setObjectName("E4Query")
        self.search_button=QPushButton("جست‌وجوی رکوردها")
        self.search_button.setObjectName("E4Search")
        row.addWidget(self.query,1);row.addWidget(self.search_button)
        self.list=QListWidget();self.list.setObjectName("E4Results");layout.addWidget(self.list,2)
        self.detail=QPlainTextEdit();self.detail.setReadOnly(True)
        self.detail.setObjectName("E4OriginalRecord");layout.addWidget(self.detail,1)
        row=QHBoxLayout();layout.addLayout(row)
        self.open_button=QPushButton("نمایش رکورد واقعی و مسیر آن")
        self.open_button.setObjectName("E4OpenRecord")
        self.open_button.setEnabled(False)
        row.addWidget(self.open_button)
        self.model_button=QPushButton("نمای 2D/3D عضو IFC با مدرک تأییدشده")
        self.model_button.setObjectName("E4VerifiedIfcNavigation")
        self.model_button.setEnabled(False)
        row.addWidget(self.model_button)
        self.status=QLabel("جست‌وجو هیچ تغییری در داده مهندسی/مالی ایجاد نمی‌کند.")
        self.status.setWordWrap(True);layout.addWidget(self.status)
        self.search_button.clicked.connect(self.run_search)
        self.query.returnPressed.connect(self.run_search)
        self.query.textChanged.connect(self.invalidate)
        self.list.currentItemChanged.connect(self.selected)
        self.open_button.clicked.connect(self.open_record)
        self.model_button.clicked.connect(self.open_model)
        if initial_query.strip():self.run_search()

    def invalidate(self,*_):
        self.digest=None
        self.results=[]
        self.list.clear();self.detail.clear()
        self.open_button.setEnabled(False)
        self.model_button.setEnabled(False)

    def run_search(self):
        self.invalidate()
        try:
            # ProjectStore enforces role and project scope before any indexing.
            # Pin the version *before* reading the project: do not combine
            # an old authorized snapshot with a digest from a newer write.
            digest=self.service.store.current_digest(self.pid)
            p=self.service.open_project(self.pid)
            if not p:raise ValueError("پروژه معتبر و قابل دسترس نیست.")
            entries=search_project(p,self.query.text(),limit=100)
            if self.service.store.current_digest(self.pid)!=digest:
                raise RuntimeError("نسخه پروژه هنگام جست‌وجو تغییر کرد.")
            self.digest=digest
            self.results=entries
            for i,row in enumerate(entries):
                label=f"{row['kind']} | {row['text']} | شناسه: {row['entity_id'] or 'فاقد'}"
                item=QListWidgetItem(label)
                item.setData(Qt.ItemDataRole.UserRole,i)
                self.list.addItem(item)
            self.status.setText(
                f"{len(entries)} نتیجه (حداکثر ۱۰۰). رکوردهای فاقد هویت صریح فقط‌خواندنی‌اند."
            )
            return entries
        except Exception as exc:
            self.status.setText("جست‌وجو مجاز نشد: "+str(exc))
            return []

    def _result_index(self, item):
        index=item.data(Qt.ItemDataRole.UserRole)
        if (type(index) is not int or not 0<=index<len(self.results) or
                self.list.row(item)!=index):
            raise ValueError("هویت انتخاب نتیجه معتبر نیست؛ دوباره جست‌وجو کنید.")
        return index

    def selected(self,current,*_):
        if current is not None:
            try:index=self._result_index(current)
            except ValueError as exc:
                self.invalidate()
                self.status.setText("ناوبری/نمایش مسدود شد: "+str(exc))
                return
        self.open_button.setEnabled(current is not None and self.digest is not None)
        self.model_button.setEnabled(
            current is not None and self.digest is not None and
            self.on_open_model is not None and
            self.results[index]["kind"]=="member")
        self.detail.clear()

    def open_model(self):
        if not self.model_button.isEnabled():return None
        digest=self.digest
        # Validate/display the selected record without also opening the generic
        # project destination. The IFC callback owns the single specialist route.
        record=self.open_record(navigate=False)
        if record is None or record["kind"]!="member" or not record["entity_id"]:
            return None
        try:
            # A specialist destination must not receive an identity from a
            # search snapshot invalidated after open_record() returned.
            if self.digest!=digest or self.service.store.current_digest(self.pid)!=digest:
                raise RuntimeError("نسخه پروژه پیش از نمایش IFC تغییر کرد.")
            result=self.on_open_model(record["project_id"],record["entity_id"])
            # Existing main.py opens modal destinations and returns None on
            # success; only literal False is an explicit failed handoff.
            if result is False:
                raise RuntimeError("مقصد IFC ناوبری را صریحاً رد کرد.")
            if self.digest!=digest or self.service.store.current_digest(self.pid)!=digest:
                raise RuntimeError("نسخه پروژه پس از اجرای مقصد IFC تغییر کرد.")
            self.status.setText("نمای IFC فقط از گیت واقعی هویت و Revision اجرا شد.")
            return result
        except Exception as exc:
            self.invalidate()
            self.status.setText("نمای مستند باز نشد: "+str(exc))
            return None

    def open_record(self, *, navigate=True):
        item=self.list.currentItem()
        if item is None or self.digest is None:return None
        digest=self.digest
        try:
            if self.service.store.current_digest(self.pid)!=digest:
                raise RuntimeError("نسخه پروژه تغییر کرده؛ دوباره جست‌وجو کنید.")
            project=self.service.open_project(self.pid)
            if not project:raise ValueError("پروژه دیگر در دسترس نیست.")
            selected=self.results[self._result_index(item)]
            # Re-run original search against the verified current project, not
            # stale serialized Qt item data.
            candidates=search_project(project,self.query.text(),limit=100)
            matching=[x for x in candidates if
                      x["kind"]==selected["kind"] and
                      x["entity_id"]==selected["entity_id"] and
                      x["text"]==selected["text"] and x["data"]==selected["data"]]
            if len(matching)!=1:
                raise RuntimeError("هویت یا محتوای رکورد مبهم است؛ انتخاب مسدود شد.")
            # Re-search may be slow, and stored records may stay byte-identical
            # while an unrelated project write revokes this navigation.
            if self.digest!=digest or self.service.store.current_digest(self.pid)!=digest:
                raise RuntimeError("نسخه پروژه هنگام بازخوانی رکورد تغییر کرد.")
            record=matching[0]
            if record['link_status']=='ambiguous_record':
                raise RuntimeError("شناسه رکورد در پروژه مبهم است؛ ناوبری مسدود شد.")
            self.detail.setPlainText(json.dumps({
                "project_id":record["project_id"],
                "entity_id":record["entity_id"],
                "source_id":record["source_id"],
                "revision":record["revision"],
                "route":record["route"],
                "record":record["data"],
            },ensure_ascii=False,indent=2,default=str))
            supported=record['route'] in {'projects','boq','drawing','drawing_session','project_controls','manual_formula'}
            if navigate and self.on_navigate and supported and record["entity_id"]:
                outcome=self.on_navigate(record["route"],record["project_id"],record["entity_id"])
                if outcome is False:
                    raise RuntimeError("مقصد رکورد ناوبری را صریحاً رد کرد.")
                # The callback may run a modal dialog or reenter the event loop.
                # Never label an obsolete snapshot as an approved destination.
                if self.digest!=digest or self.service.store.current_digest(self.pid)!=digest:
                    raise RuntimeError("نسخه پروژه پس از اجرای مقصد تغییر کرد.")
            self.status.setText("رکورد تأییدشده از SQLite بازخوانی شد؛ هیچ مقدار یا تأییدی ثبت نشد." if supported else
                "رکورد SQLite فقط‌خواندنی است؛ مسیر تخصصی معتبر برای این نوع نتیجه پشتیبانی نشده است.")
            return record
        except Exception as exc:
            self.invalidate()
            self.status.setText("ناوبری/نمایش مسدود شد: "+str(exc))
            return None
