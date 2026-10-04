import reach


def test_youtube_id():
    assert reach.youtube_id("https://www.youtube.com/watch?v=dQw4w9WgXcQ") == "dQw4w9WgXcQ"
    assert reach.youtube_id("dQw4w9WgXcQ") == "dQw4w9WgXcQ"


def test_doctor_shape():
    d = reach.doctor()
    assert d["total"] >= 6
    assert "web" in d["channels"]
    assert d["channels"]["web"]["status"] == "ok"
    assert "v2ex" in d["channels"]
    assert d["channels"]["v2ex"]["status"] == "ok"


def test_strip_html():
    assert "hi" in reach._strip_html("<b>hi</b>")


def test_v2ex_regex():
    assert reach._V2EX_TOPIC_RE.search("https://www.v2ex.com/t/12345").group(1) == "12345"
    assert reach._V2EX_MEMBER_RE.search("https://www.v2ex.com/member/Livid").group(1) == "Livid"
    assert reach._V2EX_NODE_RE.search("https://www.v2ex.com/go/python").group(1) == "python"


def test_twitter_id():
    import reach_social
    assert reach_social.twitter_id("20") == "20"
    assert reach_social.twitter_id("https://x.com/jack/status/20") == "20"


def test_vault_roundtrip():
    import vault
    vault.clear_platform("twitter")
    assert vault.status()["platforms"]["twitter"]["configured"] is False
    vault.set_secrets("twitter", {"auth_token": "abc", "ct0": "def"})
    assert vault.status()["platforms"]["twitter"]["configured"] is True
    assert vault.twitter_cookies()["auth_token"] == "abc"
    vault.clear_platform("twitter")
    assert vault.status()["platforms"]["twitter"]["configured"] is False


def test_doctor_has_social():
    d = reach.doctor()
    assert "twitter" in d["channels"]
    assert "reddit" in d["channels"]
