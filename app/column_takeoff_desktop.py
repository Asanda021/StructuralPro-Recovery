"""Standalone offline entry point for the StructuralPro column worksheet."""

import argparse
import os
from pathlib import Path
import sys

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QApplication, QMainWindow

from app.pdf_column_takeoff_panel import PDFColumnTakeoffPanel


def make_window(source=None):
    window = QMainWindow()
    window.setWindowTitle('StructuralPro | متره آزمایشی ستون')
    window.resize(1200, 790)
    window.setMinimumSize(740, 580)
    sources = {'PDF001': str(source)} if source else None
    window.setCentralWidget(PDFColumnTakeoffPanel(source_paths=sources, parent=window))
    return window


def main(argv=None):
    parser = argparse.ArgumentParser(description='StructuralPro offline draft column takeoff')
    parser.add_argument('pdf', type=Path, nargs='?')
    parser.add_argument('--smoke-test', type=Path, metavar='DIRECTORY',
                        help='Run the synthetic frozen-application check and save its receipt.')
    args = parser.parse_args(argv)
    if args.smoke_test:
        os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
    app = QApplication.instance() or QApplication([sys.argv[0]])
    app.setApplicationName('StructuralPro')
    app.setLayoutDirection(Qt.LayoutDirection.RightToLeft)
    window = make_window(args.pdf)
    window.show()
    if args.smoke_test:
        from app.column_takeoff_portable_smoke import run_smoke

        try:
            return run_smoke(app, window, args.smoke_test)
        finally:
            window.close()
    return app.exec()


if __name__ == '__main__':
    raise SystemExit(main())
