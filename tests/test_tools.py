import tools_reach


def test_tool_schemas_named():
    names = {t["function"]["name"] for t in tools_reach.TOOL_SCHEMAS}
    assert "reach_read" in names
    assert "reach_search" in names
    assert "reach_doctor" in names


def test_parse_args():
    assert tools_reach.parse_tool_arguments('{"url":"x"}')["url"] == "x"
    assert tools_reach.parse_tool_arguments({}) == {}


def test_doctor_tool():
    out = tools_reach.run_tool("reach_doctor", {})
    assert "enabled" in out or "channels" in out


def test_unknown_tool():
    out = tools_reach.run_tool("nope", {})
    assert "error" in out
