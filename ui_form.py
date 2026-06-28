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
from PySide6.QtWidgets import (QApplication, QFrame, QHBoxLayout, QLabel,
    QMainWindow, QMenu, QMenuBar, QPlainTextEdit,
    QPushButton, QSizePolicy, QStackedWidget, QStatusBar,
    QTabWidget, QVBoxLayout, QWidget)

class Ui_MainWindow(object):
    def setupUi(self, MainWindow):
        if not MainWindow.objectName():
            MainWindow.setObjectName(u"MainWindow")
        MainWindow.resize(800, 600)
        self.centralwidget = QWidget(MainWindow)
        self.centralwidget.setObjectName(u"centralwidget")
        self.verticalLayout_5 = QVBoxLayout(self.centralwidget)
        self.verticalLayout_5.setObjectName(u"verticalLayout_5")
        self.stackedWidget = QStackedWidget(self.centralwidget)
        self.stackedWidget.setObjectName(u"stackedWidget")
        self.page1 = QWidget()
        self.page1.setObjectName(u"page1")
        self.verticalLayout = QVBoxLayout(self.page1)
        self.verticalLayout.setObjectName(u"verticalLayout")
        self.TopNavBar = QHBoxLayout()
        self.TopNavBar.setObjectName(u"TopNavBar")
        self.label = QLabel(self.page1)
        self.label.setObjectName(u"label")
        sizePolicy = QSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Preferred)
        sizePolicy.setHorizontalStretch(0)
        sizePolicy.setVerticalStretch(0)
        sizePolicy.setHeightForWidth(self.label.sizePolicy().hasHeightForWidth())
        self.label.setSizePolicy(sizePolicy)

        self.TopNavBar.addWidget(self.label)

        self.plainTextEdit = QPlainTextEdit(self.page1)
        self.plainTextEdit.setObjectName(u"plainTextEdit")
        sizePolicy1 = QSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Ignored)
        sizePolicy1.setHorizontalStretch(0)
        sizePolicy1.setVerticalStretch(0)
        sizePolicy1.setHeightForWidth(self.plainTextEdit.sizePolicy().hasHeightForWidth())
        self.plainTextEdit.setSizePolicy(sizePolicy1)

        self.TopNavBar.addWidget(self.plainTextEdit)

        self.ConnectButton = QPushButton(self.page1)
        self.ConnectButton.setObjectName(u"ConnectButton")

        self.TopNavBar.addWidget(self.ConnectButton)

        self.DisconnectButton = QPushButton(self.page1)
        self.DisconnectButton.setObjectName(u"DisconnectButton")

        self.TopNavBar.addWidget(self.DisconnectButton)


        self.verticalLayout.addLayout(self.TopNavBar)

        self.main = QVBoxLayout()
        self.main.setObjectName(u"main")
        self.mainSplit = QHBoxLayout()
        self.mainSplit.setObjectName(u"mainSplit")
        self.RightFrame = QFrame(self.page1)
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

        self.ConsoleLayout.addWidget(self.ConsoleTextEdit)


        self.horizontalLayout.addLayout(self.ConsoleLayout)

        self.tabWidget.addTab(self.ConsoleTab, "")
        self.RulesTab = QWidget()
        self.RulesTab.setObjectName(u"RulesTab")
        self.verticalLayout_7 = QVBoxLayout(self.RulesTab)
        self.verticalLayout_7.setObjectName(u"verticalLayout_7")
        self.RulesLayout = QVBoxLayout()
        self.RulesLayout.setObjectName(u"RulesLayout")

        self.verticalLayout_7.addLayout(self.RulesLayout)

        self.tabWidget.addTab(self.RulesTab, "")

        self.horizontalLayout_2.addWidget(self.tabWidget)

        self.Plot = QWidget(self.RightFrame)
        self.Plot.setObjectName(u"Plot")
        self.verticalLayout_4 = QVBoxLayout(self.Plot)
        self.verticalLayout_4.setObjectName(u"verticalLayout_4")

        self.horizontalLayout_2.addWidget(self.Plot)

        self.horizontalLayout_2.setStretch(1, 1)

        self.mainSplit.addWidget(self.RightFrame)


        self.main.addLayout(self.mainSplit)


        self.verticalLayout.addLayout(self.main)

        self.verticalLayout.setStretch(0, 1)
        self.verticalLayout.setStretch(1, 10)
        self.stackedWidget.addWidget(self.page1)
        self.page_2 = QWidget()
        self.page_2.setObjectName(u"page_2")
        self.verticalLayout_2 = QVBoxLayout(self.page_2)
        self.verticalLayout_2.setObjectName(u"verticalLayout_2")
        self.test = QVBoxLayout()
        self.test.setObjectName(u"test")

        self.verticalLayout_2.addLayout(self.test)

        self.stackedWidget.addWidget(self.page_2)

        self.verticalLayout_5.addWidget(self.stackedWidget)

        MainWindow.setCentralWidget(self.centralwidget)
        self.menubar = QMenuBar(MainWindow)
        self.menubar.setObjectName(u"menubar")
        self.menubar.setGeometry(QRect(0, 0, 800, 22))
        self.menuFile = QMenu(self.menubar)
        self.menuFile.setObjectName(u"menuFile")
        self.menuSettings = QMenu(self.menubar)
        self.menuSettings.setObjectName(u"menuSettings")
        MainWindow.setMenuBar(self.menubar)
        self.statusbar = QStatusBar(MainWindow)
        self.statusbar.setObjectName(u"statusbar")
        MainWindow.setStatusBar(self.statusbar)

        self.menubar.addAction(self.menuFile.menuAction())
        self.menubar.addAction(self.menuSettings.menuAction())

        self.retranslateUi(MainWindow)

        self.tabWidget.setCurrentIndex(1)


        QMetaObject.connectSlotsByName(MainWindow)
    # setupUi

    def retranslateUi(self, MainWindow):
        MainWindow.setWindowTitle(QCoreApplication.translate("MainWindow", u"MainWindow", None))
        self.label.setText(QCoreApplication.translate("MainWindow", u"Port:", None))
        self.ConnectButton.setText(QCoreApplication.translate("MainWindow", u"Connect", None))
        self.DisconnectButton.setText(QCoreApplication.translate("MainWindow", u"Disconnect", None))
        self.tabWidget.setTabText(self.tabWidget.indexOf(self.ConsoleTab), QCoreApplication.translate("MainWindow", u"Console", None))
        self.tabWidget.setTabText(self.tabWidget.indexOf(self.RulesTab), QCoreApplication.translate("MainWindow", u"Rules", None))
        self.menuFile.setTitle(QCoreApplication.translate("MainWindow", u"File", None))
        self.menuSettings.setTitle(QCoreApplication.translate("MainWindow", u"Settings", None))
    # retranslateUi

