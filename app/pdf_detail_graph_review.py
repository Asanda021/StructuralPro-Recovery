"""Qt inspection of source-bound PDF detail evidence."""
from __future__ import annotations

from collections import defaultdict
from functools import partial
import json
from pathlib import Path

from core.drawings.pdf_revision_preflight import build_pdf_revision_register_draft
from core.drawings.pdf_designer_rfi_gate import (
    build_designer_rfi_packet, inspect_designer_reply, load_designer_reply,
    write_designer_rfi_package, write_designer_reply_crosswalk,
)

from PySide6.QtCore import QAbstractTableModel, QModelIndex, QSortFilterProxyModel, Qt
from PySide6.QtWidgets import (
    QAbstractItemView, QFileDialog, QHBoxLayout, QLabel, QLineEdit, QMenu, QPlainTextEdit,
    QPushButton, QSplitter, QTabWidget, QTableView, QToolButton, QVBoxLayout, QWidget,
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
    'occurrence_reviews': ('بازبینی اعضا', (
        ('شناسه چاپی عضو', 'printed_member_id'), ('تیپ', 'type_tag'), ('خانواده', 'family'),
        ('وضعیت بازبینی', 'status'), ('تصمیم', 'decision_code'), ('کد علت', 'reason_code'),
        ('وضعیت متره', 'quantity_status'),
    )),
    'beam_axis_grid_candidates': ('شبکه آکس مستقل', (
        ('شناسه سند', 'document_id'), ('صفحه آکس', 'page'),
        ('وضعیت', 'status'), ('محورهای قائم (pt)', 'grid_x_pt'),
        ('محورهای افقی (pt)', 'grid_y_pt'),
        ('نام‌گذاری آکس', 'axis_label_witness_status'),
    )),
    'beam_end_marker_pages': ('نمادهای انتهای دهانه', (
        ('سند', 'document_id'), ('صفحه تیر', 'page'),
        ('وضعیت', 'status'), ('نمادهای متمایز', 'marker_count'),
        ('مسیرهای هم‌مکان', 'duplicate_source_strokes'),
    )),
    'beam_span_evidence_requests': ('مدارک ناقص دهانه‌های تیر', (
        ('آکس دهانه', 'span_axes'), ('ردیف آکس', 'printed_axis_row'),
        ('شماره چاپی', 'printed_mark'), ('پروفیل تصویری', 'profile_visual'),
        ('وضعیت', 'status'), ('شواهد مورد نیاز', 'required_evidence_codes'),
    )),
    'beam_end_support_reviews': ('بازبینی دو سر تیر و دیتیل', (
        ('آکس', 'span_axes'), ('ردیف', 'printed_axis_row'),
        ('پروفیل', 'profile_text'), ('دو سر دهانه', 'status'),
        ('ارتباط دیتیل', 'detail_status'), ('شواهد نوع', 'candidate_detail_count'),
    )),
    'beam_profile_reviews': ('تطبیق مکانی پروفیل تیر', (
        ('پروفیل تصویری', 'profile_text'), ('آکس دهانه', 'span_axes'),
        ('ردیف آکس', 'printed_axis_row'), ('شمارهٔ چاپی', 'circled_mark_raw'),
        ('مرزهای نامزد', 'candidate_region_count'), ('وضعیت', 'status'),
        ('تطبیق آکس مستقل', 'independent_axis_status'),
        ('کد علت', 'reason_code'),
    )),
    'structural_plan_reviews': ('بازبینی پلان سازه', (
        ('نقش پلان', 'role'), ('خانواده', 'family'), ('تیپ', 'type_tag'),
        ('وضعیت بازبینی', 'status'), ('کد علت', 'reason_code'), ('علت', 'reason'),
        ('جفت‌خط‌های جایگزین', 'parallel_pair_alternatives'),
    )),
    'multidiscipline_gaps': ('شکاف پوشش سازه، معماری و تأسیسات', (
        ('شناسه سند', 'document_id'), ('صفحه', 'page'),
        ('رشته نامزد', 'candidate_family'), ('وضعیت', 'status'),
        ('نوع شیت', 'sheet_kind'), ('کدهای بررسی لازم', 'required_review'),
        ('ناحیه تصویری بی‌نام', 'unassigned_visual_region_ids'),
        ('شواهد ناقص', 'blocked_region_ids'),
    )),
    'operator_components': ('تطبیق مستقل اجزای هندسی دیتیل', (
        ('سند', 'document_id'), ('صفحه', 'page'), ('وضعیت شناسایی', 'classification_status'),
        ('خانوادهٔ پیشنهادی', 'classification_families'), ('نقش هندسی', 'stroke_topology_role'),
        ('علت شناسایی', 'classification_reason'), ('وضعیت تطبیق', 'status'), ('کادر هندسه (pt)', 'bbox_pt'),
        ('عنوان نامزد', 'proposed_title_anchor_id'),
        ('گروه‌های مرزی', 'bbox_group_candidate_ids'),
    )),
    'component_source_regions': ('پوشش نواحی منبع', (
        ('سند', 'document_id'), ('صفحه', 'page'), ('ناحیه', 'region_id'), ('نقش شیت', 'sheet_kind'),
        ('وضعیت شناسایی', 'classification_status'), ('خانوادهٔ پیشنهادی', 'classification_families'),
        ('علت بررسی', 'classification_reason'),
    )),
    'component_text_candidates': ('نشان‌ها و عنوان‌های نامزد اجزا', (
        ('سند', 'document_id'), ('صفحه', 'page'), ('نوع شاهد', 'kind'), ('تیپ', 'type_tag'),
        ('خانوادهٔ پیشنهادی', 'family_candidates'), ('مبنای طبقه‌بندی', 'family_basis'),
        ('عنوان شاهد', 'title_preview'), ('وضعیت بررسی', 'status'),
    )),
    'plan_detail_type_only_references': ('ارتباط احتمالی پلان با دیتیل', (
        ('شناسه پلان', 'plan_document_id'), ('صفحه پلان', 'plan_page'),
        ('نوع پلان', 'plan_sheet_kind'), ('تیپ چاپی', 'printed_type_tag'),
        ('نتیجه', 'status'), ('نامزدهای دیتیل', 'candidate_detail_type_ids'),
        ('اجزای هندسی مجاور', 'nearby_operator_component_ids'),
    )),
}

