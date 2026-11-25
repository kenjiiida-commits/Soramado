"""astropy（ERFA の内蔵暦）と比べて位置計算の精度を確かめる。

実行: python3 -m pytest tests/ または python3 tests/test_astro.py
astropy が無い環境ではスキップする。
"""

import math
import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from soramado import astro  # noqa: E402

try:
    import astropy.units as u
    from astropy.coordinates import get_body_barycentric, solar_system_ephemeris
    from astropy.time import Time
    HAVE_ASTROPY = True
except ImportError:  # pragma: no cover
    HAVE_ASTROPY = False


def _reference(name, jd):
    t = Time(jd, format="jd", scale="utc")
    with solar_system_ephemeris.set("builtin"):
        sun = get_body_barycentric("sun", t).xyz.to(u.au).value
        body = get_body_barycentric(name, t).xyz.to(u.au).value
    return astro.equatorial_to_ecliptic(body - sun)


def _angle_from_earth_deg(a, b, earth):
    va, vb = a - earth, b - earth
    c = np.dot(va, vb) / np.linalg.norm(va) / np.linalg.norm(vb)
    return math.degrees(math.acos(min(1.0, max(-1.0, c))))


DATES = [2433282.5, 2451545.0, 2460000.5, 2461005.5, 2469807.5]  # 1950〜2050年


def test_planets():
    if not HAVE_ASTROPY:
        return
    worst = {}
    for jd in DATES:
        pos = astro.all_positions(jd)
        earth_ref = _reference("earth", jd)
        for name in ("mercury", "venus", "earth", "mars", "jupiter", "saturn", "uranus", "neptune"):
            ref = _reference(name, jd)
            err_au = np.linalg.norm(pos[name] - ref)
            # 地球から見た方向のずれ（地球自身は距離誤差で評価）
            if name == "earth":
                err = err_au * astro.AU_KM
                worst[name] = max(worst.get(name, 0), err)
                assert err < 100000, (name, jd, err)  # 10万km 未満
            else:
                ang = _angle_from_earth_deg(pos[name], ref, earth_ref)
                worst[name] = max(worst.get(name, 0), ang)
                assert ang < 0.2, (name, jd, ang)  # 0.2度未満
    return worst


def test_moon():
    if not HAVE_ASTROPY:
        return
    worst = 0.0
    for jd in DATES:
        pos = astro.all_positions(jd)
        ref = _reference("moon", jd)
        earth_ref = _reference("earth", jd)
        # 地心から見た月の方向どうしを比べる
        ang = _angle_from_earth_deg(pos["moon"] - pos["earth"], ref - earth_ref, np.zeros(3))
        worst = max(worst, ang)
        assert ang < 0.2, (jd, ang)
    return worst


def test_time_roundtrip():
    for jd in DATES:
        dt = astro.datetime_from_jd(jd)
        assert abs(astro.jd_from_datetime(dt) - jd) < 2e-5


if __name__ == "__main__":
    print("惑星（地球から見た方向のずれ[度]、地球は位置のずれ[km]）:", test_planets())
    print("月（地球から見た方向のずれ[度]）:", test_moon())
    test_time_roundtrip()
    print("OK")
