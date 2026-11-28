import pytest

from soramado import script as S
from soramado.galaxies import LY_AU


def test_sample_parses():
    cmds = S.parse(S.SAMPLE)
    ops = {c.op for c in cmds}
    assert {"時刻", "地上", "宇宙へ", "飛ぶ", "引く", "着陸", "字幕", "待つ", "回る"} <= ops


def test_english_aliases_and_comments():
    cmds = S.parse("fly jupiter  # go\nwait 2\ncaption Hello # not a comment\nzoom 30au\n")
    assert [c.op for c in cmds] == ["飛ぶ", "待つ", "字幕", "引く"]
    assert cmds[2].text == "Hello # not a comment"


def test_errors_have_line_numbers():
    with pytest.raises(S.ScriptError) as e:
        S.parse("飛ぶ 月\nとぶ 火星\n待つ ながく\n線 虹 オン\n")
    msg = str(e.value)
    assert "2行目" in msg and "3行目" in msg and "4行目" in msg


def test_distances():
    assert abs(S.parse_distance("100億光年") - 1e10 * LY_AU) < 1
    assert S.parse_distance("30AU") == 30
    assert abs(S.parse_distance("1,000光年") - 1000 * LY_AU) < 1e-6
    with pytest.raises(S.ScriptError):
        S.parse_distance("とても遠く")


def test_time_and_look():
    assert S.parse_time("今") == "now"
    assert S.parse_time("日の入り") == "日の入り"
    jd = S.parse_time("2026/12/24 21:00")
    assert 2461398 < jd < 2461400
    assert S.look_direction(["南", "40"]) == (180.0, 40.0)
    assert S.look_direction(["土星"]) is None


def test_dome_command():
    cmds = S.parse("ドーム オン\ndome off\n")
    assert [c.op for c in cmds] == ["ドーム", "ドーム"]
    with pytest.raises(S.ScriptError):
        S.parse("ドーム たぶん")