_ENGINEERING_REVIEWS = {
    'occurrence_reviews', 'structural_plan_reviews', 'beam_profile_reviews',
    'beam_end_support_reviews', 'beam_span_evidence_requests', 'multidiscipline_gaps',
    'operator_components', 'plan_detail_type_only_references', 'component_source_regions',
    'component_text_candidates',
}
_DRAWING_SCOPE_FIELDS = (
    ('شناسه گره', 'node_id'), ('تراز', 'level'), ('آکس', 'axis'),
    ('نسخهٔ حاکم', 'governing_revision'),
)

_DETAIL_FIELDS = {
    'operator_components': (('شناسه هندسه', 'component_id'),
                            ('هش PDF مرجع', 'source_pdf_sha256'),
                            ('شناسه عملگرها', 'source_operator_ids'),
                            ('عملگرهای با گوشه فروریخته', 'source_degenerate_operator_ids'),
                            ('بررسی لازم', 'review_required'),
                            ('شناسه عنوان', 'proposed_title_candidate_id'),
                            ('مرز دیتیل معتبر', 'detail_boundary_verified'),
                            ('ارجاع اختصاصی دهانه', 'span_specific_detail_verified'),
                            ('عضو فیزیکی معتبر', 'physical_member_verified'),
                            ('قابل پرداخت مالی', 'financially_payable')),
    'component_source_regions': (('هش PDF مرجع', 'source_pdf_sha256'),
                                 ('کادر ناحیه (pt)', 'bbox_pt'),
                                 ('شناسهٔ اجزای هم‌پوشان', 'overlapping_component_ids'),
                                 ('بررسی لازم', 'review_required')),
    'component_text_candidates': (('هش PDF مرجع', 'source_pdf_sha256'), ('شناسهٔ نامزد', 'candidate_id'),
                                  ('شناسهٔ نواحی', 'region_ids'), ('علت بررسی', 'reason')),
    'plan_detail_type_only_references': (('هش PDF پلان', 'plan_pdf_sha256'),
                                         ('کادر نشان تیپ', 'plan_mark_bbox_pt'),
                                         ('ارجاع پلان به دیتیل', 'plan_to_section_detail_verified'),
                                         ('ارتباط اختصاصی دهانه', 'span_specific_detail_verified'),
                                         ('عضو فیزیکی معتبر', 'physical_member_verified'),
                                         ('قابل پرداخت مالی', 'financially_payable')),
    'multidiscipline_gaps': (('شناسه پوشش', 'coverage_id'),
                             ('هش PDF مرجع', 'source_pdf_sha256'),
                             ('شناسه‌های نواحی', 'source_region_ids'),
                             ('نامزدهای متنی/دیتیل', 'candidate_evidence_ids'),
                             ('نسخه معتبر بررسی‌شده', 'governing_revision_verified'),
                             ('مقیاس معتبر بررسی‌شده', 'drawing_scale_verified'),
                             ('تراز معتبر بررسی‌شده', 'level_scope_verified'),
                             ('تعداد فیزیکی عضو', 'physical_member_count'),
                             ('قابل پرداخت مالی', 'financially_payable')),
    'documents': (('عنوان PDF', 'pdf_title'), ('پروژه', 'project_id'), ('ابلاغ', 'issue_id'),
                  ('سند مرجع', 'authority_reference')),
    'pages': (('نسخهٔ چاپ‌شده', 'printed_revisions'), ('چرخش', 'rotation'),
              ('عنوان شیت', 'sheet_kind'), ('واژهٔ بومی', 'native_pdf_word_count'),
              ('ابهام OCR', 'rendered_ocr_ambiguous_glyph_count'),
              ('ابهام نوشتهٔ برداری', 'vector_text_ambiguous_count'),
              ('خوانش نوشتهٔ برداری', 'vector_text_status'),
              ('مقیاس‌های چاپی', 'printed_scales'), ('خطاهای ورودی صفحه', 'source_errors'),
              ('وضعیت خوانش مسیرها', 'topology_status'), ('کد علت خوانش مسیرها', 'topology_reason_code'),
              ('تعداد مسیرها', 'source_path_count'),
              ('تعداد عملگرهای مسیر', 'source_operator_count'),
              ('تعیین‌تکلیف تمام عملگرها', 'source_operators_accounted_for'),
              ('تحلیل‌پذیری تمام عملگرها', 'all_source_operators_decoded'),
              ('تعداد چهارضلعی‌های فروکاهیده', 'source_degenerate_operator_count'),
              ('شناسه‌های چهارضلعی فروکاهیده', 'source_degenerate_operator_ids'),
              ('بازبینی هندسه فروکاهیده لازم است', 'source_degenerate_quads_review_required'),
              ('تعداد گروه‌ها', 'topology_group_count')),
    'nodes': (('تیپ', 'type_tag'), ('تراز', 'level'), ('آکس', 'axis'),
              ('خانواده‌های نامزد', 'family_candidates'),
              ('کد دیتیل', 'detail_code'), ('مقیاس چاپی', 'printed_scale'),
              ('اعتبار شواهد', 'evidence_quality'), ('شناسه چاپی', 'printed_member_id'),
              ('وضعیت بازبینی شناسه', 'printed_id_review_status'),
              ('وضعیت متره', 'quantity_status'), ('علت توقف متره', 'quantity_reason'),
              ('وضعیت مقیاس', 'scale_status'), ('دامنهٔ ابعاد', 'dimension_scope')),
    'edges': (('کد علت', 'reason_code'),),
    'topology': (('تعداد عملگرهای گروه', 'operator_count'), ('اندیس مسیرها', 'source_path_indices'),),
    'member_review_groups': (('فقط در پلان', 'plan_only_printed_ids'), ('فقط در دیتیل', 'detail_only_printed_ids')),
    'occurrence_reviews': (*_DRAWING_SCOPE_FIELDS, ('علت', 'reason'),
                           ('ردیف شبکه', 'grid_row'), ('ستون شبکه', 'grid_column'),
                           ('مقدار عضو', 'member_quantity'), ('واحد متره', 'quantity_unit'),
                           ('فرمول متره', 'quantity_formula'), ('قابل پرداخت مالی', 'financially_payable')),
    'beam_axis_grid_candidates': (('نام فایل', 'source_name'), ('هش SHA-256', 'source_sha256'),
                                  ('منابع اپراتور', 'source_operator_refs'), ('واحد چاپی', 'printed_unit'),
                                  ('قابل پرداخت مالی', 'financially_payable')),
    'beam_end_marker_pages': (('هش منبع', 'source_sha256'),
                              ('قابل پرداخت مالی', 'financially_payable')),
    'beam_span_evidence_requests': (('شناسه درخواست', 'request_id'),
                                    ('صفحه تیر', 'beam_page'), ('صفحه آکس', 'axis_page'),
                                    ('صفحه دیتیل', 'detail_page'),
                                    ('شاهد هم‌نام دیتیل', 'type_only_detail_matches'),
                                    ('تراز تأییدشده', 'installed_length_verified'),
                                    ('قابل پرداخت مالی', 'financially_payable')),
    'beam_end_support_reviews': (('شناسه بازبینی', 'review_id'),
                                 ('منبع آکس', 'axis_page'), ('صفحه دیتیل', 'detail_page'),
                                 ('شناسه دو انتها', 'endpoint_marker_ids'),
                                 ('تکیه‌گاه اثبات‌شده', 'support_verified'),
                                 ('ارجاع دیتیل اثبات‌شده', 'detail_link_verified'),
                                 ('قابل پرداخت مالی', 'financially_payable')),
    'beam_profile_reviews': (('شناسه بازبینی', 'review_id'),
                             ('شیت آکس مستقل', 'independent_axis_page'),
                             ('شناسه بازبینی آکس', 'independent_axis_review_id'), ('شناسه مرزهای نامزد', 'candidate_review_ids'),
                             ('قابل پرداخت مالی', 'financially_payable')),
    'structural_plan_reviews': (('شناسه بازبینی', 'review_id'), *_DRAWING_SCOPE_FIELDS,
                                ('قابل پرداخت مالی', 'financially_payable')),
}

