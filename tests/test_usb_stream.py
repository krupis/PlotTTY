"""USB reception, device-clock extraction and retained console behavior."""
import os
os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
import unittest
from qt_cleanup import delete_qt_object
from PySide6.QtCore import Qt
from PySide6.QtGui import QTextCursor
from PySide6.QtTest import QSignalSpy, QTest
from PySide6.QtWidgets import QApplication, QPlainTextEdit, QVBoxLayout, QWidget
from modules.core.extraction import ExtractionEngine, ExtractionRule
from modules.controllers.console_controller import ConsoleController, STATUS_TEXT_COLOR, SENT_TEXT_COLOR

APP = QApplication.instance() or QApplication([])


class ConsoleThroughputTest(unittest.TestCase):
    def setUp(self):
        self.panel = QWidget()
        self.addCleanup(delete_qt_object, self.panel)
        layout = QVBoxLayout(self.panel)
        self.editor = QPlainTextEdit()
        layout.addWidget(self.editor)
        self.console_controller = ConsoleController(self.editor, self.panel)
        self.panel.resize(900, 300)
        self.panel.show()
        APP.processEvents()
        self.addCleanup(self.panel.close)
        self.addCleanup(self.console_controller.close)

    def fill(self, count):
        self.console_controller.append_received('\n'.join(f'row-{i:05d}' for i in range(count)) + '\n', 100)
        self.console_controller.flush()

    def search(self, text, *, backwards=False):
        spy = QSignalSpy(self.console_controller.searchFinished)
        self.console_controller.find_text(text, backwards=backwards)
        if not spy.count():
            self.assertTrue(spy.wait(3000))
        return tuple(spy.at(0))

    def test_search_reads_history_outside_the_rendered_window(self):
        self.fill(6000)
        self.assertLessEqual(self.editor.document().blockCount(), 512)
        self.assertEqual(self.search('row-04000'), (1, 1))
        self.assertEqual(self.editor.textCursor().selectedText(), 'row-04000')
        QTest.keyClick(self.editor, Qt.Key.Key_A, Qt.KeyboardModifier.ControlModifier)
        QTest.keyClick(self.editor, Qt.Key.Key_C, Qt.KeyboardModifier.ControlModifier)
        self.assertEqual(APP.clipboard().text(), self.editor.toPlainText())
        self.assertLessEqual(len(APP.clipboard().text().splitlines()), 512)

    def test_full_history_survives_beyond_the_previous_50000_line_limit(self):
        self.fill(100000)
        self.assertEqual(self.console_controller._history.count, 100001)
        self.assertEqual(self.console_controller._history.path.read_text(encoding='utf-8').splitlines()[0], 'row-00000')
        self.assertLess(len(self.console_controller._history.offsets), 200)
        self.console_controller.scroll_bar.setValue(0)
        self.assertIn('row-00000', self.editor.toPlainText())
        self.assertEqual(self.search('row-99999'), (1, 1))

    def test_frozen_history_view_does_not_follow_new_data(self):
        self.fill(6000)
        self.console_controller.scroll_bar.setValue(1000)
        before = self.editor.toPlainText()
        self.console_controller.append_received('newest\n', 100)
        self.console_controller.flush()
        self.assertEqual(self.editor.toPlainText(), before)
        self.console_controller.scroll_bar.setValue(self.console_controller.scroll_bar.maximum())
        self.assertIn('newest', self.editor.toPlainText())

    def test_split_crlf_unicode_and_colors_preserve_plain_text(self):
        self.console_controller.append_status('status: ')
        self.console_controller.append_sent('ready\r')
        self.console_controller.append_received('\nvoltage 🦊 į: 3.3\n', 100)
        self.console_controller.flush()
        self.editor.selectAll()
        self.editor.copy()
        self.assertEqual(APP.clipboard().text(), 'status: ready\nvoltage 🦊 į: 3.3\n')
        cursor = QTextCursor(self.editor.document())
        cursor.setPosition(1)
        self.assertEqual(cursor.charFormat().foreground().color(), STATUS_TEXT_COLOR)
        cursor.setPosition(9)
        self.assertEqual(cursor.charFormat().foreground().color(), SENT_TEXT_COLOR)
        self.assertEqual(self.search('į'), (1, 1))
        self.assertEqual(self.editor.textCursor().selectedText(), 'į')

    def test_clear_and_close_cancel_search_and_remove_the_temporary_file(self):
        self.fill(60000)
        path = self.console_controller._history.path
        self.console_controller.find_text('row')
        self.console_controller.clear()
        APP.processEvents()
        self.assertEqual(path.read_bytes(), b'')
        self.assertEqual(self.editor.toPlainText(), '')
        self.console_controller.close()
        self.console_controller.close()
        self.assertFalse(path.exists())


class DeviceClockTest(unittest.TestCase):
    def test_missing_time_field_never_falls_back_to_host_epoch_for_plot_values(self):
        engine = ExtractionEngine([
            ExtractionRule('Time', 'delimited_values', is_time=True, extra_setting='6'),
            ExtractionRule('Voltage', 'delimited_values', extra_setting='2')])
        self.assertEqual(engine.extract('42,3,3.3,24,5,115', 1700000000), [])
        sample = engine.extract('43,3,3.3,24,5,115,12.000100,0', 1700000000)[0]
        self.assertEqual(sample.timestamp, 12.0001)
        self.assertEqual(sample.value, 3.3)
        self.assertEqual(sample.raw_text, '43,3,3.3,24,5,115,12.000100,0')
