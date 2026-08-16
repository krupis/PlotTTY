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
from PySide6.QtWidgets import (QApplication, QFrame, QHBoxLayout, QHeaderView,
    QLabel, QMainWindow, QMenu, QMenuBar,
    QPlainTextEdit, QPushButton, QSizePolicy, QSpacerItem,
    QStatusBar, QTabWidget, QTableWidget, QTableWidgetItem,
    QVBoxLayout, QWidget)

from modules.widgets.plot_widget import PlotWidget

class Ui_MainWindow(object):
    def setupUi(self, MainWindow):
        if not MainWindow.objectName():
            MainWindow.setObjectName(u"MainWindow")
        MainWindow.resize(1191, 907)
        self.actionSave_profile = QAction(MainWindow)
        self.actionSave_profile.setObjectName(u"actionSave_profile")
        self.actionOpen_profile = QAction(MainWindow)
        self.actionOpen_profile.setObjectName(u"actionOpen_profile")
        self.actionLoad_log = QAction(MainWindow)
        self.actionLoad_log.setObjectName(u"actionLoad_log")
        self.centralwidget = QWidget(MainWindow)
        self.centralwidget.setObjectName(u"centralwidget")
        self.verticalLayout = QVBoxLayout(self.centralwidget)
        self.verticalLayout.setObjectName(u"verticalLayout")
        self.TopNavBar = QHBoxLayout()
        self.TopNavBar.setObjectName(u"TopNavBar")
        self.PortStatusLabel = QLabel(self.centralwidget)
        self.PortStatusLabel.setObjectName(u"PortStatusLabel")
        sizePolicy = QSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Fixed)
        sizePolicy.setHorizontalStretch(0)
        sizePolicy.setVerticalStretch(0)
        sizePolicy.setHeightForWidth(self.PortStatusLabel.sizePolicy().hasHeightForWidth())
        self.PortStatusLabel.setSizePolicy(sizePolicy)

        self.TopNavBar.addWidget(self.PortStatusLabel)

        self.ConnectButton = QPushButton(self.centralwidget)
        self.ConnectButton.setObjectName(u"ConnectButton")
        sizePolicy1 = QSizePolicy(QSizePolicy.Policy.Minimum, QSizePolicy.Policy.Fixed)
        sizePolicy1.setHorizontalStretch(0)
        sizePolicy1.setVerticalStretch(0)
        sizePolicy1.setHeightForWidth(self.ConnectButton.sizePolicy().hasHeightForWidth())
        self.ConnectButton.setSizePolicy(sizePolicy1)

        self.TopNavBar.addWidget(self.ConnectButton)

        self.pushButton = QPushButton(self.centralwidget)
        self.pushButton.setObjectName(u"pushButton")

        self.TopNavBar.addWidget(self.pushButton)

        self.DataReceivedLabel = QLabel(self.centralwidget)
        self.DataReceivedLabel.setObjectName(u"DataReceivedLabel")
        sizePolicy.setHeightForWidth(self.DataReceivedLabel.sizePolicy().hasHeightForWidth())
        self.DataReceivedLabel.setSizePolicy(sizePolicy)

        self.TopNavBar.addWidget(self.DataReceivedLabel)

        self.horizontalSpacer = QSpacerItem(40, 20, QSizePolicy.Policy.MinimumExpanding, QSizePolicy.Policy.Minimum)

        self.TopNavBar.addItem(self.horizontalSpacer)


        self.verticalLayout.addLayout(self.TopNavBar)

        self.main = QVBoxLayout()
        self.main.setObjectName(u"main")
        self.mainSplit = QHBoxLayout()
        self.mainSplit.setObjectName(u"mainSplit")
        self.RightFrame = QFrame(self.centralwidget)
        self.RightFrame.setObjectName(u"RightFrame")
        self.RightFrame.setFrameShape(QFrame.Shape.StyledPanel)
        self.RightFrame.setFrameShadow(QFrame.Shadow.Raised)
        self.horizontalLayout_2 = QHBoxLayout(self.RightFrame)
        self.horizontalLayout_2.setObjectName(u"horizontalLayout_2")
        self.tabWidget = QTabWidget(self.RightFrame)
        self.tabWidget.setObjectName(u"tabWidget")
        self.ConsoleTab = QWidget()
        self.ConsoleTab.setObjectName(u"ConsoleTab")
        self.horizontalLayout = QHBoxLayout(self.ConsoleTab)
        self.horizontalLayout.setObjectName(u"horizontalLayout")
        self.ConsoleLayout = QVBoxLayout()
        self.ConsoleLayout.setObjectName(u"ConsoleLayout")
        self.ConsoleTextEdit = QPlainTextEdit(self.ConsoleTab)
        self.ConsoleTextEdit.setObjectName(u"ConsoleTextEdit")
        sizePolicy2 = QSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        sizePolicy2.setHorizontalStretch(0)
        sizePolicy2.setVerticalStretch(0)
        sizePolicy2.setHeightForWidth(self.ConsoleTextEdit.sizePolicy().hasHeightForWidth())
        self.ConsoleTextEdit.setSizePolicy(sizePolicy2)
        self.ConsoleTextEdit.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)

        self.ConsoleLayout.addWidget(self.ConsoleTextEdit)

        self.ConsoleBottomLayout = QHBoxLayout()
        self.ConsoleBottomLayout.setObjectName(u"ConsoleBottomLayout")
        self.SendCommandTextEdit = QPlainTextEdit(self.ConsoleTab)
        self.SendCommandTextEdit.setObjectName(u"SendCommandTextEdit")
        sizePolicy3 = QSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        sizePolicy3.setHorizontalStretch(0)
        sizePolicy3.setVerticalStretch(0)
        sizePolicy3.setHeightForWidth(self.SendCommandTextEdit.sizePolicy().hasHeightForWidth())
        self.SendCommandTextEdit.setSizePolicy(sizePolicy3)
        self.SendCommandTextEdit.setMinimumSize(QSize(0, 0))
        self.SendCommandTextEdit.setMaximumSize(QSize(16777215, 32))
        self.SendCommandTextEdit.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)

        self.ConsoleBottomLayout.addWidget(self.SendCommandTextEdit)

        self.ClearConsoleButton = QPushButton(self.ConsoleTab)
        self.ClearConsoleButton.setObjectName(u"ClearConsoleButton")
        self.ClearConsoleButton.setMinimumSize(QSize(50, 0))
        self.ClearConsoleButton.setMaximumSize(QSize(50, 16777215))

        self.ConsoleBottomLayout.addWidget(self.ClearConsoleButton)


        self.ConsoleLayout.addLayout(self.ConsoleBottomLayout)


        self.horizontalLayout.addLayout(self.ConsoleLayout)

        self.tabWidget.addTab(self.ConsoleTab, "")
        self.RulesTab = QWidget()
        self.RulesTab.setObjectName(u"RulesTab")
        self.verticalLayout_7 = QVBoxLayout(self.RulesTab)
        self.verticalLayout_7.setObjectName(u"verticalLayout_7")
        self.RulesLayout = QVBoxLayout()
        self.RulesLayout.setSpacing(8)
        self.RulesLayout.setObjectName(u"RulesLayout")
        self.RulesLayout.setContentsMargins(8, 8, 8, 8)
        self.AutomaticLabel = QLabel(self.RulesTab)
        self.AutomaticLabel.setObjectName(u"AutomaticLabel")
        font = QFont()
        font.setBold(True)
        self.AutomaticLabel.setFont(font)
        self.AutomaticLabel.setTextFormat(Qt.TextFormat.AutoText)

        self.RulesLayout.addWidget(self.AutomaticLabel)

        self.AutomaticInfoLabel = QLabel(self.RulesTab)
        self.AutomaticInfoLabel.setObjectName(u"AutomaticInfoLabel")
        self.AutomaticInfoLabel.setStyleSheet(u"color: #a6accd;")
        self.AutomaticInfoLabel.setWordWrap(True)

        self.RulesLayout.addWidget(self.AutomaticInfoLabel)

        self.SampleOutputTextEdit = QPlainTextEdit(self.RulesTab)
        self.SampleOutputTextEdit.setObjectName(u"SampleOutputTextEdit")

        self.RulesLayout.addWidget(self.SampleOutputTextEdit)

        self.GenerateRulesButton = QPushButton(self.RulesTab)
        self.GenerateRulesButton.setObjectName(u"GenerateRulesButton")

        self.RulesLayout.addWidget(self.GenerateRulesButton)

        self.RulesSectionSpacer = QSpacerItem(20, 14, QSizePolicy.Policy.Minimum, QSizePolicy.Policy.Fixed)

        self.RulesLayout.addItem(self.RulesSectionSpacer)

        self.ManualLabel = QLabel(self.RulesTab)
        self.ManualLabel.setObjectName(u"ManualLabel")
        self.ManualLabel.setFont(font)

        self.RulesLayout.addWidget(self.ManualLabel)

        self.ManualInfoLabel = QLabel(self.RulesTab)
        self.ManualInfoLabel.setObjectName(u"ManualInfoLabel")
        self.ManualInfoLabel.setStyleSheet(u"color: #a6accd;")
        self.ManualInfoLabel.setWordWrap(True)

        self.RulesLayout.addWidget(self.ManualInfoLabel)

        self.RulesTable = QTableWidget(self.RulesTab)
        if (self.RulesTable.columnCount() < 6):
            self.RulesTable.setColumnCount(6)
        __qtablewidgetitem = QTableWidgetItem()
        self.RulesTable.setHorizontalHeaderItem(0, __qtablewidgetitem)
        __qtablewidgetitem1 = QTableWidgetItem()
        self.RulesTable.setHorizontalHeaderItem(1, __qtablewidgetitem1)
        __qtablewidgetitem2 = QTableWidgetItem()
        self.RulesTable.setHorizontalHeaderItem(2, __qtablewidgetitem2)
        __qtablewidgetitem3 = QTableWidgetItem()
        self.RulesTable.setHorizontalHeaderItem(3, __qtablewidgetitem3)
        __qtablewidgetitem4 = QTableWidgetItem()
        self.RulesTable.setHorizontalHeaderItem(4, __qtablewidgetitem4)
        __qtablewidgetitem5 = QTableWidgetItem()
        self.RulesTable.setHorizontalHeaderItem(5, __qtablewidgetitem5)
        self.RulesTable.setObjectName(u"RulesTable")

        self.RulesLayout.addWidget(self.RulesTable)

        self.AddRuleButton = QPushButton(self.RulesTab)
        self.AddRuleButton.setObjectName(u"AddRuleButton")

        self.RulesLayout.addWidget(self.AddRuleButton)

        self.RemoveRuleButton = QPushButton(self.RulesTab)
        self.RemoveRuleButton.setObjectName(u"RemoveRuleButton")

        self.RulesLayout.addWidget(self.RemoveRuleButton)


        self.verticalLayout_7.addLayout(self.RulesLayout)

        self.tabWidget.addTab(self.RulesTab, "")

        self.horizontalLayout_2.addWidget(self.tabWidget)

        self.PlotSeparator = QFrame(self.RightFrame)
        self.PlotSeparator.setObjectName(u"PlotSeparator")
        self.PlotSeparator.setFrameShape(QFrame.Shape.VLine)
        self.PlotSeparator.setFrameShadow(QFrame.Shadow.Sunken)

        self.horizontalLayout_2.addWidget(self.PlotSeparator)

        self.PlotTabWidget = QTabWidget(self.RightFrame)
        self.PlotTabWidget.setObjectName(u"PlotTabWidget")
        self.PlotTab = QWidget()
        self.PlotTab.setObjectName(u"PlotTab")
        self.PlotTabLayout = QVBoxLayout(self.PlotTab)
        self.PlotTabLayout.setSpacing(0)
        self.PlotTabLayout.setObjectName(u"PlotTabLayout")
        self.PlotTabLayout.setContentsMargins(0, 0, 0, 0)
        self.Plot = PlotWidget(self.PlotTab)
        self.Plot.setObjectName(u"Plot")

        self.PlotTabLayout.addWidget(self.Plot)

        self.PlotTabWidget.addTab(self.PlotTab, "")

        self.horizontalLayout_2.addWidget(self.PlotTabWidget)
        self.horizontalLayout_2.setStretch(0, 1)
        self.horizontalLayout_2.setStretch(2, 1)

        self.mainSplit.addWidget(self.RightFrame)


        self.main.addLayout(self.mainSplit)


        self.verticalLayout.addLayout(self.main)

        self.verticalLayout.setStretch(0, 1)
        self.verticalLayout.setStretch(1, 10)
        MainWindow.setCentralWidget(self.centralwidget)
        self.menubar = QMenuBar(MainWindow)
        self.menubar.setObjectName(u"menubar")
        self.menubar.setGeometry(QRect(0, 0, 1191, 22))
        self.menuFile = QMenu(self.menubar)
        self.menuFile.setObjectName(u"menuFile")
        MainWindow.setMenuBar(self.menubar)
        self.statusbar = QStatusBar(MainWindow)
        self.statusbar.setObjectName(u"statusbar")
        MainWindow.setStatusBar(self.statusbar)

        self.menubar.addAction(self.menuFile.menuAction())
        self.menuFile.addAction(self.actionSave_profile)
        self.menuFile.addAction(self.actionOpen_profile)
        self.menuFile.addAction(self.actionLoad_log)

        self.retranslateUi(MainWindow)

        self.tabWidget.setCurrentIndex(1)


        QMetaObject.connectSlotsByName(MainWindow)
    # setupUi

    def retranslateUi(self, MainWindow):
        MainWindow.setWindowTitle(QCoreApplication.translate("MainWindow", u"PlotTTY", None))
        self.actionSave_profile.setText(QCoreApplication.translate("MainWindow", u"Save profile", None))
        self.actionOpen_profile.setText(QCoreApplication.translate("MainWindow", u"Open profile", None))
        self.actionLoad_log.setText(QCoreApplication.translate("MainWindow", u"Load log", None))
        self.PortStatusLabel.setText(QCoreApplication.translate("MainWindow", u"No port", None))
        self.ConnectButton.setText(QCoreApplication.translate("MainWindow", u"Connect", None))
        self.pushButton.setText(QCoreApplication.translate("MainWindow", u"Settings", None))
        self.DataReceivedLabel.setText(QCoreApplication.translate("MainWindow", u"0 B/s", None))
        self.ClearConsoleButton.setText(QCoreApplication.translate("MainWindow", u"Clear", None))
        self.tabWidget.setTabText(self.tabWidget.indexOf(self.ConsoleTab), QCoreApplication.translate("MainWindow", u"Console", None))
        self.AutomaticLabel.setText(QCoreApplication.translate("MainWindow", u"Auto setup", None))
        self.AutomaticInfoLabel.setText(QCoreApplication.translate("MainWindow", u"Paste a few raw device output lines, then generate rules.", None))
        self.SampleOutputTextEdit.setPlaceholderText(QCoreApplication.translate("MainWindow", u"Examples:\n"
"Voltage: 3.31 V  Current: 0.14 A\n"
"or\n"
"12345,3.31,0.14,26.8", None))
#if QT_CONFIG(tooltip)
        self.GenerateRulesButton.setToolTip(QCoreApplication.translate("MainWindow", u"Creates plot rules from named values, delimited columns, or the first number in each sample line.", None))