_EVIDENCE_LABELS = {
    'GOVERNING_DRAWING_ISSUE': 'فهرست شیت‌ها و اصلاحیه ابلاغ‌شده',
    'PHYSICAL_SUPPORT_IDENTITY': 'هویت تکیه‌گاه‌های واقعی دو سر دهانه',
    'SPAN_SPECIFIC_CONNECTION_DETAIL': 'ارجاع اختصاصی دهانه به دیتیل اتصال',
    'INSTALLATION_LEVEL': 'تراز واقعی نصب و محدوده طبقات',
    'FABRICATION_CUT_LENGTH': 'طول برش و کسورات ساخت با تأیید طراح',
    'DIMENSION_UNIT_AND_CALIBRATION': 'واحد و کالیبراسیون معتبر نما',
    'PROFILE_VISUAL_GLYPH_CONFIRMATION': 'رفع ابهام خوانش برداری پروفیل',
    'BOTH_ENDPOINT_MARKERS_RECONCILIATION': 'شاهد مستقل دو نماد انتهایی',
    'TYPE_ONLY_DETAIL_IS_NOT_SPAN_REFERENCE': 'هم‌نامی نوع، ارجاع اختصاصی نیست',

    'OCCURRENCE_IDENTITY': 'شناسهٔ یکتای عضو اجرایی',
    'INDEPENDENT_AXIS': 'شاهد مستقل آکس‌بندی',
    'GOVERNING_REVISION': 'نسخهٔ حاکم سند',
    'OCCURRENCE_DETAIL': 'دیتیل اجرایی این عضو',
    'INSTALLATION_LEVEL_RANGE': 'تراز ابتدا و انتهای نصب',
    'SECTION_DIMENSIONS': 'ابعاد مقطع',
    'MATERIAL': 'جنس و مشخصات مصالح',
    'CONNECTION_SCOPE': 'محدودهٔ اتصال',
    'EXECUTED_LENGTH': 'طول اجرایی',
    'MEASUREMENT_UNIT': 'واحد اندازه‌گیری',
    'DEDUCTIONS': 'کسورات',
    'LOCAL_SCALE_CALIBRATION': 'کالیبراسیون مقیاس موضعی',
    'FLOOR_AND_OVERLAP_SCOPE': 'دامنهٔ طبقات و هم‌پوشانی',
    'DESIGN_AUTHORITY_DECISION': 'تصمیم مرجع طراحی',
}

