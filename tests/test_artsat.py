import math

import numpy as np

from soramado import artsat as A, astro


def _tle(name, num, inc, raan, mm):
    def cks(l):
        return str(sum(int(c) if c.isdigit() else (1 if c == "-" else 0) for c in l[:68]) % 10)
    l1 = f"1 {num:05d}U 98067A   26330.50000000  .00016717  00000+0  10270-3 0  999"[:68]
    l2 = f"2 {num:05d} {inc:8.4f} {raan:8.4f} 0006317  69.9862  25.2906 {mm:11.8f}12345"[:68]
    return f"{name}\n{l1}{cks(l1)}\n{l2}{cks(l2)}\n"


def test_parse_and_orbit():
    if not A.available():
        return
    sats = A.parse(_tle("ISS (ZARYA)", 25544, 51.64, 208.9, 15.4956) + _tle("X", 99999, 98.0, 10.0, 14.2))
    assert len(sats) == 2 and sats[0].ja.startswith("国際宇宙ステーション")
    jd = 2461371.0
    h = A.height_km(sats[0], jd)
    assert 350 < h < 450
    # 1周したら、ほぼ同じ場所（宇宙に対して）に戻る
    p = 1 / sats[0].rev_per_day
    d = np.linalg.norm(A.offset(sats[0], jd) - A.offset(sats[0], jd + p)) * astro.AU_KM
    assert d < 100
    # 軌道の傾きは約51.6度（赤道に対して）
    orb = A.orbit_path(sats[0], jd, 60)
    n = np.cross(orb[0], orb[15])
    n /= np.linalg.norm(n)
    pole = astro.equatorial_to_ecliptic(np.array([0.0, 0.0, 1.0]))
    assert abs(math.degrees(math.acos(abs(float(np.dot(n, pole))))) - 51.6) < 1.5
