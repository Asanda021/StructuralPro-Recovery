"""E5 movable/closable RTL inspector using QMainWindow's real dock system.

Presentation state is saved only in QSettings, never in SQLite or BOQ.
"""
from PySide6.QtCore import Qt,QByteArray
from PySide6.QtWidgets import (
    QDockWidget,QWidget,QVBoxLayout,QHBoxLayout,QLabel,QPushButton,QTreeWidget,QTreeWidgetItem
)


class WorkspaceDockController:
    def __init__(self, window, settings, service, project_provider):
        self.window=window
        self.settings=settings
        self.service=service
        self.project_provider=project_provider
        self.dock=QDockWidget("بازرس واقعی پروژه",window)
        self.dock.setObjectName("P6E5VerifiedProjectInspector")
        self.dock.setLayoutDirection(Qt.LayoutDirection.RightToLeft)
        self.dock.setAllowedAreas(Qt.DockWidgetArea.AllDockWidgetAreas)
        self.dock.setFeatures(
            QDockWidget.DockWidgetFeature.DockWidgetClosable |
            QDockWidget.DockWidgetFeature.DockWidgetMovable |
            QDockWidget.DockWidgetFeature.DockWidgetFloatable)
        content=QWidget();layout=QVBoxLayout(content)
        layout.addWidget(QLabel("رکوردهای واقعی پروژه؛ فقط‌خواندنی، بدون تغییر BOQ"))
        self.status=QLabel("پروژه انتخاب نشده است.");self.status.setWordWrap(True)
        layout.addWidget(self.status)
        self.tree=QTreeWidget();self.tree.setObjectName("E5ProjectTree")
        self.tree.setHeaderLabels(["طبقه / عضو","نوع / شناسه"])
        layout.addWidget(self.tree,1)
        row=QHBoxLayout();layout.addLayout(row)
        self.refresh_button=QPushButton("بازخوانی پروژه")
        self.save_button=QPushButton("ذخیره چینش")
        self.reset_button=QPushButton("بازنشانی چینش")
        self.toggle_button=QPushButton("نمایش / پنهان‌کردن بازرس")
        self.toggle_button.setObjectName("E5InspectorToggle")
        row.addWidget(self.refresh_button);row.addWidget(self.save_button)
        row.addWidget(self.reset_button)
        self.dock.setWidget(content)
        self.window.addDockWidget(Qt.DockWidgetArea.RightDockWidgetArea,self.dock)
        self.dock.hide()
        self.toggle_button.clicked.connect(self.toggle)
        self.refresh_button.clicked.connect(self.refresh)
        self.save_button.clicked.connect(self.save)
        self.reset_button.clicked.connect(self.reset)
        self.tree.itemSelectionChanged.connect(self.show_selected)

    def project_id(self):
        return str(self.project_provider() or "").strip()

    def _key(self):
        pid=self.project_id()
        if not pid:raise ValueError("برای ذخیره چینش، ابتدا پروژه واقعی انتخاب کنید.")
        p=self.service.open_project(pid)
        if not isinstance(p,dict):raise ValueError("پروژه واقعی وجود ندارد.")
        return "e5/project/"+pid+"/window-state"

    def toggle(self):
        if self.dock.isVisible():
            self.dock.hide()
        else:
            self.refresh()
            self.dock.show()
            self.dock.raise_()

    def refresh(self):
        self.tree.clear()
        try:
            pid=self.project_id()
            p=self.service.open_project(pid)
            if not isinstance(p,dict):raise ValueError("پروژه ذخیره‌شده معتبر نیست.")
            floor_nodes={}
            for floor in p.get("floors",[]):
                node=QTreeWidgetItem([str(floor["name"]),str(floor["id"])])
                node.setData(0,Qt.ItemDataRole.UserRole,("floor",floor))
                self.tree.addTopLevelItem(node)
                floor_nodes[str(floor["id"])]=node
            for m in p.get("members",[]):
                floor_id=str(m.get("floor_id",""))
                if floor_id not in floor_nodes:continue
                node=QTreeWidgetItem([str(m.get("id","")),str(m.get("kind",""))])
                node.setData(0,Qt.ItemDataRole.UserRole,("member",m))
                floor_nodes[floor_id].addChild(node)
            self.status.setText("پروژه: "+str(p.get("name",""))+" | نسخه: "+
                                str(p.get("_meta",{}).get("version","فاقد"))+
                                " | بدون تغییر اطلاعات مهندسی")
        except Exception as exc:
            self.status.setText("نمایش بازرس ممکن نیست: "+str(exc))

    def show_selected(self):
        items=self.tree.selectedItems()
        if not items:return
        kind,item=items[0].data(0,Qt.ItemDataRole.UserRole)
        self.status.setText(("عضو" if kind=="member" else "طبقه")+" واقعی: "+
                            str(item.get("id",""))+" | "+str(item.get("kind",item.get("name",""))))

    def _clamp_floating(self):
        if not self.dock.isFloating():return
        screen=self.window.screen()
        if screen is None:return
        rect=screen.availableGeometry()
        width=min(self.dock.width(),rect.width())
        height=min(self.dock.height(),rect.height())
        self.dock.resize(max(100,width),max(100,height))
        self.dock.move(max(rect.left(),min(self.dock.x(),rect.right()-width+1)),
                       max(rect.top(),min(self.dock.y(),rect.bottom()-height+1)))

    def save(self):
        try:
            key=self._key()
            self.settings.setValue(key,self.window.saveState(1))
            self.settings.sync()
            self.status.setText("چینش این پروژه فقط در تنظیمات محلی ذخیره شد.")
            return True
        except Exception as exc:
            self.status.setText("ذخیره چینش مجاز نشد: "+str(exc))
            return False

    def restore(self):
        try:
            key=self._key()
            value=self.settings.value(key)
            if isinstance(value,QByteArray) and not value.isEmpty():
                if not self.window.restoreState(value,1):raise ValueError("چینش ذخیره‌شده ناسازگار است.")
                self._clamp_floating()
                self.refresh()
                return True
        except Exception as exc:
            self.status.setText("چینش معتبر بازیابی نشد: "+str(exc))
        self.dock.hide()
        return False

    def reset(self):
        self.dock.setFloating(False)
        self.window.addDockWidget(Qt.DockWidgetArea.RightDockWidgetArea,self.dock)
        self.dock.hide()
        try:
            key=self._key()
            self.settings.remove(key)
            self.settings.sync()
        except Exception:
            pass
        self.status.setText("چینش پیش‌فرض بازگردانده شد؛ هیچ رکورد پروژه تغییر نکرد.")
