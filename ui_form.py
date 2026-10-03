# -*- coding: utf-8 -*-

################################################################################
## Form generated from reading UI file 'form.ui'
##
## Created by: Qt User Interface Compiler version 6.11.1
##
## WARNING! All changes made in this file will be lost when recompiling UI file!
################################################################################

from PySide6.QtCore import (QCoreApplication, QDate, QDateTime, QLocale,
    QMetaObject, QObject, QPoint, QRect,
    QSize, QTime, QUrl, Qt)
from PySide6.QtGui import (QAction, QBrush, QColor, QConicalGradient,
    QCursor, QFont, QFontDatabase, QGradient,
    QIcon, QImage, QKeySequence, QLinearGradient,
    QPainter, QPalette, QPixmap, QRadialGradient,
    QTransform)
from PySide6.QtWidgets import (QApplication, QHBoxLayout, QLabel, QLineEdit,
    QMainWindow, QMenu, QMenuBar, QPlainTextEdit,
    QPushButton, QSizePolicy, QSpacerItem, QSplitter,
    QStatusBar, QVBoxLayout, QWidget)

from modules.widgets.plot_widget import PlotWidget

class Ui_MainWindow(object):
    def setupUi(self, MainWindow):
        if not MainWindow.objectName():
            MainWindow.setObjectName(u"MainWindow")
        MainWindow.resize(1280, 800)
        self.actionSave_profile = QAction(MainWindow)
        self.actionSave_profile.setObjectName(u"actionSave_profile")
        self.actionOpen_profile = QAction(MainWindow)
        self.actionOpen_profile.setObjectName(u"actionOpen_profile")
        self.actionLoad_log = QAction(MainWindow)
        self.actionLoad_log.setObjectName(u"actionLoad_log")
        self.actionClearCapturedData = QAction(MainWindow)
        self.actionClearCapturedData.setObjectName(u"actionClearCapturedData")
        self.actionConsole = QAction(MainWindow)
        self.actionConsole.setObjectName(u"actionConsole")
        self.actionConsole.setCheckable(True)
        self.actionSidebar = QAction(MainWindow)
        self.actionSidebar.setObjectName(u"actionSidebar")
        self.actionSidebar.setCheckable(True)
        self.actionDiagnostics = QAction(MainWindow)
        self.actionDiagnostics.setObjectName(u"actionDiagnostics")
        self.actionDiagnostics.setCheckable(True)
        self.centralwidget = QWidget(MainWindow)
        self.centralwidget.setObjectName(u"centralwidget")
        self.MainLayout = QVBoxLayout(self.centralwidget)
        self.MainLayout.setSpacing(12)
        self.MainLayout.setObjectName(u"MainLayout")
        self.ConnectionLayout = QHBoxLayout()
        self.ConnectionLayout.setObjectName(u"ConnectionLayout")
        self.ConnectionSettingsButton = QPushButton(self.centralwidget)
        self.ConnectionSettingsButton.setObjectName(u"ConnectionSettingsButton")

        self.ConnectionLayout.addWidget(self.ConnectionSettingsButton)

        self.ConnectButton = QPushButton(self.centralwidget)
        self.ConnectButton.setObjectName(u"ConnectButton")

        self.ConnectionLayout.addWidget(self.ConnectButton)

        self.ConnectionSpacer = QSpacerItem(40, 20, QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Minimum)

        self.ConnectionLayout.addItem(self.ConnectionSpacer)


        self.MainLayout.addLayout(self.ConnectionLayout)

        self.MainSplitter = QSplitter(self.centralwidget)
        self.MainSplitter.setObjectName(u"MainSplitter")
        self.MainSplitter.setOrientation(Qt.Horizontal)
        self.SeriesSidebar = QWidget(self.MainSplitter)
        self.SeriesSidebar.setObjectName(u"SeriesSidebar")
        self.SeriesSidebar.setMinimumSize(QSize(160, 0))
        self.SeriesLayout = QVBoxLayout(self.SeriesSidebar)
        self.SeriesLayout.setObjectName(u"SeriesLayout")
        self.SeriesLayout.setContentsMargins(0, 0, 0, 0)
        self.MainSplitter.addWidget(self.SeriesSidebar)
        self.Workspace = QWidget(self.MainSplitter)
        self.Workspace.setObjectName(u"Workspace")
        self.WorkspaceLayout = QVBoxLayout(self.Workspace)
        self.WorkspaceLayout.setObjectName(u"WorkspaceLayout")
        self.WorkspaceLayout.setContentsMargins(0, 0, 0, 0)
        self.WorkspaceSplitter = QSplitter(self.Workspace)
        self.WorkspaceSplitter.setObjectName(u"WorkspaceSplitter")
        self.WorkspaceSplitter.setOrientation(Qt.Vertical)
        self.Plot = PlotWidget(self.WorkspaceSplitter)
        self.Plot.setObjectName(u"Plot")
        self.WorkspaceSplitter.addWidget(self.Plot)
        self.ConsolePanel = QWidget(self.WorkspaceSplitter)
        self.ConsolePanel.setObjectName(u"ConsolePanel")
        self.ConsoleLayout = QVBoxLayout(self.ConsolePanel)
        self.ConsoleLayout.setObjectName(u"ConsoleLayout")
        self.ConsoleLayout.setContentsMargins(0, 0, 0, 0)
        self.SearchLayout = QHBoxLayout()
        self.SearchLayout.setObjectName(u"SearchLayout")
        self.SearchEdit = QLineEdit(self.ConsolePanel)
        self.SearchEdit.setObjectName(u"SearchEdit")

        self.SearchLayout.addWidget(self.SearchEdit)

        self.SearchMatchLabel = QLabel(self.ConsolePanel)
        self.SearchMatchLabel.setObjectName(u"SearchMatchLabel")
        self.SearchMatchLabel.setMinimumSize(QSize(52, 0))

        self.SearchLayout.addWidget(self.SearchMatchLabel)

        self.SearchPreviousButton = QPushButton(self.ConsolePanel)
        self.SearchPreviousButton.setObjectName(u"SearchPreviousButton")

        self.SearchLayout.addWidget(self.SearchPreviousButton)

        self.SearchNextButton = QPushButton(self.ConsolePanel)
        self.SearchNextButton.setObjectName(u"SearchNextButton")

        self.SearchLayout.addWidget(self.SearchNextButton)


        self.ConsoleLayout.addLayout(self.SearchLayout)

        self.ConsoleTextEdit = QPlainTextEdit(self.ConsolePanel)
        self.ConsoleTextEdit.setObjectName(u"ConsoleTextEdit")

        self.ConsoleLayout.addWidget(self.ConsoleTextEdit)

        self.CommandLayout = QHBoxLayout()
        self.CommandLayout.setObjectName(u"CommandLayout")
        self.CommandEdit = QLineEdit(self.ConsolePanel)
        self.CommandEdit.setObjectName(u"CommandEdit")

        self.CommandLayout.addWidget(self.CommandEdit)

        self.SendButton = QPushButton(self.ConsolePanel)
        self.SendButton.setObjectName(u"SendButton")

        self.CommandLayout.addWidget(self.SendButton)

        self.ClearConsoleButton = QPushButton(self.ConsolePanel)
        self.ClearConsoleButton.setObjectName(u"ClearConsoleButton")

        self.CommandLayout.addWidget(self.ClearConsoleButton)


        self.ConsoleLayout.addLayout(self.CommandLayout)

        self.WorkspaceSplitter.addWidget(self.ConsolePanel)

        self.WorkspaceLayout.addWidget(self.WorkspaceSplitter)

        self.MainSplitter.addWidget(self.Workspace)

        self.MainLayout.addWidget(self.MainSplitter)

        MainWindow.setCentralWidget(self.centralwidget)
        self.menubar = QMenuBar(MainWindow)
        self.menubar.setObjectName(u"menubar")
        self.menuFile = QMenu(self.menubar)
        self.menuFile.setObjectName(u"menuFile")
        self.menuView = QMenu(self.menubar)
        self.menuView.setObjectName(u"menuView")
        MainWindow.setMenuBar(self.menubar)
        self.statusbar = QStatusBar(MainWindow)
        self.statusbar.setObjectName(u"statusbar")
        MainWindow.setStatusBar(self.statusbar)

        self.menubar.addAction(self.menuFile.menuAction())
        self.menubar.addAction(self.menuView.menuAction())
        self.menuFile.addAction(self.actionSave_profile)
        self.menuFile.addAction(self.actionOpen_profile)
        self.menuFile.addAction(self.actionLoad_log)
        self.menuFile.addAction(self.actionClearCapturedData)
        self.menuView.addAction(self.actionConsole)
        self.menuView.addAction(self.actionSidebar)
        self.menuView.addAction(self.actionDiagnostics)

        self.retranslateUi(MainWindow)

        QMetaObject.connectSlotsByName(MainWindow)
    # setupUi

    def retranslateUi(self, MainWindow):
        self.actionSave_profile.setText(QCoreApplication.translate("MainWindow", u"Save profile...", None))
        self.actionOpen_profile.setText(QCoreApplication.translate("MainWindow", u"Open profile...", None))
        self.actionLoad_log.setText(QCoreApplication.translate("MainWindow", u"Load capture...", None))
        self.actionClearCapturedData.setText(QCoreApplication.translate("MainWindow", u"Clear captured data", None))
        self.actionConsole.setText(QCoreApplication.translate("MainWindow", u"Console", None))
        self.actionSidebar.setText(QCoreApplication.translate("MainWindow", u"Extraction sidebar", None))
        self.actionDiagnostics.setText(QCoreApplication.translate("MainWindow", u"Diagnostics", None))
        self.ConnectionSettingsButton.setText(QCoreApplication.translate("MainWindow", u"Select port", None))