#endif // QT_CONFIG(tooltip)
        self.GenerateRulesButton.setText(QCoreApplication.translate("MainWindow", u"Auto generate rules", None))
        self.ManualLabel.setText(QCoreApplication.translate("MainWindow", u"Manual rules", None))
        self.ManualInfoLabel.setText(QCoreApplication.translate("MainWindow", u"Each row extracts one value. For delimited values, Field index selects which split field to read: 0 is first, 1 is second.", None))
        ___qtablewidgetitem = self.RulesTable.horizontalHeaderItem(0)
        ___qtablewidgetitem.setText(QCoreApplication.translate("MainWindow", u"Plot Y", None))
#if QT_CONFIG(tooltip)
        ___qtablewidgetitem.setToolTip(QCoreApplication.translate("MainWindow", u"Draw this rule as a plotted Y value.", None))
#endif // QT_CONFIG(tooltip)
        ___qtablewidgetitem1 = self.RulesTable.horizontalHeaderItem(1)
        ___qtablewidgetitem1.setText(QCoreApplication.translate("MainWindow", u"Use as X", None))
#if QT_CONFIG(tooltip)
        ___qtablewidgetitem1.setToolTip(QCoreApplication.translate("MainWindow", u"Use this rule's value as the X axis timestamp/counter for the other plotted rules.", None))
