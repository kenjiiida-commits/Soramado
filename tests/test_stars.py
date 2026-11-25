"""恒星の位置・名前の確認。astropy で黄道座標に直した値と比べる。"""

import math
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from soramado.stars import StarCatalog  # noqa: E402

try:
    import astropy.units as u
    from astropy.coordinates import GeocentricMeanEcliptic, SkyCoord
    HAVE_ASTROPY = True
except ImportError:  # pragma: no cover
    HAVE_ASTROPY = False

# (固有名, 赤経[度], 赤緯[度])  J2000
CHECK = [("Betelgeuse", 88.7929, 7.4071), ("Sirius", 101.2872, -16.7161),
         ("Polaris", 37.9546, 89.2641), ("Vega", 279.2347, 38.7837)]


def test_positions():
    cat = StarCatalog()
    names = list(cat.proper)
    worst = 0.0
    for name, ra, dec in CHECK:
        i = names.index(name)
        v = cat.dir[i]
        lon = math.degrees(math.atan2(v[1], v[0])) % 360
        lat = math.degrees(math.asin(v[2]))
        if HAVE_ASTROPY:
            e = SkyCoord(ra=ra * u.deg, dec=dec * u.deg, frame="icrs").transform_to(
                GeocentricMeanEcliptic(equinox="J2000"))
            dlon = (lon - e.lon.deg + 180) % 360 - 180
            err = math.hypot(dlon * math.cos(math.radians(lat)), lat - e.lat.deg)
            worst = max(worst, err)
            assert err < 0.01, (name, err)
    assert cat.short_name(names.index("Sirius")) == "シリウス"
    assert cat.designation(names.index("Betelgeuse")) == "オリオン座α星"
    return worst


if __name__ == "__main__":
    print("恒星の方向のずれ（最大）[度]:", test_positions())
    print("OK")
