from datetime import datetime, timedelta, timezone

import pytest

from soramado import tonight

pytestmark = pytest.mark.skipif(not tonight.available(), reason="PyEphem がない")
JST = timezone(timedelta(hours=9))


def test_night_of_early_morning_is_previous_evening():
    assert tonight.night_of(datetime(2026, 11, 27, 3, 0, tzinfo=JST)).day == 26
    assert tonight.night_of(datetime(2026, 11, 26, 21, 0, tzinfo=JST)).day == 26


def test_osaka_night_order_and_planets():
    g = tonight.build(datetime(2026, 11, 26, 21, 0, tzinfo=JST), 34.69, 135.50, with_events=False)
    n = g.night
    assert n.sunset < n.dusk < n.dawn < n.sunrise
    assert 0.5 < n.sunrise - n.sunset < 0.65          # 11月末の大阪の夜は約14時間
    p = {x.key: x for x in g.planets}
    assert p["saturn"].when == "evening"              # 2026年11月末: 土星は宵の空
    assert p["venus"].when == "morning"               # 金星は明け方
    assert g.moon.illum > 0.8 and g.moon.bright_night  # 満月すぎ