#endif // QT_CONFIG(tooltip)
        ___qtablewidgetitem2 = self.RulesTable.horizontalHeaderItem(2)
        ___qtablewidgetitem2.setText(QCoreApplication.translate("MainWindow", u"Series label", None))
#if QT_CONFIG(tooltip)
        ___qtablewidgetitem2.setToolTip(QCoreApplication.translate("MainWindow", u"Name used for the plotted series. Named values can override this with names from the input line.", None))
#endif // QT_CONFIG(tooltip)
        ___qtablewidgetitem3 = self.RulesTable.horizontalHeaderItem(3)
        ___qtablewidgetitem3.setText(QCoreApplication.translate("MainWindow", u"Find method", None))
#if QT_CONFIG(tooltip)
        ___qtablewidgetitem3.setToolTip(QCoreApplication.translate("MainWindow", u"How this rule finds a value in each incoming line.", None))
#endif // QT_CONFIG(tooltip)
        ___qtablewidgetitem4 = self.RulesTable.horizontalHeaderItem(4)
        ___qtablewidgetitem4.setText(QCoreApplication.translate("MainWindow", u"Pattern / delimiter", None))
#if QT_CONFIG(tooltip)
        ___qtablewidgetitem4.setToolTip(QCoreApplication.translate("MainWindow", u"For delimited values, enter the delimiter, such as comma, semicolon, or \\t. For regex, enter the pattern.", None))
