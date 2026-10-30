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
    QLineEdit, QMenu, QMenuBar, QPlainTextEdit,
    QPushButton, QSizePolicy, QSpacerItem, QStatusBar,
    QVBoxLayout, QWidget)

from modules.widgets.panel_splitter import PanelSplitter
from modules.widgets.plot_widget import PlotWidget

class Ui_ConnectionWorkspace(object):
    def setupUi(self, ConnectionWorkspace):
        if not ConnectionWorkspace.objectName():
            ConnectionWorkspace.setObjectName(u"ConnectionWorkspace")
        ConnectionWorkspace.resize(1280, 800)
        self.actionSave_profile = QAction(ConnectionWorkspace)
        self.actionSave_profile.setObjectName(u"actionSave_profile")
        self.actionOpen_profile = QAction(ConnectionWorkspace)
        self.actionOpen_profile.setObjectName(u"actionOpen_profile")
        self.actionLoad_log = QAction(ConnectionWorkspace)
        self.actionLoad_log.setObjectName(u"actionLoad_log")
        self.actionClearCapturedData = QAction(ConnectionWorkspace)
        self.actionClearCapturedData.setObjectName(u"actionClearCapturedData")
        self.actionConsole = QAction(ConnectionWorkspace)
        self.actionConsole.setObjectName(u"actionConsole")
        self.actionConsole.setCheckable(True)
        self.actionSidebar = QAction(ConnectionWorkspace)
        self.actionSidebar.setObjectName(u"actionSidebar")
        self.actionSidebar.setCheckable(True)
        self.actionDiagnostics = QAction(ConnectionWorkspace)
        self.actionDiagnostics.setObjectName(u"actionDiagnostics")
        self.actionDiagnostics.setCheckable(True)
        self.RootLayout = QVBoxLayout(ConnectionWorkspace)
        self.RootLayout.setSpacing(0)
        self.RootLayout.setObjectName(u"RootLayout")
        self.RootLayout.setContentsMargins(0, 0, 0, 0)
        self.menubar = QMenuBar(ConnectionWorkspace)
        self.menubar.setObjectName(u"menubar")
        self.menuFile = QMenu(self.menubar)
        self.menuFile.setObjectName(u"menuFile")
        self.menuView = QMenu(self.menubar)
        self.menuView.setObjectName(u"menuView")

        self.RootLayout.addWidget(self.menubar)

        self.centralwidget = QWidget(ConnectionWorkspace)
        self.centralwidget.setObjectName(u"centralwidget")
        self.MainLayout = QVBoxLayout(self.centralwidget)
        self.MainLayout.setSpacing(12)
        self.MainLayout.setObjectName(u"MainLayout")
        self.MainLayout.setContentsMargins(0, 0, 0, 0)
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

        self.MainSplitter = PanelSplitter(self.centralwidget)
        self.MainSplitter.setObjectName(u"MainSplitter")
        self.MainSplitter.setOrientation(Qt.Horizontal)
        self.SeriesSidebar = QWidget(self.MainSplitter)
        self.SeriesSidebar.setObjectName(u"SeriesSidebar")
        self.SeriesSidebar.setMinimumSize(QSize(160, 0))
        self.SeriesLayout = QVBoxLayout(self.SeriesSidebar)
        self.SeriesLayout.setObjectName(u"SeriesLayout")
        self.MainSplitter.addWidget(self.SeriesSidebar)
        self.Workspace = QWidget(self.MainSplitter)
        self.Workspace.setObjectName(u"Workspace")
        self.WorkspaceLayout = QVBoxLayout(self.Workspace)
        self.WorkspaceLayout.setObjectName(u"WorkspaceLayout")
        self.WorkspaceLayout.setContentsMargins(0, 0, 0, 0)
        self.WorkspaceSplitter = PanelSplitter(self.Workspace)
        self.WorkspaceSplitter.setObjectName(u"WorkspaceSplitter")
        self.WorkspaceSplitter.setOrientation(Qt.Vertical)
        self.Plot = PlotWidget(self.WorkspaceSplitter)
        self.Plot.setObjectName(u"Plot")
        self.WorkspaceSplitter.addWidget(self.Plot)
        self.ConsolePanel = QWidget(self.WorkspaceSplitter)
        self.ConsolePanel.setObjectName(u"ConsolePanel")
        self.ConsoleLayout = QVBoxLayout(self.ConsolePanel)
        self.ConsoleLayout.setObjectName(u"ConsoleLayout")
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

        self.CommandTerminatorCombo = QComboBox(self.ConsolePanel)
        self.CommandTerminatorCombo.setObjectName(u"CommandTerminatorCombo")
        sizePolicy = QSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Fixed)
        sizePolicy.setHorizontalStretch(0)
        sizePolicy.setVerticalStretch(0)
        sizePolicy.setHeightForWidth(self.CommandTerminatorCombo.sizePolicy().hasHeightForWidth())
        self.CommandTerminatorCombo.setSizePolicy(sizePolicy)
        self.CommandTerminatorCombo.setSizeAdjustPolicy(QComboBox.AdjustToContents)

        self.CommandLayout.addWidget(self.CommandTerminatorCombo)

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


        self.RootLayout.addWidget(self.centralwidget)

        self.statusbar = QStatusBar(ConnectionWorkspace)
        self.statusbar.setObjectName(u"statusbar")

        self.RootLayout.addWidget(self.statusbar)


        self.menubar.addAction(self.menuFile.menuAction())
        self.menubar.addAction(self.menuView.menuAction())
        self.menuFile.addAction(self.actionSave_profile)
        self.menuFile.addAction(self.actionOpen_profile)
        self.menuFile.addAction(self.actionLoad_log)
        self.menuFile.addAction(self.actionClearCapturedData)
        self.menuView.addAction(self.actionConsole)
        self.menuView.addAction(self.actionSidebar)
        self.menuView.addAction(self.actionDiagnostics)

        self.retranslateUi(ConnectionWorkspace)

        QMetaObject.connectSlotsByName(ConnectionWorkspace)
    # setupUi

    def retranslateUi(self, ConnectionWorkspace):
        self.actionSave_profile.setText(QCoreApplication.translate("ConnectionWorkspace", u"Save profile...", None))
        self.actionOpen_profile.setText(QCoreApplication.translate("ConnectionWorkspace", u"Open profile...", None))
        self.actionLoad_log.setText(QCoreApplication.translate("ConnectionWorkspace", u"Load capture...", None))
        self.actionClearCapturedData.setText(QCoreApplication.translate("ConnectionWorkspace", u"Clear captured data", None))
        self.actionConsole.setText(QCoreApplication.translate("ConnectionWorkspace", u"Console", None))
        self.actionSidebar.setText(QCoreApplication.translate("ConnectionWorkspace", u"Extraction sidebar", None))
        self.actionDiagnostics.setText(QCoreApplication.translate("ConnectionWorkspace", u"Diagnostics", None))
        self.menuFile.setTitle(QCoreApplication.translate("ConnectionWorkspace", u"File", None))
        self.menuView.setTitle(QCoreApplication.translate("ConnectionWorkspace", u"View", None))
        self.ConnectionSettingsButton.setText(QCoreApplication.translate("ConnectionWorkspace", u"Settings", None))
