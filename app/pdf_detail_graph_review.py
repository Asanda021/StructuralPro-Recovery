"""Qt inspection of source-bound PDF detail evidence."""
from __future__ import annotations

from functools import partial
import json
from pathlib import Path

from core.drawings.pdf_revision_preflight import build_pdf_revision_register_draft

from PySide6.QtCore import QAbstractTableModel, QModelIndex, QSortFilterProxyModel, Qt
from PySide6.QtWidgets import (
    QAbstractItemView, QFileDialog, QHBoxLayout, QLabel, QLineEdit, QPlainTextEdit,
    QPushButton, QSplitter, QTabWidget, QTableView, QVBoxLayout, QWidget,
)


_TABLES = {
    'documents': ('سندها', (
        ('شناسه سند', 'document_id'), ('نام فایل', 'source_name'),
        ('تعداد صفحات', 'page_count'), ('وضعیت نسخه', 'revision_status'),
        ('نسخهٔ ثبت‌شده', 'revision'), ('هش SHA-256', 'sha256'),
        ('ویرایش‌های چاپ‌شده', 'printed_revision_candidates'),
        ('موانع ثبت', 'revision_draft_problems'),
    )),
    'pages': ('صفحات', (
        ('شناسه سند', 'document_id'), ('صفحه', 'page'), ('شیت', 'sheet_id'),
        ('نقش صفحه', 'page_role'), ('وضعیت', 'status'), ('محتوا', 'content_kind'),
        ('وضعیت نسخه', 'authority_status'), ('OCR محلی', 'rendered_ocr_status'),
        ('نامزد OCR', 'rendered_ocr_type_count'), ('شاهد برداری', 'vector_text_type_count'),
        ('علت', 'reason'),
    )),
    'nodes': ('شواهد و اجزا', (
        ('شناسه گره', 'node_id'), ('نوع', 'kind'), ('عنوان', 'label'),
        ('خانواده', 'family'), ('وضعیت', 'status'), ('علت', 'reason'),
    )),
    'edges': ('پیوندها', (
        ('شناسه پیوند', 'edge_id'), ('رابطه', 'relationship'), ('وضعیت', 'status'),
        ('مبدأ', 'source_id'), ('مقصد', 'target_id'), ('علت', 'reason'),
    )),
    'topology': ('گروه‌های برداری', (
        ('شناسهٔ گروه یا عملگر', 'evidence_id'), ('شناسه سند', 'document_id'), ('صفحه', 'page'),
        ('نقش هندسه', 'role'), ('وضعیت', 'status'), ('علت', 'reason'),
    )),
    'issues': ('موارد باز', (
        ('شناسه مورد', 'issue_id'), ('وضعیت', 'status'), ('کد علت', 'reason_code'),
        ('گره مرتبط', 'node_id'), ('علت', 'reason'), ('مدرک لازم', 'required_evidence'),
    )),
    'member_review_groups': ('شناسه‌های پلان و دیتیل', (
        ('تیپ', 'type_tag'), ('وضعیت', 'status'), ('تعداد شناسه پلان', 'plan_mark_count'),
        ('شمار چاپی دیتیل', 'detail_printed_count'), ('تعداد شناسه دیتیل', 'detail_id_count'),
        ('شناسه‌های مشترک', 'shared_printed_ids'),
    )),
}

