import reach


def test_youtube_id():
    assert reach.youtube_id("https://www.youtube.com/watch?v=dQw4w9WgXcQ") == "dQw4w9WgXcQ"
    assert reach.youtube_id("dQw4w9WgXcQ") == "dQw4w9WgXcQ"


def test_doctor_shape():
    d = reach.doctor()
    assert d["total"] >= 5
    assert "web" in d["channels"]
    assert d["channels"]["web"]["status"] == "ok"


def test_strip_html():
    assert "hi" in reach._strip_html("<b>hi</b>")
