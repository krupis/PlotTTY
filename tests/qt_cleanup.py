"""Destroy test-owned Qt objects on the GUI thread, before Python drops them."""
from PySide6.QtCore import QCoreApplication, QEvent


def delete_qt_object(obj):
    obj.deleteLater()
    QCoreApplication.sendPostedEvents(None, QEvent.Type.DeferredDelete)