_DETAIL_FIELDS = {
    'documents': (('پروژه', 'project_id'), ('ابلاغ', 'issue_id'), ('سند مرجع', 'authority_reference')),
    'pages': (('نسخهٔ چاپ‌شده', 'printed_revisions'), ('چرخش', 'rotation'),
              ('عنوان شیت', 'sheet_kind'), ('واژهٔ بومی', 'native_pdf_word_count'),
              ('ابهام OCR', 'rendered_ocr_ambiguous_glyph_count'),
              ('ابهام نوشتهٔ برداری', 'vector_text_ambiguous_count'),
              ('خوانش نوشتهٔ برداری', 'vector_text_status'),
              ('مقیاس‌های چاپی', 'printed_scales'), ('خطاهای ورودی صفحه', 'source_errors'),
              ('وضعیت خوانش مسیرها', 'topology_status'), ('کد علت خوانش مسیرها', 'topology_reason_code'),
              ('تعداد مسیرها', 'source_path_count'),
              ('تعداد عملگرهای مسیر', 'source_operator_count'), ('تعداد گروه‌ها', 'topology_group_count')),
    'nodes': (('تیپ', 'type_tag'), ('تراز', 'level'), ('آکس', 'axis'),
              ('خانواده‌های نامزد', 'family_candidates'),
              ('کد دیتیل', 'detail_code'), ('مقیاس چاپی', 'printed_scale'),
              ('اعتبار شواهد', 'evidence_quality'), ('شناسه چاپی', 'printed_member_id'),
              ('وضعیت بازبینی شناسه', 'printed_id_review_status'),
              ('وضعیت متره', 'quantity_status'), ('علت توقف متره', 'quantity_reason'),
              ('وضعیت مقیاس', 'scale_status')),
    'edges': (('کد علت', 'reason_code'),),
    'topology': (('تعداد عملگرهای گروه', 'operator_count'), ('اندیس مسیرها', 'source_path_indices'),),
    'member_review_groups': (('فقط در پلان', 'plan_only_printed_ids'), ('فقط در دیتیل', 'detail_only_printed_ids')),
}


def _display(value):
    if isinstance(value, (list, tuple)):
        return '، '.join(_display(item) for item in value)
    return '—' if value is None or value == '' else str(value)


class _EvidenceTableModel(QAbstractTableModel):
    def __init__(self, records, columns, parent):
        super().__init__(parent)
        self.records = records
        self.columns = columns

    def rowCount(self, parent=QModelIndex()):
        return 0 if parent.isValid() else len(self.records)

    def columnCount(self, parent=QModelIndex()):
        return 0 if parent.isValid() else len(self.columns)

    def headerData(self, section, orientation, role=Qt.ItemDataRole.DisplayRole):
        if role == Qt.ItemDataRole.DisplayRole and orientation == Qt.Orientation.Horizontal:
            return self.columns[section][0]
        return super().headerData(section, orientation, role)

    def data(self, index, role=Qt.ItemDataRole.DisplayRole):
        if index.isValid() and role == Qt.ItemDataRole.DisplayRole:
            return _display(self.records[index.row()].get(self.columns[index.column()][1]))
        return None


