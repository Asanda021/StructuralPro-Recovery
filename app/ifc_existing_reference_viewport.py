"""Persian Windows-compatible read-only original IFC2X3 existing-building reference."""
from __future__ import annotations
from PySide6.QtCore import Qt
from PySide6.QtWidgets import QDialog,QLabel,QVBoxLayout
from app.ifc_site_viewport import SiteLoadJob,SiteTerrainCanvas
from core.drawings.existing_building_reference import verified_existing_reference


class ExistingReferenceLoadJob(SiteLoadJob):
    def run(self):
        try:
            scene=verified_existing_reference(self.path,revision=self.revision,
                expected_sha256=self.expected_sha256)
            if not self.cancelled:
                self.signals.completed.emit(self.token,scene)
        except Exception as exc:
            if not self.cancelled:
                self.signals.failed.emit(self.token,str(exc))


class ExistingBuildingReferenceDialog(QDialog):
    def __init__(self,scene,parent=None):
        super().__init__(parent)
        self.scene=scene
        self.setObjectName("IFC2X3ExistingBuildingReferenceDialog")
        self.setWindowTitle("مدل وضع موجود برای بازسازی؛ فقط مرجع بصری IFC2X3")
        self.setLayoutDirection(Qt.LayoutDirection.RightToLeft)
        self.resize(1000,680)
        layout=QVBoxLayout(self)
        caption=QLabel(
            "وضع موجود منتشرشده | فقط نمایش عضو حقیقی، بدون متره یا محاسبات بازسازی\n"
            f"کل اعضا: {scene.source_member_count} | دارای هندسه: {scene.source_with_geometry_count} | "
            "نمایش فعلی: ۱؛ بقیه بارگذاری‌نشده یا فاقد هندسه‌اند.\n"
            "IFC2X3 هنوز قرارداد مهندسی IFC4 نیست؛ امکان اتصال به BOQ، پرداخت، "
            "تأیید سناریوی مقاوم‌سازی یا بازسازی وجود ندارد.\n"
            "Revision: "+scene.revision+" | SHA-256: "+scene.source_sha256)
        caption.setObjectName("ExistingBuildingSourceProvenance")
        caption.setWordWrap(True)
        caption.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        self.caption=caption
        layout.addWidget(caption)
        self.canvas=SiteTerrainCanvas(scene,self)
        self.canvas.setObjectName("IFC2X3ExistingBuildingVisualOnlyCanvas")
        self.canvas.setAccessibleName("نمای وضع موجود واقعی، فقط تصویری و بدون امکان انتخاب عضو مالی")
        layout.addWidget(self.canvas,1)
