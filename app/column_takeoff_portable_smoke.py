"""Unmocked PDF extraction and worksheet smoke for the frozen application."""

from decimal import Decimal
from hashlib import sha256
import json
from pathlib import Path
import traceback
from unittest.mock import patch

import pymupdf
from openpyxl import load_workbook
from PySide6.QtGui import QGuiApplication

from app.pdf_column_takeoff_panel import QFileDialog, QMessageBox
from core.drawings.pdf_vector_type_labels import _C, _ONE, _TWO


def make_synthetic_column_pdf(destination, first_length, second_length):
    """Invent a small, two-type CAD drawing with printed metric lengths."""
    xs, ys = (105, 253, 420), (122, 252, 409)
    with pymupdf.open() as pdf:
        plan = pdf.new_page(width=722, height=547)
        plan.insert_text((38, 45), 'Column Type Plan')
        for x in xs:
            plan.draw_line((x, ys[0]), (x, ys[-1]))
        for y in ys:
            plan.draw_line((xs[0], y), (xs[-1], y))

        def glyph(template, x, y, width):
            shape = plan.new_shape()
            shape.draw_polyline([(x + u*width, y + v*9) for u, v in template])
            shape.finish(width=0.18, closePath=False)
            shape.commit()

        for level, y in enumerate(ys):
            for x in xs:
                plan.draw_rect((x-3, y-3, x+3, y+3))
                glyph(_C, x+8, y+9, 6)
                glyph(_ONE if level == 0 else _TWO, x+17, y+9, 1.5 if level == 0 else 5.7)
        details = pdf.new_page(width=722, height=547)
        details.insert_text((38, 45), 'Column Details')
        details.insert_text((70, 132), f'C1 L={first_length} m')
        details.insert_text((70, 270), f'C2 L={second_length} m')
        pdf.save(destination)


def _expect(condition, message):
    if not condition:
        raise AssertionError(message)


def run_smoke(app, window, directory):
    directory = Path(directory)
    directory.mkdir(parents=True, exist_ok=True)
    checks = {}
    receipt = {'status': 'FAIL', 'checks': checks, 'qt_platform': QGuiApplication.platformName()}
    panel = window.centralWidget()
    first = directory / 'نقشه-یک.pdf'
    second = directory / 'نقشه-دو.pdf'
    bad = directory / 'خراب.pdf'
    workbook = directory / 'متره-آزمایشی.xlsx'

    def select(path):
        # Supply a filename to the actual Qt chooser slot without opening a modal dialog.
        with patch.object(QFileDialog, 'getOpenFileName', return_value=(str(path), 'PDF (*.pdf)')):
            panel.choose_button.click()
        app.processEvents()

    try:
        make_synthetic_column_pdf(first, '3.5', '6.25')
        make_synthetic_column_pdf(second, '2.25', '5')
        bad.write_bytes(b'not a PDF')
        app.processEvents()
        _expect(window.isVisible() and panel.extract_button.isVisible(), 'Qt window did not initialize')
        checks['qt_window'] = 'PASS'

        select(first)
        panel.extract_button.click()
        draft = panel.schedule
        expected_length = 3*Decimal('3.5') + 6*Decimal('6.25')
        _expect(draft and draft['page_count'] == 2 and draft['draft_node_count'] == 9,
                f'synthetic source was not counted from the PDF: {panel.receipt.text()}')
        _expect(Decimal(draft['draft_extended_length_total_m']) == expected_length,
                'synthetic source printed lengths did not match')
        _expect(all(row['source_operator_ids'] and row['detail_page'] == 2 for row in draft['rows']),
                'synthetic source operator and detail evidence missing')
        checks['pdf_extraction'] = 'PASS'

        panel.scenario_ack.setChecked(True)
        panel.weight_button.click()
        old = Decimal(panel.weight_preview['draft_weight_total_kg'])
        for i in range(panel.assumptions.rowCount()):
            panel.assumptions.item(i, 4).setText('3')
            panel.assumptions.item(i, 5).setText('8.25')
        app.processEvents()
        expected_weight = expected_length*3*Decimal('8.25')
        _expect(panel.weight_preview and Decimal(panel.weight_preview['draft_weight_total_kg']) == expected_weight
                and expected_weight != old, 'edited steel assumptions did not re-evaluate')
        checks['scenario_edit'] = 'PASS'

        with patch.object(QFileDialog, 'getSaveFileName', return_value=(str(workbook), 'Excel (*.xlsx)')), \
                patch.object(QMessageBox, 'information'):
            panel.export_button.click()
        book = load_workbook(workbook, data_only=False)
        try:
            _expect(book['Preview']['B11'].data_type == 'f', 'Excel weight total is not recalculable')
            _expect(Decimal(str(book['Preview']['C11'].value)) == expected_weight, 'Excel snapshot weight mismatch')
            _expect(book['PDF positions'].max_row == 10 and book['PDF positions']['K2'].value.startswith('["PDF001:'),
                    'Excel PDF source evidence missing')
            _expect(book['Preview']['B5'].value == book['Preview']['B6'].value == 'NO'
                    and not draft['financially_payable'] and not panel.weight_preview['financially_payable'],
                    'worksheet emitted financial or engineering approval')
        finally:
            book.close()
        checks['excel_roundtrip'] = 'PASS'
        checks['persian_paths'] = 'PASS'
        checks['nonfinancial_only'] = 'PASS'
        window.grab().save(str(directory / 'synthetic-qt-window.png'))

        select(second)
        _expect(panel.schedule is None and panel.weight_preview is None and not panel.export_button.isEnabled(),
                'switching PDF left stale takeoff state')
        panel.extract_button.click()
        changed = panel.schedule
        _expect(changed and changed['document_sha256'] == sha256(second.read_bytes()).hexdigest()
                and Decimal(changed['draft_extended_length_total_m']) == 3*Decimal('2.25') + 6*Decimal('5'),
                'second drawing did not produce its own data')
        checks['file_switch'] = 'PASS'
        select(bad)
        panel.extract_button.click()
        _expect(panel.schedule is None and panel.weight_preview is None and not panel.export_button.isEnabled(),
                'invalid PDF retained a usable prior quantity')
        _expect('ناموفق' in panel.receipt.text() or 'نامعتبر' in panel.receipt.text(),
                'invalid PDF did not display an error')
        checks['invalid_pdf'] = 'PASS'
        receipt['status'] = 'PASS'
    except Exception:
        receipt['traceback'] = traceback.format_exc()
    finally:
        (directory / 'portable-smoke.json').write_text(json.dumps(receipt, ensure_ascii=False, indent=2), encoding='utf-8')
    return 0 if receipt['status'] == 'PASS' else 1
