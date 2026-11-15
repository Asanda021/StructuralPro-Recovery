"""Read-only review of automatic PDF-sheet evidence and necessary questions.

Intake never commits a member quantity, silently changes BOQ, or treats a
proposed answer as approved.  This view does not modify the source documents.
"""
from __future__ import annotations

from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QTableWidget, QTableWidgetItem,
    QHeaderView, QPushButton, QTabWidget, QWidget, QComboBox, QLineEdit,
    QFileDialog, QMessageBox,
)
from PySide6.QtCore import Qt
from core.drawings.pdf_auto_questions import PDFQuestionDecisionLedger


class PDFSheetEvidenceDialog(QDialog):
    def __init__(self, report: dict, parent=None):
        super().__init__(parent)
        self.setObjectName('PDFSheetEvidenceReview')
        self.setWindowTitle('تحلیل خودکار شیت‌های PDF | شواهد و ابهام‌ها')
        self.setLayoutDirection(Qt.LayoutDirection.RightToLeft)
        self.resize(1000, 690)
        self.report = report
        self.ledger = PDFQuestionDecisionLedger(report)
        root = QVBoxLayout(self)
        self.summary = QLabel(
            f"{len(report.get('documents', ()))} PDF | {report.get('page_count', 0)} صفحه | "
            f"{len((report.get('sheet_detail_inventory') or {}).get('sheet_inventory',()))} شیت فهرست‌شده | "
            f"{len((report.get('sheet_detail_inventory') or {}).get('region_inventory',()))} ناحیه با وضعیت پوشش | "
            f"{len((report.get('detail_object_index') or {}).get('detail_candidates',()))} نامزد عنوان/تیپ دیتیل | "
            f"{len((report.get('detail_object_index') or {}).get('unassigned_visual_regions',()))} ناحیه ترسیمی بی‌ارتباط | "
            f"{(report.get('detail_object_index') or {}).get('vector_geometry_group_count',0)} گروه هندسی احتمالی (نه دیتیل قطعی) | "
            f"{((report.get('detail_object_index') or {}).get('geometry_detail_link_ledger') or {}).get('possible_page_local_links',0)} پیوند عنوان و هندسه پیشنهادی | "
            f"{len((report.get('detail_object_index') or {}).get('vector_grouping_blocked_pages',()))} صفحه هندسه گروه‌بندی‌نشده | "
            f"{(report.get('detail_object_index') or {}).get('blocked_source_region_count',0)} ناحیه با استخراج ناقص | "
            f"{len(report.get('member_type_candidates', ()))} شاهد تیپ | "
            f"{len(report.get('grid_location_candidates', ()))} نامزد موقعیت شبکه (تأییدنشده) | "
            f"{report.get('column_layout_symbol_candidate_count', 0)} شاهد نماد در پلان ستون (غیرقطعی) | "
            f"{report.get('vector_type_label_candidate_count', 0)} برچسب برداری تیپ (پیشنهادی) | "
            f"{report.get('vector_type_detail_link_count', 0)} ارتباط پیشنهادی با دیتیل | "
            f"{report.get('independently_registered_grid_positions',0)} تطبیق شبکه با آکس‌بندی (غیرقطعی) | "
            f"{len(report.get('architectural_floor_plan_candidates',()))} پلان معماریِ تراز (بدون ضریب تکرار) | "
            f"{len((report.get('column_position_ledger') or {}).get('positions',()))} موقعیت ستون با پرونده شواهد (غیرقطعی) | "
            f"{len(report.get('unresolved_pages', ()))} صفحه با پوشش نامعلوم | "
            f"{len(report.get('questions', ()))} ابهام بین شیت‌ها")
        self.summary.setWordWrap(True)
        root.addWidget(self.summary)
        disclaimer = QLabel(
            'این نتایج فقط شواهد هندسی/متنیِ شناسایی نوع عضو هستند. '
            'شمار اعضای فیزیکی، متره کامل و تأیید مالی هنوز احراز نشده‌اند.')
        disclaimer.setObjectName('PDFAutoIntakeNoFinanceWarning')
        disclaimer.setWordWrap(True)
        root.addWidget(disclaimer)
        tabs = QTabWidget(self)
        root.addWidget(tabs)
        # The coverage index is an audit of EVERY page and evidence zone.
        # A indexed cell is not an identified detail nor a financial quantity.
        coverage = report.get('sheet_detail_inventory') or {}
        coverage_root = QWidget(tabs)
        coverage_layout = QVBoxLayout(coverage_root)
        inventory_notice = QLabel(
            'فهرست‌برداری، تحلیل و متره قطعی دیتیل نیست. '
            'ناحیه‌های برداری و تصویری نامفسر با وضعیت UNRESOLVED ثبت می‌شوند.'
        )
        inventory_notice.setWordWrap(True)
        coverage_layout.addWidget(inventory_notice)
        cover_subtabs = QTabWidget(coverage_root)
        coverage_layout.addWidget(cover_subtabs)
        sheet_page = QWidget(cover_subtabs)
        sheet_layout = QVBoxLayout(sheet_page)
        self.sheet_coverage_table = QTableWidget(0, 7, sheet_page)
        self.sheet_coverage_table.setObjectName('PDFAutoIntakeAllSheetsCoverage')
        self.sheet_coverage_table.setHorizontalHeaderLabels([
            'فایل/صفحه', 'نوع شیت احتمالی', 'ناحیه‌ها', 'عنوان دیتیل', 'یادداشت', 'ناحیه جدول/شبکه', 'وضعیت پوشش'
        ])
        page_rows = coverage.get('sheet_inventory', ())
        self.sheet_coverage_table.setRowCount(len(page_rows))
        self.sheet_coverage_table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        for i, item in enumerate(page_rows):
            vals = (f"{item.get('document_id', '')}:p{item.get('page', '')}",
                    item.get('sheet_kind') or 'نامعلوم',
                    item.get('region_count', 0),
                    item.get('detail_anchor_count', 0),
                    item.get('note_anchor_count', 0),
                    item.get('table_or_grid_candidate_region_count', 0),
                    item.get('coverage_status') or 'BLOCKED')
            for j, value in enumerate(vals):
                cell = QTableWidgetItem(str(value))
                cell.setFlags(cell.flags() & ~Qt.ItemFlag.ItemIsEditable)
                self.sheet_coverage_table.setItem(i, j, cell)
        sheet_layout.addWidget(self.sheet_coverage_table)
        cover_subtabs.addTab(sheet_page, 'تمام صفحات')

        zones_page = QWidget(cover_subtabs)
        zones_layout = QVBoxLayout(zones_page)
        self.detail_region_table = QTableWidget(0, 6, zones_page)
        self.detail_region_table.setObjectName('PDFAutoIntakeAllDetailRegions')
        self.detail_region_table.setHorizontalHeaderLabels([
            'منبع/ناحیه', 'حدود صفحه (pt)', 'متن', 'هندسه برداری', 'تصویر', 'وضعیت'
        ])
        region_rows = coverage.get('region_inventory', ())
        self.detail_region_table.setRowCount(len(region_rows))
        self.detail_region_table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        for i, item in enumerate(region_rows):
            values = (item.get('region_id',''),
                      ', '.join(map(str,item.get('bbox_pt',()))),
                      item.get('text_block_count',0),
                      item.get('vector_path_count',0),
                      item.get('image_block_count',0),
                      item.get('status','BLOCKED'))
            for j, value in enumerate(values):
                cell = QTableWidgetItem(str(value))
                cell.setFlags(cell.flags() & ~Qt.ItemFlag.ItemIsEditable)
                if j == 5:
                    cell.setToolTip(item.get('reason',''))
                self.detail_region_table.setItem(i, j, cell)
        zones_layout.addWidget(self.detail_region_table)
        cover_subtabs.addTab(zones_page, 'تمام ناحیه‌ها')

        title_page = QWidget(cover_subtabs)
        title_layout = QVBoxLayout(title_page)
        self.detail_title_table = QTableWidget(0, 4, title_page)
        self.detail_title_table.setObjectName('PDFAutoIntakeDetailTitleAnchors')
        self.detail_title_table.setHorizontalHeaderLabels([
            'فایل/صفحه', 'عنوان یافت‌شده', 'محدوده عنوان (pt)', 'وضعیت'
        ])
        anchors = coverage.get('detail_title_anchors', ())
        self.detail_title_table.setRowCount(len(anchors))
        self.detail_title_table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        for i, item in enumerate(anchors):
            vals = (f"{item.get('document_id','')}:p{item.get('page','')}",
                    item.get('title_preview',''),
                    ', '.join(map(str,item.get('bbox_pt',()))),
                    item.get('status','UNRESOLVED'))
            for j, value in enumerate(vals):
                cell = QTableWidgetItem(str(value))
                cell.setFlags(cell.flags() & ~Qt.ItemFlag.ItemIsEditable)
                self.detail_title_table.setItem(i,j,cell)
        title_layout.addWidget(self.detail_title_table)
        cover_subtabs.addTab(title_page, 'عنوان‌های دیتیل')
        note_page = QWidget(cover_subtabs)
        note_layout = QVBoxLayout(note_page)
        self.note_anchor_table = QTableWidget(0, 3, note_page)
        self.note_anchor_table.setObjectName('PDFAutoIntakeNotesInventory')
        self.note_anchor_table.setHorizontalHeaderLabels([
            'فایل/صفحه', 'متن یادداشت شناسایی‌شده', 'وضعیت'
        ])
        note_rows = coverage.get('note_anchors', ())
        self.note_anchor_table.setRowCount(len(note_rows))
        self.note_anchor_table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        for i, item in enumerate(note_rows):
            vals=(f"{item.get('document_id','')}:p{item.get('page','')}",
                  item.get('text_preview',''),item.get('status','UNRESOLVED'))
            for j, val in enumerate(vals):
                cell=QTableWidgetItem(str(val))
                cell.setFlags(cell.flags() & ~Qt.ItemFlag.ItemIsEditable)
                self.note_anchor_table.setItem(i,j,cell)
        note_layout.addWidget(self.note_anchor_table)
        cover_subtabs.addTab(note_page, 'یادداشت‌ها')
        tabs.addTab(coverage_root, 'پوشش همه شیت‌ها و دیتیل‌ها')

        # Candidate objects have source evidence but NOT verified detail
        # boundaries or quantities. The orphan list preserves unknown ink.
        detail_index = report.get('detail_object_index') or {}
        obj_tab = QWidget(tabs)
        obj_layout = QVBoxLayout(obj_tab)
        obj_notice = QLabel(
            'عنوان دیتیل، شناسه تیپ و ناحیه ترسیمی سه شاهد متفاوت‌اند. '
            'اتصال‌های پیشنهادی هنوز قطعی نیستند و هیچ مبلغی تولید نمی‌کنند.'
        )
        obj_notice.setWordWrap(True)
        obj_layout.addWidget(obj_notice)
        obj_sub = QTabWidget(obj_tab)
        obj_layout.addWidget(obj_sub)

        candidates_tab = QWidget(obj_sub)
        candidates_layout = QVBoxLayout(candidates_tab)
        self.detail_object_table = QTableWidget(0, 6, candidates_tab)
        self.detail_object_table.setObjectName('PDFAutoDetailObjectCandidates')
        self.detail_object_table.setHorizontalHeaderLabels([
            'شناسه شاهد', 'فایل/صفحه', 'عنوان یا تیپ', 'خانواده احتمالی',
            'ناحیه‌های منبع', 'وضعیت',
        ])
        objs = detail_index.get('detail_candidates', ())
        self.detail_object_table.setRowCount(len(objs))
        self.detail_object_table.horizontalHeader().setSectionResizeMode(
            QHeaderView.ResizeMode.Stretch
        )
        for i, obj in enumerate(objs):
            values=(
                obj.get('candidate_id',''),
                f"{obj.get('document_id','')}:p{obj.get('page','')}",
                obj.get('type_tag') or obj.get('title_preview') or '',
                '، '.join(obj.get('family_candidates') or ()) or 'نامعلوم',
                ', '.join(obj.get('region_ids') or ()),
                obj.get('status','BLOCKED'),
            )
            for j, val in enumerate(values):
                cell=QTableWidgetItem(str(val))
                cell.setFlags(cell.flags() & ~Qt.ItemFlag.ItemIsEditable)
                if j == 5:
                    cell.setToolTip(obj.get('reason',''))
                self.detail_object_table.setItem(i,j,cell)
        candidates_layout.addWidget(self.detail_object_table)
        obj_sub.addTab(candidates_tab, 'نامزدهای دیتیل و تیپ')

        orphan_tab = QWidget(obj_sub)
        orphan_layout = QVBoxLayout(orphan_tab)
        self.unassigned_visual_region_table = QTableWidget(0, 4, orphan_tab)
        self.unassigned_visual_region_table.setObjectName('PDFAutoUnassignedVisualRegions')
        self.unassigned_visual_region_table.setHorizontalHeaderLabels([
            'ناحیه', 'فایل/صفحه', 'خط برداری / تصویر', 'وضعیت',
        ])
        orphan_rows=detail_index.get('unassigned_visual_regions', ())
        self.unassigned_visual_region_table.setRowCount(len(orphan_rows))
        self.unassigned_visual_region_table.horizontalHeader().setSectionResizeMode(
            QHeaderView.ResizeMode.Stretch
        )
        for i, obj in enumerate(orphan_rows):
            values=(obj.get('region_id',''),
                    f"{obj.get('document_id','')}:p{obj.get('page','')}",
                    f"{obj.get('vector_path_count',0)} / {obj.get('image_block_count',0)}",
                    obj.get('status','UNRESOLVED'))
            for j, val in enumerate(values):
                cell=QTableWidgetItem(str(val))
                cell.setFlags(cell.flags() & ~Qt.ItemFlag.ItemIsEditable)
                if j==3:
                    cell.setToolTip(obj.get('reason',''))
                self.unassigned_visual_region_table.setItem(i,j,cell)
        orphan_layout.addWidget(self.unassigned_visual_region_table)
        obj_sub.addTab(orphan_tab, 'ناحیه‌های ترسیمی بی‌ارتباط')

        links_tab=QWidget(obj_sub)
        links_layout=QVBoxLayout(links_tab)
        self.type_reference_table=QTableWidget(0,4,links_tab)
        self.type_reference_table.setObjectName('PDFAutoProvisionalTypeReferences')
        self.type_reference_table.setHorizontalHeaderLabels([
            'سند', 'شناسه تیپ', 'صفحات محتمل', 'وضعیت اعتبار',
        ])
        refs=detail_index.get('potential_same_document_type_references', ())
        self.type_reference_table.setRowCount(len(refs))
        self.type_reference_table.horizontalHeader().setSectionResizeMode(
            QHeaderView.ResizeMode.Stretch
        )
        for i, obj in enumerate(refs):
            vals=(obj.get('document_id',''),obj.get('type_tag',''),
                  ', '.join(map(str,obj.get('pages',()))),
                  obj.get('status','UNRESOLVED'))
            for j, val in enumerate(vals):
                cell=QTableWidgetItem(str(val))
                cell.setFlags(cell.flags() & ~Qt.ItemFlag.ItemIsEditable)
                self.type_reference_table.setItem(i,j,cell)
        links_layout.addWidget(self.type_reference_table)
        obj_sub.addTab(links_tab, 'ارتباط احتمالی بین شیت‌ها')
        geometry_tab=QWidget(obj_sub)
        geometry_layout=QVBoxLayout(geometry_tab)
        geometry_notice=QLabel(
            'گروه هندسی صرفاً از نزدیکی مستطیل‌های مسیر برداری ساخته می‌شود؛ '
            'مرز واقعی دیتیل، اتصال قطعات و مالکیت عضو احراز نشده‌اند. هیچ مبلغی ایجاد نمی‌شود.'
        )
        geometry_notice.setWordWrap(True)
        geometry_layout.addWidget(geometry_notice)
        self.vector_group_table=QTableWidget(0,5,geometry_tab)
        self.vector_group_table.setObjectName('PDFAutoVectorGeometryGroups')
        self.vector_group_table.setHorizontalHeaderLabels([
            'شناسه گروه', 'محدوده (pt)', 'مسیرهای منبع', 'عنوان‌های نزدیک', 'وضعیت',
        ])
        vector_groups=detail_index.get('vector_geometry_groups',())
        self.vector_group_table.setRowCount(len(vector_groups))
        self.vector_group_table.horizontalHeader().setSectionResizeMode(
            QHeaderView.ResizeMode.Stretch
        )
        for i, entry in enumerate(vector_groups):
            vals=(entry.get('candidate_id',''),
                  ', '.join(map(str,entry.get('bbox_pt',()))),
                  entry.get('source_path_count',0),
                  ', '.join(entry.get('nearby_title_anchor_ids',())) or 'نامشخص',
                  entry.get('status','UNRESOLVED'))
            for j, val in enumerate(vals):
                cell=QTableWidgetItem(str(val))
                cell.setFlags(cell.flags() & ~Qt.ItemFlag.ItemIsEditable)
                if j==4:cell.setToolTip(entry.get('reason',''))
                self.vector_group_table.setItem(i,j,cell)
        geometry_layout.addWidget(self.vector_group_table)
        blocked_rows=detail_index.get('vector_grouping_blocked_pages',())
        self.vector_group_blocked_table=QTableWidget(0,3,geometry_tab)
        self.vector_group_blocked_table.setObjectName('PDFAutoVectorGroupingBlockedPages')
        self.vector_group_blocked_table.setHorizontalHeaderLabels([
            'فایل/صفحه مسدود', 'علت مسدودسازی', 'تعداد مسیر تعیین‌تکلیف‌نشده',
        ])
        self.vector_group_blocked_table.setRowCount(len(blocked_rows))
        self.vector_group_blocked_table.horizontalHeader().setSectionResizeMode(
            QHeaderView.ResizeMode.Stretch
        )
        for i, item in enumerate(blocked_rows):
            vals=(f"{item.get('document_id','')}:p{item.get('page','')}",
                  item.get('status','BLOCKED'),
                  item.get('ungrouped_path_count')
                  if item.get('ungrouped_path_count') is not None else 'نامشخص')
            for j, val in enumerate(vals):
                cell=QTableWidgetItem(str(val))
                cell.setFlags(cell.flags() & ~Qt.ItemFlag.ItemIsEditable)
                self.vector_group_blocked_table.setItem(i,j,cell)
        geometry_layout.addWidget(self.vector_group_blocked_table)
        obj_sub.addTab(geometry_tab,'گروه‌های هندسی احتمالی')

        linkage_tab=QWidget(obj_sub)
        linkage_layout=QVBoxLayout(linkage_tab)
        link_notice=QLabel(
            'پیوند تک‌عنوان/تک‌گروه فقط حدس مبتنی بر نزدیکی است؛ '
            'شناسه تیپ از شبکه درشت صفحه می‌آید و برای اثبات عضو فیزیکی کافی نیست.'
        )
        link_notice.setWordWrap(True)
        linkage_layout.addWidget(link_notice)
        self.geometry_detail_link_table=QTableWidget(0,5,linkage_tab)
        self.geometry_detail_link_table.setObjectName('PDFAutoGeometryDetailLinkEvidence')
        self.geometry_detail_link_table.setHorizontalHeaderLabels([
            'گروه برداری', 'عنوان پیشنهادی', 'تیپ از ناحیه درشت', 'وضعیت', 'پرداخت',
        ])
        links=((detail_index.get('geometry_detail_link_ledger') or {})
               .get('geometry_group_link_records',()))
        self.geometry_detail_link_table.setRowCount(len(links))
        self.geometry_detail_link_table.horizontalHeader().setSectionResizeMode(
            QHeaderView.ResizeMode.Stretch
        )
        for i, edge in enumerate(links):
            vals=(edge.get('vector_group_candidate_id',''),
                  edge.get('proposed_title_candidate_id') or 'نامعلوم/مبهم',
                  ', '.join(edge.get('coarse_zone_type_mark_candidate_ids',())) or 'فاقد شاهد معتبر',
                  edge.get('status','BLOCKED'),
                  'غیرقابل پرداخت')
            for j,val in enumerate(vals):
                cell=QTableWidgetItem(str(val))
                cell.setFlags(cell.flags() & ~Qt.ItemFlag.ItemIsEditable)
                self.geometry_detail_link_table.setItem(i,j,cell)
        linkage_layout.addWidget(self.geometry_detail_link_table)
        tabs_titles=((detail_index.get('geometry_detail_link_ledger') or {})
                     .get('title_coverage_records',()))
        self.geometry_title_coverage_table=QTableWidget(0,3,linkage_tab)
        self.geometry_title_coverage_table.setObjectName('PDFAutoGeometryTitleCoverage')
        self.geometry_title_coverage_table.setHorizontalHeaderLabels([
            'عنوان شناسایی‌شده','گروه‌های احتمالی','وضعیت'])
        self.geometry_title_coverage_table.setRowCount(len(tabs_titles))
        self.geometry_title_coverage_table.horizontalHeader().setSectionResizeMode(
            QHeaderView.ResizeMode.Stretch)
        for i,item in enumerate(tabs_titles):
            vals=(item.get('title_candidate_id',''),
                  ', '.join(item.get('possible_vector_group_ids',())) or 'بدون گروه',
                  item.get('status','BLOCKED'))
            for j,val in enumerate(vals):
                cell=QTableWidgetItem(str(val))
                cell.setFlags(cell.flags() & ~Qt.ItemFlag.ItemIsEditable)
                self.geometry_title_coverage_table.setItem(i,j,cell)
        linkage_layout.addWidget(self.geometry_title_coverage_table)
        obj_sub.addTab(linkage_tab,'پیوند پیشنهادی دیتیل و هندسه')
        tabs.addTab(obj_tab, 'دیتیل‌های شناسایی‌شده و موارد باز')



        candidates = QWidget(tabs)
        candidate_layout = QVBoxLayout(candidates)
        self.candidate_table = QTableWidget(0, 5, candidates)
        self.candidate_table.setObjectName('PDFAutoIntakeCandidates')
        self.candidate_table.setHorizontalHeaderLabels([
            'شناسه تیپ', 'سند / صفحه', 'بعد مستند', 'وضعیت', 'قابلیت استفاده مالی'])
        self.candidate_table.setRowCount(len(report.get('member_type_candidates', ())))
        self.candidate_table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        for i, row in enumerate(report.get('member_type_candidates', ())):
            vals = [row.get('tag', ''), f"{row.get('document_id','')}:p{row.get('page','')}",
                    f"{row.get('dimension_m') or 'نامشخص'} m" if row.get('dimension_m') else 'نامشخص',
                    row.get('status', ''), 'خیر']
            for j, text in enumerate(vals):
                cell = QTableWidgetItem(str(text))
                cell.setFlags(cell.flags() & ~Qt.ItemFlag.ItemIsEditable)
                self.candidate_table.setItem(i, j, cell)
        candidate_layout.addWidget(self.candidate_table)
        tabs.addTab(candidates, 'شواهد تیپ‌ها')

        grid_tab = QWidget(tabs)
        grid_layout = QVBoxLayout(grid_tab)
        self.grid_table = QTableWidget(0, 6, grid_tab)
        self.grid_table.setObjectName('PDFAutoIntakeGridLocations')
        self.grid_table.setHorizontalHeaderLabels([
            'شناسه موقعیت', 'سند / صفحه', 'مختصات PDF (pt)',
            'تیپ پیشنهادی (غیرقطعی)', 'وضعیت', 'شاهد نماد برداری',
        ])
        locations = report.get('grid_location_candidates', ())
        self.grid_table.setRowCount(len(locations))
        self.grid_table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        for i, item in enumerate(locations):
            values = (
                item.get('candidate_id', ''),
                f"{item.get('document_id','')}:p{item.get('page','')}",
                f"({item.get('x_pt','')}, {item.get('y_pt','')})",
                item.get('suggested_type') or 'شناسایی نشده',
                item.get('status', ''),
                ('شاهد فشرده، غیرقطعی' if
                 item.get('symbol_status') == 'COMPACT_VECTOR_SYMBOL_CANDIDATE'
                 else 'شاهد مستقل پیدا نشد'),
            )
            for j, value in enumerate(values):
                cell = QTableWidgetItem(str(value))
                cell.setFlags(cell.flags() & ~Qt.ItemFlag.ItemIsEditable)
                if j == 3 and item.get('vector_type_label_evidence'):
                    detail = item.get('cross_sheet_type_reference') or {}
                    references = detail.get('details') or []
                    hint = 'شناسه از هندسه خطوط خود برچسب PDF استخراج شده و هنوز تأیید مهندسی نشده است.'
                    if references:
                        r = references[0]
                        hint += (f" دیتیل پیشنهادی: صفحه {r.get('page','؟')}، "
                                 f"{r.get('dimension_kind','')} = {r.get('dimension_m','')} m.")
                    cell.setToolTip(hint)
                if j == 4 and item.get('independent_axis_grid_witness'):
                    witness = item['independent_axis_grid_witness']
                    cell.setToolTip(
                        f"تطبیق هندسی با آکس‌بندی صفحه {witness['axis_page']}، "
                        f"حداکثر اختلاف {witness['max_residual_pt']} pt. "
                        "این تطبیق اثبات عضو فیزیکی یا تکرار در طبقات نیست."
                    )
                self.grid_table.setItem(i, j, cell)
        grid_layout.addWidget(self.grid_table)
        tabs.addTab(grid_tab, 'موقعیت‌های احتمالی شبکه')


        # Sheet-title coverage is shown separately from member/BOQ approvals.
        floor_tab = QWidget(tabs)
        floor_layout = QVBoxLayout(floor_tab)
        self.floor_table = QTableWidget(0, 3, floor_tab)
        self.floor_table.setObjectName('PDFAutoIntakeFloorScope')
        self.floor_table.setHorizontalHeaderLabels([
            'سند / صفحه', 'پلان شناسایی‌شده', 'تکرار ستون در این تراز'])
        floor_items = report.get('architectural_floor_plan_candidates', ())
        self.floor_table.setRowCount(len(floor_items))
        self.floor_table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        floor_names = {'pilot_floor_plan':'پیلوت',
                       'ground_floor_plan':'همکف',
                       'first_floor_plan':'طبقه اول'}
        for i, item in enumerate(floor_items):
            values = (f"{item.get('document_id','')}:p{item.get('page','')}",
                      floor_names.get(item.get('sheet_kind'), item.get('sheet_kind','')),
                      'نامعلوم؛ مدرک تراز/مقطع لازم است')
            for j, value in enumerate(values):
                cell = QTableWidgetItem(str(value))
                cell.setFlags(cell.flags() & ~Qt.ItemFlag.ItemIsEditable)
                self.floor_table.setItem(i, j, cell)
        floor_layout.addWidget(self.floor_table)
        tabs.addTab(floor_tab, 'دامنه طبقات؛ بدون تکرار حدسی')


        # Grid candidates never count as installed columns or payable BOQ.
        proof_tab = QWidget(tabs)
        proof_layout = QVBoxLayout(proof_tab)
        self.column_position_table = QTableWidget(0, 6, proof_tab)
        self.column_position_table.setObjectName('PDFAutoIntakeColumnPositionProof')
        self.column_position_table.setHorizontalHeaderLabels([
            'موقعیت شبکه', 'آکس مستقل', 'تیپ پیشنهادی',
            'دیتیل تیپ / طول اسمی', 'تکرار در طبقات', 'وضعیت شواهد',
        ])
        proof_rows = (report.get('column_position_ledger') or {}).get('positions', ())
        self.column_position_table.setRowCount(len(proof_rows))
        self.column_position_table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        for i, item in enumerate(proof_rows):
            axis = item.get('axis_evidence') or {}
            detail = item.get('type_detail_evidence') or {}
            labels = (
                item.get('candidate_id', ''),
                (f"آکس‌بندی صفحه {axis.get('page')}" if axis else 'نامشخص'),
                item.get('proposed_type') or 'نامشخص',
                (f"صفحه {detail.get('page')} | L={detail.get('type_detail_length_m')} m (صرفاً دیتیل تیپ)"
                 if detail else 'دیتیل مستقل احراز نشد'),
                'تکرار طبقات نامعلوم',
                item.get('status', ''),
            )
            for j, label in enumerate(labels):
                cell = QTableWidgetItem(str(label))
                cell.setFlags(cell.flags() & ~Qt.ItemFlag.ItemIsEditable)
                if j == 4:
                    cell.setToolTip('پلان معماری به‌تنهایی تعداد ستون اجرایی در هر طبقه را ثابت نمی‌کند.')
                self.column_position_table.setItem(i, j, cell)
        proof_layout.addWidget(self.column_position_table)
        tabs.addTab(proof_tab, 'دفتر شواهد ستون (غیرمالی)')

        questions = QWidget(tabs)
        question_layout = QVBoxLayout(questions)
        self.question_table = QTableWidget(0, 3, questions)
        self.question_table.setObjectName('PDFAutoIntakeQuestions')
        self.question_table.setHorizontalHeaderLabels(['شناسه', 'سؤال ضروری برای کاربر نرم‌افزار', 'پیشنهاد مستند'])
        question_rows = report.get('questions', ())
        self.question_table.setRowCount(len(question_rows))
        self.question_table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        for i, question in enumerate(question_rows):
            suggestion = question.get('suggestion') or {}
            value = suggestion.get('value')
            if value is not None:
                guess = str(value)
            elif suggestion.get('per_location_type_candidates'):
                from collections import Counter
                types = Counter(x.get('type', '?') for x in
                                suggestion['per_location_type_candidates'])
                guess = ('خوانش برچسب‌های برداری: ' +
                         '، '.join(f'{k}: {types[k]}' for k in sorted(types)) +
                         '؛ انتساب‌ها هنوز پیشنهادی و غیرمالی‌اند')
            elif suggestion.get('floor_plan_candidates'):
                sheets = suggestion['floor_plan_candidates']
                guess = ('پلان‌های موجود: ' +
                         '، '.join(f"صفحه {x.get('page','؟')}" for x in sheets) +
                         '؛ تعداد تکرار ستون در طبقات با اسناد موجود اثبات نشده است')
            elif suggestion.get('candidate_types_from_details'):
                guess = ('تیپ‌های موجود در دیتیل‌ها: ' +
                         '، '.join(suggestion['candidate_types_from_details']) +
                         '؛ انتساب به هر موقعیت نامعلوم است')
            else:
                guess = 'سند حاکم معلوم نیست؛ حدس قطعی مجاز نیست'
            for j, text in enumerate((question.get('tag',''), question.get('question',''), guess)):
                cell = QTableWidgetItem(str(text))
                cell.setFlags(cell.flags() & ~Qt.ItemFlag.ItemIsEditable)
                self.question_table.setItem(i, j, cell)
        question_layout.addWidget(self.question_table)
        answer_row = QHBoxLayout()
        self.question_action = QComboBox()
        self.question_action.setObjectName('PDFAutoIntakeQuestionAction')
        self.question_action.addItem('درخواست سند اصلاحی', 'request_document')
        self.question_action.addItem('اصلاح پاسخ پیشنهادی', 'correct')
        self.question_action.addItem('تأیید پیشنهاد با ذکر مستند', 'confirm_suggestion')
        self.question_answer = QLineEdit()
        self.question_answer.setObjectName('PDFAutoIntakeQuestionCorrection')
        self.question_answer.setPlaceholderText('مقدار یا توضیح اصلاح‌شده در صورت انتخاب اصلاح')
        self.record_question = QPushButton('ثبت پاسخ بازبین (غیرمالی)')
        self.record_question.setObjectName('PDFAutoIntakeRecordQuestion')
        self.record_question.clicked.connect(self._record_question_answer)
        self.export_questions = QPushButton('ذخیره پاسخ‌های بازبینی')
        self.export_questions.setObjectName('PDFAutoIntakeExportAnswers')
        self.export_questions.clicked.connect(self._export_question_answers)
        for widget in (self.question_action, self.question_answer, self.record_question, self.export_questions):
            answer_row.addWidget(widget)
        question_layout.addLayout(answer_row)
        self.answer_status = QLabel('پاسخ‌ها فقط برای بازبینی ذخیره می‌شوند؛ مقدار مالی تغییر نمی‌کند.')
        self.answer_status.setWordWrap(True)
        question_layout.addWidget(self.answer_status)
        self.record_question.setEnabled(bool(question_rows))
        self.export_questions.setEnabled(bool(question_rows))
        tabs.addTab(questions, 'سؤال‌های ضروری')

        coverage = QWidget(tabs)
        coverage_layout = QVBoxLayout(coverage)
        self.coverage_table = QTableWidget(0, 2, coverage)
        self.coverage_table.setObjectName('PDFAutoIntakeUnresolvedPages')
        self.coverage_table.setHorizontalHeaderLabels(['سند / صفحه', 'محدودیت خوانش'])
        unknown = report.get('unresolved_pages', ())
        self.coverage_table.setRowCount(len(unknown))
        self.coverage_table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        for i, item in enumerate(unknown):
            for j, text in enumerate((f"{item.get('document_id')}:p{item.get('page')}",
                                      item.get('reason', ''))):
                cell = QTableWidgetItem(str(text))
                cell.setFlags(cell.flags() & ~Qt.ItemFlag.ItemIsEditable)
                self.coverage_table.setItem(i, j, cell)
        coverage_layout.addWidget(self.coverage_table)
        tabs.addTab(coverage, 'صفحات نیازمند شواهد بیشتر')

        row = QHBoxLayout()
        row.addWidget(QLabel('این پنجره فقط‌خواندنی است و مقدار پیشنهادی را به BOQ نمی‌فرستد.'))
        close = QPushButton('بستن گزارش')
        close.clicked.connect(self.accept)
        row.addWidget(close)
        root.addLayout(row)

    def _record_question_answer(self):
        row = self.question_table.currentRow()
        if row < 0:
            selected = self.question_table.selectionModel().selectedRows()
            if selected:
                row = selected[0].row()
            elif self.question_table.rowCount() == 1:
                row = 0
        if row < 0 or row >= len(self.report.get('questions', ())):
            QMessageBox.information(self, 'پرسش مهندسی', 'برای ثبت پاسخ، یک سؤال را انتخاب کنید.')
            return
        tag = self.report['questions'][row]['tag']
        try:
            result = self.ledger.answer(
                tag, self.question_action.currentData(),
                value=self.question_answer.text(),
            )
            self.answer_status.setText(
                f"پاسخ {result['tag']} ثبت شد؛ صرفاً پیش‌نویس بازبینی، بدون تأیید مالی."
            )
        except (KeyError, ValueError) as exc:
            QMessageBox.warning(self, 'پاسخ نامعتبر', str(exc))

    def _export_question_answers(self):
        if not self.ledger.answers:
            QMessageBox.information(self, 'ذخیره پاسخ‌ها', 'هنوز هیچ پاسخی ثبت نشده است.')
            return
        name, _ = QFileDialog.getSaveFileName(self, 'ذخیره پرونده بازبینی PDF',
                                             'pdf_intake_review_draft.json', 'JSON (*.json)')
        if not name:
            return
        try:
            from pathlib import Path
            Path(name).write_text(self.ledger.export_json(), encoding='utf-8')
            self.answer_status.setText('پاسخ‌ها در پرونده بازبینی ذخیره شدند؛ BOQ تغییر نکرده است.')
        except OSError as exc:
            QMessageBox.warning(self, 'خطای ذخیره', str(exc))