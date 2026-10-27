"""E5 movable/closable RTL inspector using QMainWindow's real dock system.

Presentation state is saved only in QSettings, never in SQLite or BOQ.
"""
from PySide6.QtCore import Qt,QByteArray,QTimer
from PySide6.QtWidgets import (
    QDockWidget,QWidget,QVBoxLayout,QHBoxLayout,QLabel,QPushButton,QTreeWidget,QTreeWidgetItem,QTableWidget,QTableWidgetItem,QScrollArea
)


class WorkspaceDockController:
    def __init__(self, window, settings, service, project_provider):
        self.window=window
        self.settings=settings
        self.service=service
        self.project_provider=project_provider
        self.views={}
        self.view_docks={}
        self._view_timer=QTimer(window)
        self._view_timer.setInterval(250)
        self._view_timer.timeout.connect(self.validate_views)
        self._view_timer.start()
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
        self.boq_dock=QDockWidget("ردیف‌های واقعی BOQ",window)
        self.boq_dock.setObjectName("P6E5BoqReadOnlyDock")
        self.boq_dock.setLayoutDirection(Qt.LayoutDirection.RightToLeft)
        self.boq_dock.setFeatures(
            QDockWidget.DockWidgetFeature.DockWidgetClosable |
            QDockWidget.DockWidgetFeature.DockWidgetMovable |
            QDockWidget.DockWidgetFeature.DockWidgetFloatable)
        body=QWidget();v=QVBoxLayout(body)
        v.addWidget(QLabel("فقط خواندن از سند پروژه؛ هیچ برآورد یا قیمتی محاسبه نمی‌شود."))
        self.boq_table=QTableWidget(0,4)
        self.boq_table.setObjectName("E5StoredBOQ")
        self.boq_table.setHorizontalHeaderLabels(["ردیف","شرح","مقدار","واحد"])
        self.boq_table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        v.addWidget(self.boq_table)
        self.boq_dock.setWidget(body)
        self.window.addDockWidget(Qt.DockWidgetArea.LeftDockWidgetArea,self.boq_dock)
        self.boq_dock.hide()
        self.boq_toggle=QPushButton("نمایش / پنهان‌کردن جدول BOQ")
        self.boq_toggle.setObjectName("E5BoqToggle")
        self.boq_toggle.clicked.connect(self.toggle_boq)

    def attach_view(self, kind, view, project_id):
        """Embed the existing viewer instance; docking never reloads its scene."""
        if kind not in ('2d','3d'):
            raise ValueError('نوع نمای فضای کار معتبر نیست.')
        pid=str(project_id).strip()
        if pid!=self.project_id() or not isinstance(self.service.open_project(pid),dict):
            raise ValueError('نمای پروژه دیگر وارد فضای کار نمی‌شود.')
        digest=self.service.store.current_digest(pid)
        if kind=='2d':self._release_view('3d')
        self._release_view(kind)
        dock=self.view_docks.get(kind)
        if dock is None:
            dock=QDockWidget('نقشه دوبعدی' if kind=='2d' else 'مدل سه‌بعدی',self.window)
            dock.setObjectName('P6E5ExistingViewer'+kind)
            dock.setLayoutDirection(Qt.LayoutDirection.RightToLeft)
            if not self.window.restoreDockWidget(dock):
                self.window.addDockWidget(Qt.DockWidgetArea.BottomDockWidgetArea,dock)
            self.window.menuBar().addAction(dock.toggleViewAction())
            self.view_docks[kind]=dock
        view.setWindowFlags(Qt.WindowType.Widget)
        scroll=QScrollArea(dock)
        scroll.setWidgetResizable(True)
        scroll.setWidget(view)
        dock.setWidget(scroll)
        self.views[kind]=(view,pid,digest)
        # The 2D viewer hands its existing validated 3D dialog back here.
        view._workspace_controller=self
        dock.show();view.show();dock.raise_()
        self._clamp_floating()
        return dock

    def _release_view(self, kind):
        entry=self.views.pop(kind,None)
        if entry is None:return
        dock=self.view_docks[kind]
        dock.hide()
        view=entry[0]
        # closeEvent owns cancellation and connection cleanup in the real viewer.
        body=dock.widget()
        dock.setWidget(None)
        view.close()
        view.deleteLater()
        if body is not None:body.deleteLater()

    def validate_views(self):
        for kind,(_,pid,digest) in list(self.views.items()):
            try:
                valid=(pid==self.project_id() and
                       isinstance(self.service.open_project(pid),dict) and
                       self.service.store.current_digest(pid)==digest)
            except Exception:
                valid=False
            if not valid:
                self._release_view(kind)
                self.status.setText('پروژه یا نسخه تغییر کرد؛ نمای قبلی بسته شد. سند را دوباره باز کنید.')

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

    def toggle_boq(self):
        if self.boq_dock.isVisible():
            self.boq_dock.hide()
        else:
            self.refresh()
            self.boq_dock.show()
            self.boq_dock.raise_()

    def refresh(self):
        self.validate_views()
        self.tree.clear()
        self.boq_table.setRowCount(0)
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
            rows=p.get("boq",[])
            if not isinstance(rows,list):raise ValueError("داده BOQ نامعتبر است")
            self.boq_table.setRowCount(len(rows))
            for i,row in enumerate(rows):
                if not isinstance(row,dict):raise ValueError("ردیف BOQ معتبر نیست")
                values=[row.get("row_id",row.get("id",i+1)),
                        row.get("description",""),row.get("quantity","نامشخص"),
                        row.get("unit","")]
                for j,value in enumerate(values):
                    self.boq_table.setItem(i,j,QTableWidgetItem(str(value)))
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
            self.tree.clear()
            self.boq_table.setRowCount(0)
            self.status.setText("نمایش بازرس ممکن نیست: "+str(exc))

    def show_selected(self):
        items=self.tree.selectedItems()
        if not items:return
        kind,item=items[0].data(0,Qt.ItemDataRole.UserRole)
        self.status.setText(("عضو" if kind=="member" else "طبقه")+" واقعی: "+
                            str(item.get("id",""))+" | "+str(item.get("kind",item.get("name",""))))

    def focus_member(self, member_id):
        """Select a stored member from the real project tree, never guessed geometry."""
        pid=self.project_id()
        project=self.service.open_project(pid)
        if not isinstance(project,dict):return False
        matches=[m for m in project.get("members",[])
                 if str(m.get("id",""))==str(member_id)]
        if len(matches)!=1:return False
        self.refresh()
        for index in range(self.tree.topLevelItemCount()):
            floor=self.tree.topLevelItem(index)
            for sub in range(floor.childCount()):
                child=floor.child(sub)
                if child.text(0)==str(member_id):
                    floor.setExpanded(True)
                    self.dock.show()
                    child.setSelected(True)
                    self.tree.setCurrentItem(child)
                    self.tree.scrollToItem(child)
                    return True
        return False

    def _clamp_floating(self):
        for dock in (self.dock,self.boq_dock,*self.view_docks.values()):
            if not dock.isFloating():continue
            screen=dock.screen() or self.window.screen()
            if screen is None:continue
            rect=screen.availableGeometry()
            width=min(dock.width(),rect.width())
            height=min(dock.height(),rect.height())
            dock.resize(max(100,width),max(100,height))
            dock.move(max(rect.left(),min(dock.x(),rect.right()-width+1)),
                      max(rect.top(),min(dock.y(),rect.bottom()-height+1)))

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
        self.refresh()
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
        self.boq_dock.hide()
        for dock in self.view_docks.values():dock.hide()
        return False

    def reset(self):
        for dock in self.view_docks.values():
            dock.setFloating(False)
            self.window.addDockWidget(Qt.DockWidgetArea.BottomDockWidgetArea,dock)
            dock.hide()
        self.dock.setFloating(False)
        self.boq_dock.setFloating(False)
        self.window.addDockWidget(Qt.DockWidgetArea.RightDockWidgetArea,self.dock)
        self.window.addDockWidget(Qt.DockWidgetArea.LeftDockWidgetArea,self.boq_dock)
        self.dock.hide()
        self.boq_dock.hide()
        try:
            key=self._key()
            self.settings.remove(key)
            self.settings.sync()
        except Exception:
            pass
        self.status.setText("چینش پیش‌فرض بازگردانده شد؛ هیچ رکورد پروژه تغییر نکرد.")
