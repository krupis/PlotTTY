"""Qt-painted indicators for the application's dark theme."""

from PySide6.QtCore import QPointF, QRectF, Qt
from PySide6.QtGui import QColor, QPainter, QPainterPath, QPen
from PySide6.QtWidgets import QProxyStyle, QStyle, QStyleOptionComboBox, QStyleOption


class ApplicationStyle(QProxyStyle):
    def __init__(self):
        super().__init__("Fusion")

    def pixelMetric(self, metric, option=None, widget=None):
        if metric in (QStyle.PixelMetric.PM_IndicatorWidth, QStyle.PixelMetric.PM_IndicatorHeight):
            return 18
        return super().pixelMetric(metric, option, widget)

    def subControlRect(self, control, option, subcontrol, widget=None):
        rect = super().subControlRect(control, option, subcontrol, widget)
        if control == QStyle.ComplexControl.CC_ComboBox and subcontrol == QStyle.SubControl.SC_ComboBoxArrow:
            rect.setWidth(24)
            if option.direction == Qt.LayoutDirection.RightToLeft:
                rect.moveLeft(option.rect.left() + 3)
            else:
                rect.moveRight(option.rect.right() - 3)
        return rect

    def drawComplexControl(self, control, option, painter, widget=None):
        if control != QStyle.ComplexControl.CC_ComboBox:
            return super().drawComplexControl(control, option, painter, widget)
        arrow = QStyle.SubControl.SC_ComboBoxArrow
        base_option = QStyleOptionComboBox(option)
        base_option.subControls &= ~arrow
        super().drawComplexControl(control, base_option, painter, widget)
        if option.subControls & arrow:
            arrow_option = QStyleOption(option)
            arrow_option.rect = self.subControlRect(control, option, arrow, widget)
            self.drawPrimitive(QStyle.PrimitiveElement.PE_IndicatorArrowDown,
                               arrow_option, painter, widget)

    def drawPrimitive(self, element, option, painter, widget=None):
        checks = (QStyle.PrimitiveElement.PE_IndicatorCheckBox,
                  QStyle.PrimitiveElement.PE_IndicatorItemViewItemCheck)
        if element not in checks and element != QStyle.PrimitiveElement.PE_IndicatorArrowDown:
            return super().drawPrimitive(element, option, painter, widget)

        enabled = bool(option.state & QStyle.StateFlag.State_Enabled)
        painter.save()
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        center = QRectF(option.rect).center()
        if element in checks:
            checked = bool(option.state & QStyle.StateFlag.State_On)
            mixed = bool(option.state & QStyle.StateFlag.State_NoChange)
            hovered = enabled and bool(option.state & QStyle.StateFlag.State_MouseOver)
            size = min(16.0, option.rect.width() - 2.0, option.rect.height() - 2.0)
            box = QRectF(center.x() - size / 2, center.y() - size / 2, size, size)
            border = "#a9c0d4" if hovered else "#879bad"
            fill = "#279665" if checked or mixed else "#303d49"
            painter.setPen(QPen(QColor(border if enabled else "#53606c"), 1.2))
            painter.setBrush(QColor(fill if enabled else "#30363d"))
            painter.drawRoundedRect(box, 3, 3)
            pen = QPen(QColor("#ffffff" if enabled else "#858b93"), 1.8)
            pen.setCapStyle(Qt.PenCapStyle.RoundCap)
            pen.setJoinStyle(Qt.PenJoinStyle.RoundJoin)
            painter.setPen(pen)
            if mixed:
                painter.drawLine(QPointF(box.left() + size * .25, center.y()),
                                 QPointF(box.right() - size * .25, center.y()))
            elif checked:
                path = QPainterPath(QPointF(box.left() + size * .23, box.top() + size * .51))
                path.lineTo(box.left() + size * .43, box.top() + size * .71)
                path.lineTo(box.left() + size * .78, box.top() + size * .30)
                painter.setBrush(Qt.BrushStyle.NoBrush)
                painter.drawPath(path)
        else:
            pen = QPen(QColor("#dce3ea" if enabled else "#778491"), 1.5)
            pen.setCapStyle(Qt.PenCapStyle.RoundCap)
            pen.setJoinStyle(Qt.PenJoinStyle.RoundJoin)
            painter.setPen(pen)
            painter.setBrush(Qt.BrushStyle.NoBrush)
            half_width = min(4.0, option.rect.width() / 3)
            path = QPainterPath(QPointF(center.x() - half_width, center.y() - 2))
            path.lineTo(center.x(), center.y() + 2)
            path.lineTo(center.x() + half_width, center.y() - 2)
            painter.drawPath(path)
        painter.restore()
