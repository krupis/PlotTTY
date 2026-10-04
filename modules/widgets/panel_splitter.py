"""Thin panel dividers; collapse controls live in the panel headings."""
from PySide6.QtCore import QPointF, Qt
from PySide6.QtGui import QColor, QPainter, QPen
from PySide6.QtWidgets import QHBoxLayout, QLabel, QSplitter, QSplitterHandle, QToolButton


class PanelSplitter(QSplitter):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setHandleWidth(8)
        self.setChildrenCollapsible(False)

    def createHandle(self):
        return PanelHandle(self.orientation(), self)

    def configure_panel(self, title, index, action, expanded_size):
        panel = self.widget(index)
        row = QHBoxLayout()
        row.setSpacing(3)
        heading = QLabel(title, panel)
        heading.setObjectName('PanelHeading')
        row.addWidget(heading)
        button = QToolButton(panel)
        button.setObjectName('PanelCollapseButton')
        button.setFixedSize(20, 20)
        button.setCursor(Qt.PointingHandCursor)
        button.setFocusPolicy(Qt.StrongFocus)
        row.addWidget(button)
        row.addStretch()
        panel.layout().insertLayout(0, row)
        panel.layout().setAlignment(row, Qt.AlignTop)
        self.panel_name = title.lower()
        self.panel_index = index
        self.collapse_button = button
        self.collapsed = False
        self._hidden_content = []
        self._expanded_size = expanded_size
        self._expanded_minimum = panel.minimumSize()
        self._expanded_maximum = panel.maximumSize()
        button.clicked.connect(action.toggle)
        action.toggled.connect(self.set_panel_expanded)
        self.update_control()

    @property
    def expanded_size(self):
        return self._expanded_size if self.collapsed else self.sizes()[self.panel_index]

    @expanded_size.setter
    def expanded_size(self, size):
        self._expanded_size = size

    def set_panel_expanded(self, expanded):
        if not expanded and not self.collapsed:
            self._expanded_size = self.sizes()[self.panel_index]
        self.set_panel_collapsed(not expanded)
        panel = self.widget(self.panel_index)
        minimum = panel.minimumWidth() if self.orientation() == Qt.Horizontal else panel.minimumHeight()
        size = max(minimum, self._expanded_size) if expanded else minimum
        total = sum(self.sizes())
        sizes = [max(220, total-size)] * 2
        sizes[self.panel_index] = size
        self.setSizes(sizes)

    def set_panel_collapsed(self, collapsed):
        if self.collapsed == collapsed:
            return
        panel = self.widget(self.panel_index)
        layout = panel.layout()
        if collapsed:
            def hide_content(item):
                widget = item.widget()
                if widget is not None and not widget.isHidden():
                    self._hidden_content.append(widget)
                    widget.hide()
                child = item.layout()
                if child is not None:
                    for index in range(child.count()):
                        hide_content(child.itemAt(index))
            for index in range(1, layout.count()):
                hide_content(layout.itemAt(index))
            margins = layout.contentsMargins()
            heading = layout.itemAt(0).minimumSize()
            if self.orientation() == Qt.Horizontal:
                panel.setFixedWidth(heading.width() + margins.left() + margins.right())
            else:
                panel.setFixedHeight(heading.height() + margins.top() + margins.bottom())
        else:
            panel.setMinimumSize(self._expanded_minimum)
            panel.setMaximumSize(self._expanded_maximum)
            for widget in self._hidden_content:
                widget.show()
            self._hidden_content.clear()
        self.collapsed = collapsed
        layout.activate()
        self.update_control()

    def update_control(self, *_):
        handle = self.handle(1)
        collapsed = self.collapsed
        button = self.collapse_button
        text = f"{'Expand' if collapsed else 'Collapse'} {self.panel_name}"
        button.setToolTip(text)
        button.setAccessibleName(text)
        button.setArrowType(Qt.RightArrow if collapsed else Qt.DownArrow)
        handle.setToolTip(f"{'Use the title arrow to expand' if collapsed else 'Drag to resize'} {self.panel_name}")
        handle.setAccessibleName(f"Resize {self.panel_name}")
        handle.update()


class PanelHandle(QSplitterHandle):
    def __init__(self, orientation, splitter):
        super().__init__(orientation, splitter)
        self._hovered = False
        self._dragging = False

    def enterEvent(self, event):
        self._hovered = True
        self.update()
        super().enterEvent(event)

    def leaveEvent(self, event):
        self._hovered = False
        self.update()
        super().leaveEvent(event)

    def mousePressEvent(self, event):
        self._dragging = event.button() == Qt.LeftButton
        super().mousePressEvent(event)
        self.update()

    def mouseReleaseEvent(self, event):
        self._dragging = False
        super().mouseReleaseEvent(event)
        self.update()

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        active = self._hovered or self._dragging
        color = QColor('#6edbd3' if active else '#658f98')
        painter.setPen(QPen(color, 3 if active else 2))
        cx, cy = self.width()/2, self.height()/2
        vertical = self.orientation() == Qt.Horizontal
        if vertical:
            painter.drawLine(QPointF(cx, 0), QPointF(cx, self.height()))
        else:
            painter.drawLine(QPointF(0, cy), QPointF(self.width(), cy))
