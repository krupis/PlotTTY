from plottty.core.line_decoder import LineDecoder


def test_decoder_returns_complete_lines_across_chunks():
    decoder = LineDecoder()

    assert decoder.feed(b"Temp") == []
    assert decoder.feed(b":30\nHum") == ["Temp:30"]
    assert decoder.feed(b"idity:50\r\n") == ["Humidity:50"]
    assert decoder.flush() == ""
