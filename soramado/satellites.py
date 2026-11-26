"""惑星の衛星。

火星・木星・土星・天王星の衛星は、PyEphem（XEphem の衛星理論）で位置を計算する。
PyEphem は「地球から見て惑星からどれだけ東西・南北・手前奥にずれているか」を返すので、
それを宇宙空間のベクトルに直して使う（光が届くのにかかる時間の分だけ、地球から見た姿になる）。

海王星のトリトンは PyEphem にないので、NASA JPL "Planetary Satellite Mean Elements"
(https://ssd.jpl.nasa.gov/sats/elem/) の平均軌道要素から計算する（おおよその位置）。
"""

from __future__ import annotations

import math
from dataclasses import dataclass

import numpy as np

from . import astro

try:
    import ephem
except ImportError:      # PyEphem が無いときは衛星を出さない
    ephem = None

JD_EPOCH = 2451545.0


@dataclass(frozen=True)
class Satellite:
    key: str
    name: str
    parent: str
    a_km: float
    e: float
    w: float          # 近点引数 [度]
    m: float          # 平均近点角 [度]
    i: float          # 軌道傾斜角 [度]
    node: float       # 昇交点黄経 [度]
    period: float     # 公転周期 [日]
    p_apsis: float    # 近点の歳差周期 [年]（0 = なし）
    p_node: float     # 交点の歳差周期 [年]（0 = なし）
    pole_ra: float    # 基準面の極 [度]
    pole_dec: float
    radius_km: float
    color: tuple


# 赤道面基準の衛星は、惑星の自転軸（IAU 2015）を極に使う
_URANUS = (257.311, -15.175)
_NEPTUNE = (299.36, 43.46)

SATELLITES = [
    Satellite("phobos", "フォボス", "mars", 9375, 0.015, 216.3, 189.7, 1.1, 169.2, 0.3187, 1.1, 2.3,
              317.7, 52.9, 11.08, (0.55, 0.50, 0.45)),
    Satellite("deimos", "ダイモス", "mars", 23457, 0.000, 0.0, 205.0, 1.8, 54.3, 1.2625, 0.0, 56.2,
              316.6, 53.5, 6.2, (0.62, 0.57, 0.50)),
    Satellite("io", "イオ", "jupiter", 421800, 0.004, 49.1, 330.9, 0.0, 0.0, 1.762732, 1.333, 0.0,
              268.1, 64.5, 1821.6, (0.95, 0.85, 0.45)),
    Satellite("europa", "エウロパ", "jupiter", 671100, 0.009, 45.0, 345.4, 0.5, 184.0, 3.525463, 1.394, 30.202,
              268.1, 64.5, 1560.8, (0.92, 0.88, 0.80)),
    Satellite("ganymede", "ガニメデ", "jupiter", 1070400, 0.001, 198.3, 324.8, 0.2, 58.5, 7.155588, 68.301, 137.812,
              268.2, 64.6, 2631.2, (0.70, 0.66, 0.60)),
    Satellite("callisto", "カリスト", "jupiter", 1882700, 0.007, 43.8, 87.4, 0.3, 309.1, 16.690440, 277.921, 577.264,
              268.7, 64.8, 2410.3, (0.50, 0.46, 0.42)),
    Satellite("mimas", "ミマス", "saturn", 186000, 0.020, 160.4, 275.3, 1.6, 66.2, 0.942422, 0.493, 0.986,
              40.6, 83.5, 198.2, (0.80, 0.80, 0.80)),
    Satellite("enceladus", "エンケラドゥス", "saturn", 238400, 0.005, 119.5, 57.0, 0.0, 0.0, 1.370218, 2.916, 0.0,
              40.6, 83.5, 252.1, (0.97, 0.98, 1.0)),
    Satellite("tethys", "テティス", "saturn", 295000, 0.001, 335.3, 0.0, 1.1, 273.0, 1.887802, 0.005, 4.982,
              40.6, 83.5, 531.1, (0.90, 0.90, 0.92)),
    Satellite("dione", "ディオネ", "saturn", 377700, 0.002, 116.0, 212.0, 0.0, 0.0, 2.736916, 11.698, 0.0,
              40.6, 83.5, 561.4, (0.85, 0.85, 0.86)),
    Satellite("rhea", "レア", "saturn", 527200, 0.001, 44.3, 31.5, 0.3, 133.7, 4.517503, 33.939, 35.775,
              40.6, 83.5, 763.8, (0.82, 0.82, 0.82)),
    Satellite("titan", "タイタン", "saturn", 1221900, 0.029, 78.3, 11.7, 0.3, 78.6, 15.945448, 346.680, 687.370,
              36.4, 84.0, 2574.7, (0.90, 0.65, 0.30)),
    Satellite("iapetus", "イアペトゥス", "saturn", 3561700, 0.028, 254.5, 74.8, 7.6, 86.5, 79.331002, 1662.900, 3130.302,
              288.7, 78.9, 734.5, (0.70, 0.62, 0.52)),
    Satellite("miranda", "ミランダ", "uranus", 129846, 0.001, 154.8, 73.0, 4.4, 100.9, 1.413479, 8.939, 17.787,
              *_URANUS, 235.8, (0.75, 0.75, 0.75)),
    Satellite("ariel", "アリエル", "uranus", 190929, 0.001, 9.6, 193.5, 0.0, 0.0, 2.520379, 28.901, 0.0,
              *_URANUS, 578.9, (0.80, 0.80, 0.80)),
    Satellite("umbriel", "ウンブリエル", "uranus", 265986, 0.004, 183.4, 253.0, 0.1, 174.8, 4.144177, 64.126, 129.945,
              *_URANUS, 584.7, (0.55, 0.55, 0.55)),
    Satellite("titania", "チタニア", "uranus", 436298, 0.002, 184.0, 68.1, 0.1, 29.5, 8.705869, 579.928, 1644.649,
              *_URANUS, 788.9, (0.75, 0.73, 0.72)),
    Satellite("oberon", "オベロン", "uranus", 583511, 0.002, 132.2, 143.6, 0.1, 76.8, 13.463237, 158.604, 192.798,
              *_URANUS, 761.4, (0.68, 0.65, 0.63)),
    Satellite("triton", "トリトン", "neptune", 354800, 0.000, 0.0, 63.0, 157.3, 177.7, 5.8792, 675.2, 299.4,
              *_NEPTUNE, 1353.4, (0.85, 0.80, 0.78)),
]