_OBSERVATION_LABELS = {
    'detail_id_kind': 'وضعیت شناسهٔ دیتیل',
    'section_width_m': 'عرض مقطع (m)',
    'section_depth_m': 'عمق مقطع (m)',
    'length_m': 'طول اجرایی (m)',
    'installation_from_m': 'تراز ابتدای نصب (m)',
    'installation_to_m': 'تراز انتهای نصب (m)',
    'deductions_m3': 'کسورات (m³)',
    'material': 'جنس مصالح',
    'printed_scale': 'مقیاس چاپی',
}

_FOUNDATION_SHEETS = {
    'excavation_plan': 'پلان پی‌کنی',
    'foundation_plan': 'پلان فونداسیون',
}


_COMPONENT_STATUS_LABELS = {
    'CLASSIFIED_CANDIDATE': 'شناسایی پیشنهادی',
    'AMBIGUOUS': 'مبهم، نیازمند بازبینی',
    'NON_MEMBER': 'شاهد غیرعضو',
}


def _display(value):
    if isinstance(value, bool):
        return 'بله' if value else 'خیر'
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
            field = self.columns[index.column()][1]
            value = self.records[index.row()].get(field)
            if field == 'classification_status':
                label = 'مسدود' if value == 'BLOCKED' else _COMPONENT_STATUS_LABELS.get(value)
                if label is not None:
                    return f'{label} [{value}]'
            return _display(value)
        return None


