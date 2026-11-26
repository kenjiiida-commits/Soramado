"""小天体の確認。冥王星は PyEphem と比べ、その他は軌道の形（近日点距離など）を確かめる。"""

import math
import sys
from datetime import datetime, timezone
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from soramado import astro, smallbodies as SB  # noqa: E402

try:
    import ephem
except ImportError:  # pragma: no cover
    ephem = None


def test_pluto():
    if ephem is None:
        return
    worst = 0.0
    c, s = math.cos(astro.OBLIQUITY_J2000), math.sin(astro.OBLIQUITY_J2000)
    for y in (1990, 2000, 2015, 2026, 2040):
        when = datetime(y, 6, 1)
        jd = astro.jd_from_datetime(when.replace(tzinfo=timezone.utc))
        pos = SB.add_positions(astro.all_positions(jd), jd)
        v = pos["pluto"] - pos["earth"]
        ra = math.atan2(c * v[1] - s * v[2], v[0])
        dec = math.asin((s * v[1] + c * v[2]) / np.linalg.norm(v))
        p = ephem.Pluto(when)
        cosd = (math.sin(dec) * math.sin(p.a_dec)
                + math.cos(dec) * math.cos(p.a_dec) * math.cos(ra - p.a_ra))
        worst = max(worst, math.degrees(math.acos(min(1.0, cosd))))
    assert worst < 0.05, worst
    return worst


def test_shapes():
    for b in SB.SMALL_BODIES:
        pts = SB.orbit_path(b, 2000)
        r = np.linalg.norm(pts, axis=1)
        q, Q = b.a * (1 - b.e), b.a * (1 + b.e)
        assert abs(r.min() - q) < 1e-3 * Q and abs(r.max() - Q) < 1e-3 * Q, b.key
        # 近日点通過日には太陽からの距離が近日点距離になる
        if b.tp:
            assert abs(np.linalg.norm(SB.position(b, b.tp)) - q) < 1e-6, b.key


if __name__ == "__main__":
    print("冥王星（PyEphem とのずれ、最大）[度]:", test_pluto())
    test_shapes()
    print("OK")