class PDFDetailGraphReview(QWidget):
    def __init__(self, report, parent=None, *, attach_revision_register=None, attach_member_review=None, open_question=None):
        super().__init__(parent)
        self.setObjectName('PDFDetailEvidenceGraph')
        graph = report['detail_evidence_graph']
        self._source_report = report
        try:
            self._revision_draft = build_pdf_revision_register_draft(report)
        except ValueError:
            # Incomplete preview may still be browsed, but cannot produce
            # an operator template pretending to be a verified source list.
            self._revision_draft = None
        self._nodes = graph.get('nodes', ())
        self._node_rows = {node['node_id']: row for row, node in enumerate(self._nodes)}
        authorities = {node.get('document_id'): node.get('authority') or {}
                       for node in self._nodes if node['kind'] == 'DOCUMENT'}
        self._documents = {}
        draft_review = {item['document_id']: item
                        for item in (self._revision_draft or {}).get('review', ())}
        for doc in report.get('documents', ()):
            doc_id = doc['document_id']
            authority = authorities.get(doc_id, {})
            audit = draft_review.get(doc_id, {})
            self._documents[doc_id] = {
                **authority, **doc, 'revision_status': authority.get('status', 'UNREGISTERED'),
                'printed_revision_candidates': audit.get('printed_revision_candidates', ()),
                'revision_draft_problems': audit.get('required_actions', ()),
            }
        documents = tuple(self._documents.values())
        self._attach_revision_register = attach_revision_register
        self._attach_member_review = attach_member_review
        self._open_question = open_question
        self._question_tag = None
        geometry = []
        for page in graph.get('topology_pages', ()):
            for group in page['groups']:
                geometry.append({
                    **group, 'evidence_id': group['candidate_id'], 'operator_count': len(group['source_operators']),
                    'anchors': [{'document_id': group['document_id'], 'page': group['page'],
                                 'bbox_pt': group['bbox_pt'], 'kind': group['role']}],
                })
            for item in (*page['unresolved_operators'], *page['unresolved_paths']):
                geometry.append({
                    **item, 'evidence_id': item['source_id'], 'document_id': page['document_id'],
                    'page': page['page'], 'role': item.get('operator') or 'UNREADABLE',
                    'source_path_indices': [item['path_index']],
                })
        rows_by_table = {**graph, 'documents': documents, 'topology': geometry}

        layout = QVBoxLayout(self)
        receipt = QLabel(
            f"{len(documents)} سند | {len(graph.get('pages', ()))} صفحه | "
            f"{len(self._nodes)} گره | {len(graph.get('edges', ()))} پیوند | "
            f"{len(graph.get('issues', ()))} مورد باز | "
            f"{graph.get('quantity_approval_count', 0)} مقدار تأییدشده\n"
            f"SHA-256 — {graph.get('graph_sha256', '—')}"
        )
        receipt.setTextFormat(Qt.TextFormat.PlainText)
        receipt.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        receipt.setWordWrap(True)
        layout.addWidget(receipt)

        self.export_draft_button = QPushButton('ساخت پیش‌نویس ثبت نسخه (بدون تأیید)')
        self.export_draft_button.setObjectName('PDFDetailExportRevisionRegisterDraft')
        self.export_draft_button.clicked.connect(self._export_revision_register_draft)
        self.export_draft_button.setEnabled(self._revision_draft is not None)
        layout.addWidget(self.export_draft_button, alignment=Qt.AlignmentFlag.AlignRight)
        self.export_draft_status = QLabel()
        self.export_draft_status.setObjectName('PDFDetailExportRevisionRegisterStatus')
        self.export_draft_status.setTextFormat(Qt.TextFormat.PlainText)
        self.export_draft_status.setWordWrap(True)
        self.export_draft_status.hide()
        layout.addWidget(self.export_draft_status)

        if attach_revision_register is not None:
            self.attach_button = QPushButton('پیوست ثبت نسخهٔ نقشه (JSON)')
            self.attach_button.setObjectName('PDFDetailAttachRevisionRegister')
            self.attach_button.clicked.connect(self._pick_revision_register)
            layout.addWidget(self.attach_button, alignment=Qt.AlignmentFlag.AlignRight)
            self.attach_status = QLabel()
            self.attach_status.setObjectName('PDFDetailRevisionRegisterStatus')
            self.attach_status.setTextFormat(Qt.TextFormat.PlainText)
            self.attach_status.setWordWrap(True)
            self.attach_status.hide()
            layout.addWidget(self.attach_status)

        if attach_member_review is not None:
            self.member_review_button = QPushButton('پیوست بازخوانی شناسه‌های پلان و دیتیل', self)
            self.member_review_button.setObjectName('PDFDetailAttachMemberReview')
            self.member_review_button.clicked.connect(self._pick_member_review)
            layout.addWidget(self.member_review_button, alignment=Qt.AlignmentFlag.AlignRight)
            self.member_review_status = QLabel(self)
            self.member_review_status.setTextFormat(Qt.TextFormat.PlainText)
            self.member_review_status.setWordWrap(True)
            self.member_review_status.hide()
            layout.addWidget(self.member_review_status)

        split = QSplitter(Qt.Orientation.Vertical, self)
        layout.addWidget(split)
        self.sections = QTabWidget(split)
        self.tables = {}
        self.filters = {}
        self._section_keys = list(_TABLES)
        for key, (title, columns) in _TABLES.items():
            panel = QWidget(self.sections)
            panel_layout = QVBoxLayout(panel)
            search = QLineEdit(panel)
            search.setPlaceholderText('جست‌وجو در جدول')
            search.setClearButtonEnabled(True)
            panel_layout.addWidget(search)
            view = QTableView(panel)
            view.setObjectName(f'PDFDetailGraph{key.title()}')
            model = _EvidenceTableModel(rows_by_table.get(key, ()), columns, view)
            proxy = QSortFilterProxyModel(view)
            proxy.setSourceModel(model)
            proxy.setFilterKeyColumn(-1)
            proxy.setFilterCaseSensitivity(Qt.CaseSensitivity.CaseInsensitive)
            view.setModel(proxy)
            view.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
            view.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
            view.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
            view.setAlternatingRowColors(True)
            view.horizontalHeader().setDefaultSectionSize(145)
            view.horizontalHeader().setStretchLastSection(True)
            view.verticalHeader().hide()
            panel_layout.addWidget(view)
            self.tables[key] = view
            self.filters[key] = search
            search.textChanged.connect(proxy.setFilterFixedString)
            view.selectionModel().selectionChanged.connect(self._refresh_selection)
            self.sections.addTab(panel, title)

        detail_panel = QWidget(split)
        detail_layout = QVBoxLayout(detail_panel)
        self.details = QPlainTextEdit(detail_panel)
        self.details.setReadOnly(True)
        self.details.setObjectName('PDFDetailGraphSelection')
        detail_layout.addWidget(self.details)
        navigation = QHBoxLayout()
        self._endpoint_buttons = {}
        for role, label in (('source', 'شاهد مبدأ'), ('target', 'شاهد مقصد'),
                            ('related', 'گره مرتبط')):
            button = QPushButton(label, detail_panel)
            button.setObjectName(f'PDFDetailGraphNavigate{role.title()}')
            button.clicked.connect(partial(self._navigate_to_endpoint, role))
            navigation.addWidget(button)
            self._endpoint_buttons[role] = button
        self.question_button = QPushButton('ثبت اصلاح یا درخواست مدرک', detail_panel)
        self.question_button.setObjectName('PDFDetailGraphOpenReviewQuestion')
        self.question_button.clicked.connect(self._review_selected_issue)
        navigation.addWidget(self.question_button)
        detail_layout.addLayout(navigation)
        split.setStretchFactor(0, 3)
        split.setStretchFactor(1, 2)
        self.sections.currentChanged.connect(self._refresh_selection)
        self._refresh_selection()

    def _export_revision_register_draft(self):
        if self._revision_draft is None:
            self.export_draft_status.setText('ثبت پیش‌نویس مسدود: فهرست سند یا صفحات نامعتبر است.')
            self.export_draft_status.show()
            return
        name, _ = QFileDialog.getSaveFileName(
            self, 'ذخیره پیش‌نویس ثبت نسخه', '', 'JSON (*.json)'
        )
        if not name:
            return
        try:
            path = Path(name)
            if path.suffix.lower() != '.json':
                raise ValueError('فایل باید پسوند .json داشته باشد.')
            # Exclusive creation prevents damage to a completed signed
            # register or to a previous draft. No project DB writes.
            with path.open('x', encoding='utf-8') as stream:
                json.dump(self._revision_draft['template'], stream,
                          ensure_ascii=False, indent=2)
                stream.write('\n')
        except (OSError, ValueError) as exc:
            self.export_draft_status.setText(
                f'فایل پیش‌نویس ذخیره نشد؛ فایل موجود بازنویسی نمی‌شود: {exc}'
            )
        else:
            self.export_draft_status.setText(
                'پیش‌نویس فقط هش منابع را دارد و ثبت معتبر نیست. '
                'پروژه، ابلاغ، ویرایش سند، وضعیت جاری/منسوخ و مرجع '
                'رسمی باید از دفتر ابلاغ مستقل تأیید و تکمیل شوند.'
            )
        self.export_draft_status.show()

    def _pick_revision_register(self):
        name, _ = QFileDialog.getOpenFileName(
            self, 'انتخاب فایل ثبت نسخهٔ نقشه', '', 'JSON (*.json)'
        )
        if not name:
            return
        try:
            self._attach_revision_register(name)
        except Exception as exc:
            self.attach_status.setText(f'ثبت نسخه پیوست نشد. رسید پیشین در دسترس است.\n{exc}')
            self.attach_status.show()

    def _pick_member_review(self):
        name, _ = QFileDialog.getOpenFileName(self, 'انتخاب رسید بازخوانی شناسه‌ها', '', 'JSON (*.json)')
        if not name:
            return
        try:
            self._attach_member_review(name)
        except (OSError, ValueError, RuntimeError) as exc:
            self.member_review_status.setText(f'پیوست بازخوانی پذیرفته نشد. گزارش پیشین در دسترس است.\n{exc}')
            self.member_review_status.show()

    def _refresh_selection(self, *_):
        key = self._section_keys[self.sections.currentIndex()]
        view = self.tables[key]
        proxy = view.model()
        selected = view.selectionModel().selectedRows()
        self._endpoint_ids = {}
        self._question_tag = None
        if not selected:
            self.details.setPlainText('برای مشاهدهٔ جزئیات و نشانی شواهد، یک ردیف را انتخاب کنید.')
        else:
            model = proxy.sourceModel()
            record = model.records[proxy.mapToSource(selected[0]).row()]
            lines = [f'{heading} — {_display(record.get(field))}'
                     for heading, field in (*model.columns, *_DETAIL_FIELDS.get(key, ()))
                     if field in record]
            if key == 'edges':
                self._endpoint_ids = {'source': record.get('source_id'),
                                      'target': record.get('target_id')}
                lines.extend(self._endpoint_lines('مبدأ پیوند', record.get('source_id')))
                lines.extend(self._endpoint_lines('مقصد پیوند', record.get('target_id')))
                for candidate in record.get('candidate_ids', ()):
                    lines.extend(self._endpoint_lines('مقصد احتمالی', candidate))
            elif key == 'issues':
                self._question_tag = record.get('review_tag')
                self._endpoint_ids = {'related': record.get('node_id')}
                lines.extend(self._endpoint_lines('گره مرتبط', record.get('node_id')))
            elif key == 'pages':
                self._endpoint_ids = {'related': record.get('node_id')}
                lines.extend(self._anchor_lines('صفحهٔ منبع', [{
                    'document_id': record['document_id'], 'page': record['page'],
                    'bbox_pt': record.get('source_bbox_pt'), 'kind': 'PAGE',
                }]))
            if key != 'documents':
                anchors = record.get('anchors', ())
                if key != 'pages' or anchors:
                    lines.extend(self._anchor_lines('نشانی شواهد', anchors))
            self.details.setPlainText('\n'.join(lines))
        for role, button in self._endpoint_buttons.items():
            button.setVisible(role in self._endpoint_ids)
            button.setEnabled(self._endpoint_ids.get(role) in self._node_rows)
        self.question_button.setVisible(bool(self._question_tag and self._open_question))

    def _review_selected_issue(self):
        if self._question_tag and self._open_question:
            self._open_question(self._question_tag)

    def _endpoint_lines(self, title, node_id):
        row = self._node_rows.get(node_id)
        if row is None:
            return ['', title, 'شاهد مشخص نشده است.']
        node = self._nodes[row]
        label = f'{title} — {_display(node.get("label"))} ({node_id})'
        if node['kind'] == 'DOCUMENT':
            return ['', label, f'سند کامل — {_display(node.get("document_id"))}']
        return self._anchor_lines(label, node.get('anchors', ()))

    def _anchor_lines(self, title, anchors):
        lines = ['', f'{title} (مختصات بدون چرخش)']
        if not anchors:
            return lines + ['نشانی ثبت نشده است.']
        for anchor in anchors:
            doc_id = anchor.get('document_id')
            name = self._documents.get(doc_id, {}).get('source_name')
            source = f'{name} ({doc_id})' if name else _display(doc_id)
            box = anchor.get('bbox_pt')
            coords = '[' + ', '.join(str(coord) for coord in box) + ']' if box else '—'
            witness = f'{_display(anchor.get("kind"))} {_display(anchor.get("anchor_id"))}'
            lines.append(f'{source} | صفحه {_display(anchor.get("page"))} | کادر (pt) {coords} | {witness}')
            for label, field in (
                ('نوشتهٔ خام', 'raw_token'), ('خوانش استاندارد', 'normalized_tag'),
                ('خوانش‌های ممکن', 'glyph_interpretations'), ('علت ابهام برداری', 'glyph_ambiguity_reason'),
                ('طول نوشته‌شدهٔ تیپ (m)', 'dimension_m'),
            ):
                if field in anchor:
                    lines.append(f'{label} — {_display(anchor[field])}')
        return lines

    def _navigate_to_endpoint(self, role):
        row = self._node_rows.get(self._endpoint_ids.get(role))
        if row is None:
            return
        table = self.tables['nodes']
        proxy = table.model()
        source_index = proxy.sourceModel().index(row, 0)
        index = proxy.mapFromSource(source_index)
        if not index.isValid():
            self.filters['nodes'].clear()
            index = proxy.mapFromSource(source_index)
        self.sections.setCurrentIndex(self._section_keys.index('nodes'))
        table.setCurrentIndex(index)
        table.scrollTo(index)