class PDFDetailGraphReview(QWidget):
    def __init__(self, report, parent=None, *, attach_revision_register=None, attach_member_review=None,
                 attach_beam_profile_witnesses=None, attach_beam_axis_labels=None,
                 attach_beam_detail_profile_witnesses=None, open_question=None):
        super().__init__(parent)
        self.setObjectName('PDFDetailEvidenceGraph')
        self.setLayoutDirection(Qt.LayoutDirection.RightToLeft)
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
        self._edges = graph.get('edges', ())
        self._edge_rows = {}
        self._edges_from_node = defaultdict(list)
        for row, edge in enumerate(self._edges):
            self._edge_rows[edge['edge_id']] = row
            self._edges_from_node[edge.get('source_id')].append(edge)
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
            title = (doc.get('metadata') or {}).get('title')
            if title:
                self._documents[doc_id]['pdf_title'] = title
        documents = tuple(self._documents.values())
        self._attach_revision_register = attach_revision_register
        self._attach_member_review = attach_member_review
        self._attach_beam_profile_witnesses = attach_beam_profile_witnesses
        self._attach_beam_axis_labels = attach_beam_axis_labels
        self._attach_beam_detail_profile_witnesses = attach_beam_detail_profile_witnesses
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
        gap_register = report.get('multidiscipline_gap_register')
        if isinstance(gap_register, dict):
            rows_by_table['multidiscipline_gaps'] = gap_register.get('coverage_rows', [])
        component_review = report.get('operator_component_review')
        self._component_text_sources = {}
        if isinstance(component_review, dict):
            rows_by_table['operator_components'] = component_review.get('operator_components', [])
            rows_by_table['plan_detail_type_only_references'] = component_review.get(
                'plan_detail_type_only_references', []
            )
            if 'region_classifications' in component_review:
                rows_by_table['component_source_regions'] = component_review['region_classifications']
                self._component_text_sources = {
                    row['source_id']: row for row in component_review.get('classification_text_witnesses', ())
                }
        detail_index = report.get('detail_object_index')
        if isinstance(detail_index, dict) and 'detail_candidates' in detail_index:
            rows_by_table['component_text_candidates'] = detail_index['detail_candidates']

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

        self.designer_rfi_button = QPushButton('ایجاد درخواست رسمی مدارک طراح (بدون ارسال)', self)
        self.designer_rfi_button.setObjectName('PDFDetailExportDesignerRFI')
        self.designer_rfi_button.setEnabled(
            graph.get('beam_span_request_status') == 'BLOCKED_AWAITING_GOVERNING_ENGINEERING_DOCUMENTS'
            and bool(graph.get('beam_span_evidence_requests'))
        )
        self.designer_rfi_button.clicked.connect(self._export_designer_rfi)
        layout.addWidget(self.designer_rfi_button, alignment=Qt.AlignmentFlag.AlignRight)
        self.designer_reply_button = QPushButton('بررسی فایل پاسخ طراح، فقط ثبت دریافت', self)
        self.designer_reply_button.setObjectName('PDFDetailInspectDesignerReply')
        self.designer_reply_button.setEnabled(self.designer_rfi_button.isEnabled())
        self.designer_reply_button.clicked.connect(self._inspect_designer_reply)
        layout.addWidget(self.designer_reply_button, alignment=Qt.AlignmentFlag.AlignRight)
        self.designer_reply_status = QLabel(self)
        self.designer_reply_status.setObjectName('PDFDetailDesignerReplyStatus')
        self.designer_reply_status.setTextFormat(Qt.TextFormat.PlainText)
        self.designer_reply_status.setWordWrap(True)
        self.designer_reply_status.hide()
        layout.addWidget(self.designer_reply_status)
        self._designer_reply_receipt = None
        self.designer_crosswalk_button = QPushButton(
            'ذخیره تطبیق سؤال، شیت و مدرک طراح (فقط بررسی، JSON)', self
        )
        self.designer_crosswalk_button.setObjectName('PDFDetailExportDesignerReplyCrosswalk')
        self.designer_crosswalk_button.setEnabled(False)
        self.designer_crosswalk_button.clicked.connect(self._export_designer_reply_crosswalk)
        layout.addWidget(self.designer_crosswalk_button, alignment=Qt.AlignmentFlag.AlignRight)

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

        if attach_beam_profile_witnesses is not None:
            self.beam_profile_button = QPushButton('پیوست قرائت تصویری پروفیل‌های تیر (JSON)', self)
            self.beam_profile_button.setObjectName('PDFDetailAttachBeamProfileWitnesses')
            self.beam_profile_button.clicked.connect(self._pick_beam_profile_witnesses)
            layout.addWidget(self.beam_profile_button, alignment=Qt.AlignmentFlag.AlignRight)
            self.beam_profile_status = QLabel(self)
            self.beam_profile_status.setTextFormat(Qt.TextFormat.PlainText)
            self.beam_profile_status.setWordWrap(True)
            self.beam_profile_status.hide()
            layout.addWidget(self.beam_profile_status)

        if attach_beam_axis_labels is not None:
            self.beam_axis_button = QPushButton('پیوست برچسب و فاصله آکس مستقل (JSON)', self)
            self.beam_axis_button.setObjectName('PDFDetailAttachIndependentBeamAxis')
            self.beam_axis_button.clicked.connect(self._pick_beam_axis_labels)
            layout.addWidget(self.beam_axis_button, alignment=Qt.AlignmentFlag.AlignRight)
            self.beam_axis_status = QLabel(self)
            self.beam_axis_status.setTextFormat(Qt.TextFormat.PlainText)
            self.beam_axis_status.setWordWrap(True)
            self.beam_axis_status.hide()
            layout.addWidget(self.beam_axis_status)

        if attach_beam_detail_profile_witnesses is not None:
            self.beam_detail_button = QPushButton('پیوست شاهد تصویری دیتیل اتصال تیر (JSON)', self)
            self.beam_detail_button.setObjectName('PDFDetailAttachBeamConnectionDetails')
            self.beam_detail_button.clicked.connect(self._pick_beam_detail_profile_witnesses)
            layout.addWidget(self.beam_detail_button, alignment=Qt.AlignmentFlag.AlignRight)
            self.beam_detail_status = QLabel(self)
            self.beam_detail_status.setTextFormat(Qt.TextFormat.PlainText)
            self.beam_detail_status.setWordWrap(True)
            self.beam_detail_status.hide()
            layout.addWidget(self.beam_detail_status)

        split = QSplitter(Qt.Orientation.Vertical, self)
        layout.addWidget(split)
        self.sections = QTabWidget(split)
        self.tables = {}
        self.filters = {}
        self._section_keys = []
        for key, (title, columns) in _TABLES.items():
            if key in _ENGINEERING_REVIEWS and key not in rows_by_table:
                continue
            self._section_keys.append(key)
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
        self.related_evidence_button = QToolButton(detail_panel)
        self.related_evidence_button.setObjectName('PDFDetailGraphRelatedEvidence')
        self.related_evidence_button.setText('آکس‌ها و پیوندها')
        self.related_evidence_button.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonTextOnly)
        self.related_evidence_button.setPopupMode(QToolButton.ToolButtonPopupMode.InstantPopup)
        self.related_evidence_button.setMenu(QMenu(self.related_evidence_button))
        navigation.addWidget(self.related_evidence_button)
        self.question_button = QPushButton('ثبت اصلاح یا درخواست مدرک', detail_panel)
        self.question_button.setObjectName('PDFDetailGraphOpenReviewQuestion')
        self.question_button.clicked.connect(self._review_selected_issue)
        navigation.addWidget(self.question_button)
        detail_layout.addLayout(navigation)
        split.setStretchFactor(0, 3)
        split.setStretchFactor(1, 2)
        self.sections.currentChanged.connect(self._refresh_selection)
        self._refresh_selection()

    def _current_designer_rfi_packet(self):
        graph = self._source_report['detail_evidence_graph']
        docs = self._source_report.get('documents') or []
        if len(docs) != 1 or not graph.get('graph_sha256'):
            raise ValueError('برای ثبت درخواست طراح، یک PDF و رسید معتبر گراف لازم است.')
        data = {'status': graph.get('beam_span_request_status'),
                'requests': graph.get('beam_span_evidence_requests', [])}
        return build_designer_rfi_packet(
            data, source_sha256=docs[0]['sha256'], source_name=docs[0]['source_name'],
            graph_sha256=graph['graph_sha256'],
        )

    def _export_designer_rfi(self):
        folder = QFileDialog.getExistingDirectory(self, 'انتخاب پوشه خصوصی ذخیره درخواست طراح')
        if not folder:
            return
        try:
            packet = self._current_designer_rfi_packet()
            directory = Path(folder) / ('StructuralPro_RFI_' + packet['packet_sha256'][:12])
            if directory.exists():
                raise ValueError('پوشه درخواست قبلاً وجود دارد؛ بازنویسی ممنوع است.')
            write_designer_rfi_package(packet, directory)
        except (OSError, ValueError, KeyError) as exc:
            self.designer_reply_status.setText('خروجی درخواست مدارک ساخته نشد: ' + str(exc))
        else:
            self.designer_reply_status.setText(
                'درخواست مدارک فقط در مسیر انتخابی ذخیره شد، ارسال نشده و هیچ مقدار مالی تأیید نشد: '
                + str(directory)
            )
        self.designer_reply_status.show()

    def _inspect_designer_reply(self):
        name, _ = QFileDialog.getOpenFileName(self, 'انتخاب پاسخ مستند طراح', '', 'JSON (*.json)')
        if not name:
            return
        try:
            packet = self._current_designer_rfi_packet()
            source = Path(name)
            response = inspect_designer_reply(
                packet, load_designer_reply(source), attachment_directory=source.parent,
            )
        except (OSError, ValueError, KeyError) as exc:
            self._designer_reply_receipt = None
            self.designer_crosswalk_button.setEnabled(False)
            self.designer_reply_status.setText('پاسخ رد شد؛ گراف قبلی تغییری نکرد: ' + str(exc))
        else:
            self._designer_reply_receipt = response
            self.designer_crosswalk_button.setEnabled(True)
            self.designer_reply_status.setText(
                f"{response['received_evidence_count']} شاهد دریافت شد؛ "
                f"{response['questions_with_all_evidence_received']} درخواست با همه کدهای مدرک، "
                f"{response['questions_partially_received']} ناقص، "
                f"{response['questions_still_without_response']} بدون پاسخ. "
                'کامل بودن کدها فقط رسید دریافت است، نه اصالت یا تأیید مهندسی. '
                'همه اعضا و متره‌ها همچنان مسدود هستند.'
            )
        self.designer_reply_status.show()

    def _export_designer_reply_crosswalk(self):
        if self._designer_reply_receipt is None:
            self.designer_reply_status.setText('هیچ رسید پاسخ معتبر برای خروجی وجود ندارد.')
            self.designer_reply_status.show()
            return
        name, _ = QFileDialog.getSaveFileName(
            self, 'ذخیره تطبیق خصوصی ارجاعات پاسخ طراح',
            'PRIVATE_DESIGNER_REPLY_CROSSWALK.json', 'JSON (*.json)'
        )
        if not name:
            return
        try:
            packet = self._current_designer_rfi_packet()
            write_designer_reply_crosswalk(packet, self._designer_reply_receipt, name)
        except (OSError, ValueError, KeyError) as exc:
            self.designer_reply_status.setText('تطبیق ذخیره نشد؛ فایل موجود بازنویسی نمی‌شود: ' + str(exc))
        else:
            self.designer_reply_status.setText(
                'تطبیق منبع و ارجاعات PDF پاسخ در فایل خصوصی ثبت شد، نه تأیید '
                'هویت عضو، اتصال دهانه، ابعاد، نسخه حاکم یا متره مالی.'
            )
        self.designer_reply_status.show()

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

    def _pick_beam_profile_witnesses(self):
        path, _ = QFileDialog.getOpenFileName(self, 'انتخاب مشاهدات تصویری پروفیل تیر', '', 'JSON (*.json)')
        if not path:
            return
        try:
            self._attach_beam_profile_witnesses(path)
        except (OSError, ValueError, RuntimeError) as exc:
            self.beam_profile_status.setText(f'قرائت تصویری پیوست نشد؛ گزارش قبلی محفوظ است.\\n{exc}')
            self.beam_profile_status.show()

    def _pick_beam_axis_labels(self):
        path, _ = QFileDialog.getOpenFileName(self, 'انتخاب رسید مستقل آکس', '', 'JSON (*.json)')
        if not path:
            return
        try:
            self._attach_beam_axis_labels(path)
        except (OSError, ValueError, RuntimeError) as exc:
            self.beam_axis_status.setText(f'شاهد آکس مستقل پیوست نشد؛ گزارش قبلی محفوظ است.\\n{exc}')
            self.beam_axis_status.show()

    def _pick_beam_detail_profile_witnesses(self):
        path, _ = QFileDialog.getOpenFileName(self, 'انتخاب شاهد تصویری اتصال تیر', '', 'JSON (*.json)')
        if not path:
            return
        try:
            self._attach_beam_detail_profile_witnesses(path)
        except (OSError, ValueError, RuntimeError) as exc:
            self.beam_detail_status.setText('شاهد دیتیل پذیرفته نشد؛ گزارش پیشین محفوظ است.\\n' + str(exc))
            self.beam_detail_status.show()

    def _refresh_selection(self, *_):
        key = self._section_keys[self.sections.currentIndex()]
        view = self.tables[key]
        proxy = view.model()
        selected = view.selectionModel().selectedRows()
        self._endpoint_ids = {}
        self._question_tag = None
        has_related_evidence = False
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
            elif key in _ENGINEERING_REVIEWS:
                lines.extend(self._engineering_review_lines(key, record))
                has_related_evidence = self._populate_related_evidence(record)
            if key != 'documents':
                anchors = record.get('anchors', ())
                if key != 'pages' or anchors:
                    lines.extend(self._anchor_lines('نشانی شواهد', anchors))
            self.details.setPlainText('\n'.join(lines))
        for role, button in self._endpoint_buttons.items():
            button.setVisible(role in self._endpoint_ids)
            button.setEnabled(self._endpoint_ids.get(role) in self._node_rows)
        self.related_evidence_button.setVisible(has_related_evidence)
        self.question_button.setVisible(bool(self._question_tag and self._open_question))

    def _engineering_review_lines(self, key, record):
        lines = []
        if key in {'operator_components', 'component_source_regions', 'component_text_candidates'}:
            lines.append('تأیید مهندسی نشده | قابل پرداخت مالی — خیر')
            source = {
                'document_id': record.get('document_id'), 'page': record.get('page'),
                'source_sha256': record.get('source_pdf_sha256'),
            }
            title = record.get('classification_title')
            words = (self._component_text_sources[ref] for ref in record.get('source_type_word_ids', ())
                     if ref in self._component_text_sources)
            anchors = [{**source, **word, 'kind': word['method'], 'anchor_id': word['source_id'],
                        'raw_token': word.get('source_token'), 'source_ref': word['status']}
                       for word in words]
            if title:
                anchors.append({**source, **title, 'kind': title['method'], 'anchor_id': title['source_id']})
            anchors.extend({**source, **word, 'kind': 'NATIVE_TYPE_WORD', 'anchor_id': word['witness_id']}
                           for word in record.get('source_word_witnesses', ()))
            if record.get('title_preview') and record.get('bbox_pt'):
                anchors.append({**source, 'kind': 'NATIVE_TITLE_BLOCK', 'anchor_id': record.get('title_anchor_id'),
                                'bbox_pt': record['bbox_pt'], 'raw_token': record['title_preview']})
            lines.extend(self._anchor_lines('شاهد متن و عنوان', anchors))
        missing = record.get('missing_evidence', ())
        if missing:
            lines.extend(['', 'مدارک لازم برای رفع ابهام'])
            for code in missing:
                label = _EVIDENCE_LABELS.get(code)
                lines.append(f'{label} [{code}]' if label else code)
        observations = [
            f'{_OBSERVATION_LABELS.get(name, name)} — {_display(value)}'
            for name, value in (record.get('observations') or {}).items() if value is not None
        ]
        if observations:
            lines.extend(['', 'مشاهدات نقشه'])
            lines.extend(observations)
        sheet_counts = record.get('sheet_mark_counts', ())
        if sheet_counts:
            lines.extend(['', 'فراوانی نشانه‌های چاپی'])
            for sheet in sheet_counts:
                sheet_kind = _FOUNDATION_SHEETS.get(sheet['sheet_kind'], sheet['sheet_kind'])
                lines.append(f"{self._source_label(sheet)} | صفحه {sheet['page']} | {sheet_kind} — {sheet['count']}")
        source_id = record.get('source_id')
        target_id = record.get('target_id')
        self._endpoint_ids = {'source': source_id, 'target': target_id}
        if record.get('node_id') not in (None, source_id, target_id):
            self._endpoint_ids['related'] = record['node_id']
        conflicts = record.get('conflicting_anchors', ())
        if conflicts:
            lines.extend(self._anchor_lines('شواهد ناسازگار', conflicts))
        lines.extend(self._endpoint_lines('شاهد پلان', source_id))
        target_label = 'شاهد دیتیل' if key == 'occurrence_reviews' else 'شاهد مرتبط'
        lines.extend(self._endpoint_lines(target_label, target_id))
        for axis_id in record.get('axis_node_ids', ()):
            lines.extend(self._endpoint_lines('شاهد آکس', axis_id))
        return lines

    def _populate_related_evidence(self, record):
        menu = self.related_evidence_button.menu()
        menu.clear()
        axes = record.get('axis_node_ids', ())
        for axis_id in dict.fromkeys(axes):
            row = self._node_rows.get(axis_id)
            if row is not None:
                label = self._nodes[row]['label'].replace('&', '&&')
                menu.addAction(f'آکس — {label}', partial(self._navigate_to_record, 'nodes', axis_id))

        source_ids = dict.fromkeys((record.get('source_id'), record.get('node_id')))
        targets = {record.get('target_id'), *axes}
        edge_ids = dict.fromkeys(record.get('edge_ids', ()))
        for source_id in source_ids:
            for edge in self._edges_from_node.get(source_id, ()):
                if edge.get('target_id') in targets:
                    edge_ids[edge['edge_id']] = None
        for edge_id in edge_ids:
            row = self._edge_rows.get(edge_id)
            if row is not None:
                edge = self._edges[row]
                label = f"پیوند — {edge['relationship']} | {edge['status']} | {edge_id}"
                menu.addAction(label, partial(self._navigate_to_record, 'edges', edge_id))
        return not menu.isEmpty()

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
        displayed_sources = set()
        for anchor in anchors:
            doc_id = anchor.get('document_id')
            document = self._documents.get(doc_id, {})
            source = self._source_label(anchor)
            box = anchor.get('bbox_pt')
            coords = '[' + ', '.join(str(coord) for coord in box) + ']' if box else '—'
            witness = f'{_display(anchor.get("kind"))} {_display(anchor.get("anchor_id"))}'
            lines.append(f'{source} | صفحه {_display(anchor.get("page"))} | کادر (pt) {coords} | {witness}')
            digest = anchor.get('source_sha256') or document.get('sha256')
            if (doc_id, digest) not in displayed_sources:
                title = document.get('pdf_title')
                if title:
                    lines.append(f'عنوان PDF — {title}')
                if digest:
                    lines.append(f'هش سند SHA-256 — {digest}')
                displayed_sources.add((doc_id, digest))
            for label, field in (
                ('نوشتهٔ خام', 'raw_token'), ('خوانش استاندارد', 'normalized_tag'),
                ('نوشتهٔ چاپ‌شده', 'printed'), ('عنوان منبع', 'title'),
                ('نوشتهٔ بومی PDF', 'source_token'), ('معرف شاهد در منبع', 'source_ref'),
                ('خوانش‌های ممکن', 'glyph_interpretations'), ('علت ابهام برداری', 'glyph_ambiguity_reason'),
                ('نوع بُعد', 'dimension_kind'), ('بُعد چاپی (m)', 'dimension_m'),
            ):
                if field in anchor:
                    lines.append(f'{label} — {_display(anchor[field])}')
        return lines

    def _source_label(self, evidence):
        doc_id = evidence.get('document_id')
        name = evidence.get('source_name') or self._documents.get(doc_id, {}).get('source_name')
        return f'{name} ({doc_id})' if name else _display(doc_id)

    def _navigate_to_endpoint(self, role):
        self._navigate_to_record('nodes', self._endpoint_ids.get(role))

    def _navigate_to_record(self, key, record_id):
        rows = self._node_rows if key == 'nodes' else self._edge_rows
        row = rows.get(record_id)
        if row is None:
            return
        table = self.tables[key]
        proxy = table.model()
        source_index = proxy.sourceModel().index(row, 0)
        index = proxy.mapFromSource(source_index)
        if not index.isValid():
            self.filters[key].clear()
            index = proxy.mapFromSource(source_index)
        self.sections.setCurrentIndex(self._section_keys.index(key))
        table.setCurrentIndex(index)
        table.scrollTo(index)
