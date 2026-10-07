import csv
from pathlib import Path
import struct
import tempfile
import unittest
from unittest.mock import patch
import zlib

from modules.core.binary_logging import (
    BinaryCaptureWriter, BLOCK_HEADER, CaptureFormatError, MAGIC, MAX_BLOCK,
    iter_binary_capture, CaptureCancelled, export_capture_csv, PlotSessionLog,
)
from modules.core.extraction import CapturedValue


class CaptureFileTest(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        self.root = Path(self.directory.name)
        self.path = self.root / "test.plotty"

    def write(self, values):
        with self.path.open("wb") as file:
            writer = BinaryCaptureWriter(file)
            writer.write_values(values)
            writer.finish()

    def read(self):
        return [v for batch in iter_binary_capture(self.path, 3) for v in batch]

    def test_round_trip_across_blocks_calls_and_labels(self):
        values = [CapturedValue(1700000000 + i / 2000, label, value, 'a,"b"\nĮrašas')
                  for i in range(30)
                  for label, value in (("Voltage", 3.123456789012345), ("Current", -0.0))]
        values += [CapturedValue(1700000001, "Current", 25.0, "different")]
        with patch("modules.core.binary_logging.BLOCK_TARGET", 160):
            with self.path.open("wb") as file:
                writer = BinaryCaptureWriter(file)
                for i in range(0, len(values), 5):
                    writer.write_values(values[i:i + 5])
                writer.flush()
                writer.finish()
                writer.finish()
        result = self.read()
        self.assertEqual(result, values)
        self.assertEqual(struct.pack("<d", result[1].value), struct.pack("<d", -0.0))

    def test_special_doubles_preserve_bits(self):
        values = [CapturedValue(1, "a", value) for value in (float('nan'), float('inf'), -float('inf'), -0.0)]
        self.write(values)
        self.assertEqual([struct.pack('<d', v.value) for v in self.read()],
                         [struct.pack('<d', v.value) for v in values])

    def test_shared_raw_text_and_timestamp_are_stored_once(self):
        # Register metadata first so the six subsequent values form one group.
        raw = "unique full serial line"
        with self.path.open("wb") as file:
            writer = BinaryCaptureWriter(file)
            writer.write_values([CapturedValue(0, str(i), i) for i in range(6)])
            writer.flush()
            writer.write_values([CapturedValue(1, str(i), i, raw) for i in range(6)])
            writer.finish()
        data = self.path.read_bytes(); offset = len(MAGIC); decoded = b""
        while True:
            size, compressed = BLOCK_HEADER.unpack_from(data, offset); offset += BLOCK_HEADER.size
            if size == 0: break
            decoded += zlib.decompress(data[offset:offset + compressed]); offset += compressed
        self.assertEqual(decoded.count(raw.encode()), 1)
        self.assertEqual(len(self.read()), 12)

    def test_empty_and_one_value_captures(self):
        self.write([])
        self.assertEqual(self.read(), [])
        self.write([CapturedValue(1, "a", 2)])
        self.assertEqual(len(self.read()), 1)

    def test_truncation_corruption_version_and_trailing_bytes_rejected(self):
        self.write([CapturedValue(1, "a", 2)])
        data = self.path.read_bytes()
        damaged = bytearray(data); damaged[len(MAGIC) + BLOCK_HEADER.size + 3] ^= 255
        variants = [data[:-1], data[:-8], data[:12], data[:7] + b'\x01' + data[8:],
                    bytes(damaged), data + b'extra', MAGIC + BLOCK_HEADER.pack(MAX_BLOCK + 1, 10)]
        for value in variants:
            with self.subTest(value=value[:16]):
                self.path.write_bytes(value)
                with self.assertRaises(CaptureFormatError): self.read()

    def test_unknown_series_rejected(self):
        record = b'R' + struct.pack('<dIIId', 1, 0, 1, 99, 2)
        packed = zlib.compress(record)
        self.path.write_bytes(MAGIC + BLOCK_HEADER.pack(len(record), len(packed)) + packed + b'\0' * 8)
        with self.assertRaisesRegex(CaptureFormatError, "undefined series"): self.read()

    def test_csv_export_preserves_fields(self):
        values = [CapturedValue(1.123456789, "Įtampa", -0.0, 'a,\n"quoted"'), CapturedValue(2, 'b', 42)]
        self.write(values)
        target = self.root / 'export.csv'
        self.assertEqual(export_capture_csv(self.path, target), 2)
        with target.open(newline='', encoding='utf-8') as file:
            reader = csv.DictReader(file)
            self.assertEqual(reader.fieldnames, ['timestamp', 'label', 'value', 'raw_text'])
            rows = list(reader)
        self.assertEqual([CapturedValue(float(r['timestamp']), r['label'], float(r['value']), r['raw_text'])
                          for r in rows], values)

    def test_failed_or_cancelled_export_keeps_destination(self):
        self.write([CapturedValue(1, 'a', 2)])
        target = self.root / 'existing.csv'; target.write_text('existing content')
        with self.assertRaises(CaptureCancelled):
            export_capture_csv(self.path, target, cancelled=lambda: True)
        self.assertEqual(target.read_text(), 'existing content')
        self.path.write_bytes(self.path.read_bytes()[:-8])
        with self.assertRaises(CaptureFormatError): export_capture_csv(self.path, target)
        self.assertEqual(target.read_text(), 'existing content')
        self.assertEqual(list(self.root.glob('.plottty_*')), [])

    def test_same_source_destination_rejected(self):
        self.write([])
        with self.assertRaises(ValueError): export_capture_csv(self.path, self.path)
        self.assertEqual(self.read(), [])

    def test_session_close_flushes_and_reconnect_does_not_overwrite(self):
        log = PlotSessionLog(self.root)
        first = log.start('Serial COM15 at 115200 baud')
        log.write_values([CapturedValue(1, 'a', 2)])
        log.flush(); log.close(); log.close()
        second = log.start('Serial COM15 at 115200 baud')
        log.close()
        self.assertNotEqual(first, second)
        self.assertEqual(sum(len(b) for b in iter_binary_capture(first)), 1)


if __name__ == '__main__':
    unittest.main()