#if QT_CONFIG(tooltip)
        self.ConnectionSettingsButton.setToolTip(QCoreApplication.translate("ConnectionWorkspace", u"Connection settings", None))
#endif // QT_CONFIG(tooltip)
        self.ConnectButton.setText(QCoreApplication.translate("ConnectionWorkspace", u"Connect", None))
        self.SearchEdit.setPlaceholderText(QCoreApplication.translate("ConnectionWorkspace", u"Search console", None))
        self.SearchMatchLabel.setText("")
        self.SearchPreviousButton.setText(QCoreApplication.translate("ConnectionWorkspace", u"Previous", None))
        self.SearchNextButton.setText(QCoreApplication.translate("ConnectionWorkspace", u"Next", None))
        self.CommandEdit.setPlaceholderText(QCoreApplication.translate("ConnectionWorkspace", u"Type command and press Enter", None))
#if QT_CONFIG(tooltip)
        self.CommandTerminatorCombo.setToolTip(QCoreApplication.translate("ConnectionWorkspace", u"Command terminator appended when sending: \\n (LF), \\r (CR), \\r\\n (CRLF), or None.", None))
#endif // QT_CONFIG(tooltip)
#if QT_CONFIG(accessibility)
        self.CommandTerminatorCombo.setAccessibleName(QCoreApplication.translate("ConnectionWorkspace", u"Command terminator", None))
#endif // QT_CONFIG(accessibility)
        self.SendButton.setText(QCoreApplication.translate("ConnectionWorkspace", u"Send", None))
        self.ClearConsoleButton.setText(QCoreApplication.translate("ConnectionWorkspace", u"Clear", None))
#if QT_CONFIG(tooltip)
        self.ClearConsoleButton.setToolTip(QCoreApplication.translate("ConnectionWorkspace", u"Clear console text", None))
#endif // QT_CONFIG(tooltip)
#if QT_CONFIG(accessibility)
        self.ClearConsoleButton.setAccessibleName(QCoreApplication.translate("ConnectionWorkspace", u"Clear console", None))
#endif // QT_CONFIG(accessibility)
        pass
    # retranslateUi

