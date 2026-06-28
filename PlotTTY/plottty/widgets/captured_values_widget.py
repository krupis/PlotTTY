"""Table of values captured by extraction rules."""

from __future__ import annotations

from datetime import datetime

from PySide6.QtCore import QTimer
from PySide6.QtWidgets import QAbstractItemView, QTableWidget, QTableWidgetItem

from plottty.core.models import CapturedValue


class CapturedValuesWidget(QTableWidget):
    REFRESH_INTERVAL_MS = 100

    def __init__(self, parent=None):
        super().__init__(0, 5, parent)
        self._rows_by_label: dict[str, int] = {}
        self._pending_by_label: dict[str, CapturedValue] = {}
        self.setHorizontalHeaderLabels(["Time", "Label", "Value", "Unit", "Raw Text"])
        self.horizontalHeader().setStretchLastSection(True)
        self.verticalHeader().setVisible(False)
        self.setAlternatingRowColors(True)
        self.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)

        # Introduce a table refresh timer instead of updating the table immediately as the data arrives.
        self._refresh_timer = QTimer(self)
        self._refresh_timer.setInterval(self.REFRESH_INTERVAL_MS)
        self._refresh_timer.timeout.connect(self.flush_pending_updates)


    def append_values(self, values: list[CapturedValue]) -> None:
        for value in values:
            self._pending_by_label[value.label] = value

        if self._pending_by_label and not self._refresh_timer.isActive():
            self._refresh_timer.start()

    def clear_values(self) -> None:
        self._refresh_timer.stop()
        self._pending_by_label.clear()
        self.setRowCount(0)
        self._rows_by_label.clear()

    # 
    def flush_pending_updates(self) -> None:
        if not self._pending_by_label:
            self._refresh_timer.stop()
            return

        pending_values = list(self._pending_by_label.values())
        self._pending_by_label.clear()

        for value in pending_values:
            row = self._rows_by_label.get(value.label)
            if row is None:
                row = self.rowCount()
                self.insertRow(row)
                self._rows_by_label[value.label] = row

            timestamp_text = datetime.fromtimestamp(value.timestamp).strftime("%H:%M:%S.%f")[:-3]
            columns = [
                timestamp_text,
                value.label,
                f"{value.value:g}",
                value.unit,
                value.raw_text,
            ]
            for column, text in enumerate(columns):
                item = self.item(row, column)
                if item is None:
                    item = QTableWidgetItem()
                    self.setItem(row, column, item)
                item.setText(text)

        if not self._pending_by_label:
            self._refresh_timer.stop()
