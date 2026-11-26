"""日食・月食の予報を、よく知られた予報とくらべる。"""
from soramado import astro, eclipses as E


def _find(lst, y, m, d, kind):
    for e in lst:
        dt = astro.datetime_from_jd(e.jd_max)
        if e.kind == kind and (dt.year, dt.month) == (y, m) and abs(dt.day - d) <= 1:
            return e
    raise AssertionError((y, m, d, kind))


def test_known_eclipses():
    if not E.available():
        return
    lst = E.search(astro.jd_from_datetime(__import__("datetime").datetime(2027, 1, 1,
                   tzinfo=__import__("datetime").timezone.utc)), 4.0, 34.69, 135.50)
    # NASA の日食・月食カタログ（Espenak）による
    assert _find(lst, 2027, 2, 6, "solar").type == "annular"
    assert _find(lst, 2027, 8, 2, "solar").type == "total"
    assert _find(lst, 2028, 7, 22, "solar").type == "total"
    assert _find(lst, 2028, 7, 6, "lunar").type == "partial"
    assert _find(lst, 2028, 12, 31, "lunar").type == "total"
    assert _find(lst, 2029, 6, 26, "lunar").type == "total"
    assert _find(lst, 2027, 2, 20, "lunar").type == "penumbral"
    e = _find(lst, 2027, 8, 2, "solar")
    dt = astro.datetime_from_jd(e.jd_max)
    assert (dt.hour, dt.minute) in ((10, m) for m in range(0, 15))     # 最大 10:07 UT
    # 2030年6月1日の日食：大阪では部分日食（北海道では金環日食）
    lst2 = E.search(2462650.5, 0.05, 34.69, 135.50)
    sol = [e for e in lst2 if e.kind == "solar"][0]
    assert sol.type == "annular" and sol.local["visible"] and sol.local["type"] == "partial"
    lst3 = E.search(2462650.5, 0.05, 43.06, 141.35)
    assert [e for e in lst3 if e.kind == "solar"][0].local["type"] == "annular"


def test_light_fraction():
    import numpy as np
    # 太陽と同じ大きさの円が真ん前にあれば、太陽は全部かくれる
    f = E.sun_light_fraction(np.zeros(3), np.array([1.0, 0, 0]), 0.00465, np.array([0.5, 0, 0]), 0.0024)
    assert f < 0.01
    assert E.sun_light_fraction(np.zeros(3), np.array([1.0, 0, 0]), 0.00465, np.array([0, 0.5, 0]), 0.0024) == 1.0