BY_KEY = {s.key: s for s in SATELLITES}
BY_PARENT: dict[str, list[Satellite]] = {}
for _s in SATELLITES:
    BY_PARENT.setdefault(_s.parent, []).append(_s)


def _plane_axes(s: Satellite):
    """基準面の軸（x=ICRF赤道上の昇交点方向, z=極）を黄道座標で。"""
    ra, dec = math.radians(s.pole_ra), math.radians(s.pole_dec)
    pole = np.array([math.cos(dec) * math.cos(ra), math.cos(dec) * math.sin(ra), math.sin(dec)])
    x = np.cross([0.0, 0.0, 1.0], pole)
    x /= np.linalg.norm(x)
    y = np.cross(pole, x)
    to_ecl = astro.equatorial_to_ecliptic
    return to_ecl(x), to_ecl(y), to_ecl(pole)


_AXES = {s.key: _plane_axes(s) for s in SATELLITES}


def _elements(s: Satellite, jd: float):
    t = jd - JD_EPOCH
    w_rate = 360.0 / (s.p_apsis * 365.25) if s.p_apsis > 0 else 0.0
    n_rate = -360.0 / (s.p_node * 365.25) if s.p_node > 0 else 0.0
    w = s.w + w_rate * t
    node = s.node + n_rate * t
    # 公転周期は恒星周期なので、平均近点角の進み方は近点・交点の歳差の分だけ遅い
    m = s.m + (360.0 / s.period - w_rate - n_rate) * t
    return w, node, m


def _rotate(s, w, node, xp, yp):
    """軌道面内の座標 → 黄道座標 [km]。"""
    ax, ay, az = _AXES[s.key]
    wr, o, i = math.radians(w), math.radians(node), math.radians(s.i)
    cw, sw, co, so, ci, si = math.cos(wr), math.sin(wr), math.cos(o), math.sin(o), math.cos(i), math.sin(i)
    x = (cw * co - sw * so * ci) * xp + (-sw * co - cw * so * ci) * yp
    y = (cw * so + sw * co * ci) * xp + (-sw * so + cw * co * ci) * yp
    z = (sw * si) * xp + (cw * si) * yp
    return np.multiply.outer(x, ax) + np.multiply.outer(y, ay) + np.multiply.outer(z, az)


_EPHEM_MOON = {"phobos": "Phobos", "deimos": "Deimos", "io": "Io", "europa": "Europa",
               "ganymede": "Ganymede", "callisto": "Callisto", "mimas": "Mimas", "enceladus": "Enceladus",
               "tethys": "Tethys", "dione": "Dione", "rhea": "Rhea", "titan": "Titan", "iapetus": "Iapetus",
               "miranda": "Miranda", "ariel": "Ariel", "umbriel": "Umbriel", "titania": "Titania",
               "oberon": "Oberon"}
_EPHEM_PLANET = {"mars": "Mars", "jupiter": "Jupiter", "saturn": "Saturn", "uranus": "Uranus"}


def available() -> bool:
    return ephem is not None


