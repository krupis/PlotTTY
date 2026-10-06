"""RTT target catalog loading and search behavior."""
import os
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
from threading import Event
from types import SimpleNamespace
import unittest
from unittest.mock import Mock, patch

from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication

from modules.core.rtt_transport import RttSettings
from modules.widgets.rtt_settings_widget import RttSettingsWidget

APP = QApplication.instance() or QApplication([])


class RttTargetSearchTest(unittest.TestCase):
    def setUp(self):
        self.widget = RttSettingsWidget()
        self.addCleanup(self.widget.close)

    def test_background_catalog_preserves_draft_filters_and_caches_without_opening_probe(self):
        release = Event()
        self.addCleanup(release.set)
        names = ["STM32G474VE", "nRF52840_xxAA", "STM32G474RE", "STM32G474VE"]
        probe = Mock()
        probe.num_supported_devices.return_value = len(names)
        def device(index):
            release.wait(2)
            return SimpleNamespace(name=names[index])
        probe.supported_device.side_effect = device
        factory = Mock(return_value=probe)
        with patch.dict("sys.modules", {"pylink": SimpleNamespace(JLink=factory)}):
            factory.assert_not_called()
            self.widget.show()
            self.assertTrue(self.widget._targets_loading)
            self.widget.target_combo.setEditText("custom-target")
            release.set()
            for _ in range(100):
                APP.processEvents()
                if self.widget._targets_loaded:
                    break
                QTest.qWait(10)
            self.assertTrue(self.widget._targets_loaded)
            self.assertEqual(self.widget.selected_settings().target, "custom-target")
            self.assertEqual(self.widget.target_model.rowCount(), 3)
            completer = self.widget.target_combo.completer()
            completer.setCompletionPrefix("g474")
            self.assertEqual(completer.completionCount(), 2)
            self.widget.target_combo.setCurrentIndex(self.widget.target_combo.findText("STM32G474VE"))
            self.assertEqual(self.widget.selected_settings().target, "STM32G474VE")
            self.widget.hide()
            self.widget.show()
            APP.processEvents()
            factory.assert_called_once_with()
            probe.open.assert_not_called()
            probe.connect.assert_not_called()

    def test_unavailable_catalog_keeps_custom_target_editable(self):
        self.widget.set_settings(RttSettings(target="custom-target"))
        factory = Mock(side_effect=RuntimeError("J-Link library not found"))
        with patch.dict("sys.modules", {"pylink": SimpleNamespace(JLink=factory)}):
            self.widget._load_targets()
            APP.processEvents()
        self.assertIn("unavailable", self.widget.target_hint.text())
        self.assertIn("J-Link library not found", self.widget.target_hint.toolTip())
        self.widget.target_combo.setEditText("different-target")
        self.assertEqual(self.widget.selected_settings().target, "different-target")
        self.assertFalse(self.widget._targets_loaded)

    def test_setting_target_does_not_load_catalog_or_modify_source_settings(self):
        settings = RttSettings(target="STM32G474VE", probe_serial="123", up_channel=2)
        factory = Mock()
        with patch.dict("sys.modules", {"pylink": SimpleNamespace(JLink=factory)}):
            self.widget.set_settings(settings)
            factory.assert_not_called()
        self.assertEqual(self.widget.selected_settings(), settings)
        self.widget.target_combo.setEditText("STM32U545RETx")
        self.assertEqual(settings.target, "STM32G474VE")
