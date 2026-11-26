"""地上から見た高度・方位を astropy と比べる（大気差なし）。"""

import math
import sys
from pathlib import Path


sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from soramado import astro  # noqa: E402
from soramado.stars import StarCatalog  # noqa: E402

try:
    import astropy.units as u
    from astropy.coordinates import AltAz, EarthLocation, SkyCoord, get_body
    from astropy.time import Time
    from astropy.utils import iers
    iers.conf.auto_download = False
    HAVE = True
except ImportError:  # pragma: no cover
    HAVE = False

LAT, LON = 34.65, 135.51          # 大阪
DATES = [astro.jd_from_datetime(__import__("datetime").datetime(2026, 11, 26, 12, 0,
                                                                tzinfo=__import__("datetime").timezone.utc)),
         2461200.75, 2462000.6]


def _ref(target, jd):
    t = Time(jd, format="jd", scale="utc")
    loc = EarthLocation(lat=LAT * u.deg, lon=LON * u.deg, height=0 * u.m)
    frame = AltAz(obstime=t, location=loc, pressure=0)
    c = (SkyCoord(ra=target[0] * u.deg, dec=target[1] * u.deg) if isinstance(target, tuple)
         else get_body(target, t, loc, ephemeris="builtin"))
    a = c.transform_to(frame)
    return a.alt.deg, a.az.deg


def _sep(a1, z1, a2, z2):
    a1, z1, a2, z2 = map(math.radians, (a1, z1, a2, z2))
    c = math.sin(a1) * math.sin(a2) + math.cos(a1) * math.cos(a2) * math.cos(z1 - z2)
    return math.degrees(math.acos(max(-1, min(1, c))))


def test_ground():
    if not HAVE:
        return
    cat = StarCatalog()
    names = list(cat.proper)
    worst = {}
    for jd in DATES:
        off, zen, north, east = astro.observer_frame(jd, LAT, LON)
        pos = astro.all_positions(jd)
        obs = pos["earth"] + off
        checks = {"Sirius": (101.2872, -16.7161), "Vega": (279.2347, 38.7837)}
        for nm, radec in checks.items():
            d = cat.dir[names.index(nm)]
            a, z = astro.alt_az(d, zen, north, east)
            ra, za = _ref(radec, jd)
            worst[nm] = max(worst.get(nm, 0), _sep(a, z, ra, za))
        for body in ("moon", "jupiter", "sun"):
            # 月は地球との相対位置が正確なので、地心からの向き＋視差で比べる
            a, z = astro.alt_az(pos[body] - obs, zen, north, east)
            ra, za = _ref(body, jd)
            worst[body] = max(worst.get(body, 0), _sep(a, z, ra, za))
    for k, v in worst.items():
        # 恒星は歳差以外に章動・光行差（最大約0.01度）を無視している
        assert v < (0.25 if k in ("moon", "jupiter") else 0.05), (k, v)
    return worst


if __name__ == "__main__":
    print("地上から見た方向のずれ（最大）[度]:", test_ground())
    print("OK")