def _ephem_offsets(jd: float) -> dict:
    """PyEphem で、全衛星の惑星からのベクトル [AU]（黄道座標）を求める。"""
    out = {}
    date = ephem.Date(jd - 2415020.0)
    planets = {}
    for key, cls in _EPHEM_PLANET.items():
        p = getattr(ephem, cls)(date)
        ra, dec = float(p.a_ra), float(p.a_dec)
        toward = -np.array([math.cos(dec) * math.cos(ra), math.cos(dec) * math.sin(ra), math.sin(dec)])
        east = np.array([-math.sin(ra), math.cos(ra), 0.0])
        north = np.cross(-toward, east)
        planets[key] = (ra, dec, float(p.earth_distance), toward, east, north)
    for key, cls in _EPHEM_MOON.items():
        s = BY_KEY[key]
        ra, dec, d_au, toward, east, north = planets[s.parent]
        m = getattr(ephem, cls)(date)
        dra = (float(m.a_ra) - ra + math.pi) % (2 * math.pi) - math.pi
        dra *= math.cos(dec)
        ddec = float(m.a_dec) - dec
        # x, y, z は惑星半径単位。空での見かけのずれから縮尺を求め、奥行き z にも使う
        k = math.hypot(dra, ddec) * d_au / max(math.hypot(m.x, m.y), 1e-12)
        v = dra * d_au * east + ddec * d_au * north + m.z * k * toward
        out[key] = astro.equatorial_to_ecliptic(v)
    return out


def offset(s: Satellite, jd: float) -> np.ndarray:
    """惑星から衛星までのベクトル [AU]（黄道座標）。"""
    if ephem is not None and s.key in _EPHEM_MOON:
        return _ephem_offsets(jd)[s.key]
    return _mean_offset(s, jd)


def _mean_offset(s: Satellite, jd: float) -> np.ndarray:
    w, node, m = _elements(s, jd)
    ecc = astro._solve_kepler(math.radians(m % 360.0), s.e)
    xp = s.a_km * (math.cos(ecc) - s.e)
    yp = s.a_km * math.sqrt(1 - s.e * s.e) * math.sin(ecc)
    return _rotate(s, w, node, xp, yp) / astro.AU_KM


def orbit_paths(jd: float, segments: int = 180) -> dict:
    """全衛星の軌道（1周ぶん）の点列 [AU]（惑星中心）。"""
    out = {}
    if ephem is not None:
        samples = {k: [] for k in _EPHEM_MOON}
        # 周期がばらばらなので、衛星ごとにその周期で 1 周ぶんを計算する
        for key in _EPHEM_MOON:
            s = BY_KEY[key]
            for i in range(segments + 1):
                t = jd + s.period * (i / segments - 0.5)
                samples[key].append(_single(key, t))
        out.update({k: np.array(v) for k, v in samples.items()})
    for s in SATELLITES:
        if s.key not in out:
            out[s.key] = _mean_orbit(s, jd, segments)
    return out


def _single(key: str, jd: float) -> np.ndarray:
    s = BY_KEY[key]
    date = ephem.Date(jd - 2415020.0)
    p = getattr(ephem, _EPHEM_PLANET[s.parent])(date)
    m = getattr(ephem, _EPHEM_MOON[key])(date)
    ra, dec = float(p.a_ra), float(p.a_dec)
    toward = -np.array([math.cos(dec) * math.cos(ra), math.cos(dec) * math.sin(ra), math.sin(dec)])
    east = np.array([-math.sin(ra), math.cos(ra), 0.0])
    north = np.cross(-toward, east)
    d_au = float(p.earth_distance)
    dra = ((float(m.a_ra) - ra + math.pi) % (2 * math.pi) - math.pi) * math.cos(dec)
    ddec = float(m.a_dec) - dec
    k = math.hypot(dra, ddec) * d_au / max(math.hypot(m.x, m.y), 1e-12)
    return astro.equatorial_to_ecliptic(dra * d_au * east + ddec * d_au * north + m.z * k * toward)


def _mean_orbit(s: Satellite, jd: float, segments: int) -> np.ndarray:
    w, node, _ = _elements(s, jd)
    ecc = np.linspace(0, 2 * math.pi, segments + 1)
    xp = s.a_km * (np.cos(ecc) - s.e)
    yp = s.a_km * math.sqrt(1 - s.e * s.e) * np.sin(ecc)
    return _rotate(s, w, node, xp, yp) / astro.AU_KM


def add_positions(pos: dict, jd: float) -> dict:
    eo = _ephem_offsets(jd) if ephem is not None else {}
    for s in SATELLITES:
        if s.key in eo:
            pos[s.key] = pos[s.parent] + eo[s.key]
        elif ephem is not None or s.key not in _EPHEM_MOON:
            pos[s.key] = pos[s.parent] + _mean_offset(s, jd)
        else:
            pos[s.key] = pos[s.parent] + _mean_offset(s, jd)
    return pos
