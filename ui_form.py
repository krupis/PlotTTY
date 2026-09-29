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
from PySide6.QtWidgets import (QApplication, QComboBox, QHBoxLayout, QLabel,
    QLineEdit, QListWidget, QListWidgetItem, QMainWindow,
    QMenu, QMenuBar, QPlainTextEdit, QPushButton,
    QSizePolicy, QSpacerItem, QSplitter, QStatusBar,
    QToolButton, QVBoxLayout, QWidget)

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
        self.PortLabel = QLabel(self.centralwidget)
        self.PortLabel.setObjectName(u"PortLabel")

        self.ConnectionLayout.addWidget(self.PortLabel)

        self.PortCombo = QComboBox(self.centralwidget)
        self.PortCombo.setObjectName(u"PortCombo")
        self.PortCombo.setMinimumSize(QSize(150, 0))

        self.ConnectionLayout.addWidget(self.PortCombo)

        self.RefreshPortsButton = QPushButton(self.centralwidget)
        self.RefreshPortsButton.setObjectName(u"RefreshPortsButton")

        self.ConnectionLayout.addWidget(self.RefreshPortsButton)

        self.BaudLabel = QLabel(self.centralwidget)
        self.BaudLabel.setObjectName(u"BaudLabel")

        self.ConnectionLayout.addWidget(self.BaudLabel)

        self.BaudCombo = QComboBox(self.centralwidget)
        self.BaudCombo.setObjectName(u"BaudCombo")

        self.ConnectionLayout.addWidget(self.BaudCombo)

        self.PortStatusLabel = QLabel(self.centralwidget)
        self.PortStatusLabel.setObjectName(u"PortStatusLabel")

        self.ConnectionLayout.addWidget(self.PortStatusLabel)

        self.ConnectButton = QPushButton(self.centralwidget)
        self.ConnectButton.setObjectName(u"ConnectButton")

        self.ConnectionLayout.addWidget(self.ConnectButton)

        self.Spacer8 = QSpacerItem(40, 20, QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Minimum)

        self.ConnectionLayout.addItem(self.Spacer8)

        self.SettingsButton = QPushButton(self.centralwidget)
        self.SettingsButton.setObjectName(u"SettingsButton")

        self.ConnectionLayout.addWidget(self.SettingsButton)


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
        self.SeriesHeading = QLabel(self.SeriesSidebar)
        self.SeriesHeading.setObjectName(u"SeriesHeading")

        self.SeriesLayout.addWidget(self.SeriesHeading)

        self.SeriesList = QListWidget(self.SeriesSidebar)
        self.SeriesList.setObjectName(u"SeriesList")
        self.SeriesList.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.SeriesList.setTextElideMode(Qt.ElideRight)

        self.SeriesLayout.addWidget(self.SeriesList)

        self.EditRulesButton = QPushButton(self.SeriesSidebar)
        self.EditRulesButton.setObjectName(u"EditRulesButton")

        self.SeriesLayout.addWidget(self.EditRulesButton)

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

        self.ConsoleToggle = QToolButton(self.Workspace)
        self.ConsoleToggle.setObjectName(u"ConsoleToggle")
        self.ConsoleToggle.setToolButtonStyle(Qt.ToolButtonTextBesideIcon)
        self.ConsoleToggle.setArrowType(Qt.RightArrow)
        sizePolicy = QSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        sizePolicy.setHorizontalStretch(0)
        sizePolicy.setVerticalStretch(0)
        sizePolicy.setHeightForWidth(self.ConsoleToggle.sizePolicy().hasHeightForWidth())
        self.ConsoleToggle.setSizePolicy(sizePolicy)

        self.WorkspaceLayout.addWidget(self.ConsoleToggle)

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
        self.actionSave_profile.setText(QCoreApplication.translate("MainWindow", u"Save profile\u2026", None))
        self.actionOpen_profile.setText(QCoreApplication.translate("MainWindow", u"Open profile\u2026", None))
        self.actionLoad_log.setText(QCoreApplication.translate("MainWindow", u"Load capture\u2026", None))
        self.actionClearCapturedData.setText(QCoreApplication.translate("MainWindow", u"Clear captured data", None))
        self.actionConsole.setText(QCoreApplication.translate("MainWindow", u"Console", None))
        self.actionSidebar.setText(QCoreApplication.translate("MainWindow", u"Series sidebar", None))
        self.actionDiagnostics.setText(QCoreApplication.translate("MainWindow", u"Diagnostics", None))
        self.PortLabel.setText(QCoreApplication.translate("MainWindow", u"Port", None))
        self.RefreshPortsButton.setText(QCoreApplication.translate("MainWindow", u"Refresh", None))
        self.BaudLabel.setText(QCoreApplication.translate("MainWindow", u"Baud rate", None))
        self.PortStatusLabel.setText(QCoreApplication.translate("MainWindow", u"\u25cf Disconnected", None))
        self.ConnectButton.setText(QCoreApplication.translate("MainWindow", u"Connect", None))
        self.SettingsButton.setText(QCoreApplication.translate("MainWindow", u"Settings", None))
        self.SeriesHeading.setText(QCoreApplication.translate("MainWindow", u"Series", None))
        self.EditRulesButton.setText(QCoreApplication.translate("MainWindow", u"Edit rules\u2026", None))
        self.CommandEdit.setPlaceholderText(QCoreApplication.translate("MainWindow", u"Type command and press Enter", None))
        self.SendButton.setText(QCoreApplication.translate("MainWindow", u"Send", None))
        self.ClearConsoleButton.setText(QCoreApplication.translate("MainWindow", u"Clear console", None))
        self.ConsoleToggle.setText(QCoreApplication.translate("MainWindow", u"Console", None))
        self.menuFile.setTitle(QCoreApplication.translate("MainWindow", u"File", None))
        self.menuView.setTitle(QCoreApplication.translate("MainWindow", u"View", None))
        pass
    # retranslateUi

