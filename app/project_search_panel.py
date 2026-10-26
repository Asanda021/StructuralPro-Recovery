"""E4 searchable, project-bound Qt record navigator over original search."""
import json
from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QDialog,QVBoxLayout,QHBoxLayout,QLabel,QLineEdit,QPushButton,
    QListWidget,QListWidgetItem,QPlainTextEdit
)
from core.search.global_search import search_project


class ProjectSearchDialog(QDialog):
    def __init__(self, service, project_id, *, parent=None, initial_query="", on_navigate=None):
        super().__init__(parent)
        self.service=service
        self.pid=str(project_id).strip()
        self.on_navigate=on_navigate
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
        self.status=QLabel("جست‌وجو هیچ تغییری در داده مهندسی/مالی ایجاد نمی‌کند.")
        self.status.setWordWrap(True);layout.addWidget(self.status)
        self.search_button.clicked.connect(self.run_search)
        self.query.returnPressed.connect(self.run_search)
        self.query.textChanged.connect(self.invalidate)
        self.list.currentItemChanged.connect(self.selected)
        self.open_button.clicked.connect(self.open_record)
        if initial_query.strip():self.run_search()

    def invalidate(self,*_):
        self.digest=None
        self.results=[]
        self.list.clear();self.detail.clear()
        self.open_button.setEnabled(False)

    def run_search(self):
        self.invalidate()
        try:
            # ProjectStore enforces role and project scope before any indexing.
            p=self.service.open_project(self.pid)
            if not p:raise ValueError("پروژه معتبر و قابل دسترس نیست.")
            digest=self.service.store.current_digest(self.pid)
            entries=search_project(p,self.query.text(),limit=100)
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

    def selected(self,current,*_):
        self.open_button.setEnabled(current is not None and self.digest is not None)
        self.detail.clear()

    def open_record(self):
        item=self.list.currentItem()
        if item is None or self.digest is None:return None
        try:
            if self.service.store.current_digest(self.pid)!=self.digest:
                raise RuntimeError("نسخه پروژه تغییر کرده؛ دوباره جست‌وجو کنید.")
            project=self.service.open_project(self.pid)
            if not project:raise ValueError("پروژه دیگر در دسترس نیست.")
            selected=self.results[item.data(Qt.ItemDataRole.UserRole)]
            # Re-run original search against the verified current project, not
            # stale serialized Qt item data.
            candidates=search_project(project,self.query.text(),limit=100)
            matching=[x for x in candidates if
                      x["kind"]==selected["kind"] and
                      x["entity_id"]==selected["entity_id"] and
                      x["text"]==selected["text"] and x["data"]==selected["data"]]
            if len(matching)!=1:
                raise RuntimeError("هویت یا محتوای رکورد مبهم است؛ انتخاب مسدود شد.")
            record=matching[0]
            self.detail.setPlainText(json.dumps({
                "project_id":record["project_id"],
                "entity_id":record["entity_id"],
                "source_id":record["source_id"],
                "revision":record["revision"],
                "route":record["route"],
                "record":record["data"],
            },ensure_ascii=False,indent=2,default=str))
            if self.on_navigate and record["route"] and record["entity_id"]:
                self.on_navigate(record["route"],record["project_id"],record["entity_id"])
            self.status.setText("رکورد تأییدشده از SQLite بازخوانی شد؛ هیچ مقدار یا تأییدی ثبت نشد.")
            return record
        except Exception as exc:
            self.invalidate()
            self.status.setText("ناوبری/نمایش مسدود شد: "+str(exc))
            return None
