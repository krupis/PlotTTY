"""Compact plot rendering badge with a visual, keyboard-accessible picker."""

from PySide6.QtCore import QPoint, QSize, Qt, Signal
from PySide6.QtGui import QIcon, QPainter
from PySide6.QtWidgets import QDialog, QHBoxLayout, QLabel, QPushButton, QToolButton, QVBoxLayout

import rc_resources  # noqa: F401


PLOT_STYLES = {"lines": "Analog", "digital": "Digital", "dots": "Dots"}
MODE_DESCRIPTIONS = {
    "lines": "Straight connections between samples",
    "digital": "Hold each value; draw vertical edges",
    "dots": "Sample points without connections",
}
MODE_ICONS = {
    "lines": ":/icons/waveform-analog.svg",
    "digital": ":/icons/waveform-digital.svg",
    "dots": ":/icons/waveform-dots.svg",
}


class _ModeOption(QPushButton):
    def __init__(self, mode, parent):
        super().__init__(parent)
        self.setObjectName("PlotModeOption")
        self.setCheckable(True)
        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        self.setAccessibleName(PLOT_STYLES[mode])
        self.setAccessibleDescription(MODE_DESCRIPTIONS[mode])
        self.setMinimumHeight(58)
        layout = QHBoxLayout(self)
        layout.setContentsMargins(12, 8, 12, 8)
        layout.setSpacing(14)
        waveform = QLabel(self)
        waveform.setPixmap(QIcon(MODE_ICONS[mode]).pixmap(QSize(40, 24)))
        waveform.setFixedSize(40, 24)
        layout.addWidget(waveform)
        labels = QVBoxLayout()
        labels.setSpacing(3)
        self.title = QLabel(PLOT_STYLES[mode], self)
        self.title.setObjectName("PlotModeOptionTitle")
        description = QLabel(MODE_DESCRIPTIONS[mode], self)
        description.setObjectName("PlotModeDescription")
        labels.addWidget(self.title)
        labels.addWidget(description)
        layout.addLayout(labels, 1)
        self.checkmark = QLabel(self)
        self.checkmark.setPixmap(QIcon(":/icons/check-teal.svg").pixmap(QSize(14, 14)))
        self.checkmark.setObjectName("PlotModeCheckmark")
        self.checkmark.setFixedWidth(16)
        layout.addWidget(self.checkmark)
        for label in (waveform, self.title, description, self.checkmark):
            label.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)

    def set_selected(self, selected):
        self.setChecked(selected)
        self.checkmark.setVisible(selected)
        self.title.setProperty("selected", selected)
        self.title.style().unpolish(self.title)
        self.title.style().polish(self.title)

    def keyPressEvent(self, event):
        if event.key() in (Qt.Key.Key_Up, Qt.Key.Key_Down):
            self.parentWidget().move_focus(-1 if event.key() == Qt.Key.Key_Up else 1)
            event.accept()
        else:
            super().keyPressEvent(event)


class _ModePicker(QDialog):
    modeSelected = Signal(str)

    def __init__(self, parent):
        super().__init__(parent, Qt.WindowType.Popup)
        self.setObjectName("PlotModePicker")
        self.setWindowTitle("Rendering mode")
        self.setMinimumWidth(340)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(8, 10, 8, 8)
        layout.setSpacing(4)
        heading = QLabel("RENDERING MODE", self)
        heading.setObjectName("PlotModePickerHeading")
        heading.setContentsMargins(8, 0, 0, 4)
        layout.addWidget(heading)
        self.options = {}
        for mode in PLOT_STYLES:
            option = _ModeOption(mode, self)
            option.clicked.connect(lambda _checked, mode=mode: self._select(mode))
            self.options[mode] = option
            layout.addWidget(option)

    def _select(self, mode):
        self.modeSelected.emit(mode)
        self.hide()

    def move_focus(self, offset):
        options = list(self.options.values())
        focused = self.focusWidget()
        index = options.index(focused) if focused in options else 0
        options[(index + offset) % len(options)].setFocus()

    def show_below(self, anchor, mode):
        for key, option in self.options.items():
            selected = key == mode
            option.set_selected(selected)
        self.adjustSize()
        origin = anchor.mapToGlobal(QPoint(0, anchor.height() + 4))
        available = anchor.screen().availableGeometry()
        x = max(available.left(), min(origin.x(), available.right() - self.width() + 1))
        y = origin.y()
        if y + self.height() > available.bottom() + 1:
            y = anchor.mapToGlobal(QPoint(0, -self.height() - 4)).y()
        y = max(available.top(), min(y, available.bottom() - self.height() + 1))
        self.move(x, y)
        self.show()
        self.options[mode].setFocus()


class PlotModeButton(QToolButton):
    modeSelected = Signal(str)

    def __init__(self, label, parent=None):
        super().__init__(parent)
        self.setObjectName("PlotModeBadge")
        self.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonTextBesideIcon)
        self.setIconSize(QSize(24, 18))
        self._chevron = QIcon(":/icons/combo-chevron.svg")
        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        self._label = label
        self.mode = "lines"
        self.picker = _ModePicker(self)
        self.picker.modeSelected.connect(self.modeSelected)
        self.clicked.connect(lambda: self.picker.show_below(self, self.mode))
        self.set_mode(self.mode)

    def set_mode(self, mode):
        self.mode = mode
        self.setText(f"Mode: {PLOT_STYLES[mode]}")
        self.setIcon(QIcon(MODE_ICONS[mode]))
        self.setAccessibleName(f"Rendering mode for {self._label}: {PLOT_STYLES[mode]}")
        self.setToolTip(f"{MODE_DESCRIPTIONS[mode]}. Click to change rendering mode.")

    def paintEvent(self, event):
        super().paintEvent(event)
        painter = QPainter(self)
        self._chevron.paint(painter, self.width()-16, (self.height()-10)//2, 10, 10)