#endif // QT_CONFIG(tooltip)
        ___qtablewidgetitem5 = self.RulesTable.horizontalHeaderItem(5)
        ___qtablewidgetitem5.setText(QCoreApplication.translate("MainWindow", u"Field index", None))
#if QT_CONFIG(tooltip)
        ___qtablewidgetitem5.setToolTip(QCoreApplication.translate("MainWindow", u"For delimited values, enter the zero-based field index, such as 0, 1, or 2.", None))
#endif // QT_CONFIG(tooltip)
#if QT_CONFIG(tooltip)
        self.AddRuleButton.setToolTip(QCoreApplication.translate("MainWindow", u"Add a manual rule for one plotted value.", None))
#endif // QT_CONFIG(tooltip)
        self.AddRuleButton.setText(QCoreApplication.translate("MainWindow", u"Add rule", None))
#if QT_CONFIG(tooltip)
        self.RemoveRuleButton.setToolTip(QCoreApplication.translate("MainWindow", u"Remove the selected manual rule.", None))
#endif // QT_CONFIG(tooltip)
        self.RemoveRuleButton.setText(QCoreApplication.translate("MainWindow", u"Remove rule", None))
        self.tabWidget.setTabText(self.tabWidget.indexOf(self.RulesTab), QCoreApplication.translate("MainWindow", u"Rules", None))
        self.PlotTabWidget.setTabText(self.PlotTabWidget.indexOf(self.PlotTab), QCoreApplication.translate("MainWindow", u"Plot", None))
        self.menuFile.setTitle(QCoreApplication.translate("MainWindow", u"File", None))
    # retranslateUi

