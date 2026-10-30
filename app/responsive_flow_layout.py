"""Responsive wrapping layout for existing Qt tool strips.

Only presentation geometry changes when a viewer is narrow or DPI is high.
The original widgets, object names, signal wiring and engineering services stay
untouched. Vertical scrolling is preferable to hiding unpriced/verified tools.
"""
from PySide6.QtCore import QPoint, QRect, QSize, Qt
from PySide6.QtWidgets import QLayout


class ResponsiveFlowLayout(QLayout):
    """Place complete controls on another row instead of clipping them.

    Minimum width is that of the widest control, not the sum of the strip.
    addStretch is a compatibility no-op: spacing is controlled by wrap.
    """

    def __init__(self, parent=None, *, spacing=8):
        super().__init__(parent)
        self._items = []
        self.setSpacing(spacing)

    def addItem(self, item):
        self._items.append(item)

    def addStretch(self, _stretch=0):
        # Reflow makes an expanding horizontal spacer unnecessary.
        return None

    def count(self):
        return len(self._items)

    def itemAt(self, index):
        return self._items[index] if 0 <= index < len(self._items) else None

    def takeAt(self, index):
        return self._items.pop(index) if 0 <= index < len(self._items) else None

    def expandingDirections(self):
        return Qt.Orientations()

    def hasHeightForWidth(self):
        return True

    def heightForWidth(self, width):
        return self._layout(QRect(0, 0, max(1, width), 0), measure=True)

    def setGeometry(self, rect):
        super().setGeometry(rect)
        self._layout(rect, measure=False)

    def minimumSize(self):
        size = QSize(0, 0)
        for item in self._items:
            if item.isEmpty():
                continue
            hint = item.minimumSize()
            size.setWidth(max(size.width(), hint.width()))
            size.setHeight(max(size.height(), hint.height()))
        left, top, right, bottom = self.getContentsMargins()
        return size + QSize(left + right, top + bottom)

    def sizeHint(self):
        return self.minimumSize()

    def _layout(self, rect, *, measure):
        left, top, right, bottom = self.getContentsMargins()
        effective = rect.adjusted(left, top, -right, -bottom)
        x, y = effective.x(), effective.y()
        line_height = 0
        hspace = max(self.spacing(), 0)
        vspace = hspace
        for item in self._items:
            if item.isEmpty():
                continue
            hint = item.sizeHint()
            width, height = hint.width(), hint.height()
            # At very small dock widths a single long control still fits.
            width = min(width, max(1, effective.width()))
            next_x = x + width + hspace
            if line_height and next_x - hspace > effective.right() + 1:
                x = effective.x()
                y += line_height + vspace
                next_x = x + width + hspace
                line_height = 0
            if not measure:
                item.setGeometry(QRect(QPoint(x, y), QSize(width, height)))
            x = next_x
            line_height = max(line_height, height)
        return (y + line_height - rect.y()) + bottom