#if QT_CONFIG(tooltip)
        self.ConnectionSettingsButton.setToolTip(QCoreApplication.translate("MainWindow", u"Connection settings", None))
#endif // QT_CONFIG(tooltip)
        self.ConnectButton.setText(QCoreApplication.translate("MainWindow", u"Connect", None))
        self.SearchEdit.setPlaceholderText(QCoreApplication.translate("MainWindow", u"Search console", None))
        self.SearchMatchLabel.setText("")
        self.SearchPreviousButton.setText(QCoreApplication.translate("MainWindow", u"Previous", None))
        self.SearchNextButton.setText(QCoreApplication.translate("MainWindow", u"Next", None))
        self.CommandEdit.setPlaceholderText(QCoreApplication.translate("MainWindow", u"Type command and press Enter", None))
        self.SendButton.setText(QCoreApplication.translate("MainWindow", u"Send", None))
        self.ClearConsoleButton.setText(QCoreApplication.translate("MainWindow", u"Clear", None))
#if QT_CONFIG(tooltip)
        self.ClearConsoleButton.setToolTip(QCoreApplication.translate("MainWindow", u"Clear console text", None))
#endif // QT_CONFIG(tooltip)
#if QT_CONFIG(accessibility)
        self.ClearConsoleButton.setAccessibleName(QCoreApplication.translate("MainWindow", u"Clear console", None))
#endif // QT_CONFIG(accessibility)
        self.menuFile.setTitle(QCoreApplication.translate("MainWindow", u"File", None))
        self.menuView.setTitle(QCoreApplication.translate("MainWindow", u"View", None))
        pass
    # retranslateUi

