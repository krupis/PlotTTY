"""Stream text is available immediately; extraction waits for complete lines."""

import unittest

from modules.core.line_decoder import LineDecoder


class LineDecoderTest(unittest.TestCase):
    def test_partial_text_is_available_before_a_complete_line(self):
        decoder = LineDecoder()
        for data, expected_text, expected_lines in (
            (b"voltage=3.", "voltage=3.", []),
            (b"25\ncurrent=", "25\ncurrent=", ["voltage=3.25"]),
            (b"", "", []),
            (b"1\n\n", "1\n\n", ["current=1", ""]),
        ):
            with self.subTest(data=data):
                text = decoder.decode(data)
                self.assertEqual(text, expected_text)
                self.assertEqual(decoder.split_lines(text), expected_lines)

    def test_unicode_and_crlf_can_cross_receive_boundaries(self):
        decoder = LineDecoder()
        displayed_text = []
        complete_lines = []
        for byte in "į=3.25\r\nnext\rlast\n".encode():
            text = decoder.decode(bytes([byte]))
            displayed_text.append(text)
            complete_lines.extend(decoder.split_lines(text))

        self.assertEqual("".join(displayed_text), "į=3.25\nnext\nlast\n")
        self.assertEqual(complete_lines, ["į=3.25", "next", "last"])
