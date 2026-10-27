"""Lightweight startup feedback, loaded before the application and NumPy."""

import sys
from importlib import import_module
from math import sin, tau
from time import monotonic

from PySide6.QtCore import QPointF, QRectF, Qt, QTimer
from PySide6.QtGui import QColor, QIcon, QPainter, QPainterPath, QPen, QPixmap
from PySide6.QtWidgets import QApplication, QLabel, QSplashScreen, QVBoxLayout, QWidget

import rc_resources  # noqa: F401


class StartupPlot(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFixedHeight(72)
        self.setAccessibleName("Animated startup plot")
        self._started = monotonic()
        self._timer = QTimer(self)
        self._timer.setInterval(30)
        self._timer.timeout.connect(self.update)

    def showEvent(self, event):
        super().showEvent(event)
        self._timer.start()

    def hideEvent(self, event):
        self._timer.stop()
        super().hideEvent(event)

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        panel = QPainterPath()
        panel.addRoundedRect(QRectF(self.rect()), 8, 8)
        painter.fillPath(panel, QColor("#0f1417"))
        painter.setClipPath(panel)
        plot = QRectF(self.rect()).adjusted(12, 10, -12, -10)
        painter.setPen(QPen(QColor("#263237"), 1))
        for column in range(7):
            x = plot.left() + plot.width() * column / 6
            painter.drawLine(QPointF(x, plot.top()), QPointF(x, plot.bottom()))
        for row in range(3):
            y = plot.top() + plot.height() * row / 2
            painter.drawLine(QPointF(plot.left(), y), QPointF(plot.right(), y))

        phase = (monotonic() - self._started) * 2.3
        for offset, color in ((0.0, "#41ccc3"), (1.8, "#ff9c36")):
            trace = QPainterPath()
            for index in range(121):
                fraction = index / 120
                angle = fraction * tau * 2 + phase + offset
                value = sin(angle) * 0.62 + sin(angle * 1.7 + offset) * 0.22
                point = QPointF(plot.left() + fraction * plot.width(),
                                plot.center().y() - value * plot.height() * 0.43)
                if index == 0:
                    trace.moveTo(point)
                else:
                    trace.lineTo(point)
            painter.setPen(QPen(QColor(color), 1.8, Qt.PenStyle.SolidLine,
                                Qt.PenCapStyle.RoundCap, Qt.PenJoinStyle.RoundJoin))
            painter.setBrush(Qt.BrushStyle.NoBrush)
            painter.drawPath(trace)
            painter.setPen(Qt.PenStyle.NoPen)
            painter.setBrush(QColor(color))
            painter.drawEllipse(point, 3, 3)


class StartupSplash(QSplashScreen):
    def __init__(self):
        background = QPixmap(400, 300)
        background.fill(QColor("#151c20"))
        super().__init__(background)
        self.setWindowTitle("Starting PlotTTY")
        self.setWindowIcon(QIcon(":/icons/Plottty.png"))
        self.setStyleSheet("""
            QLabel { color: #f3f6f7; background: transparent; }
            QLabel#StartupTitle { font-size: 24px; font-weight: 600; }
            QLabel#StartupStatus { color: #bac5cb; font-size: 12px; }
        """)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(40, 24, 40, 28)
        layout.setSpacing(12)
        icon = QLabel()
        logo = QIcon(":/icons/Plottty.png").pixmap(64, 64)
        rounded_logo = QPixmap(logo.size())
        rounded_logo.setDevicePixelRatio(logo.devicePixelRatio())
        rounded_logo.fill(Qt.GlobalColor.transparent)
        painter = QPainter(rounded_logo)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        outline = QPainterPath()
        outline.addRoundedRect(QRectF(0, 0, logo.deviceIndependentSize().width(),
                                     logo.deviceIndependentSize().height()), 10, 10)
        painter.setClipPath(outline)
        painter.drawPixmap(0, 0, logo)
        painter.end()
        icon.setPixmap(rounded_logo)
        icon.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(icon)
        title = QLabel("PlotTTY")
        title.setObjectName("StartupTitle")
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(title)
        self.plot_animation = StartupPlot()
        layout.addWidget(self.plot_animation)
        self.status = QLabel("Loading plotting engine…")
        self.status.setObjectName("StartupStatus")
        self.status.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(self.status)

    def mousePressEvent(self, event):
        # QSplashScreen normally hides on click; keep feedback until startup ends.
        event.accept()


def run() -> int:
    app = QApplication(sys.argv)
    app.setStyle("Fusion")
    splash = StartupSplash()
    app.setWindowIcon(splash.windowIcon())
    splash.show()
    window = None

    # Yield between import stages so Qt can paint and animate the busy indicator.
    stages = iter((
        ("Loading plotting engine…", "numpy"),
        ("Loading workspace…", "modules.widgets.plot_widget"),
        ("Loading connections…", "modules.controllers.connection_session"),
        ("Preparing window…", "mainwindow"),
    ))

    def advance():
        nonlocal window
        try:
            stage = next(stages, None)
            if stage is not None:
                message, module = stage
                splash.status.setText(message)
                splash.repaint()
                import_module(module)
                QTimer.singleShot(0, advance)
                return

            from mainwindow import APP_NAME, APP_VERSION, MainWindow, apply_application_style

            app.setApplicationName(APP_NAME)
            app.setApplicationVersion(APP_VERSION)
            apply_application_style(app)
            window = MainWindow()
            window.show()
            # MainWindow queues layout restoration during construction. Finish
            # after it runs, keeping the splash through the initial layout pass.
            QTimer.singleShot(0, lambda: splash.finish(window))
        except Exception:
            splash.close()
            sys.excepthook(*sys.exc_info())
            app.exit(1)

    QTimer.singleShot(0, advance)
    return app.exec()
