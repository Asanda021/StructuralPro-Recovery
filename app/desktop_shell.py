"""Presentation-only controls for the Windows-first RTL shell.

The ribbon always runs existing commands; collapsing it only changes window
presentation. No project, BOQ, drawing or autosave data is modified here.
"""
from __future__ import annotations

from PySide6.QtCore import QObject, QPropertyAnimation, QEasingCurve
from PySide6.QtWidgets import QGraphicsOpacityEffect, QPushButton, QWidget


class ContextRibbonController(QObject):
    """Keyboard-accessible, persistent, optional motion for the real ribbon."""

    def __init__(self, ribbon: QWidget, preferences, parent: QObject | None = None):
        super().__init__(parent or ribbon)
        self.ribbon = ribbon
        self.preferences = preferences
        self.settings = preferences.settings
        self.collapsed = self.settings.value('ribbon_collapsed', False, type=bool)
        self.toggle_button = QPushButton()
        self.toggle_button.setObjectName('RibbonToggle')
        self.toggle_button.setAccessibleName('نمایش یا جمع‌کردن نوار ابزار زمینه‌ای')
        self.toggle_button.setToolTip('نمایش یا جمع‌کردن ابزارهای تب فعال (Ctrl+Shift+R)')
        self.toggle_button.setCheckable(True)
        self.toggle_button.clicked.connect(self.toggle)
        self.effect = QGraphicsOpacityEffect(self.ribbon)
        self.ribbon.setGraphicsEffect(self.effect)
        self.animation = QPropertyAnimation(self.effect, b'opacity', self)
        self.animation.setEasingCurve(QEasingCurve.Type.InOutQuad)
        self.animation.finished.connect(self._finish_animation)
        self._set_initial_state()

    def _label(self):
        self.toggle_button.setChecked(self.collapsed)
        self.toggle_button.setText('نمایش نوار ابزار' if self.collapsed else 'جمع‌کردن نوار ابزار')

    def _set_initial_state(self):
        self._label()
        self.effect.setOpacity(1.0)
        self.ribbon.setVisible(not self.collapsed)

    def toggle(self, _checked=False):
        self.set_collapsed(not self.collapsed)

    def set_collapsed(self, collapsed: bool, *, animate=True):
        collapsed = bool(collapsed)
        if self.animation.state() == QPropertyAnimation.State.Running:
            self.animation.stop()
        if collapsed == self.collapsed:
            self._label()
            return
        self.collapsed = collapsed
        self.settings.setValue('ribbon_collapsed', collapsed)
        self.settings.sync()
        self._label()
        if animate and self.preferences.animations:
            self.ribbon.show()
            self.animation.setDuration(150)
            self.animation.setStartValue(1.0 if collapsed else 0.0)
            self.animation.setEndValue(0.0 if collapsed else 1.0)
            self.effect.setOpacity(1.0 if collapsed else 0.0)
            self.animation.start()
        else:
            self.effect.setOpacity(1.0)
            self.ribbon.setVisible(not collapsed)

    def _finish_animation(self):
        if self.collapsed:
            self.ribbon.hide()
        self.effect.setOpacity(1.0)

    def refresh_after_command_change(self):
        """Never let a page change reopen a user-collapsed ribbon."""
        if self.collapsed and self.animation.state() != QPropertyAnimation.State.Running:
            self.ribbon.hide()
