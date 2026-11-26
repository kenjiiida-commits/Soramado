"""天体の位置計算。

座標系はすべて「日心黄道座標（J2000.0）」、単位は AU（天文単位）。
  x 軸: 春分点の方向 / z 軸: 黄道の北極 方向

惑星の位置は NASA JPL "Approximate Positions of the Planets"
(https://ssd.jpl.nasa.gov/planets/approx_pos.html) の Table 1
（1800年〜2050年で有効）の軌道要素から計算する。
月の位置は Paul Schlyter "How to compute planetary positions" の
簡易式（主要な摂動項つき）で計算する。
"""

from __future__ import annotations

import math
from datetime import datetime, timezone

import numpy as np

AU_KM = 149_597_870.7
EARTH_RADIUS_KM = 6378.14
OBLIQUITY_J2000 = math.radians(23.4392911)
JD_J2000 = 2451545.0

# 軌道要素の有効範囲（JPL Table 1）
VALID_FROM_YEAR = 1800
VALID_TO_YEAR = 2050

# JPL Table 1: (a, e, I, L, 近日点黄経ϖ, 昇交点黄経Ω) と 1世紀あたりの変化率
_ELEMENTS = {
    "mercury": ((0.38709927, 0.20563593, 7.00497902, 252.25032350, 77.45779628, 48.33076593),
                (0.00000037, 0.00001906, -0.00594749, 149472.67411175, 0.16047689, -0.12534081)),
    "venus": ((0.72333566, 0.00677672, 3.39467605, 181.97909950, 131.60246718, 76.67984255),
              (0.00000390, -0.00004107, -0.00078890, 58517.81538729, 0.00268329, -0.27769418)),
    "emb": ((1.00000261, 0.01671123, -0.00001531, 100.46457166, 102.93768193, 0.0),
            (0.00000562, -0.00004392, -0.01294668, 35999.37244981, 0.32327364, 0.0)),
    "mars": ((1.52371034, 0.09339410, 1.84969142, -4.55343205, -23.94362959, 49.55953891),
             (0.00001847, 0.00007882, -0.00813131, 19140.30268499, 0.44441088, -0.29257343)),
    "jupiter": ((5.20288700, 0.04838624, 1.30439695, 34.39644051, 14.72847983, 100.47390909),
                (-0.00011607, -0.00013253, -0.00183714, 3034.74612775, 0.21252668, 0.20469106)),
    "saturn": ((9.53667594, 0.05386179, 2.48599187, 49.95424423, 92.59887831, 113.66242448),
               (-0.00125060, -0.00050991, 0.00193609, 1222.49362201, -0.41897216, -0.28867794)),
    "uranus": ((19.18916464, 0.04725744, 0.77263783, 313.23810451, 170.95427630, 74.01692503),
               (-0.00196176, -0.00004397, -0.00242939, 428.48202785, 0.40805281, 0.04240589)),
    "neptune": ((30.06992276, 0.00859048, 1.77004347, -55.12002969, 44.96476227, 131.78422574),
                (0.00026291, 0.00005105, 0.00035372, 218.45945325, -0.32241464, -0.00508664)),
    "pluto": ((39.48211675, 0.24882730, 17.14001206, 238.92903833, 224.06891629, 110.30393684),
              (-0.00031596, 0.00005170, 0.00004818, 145.20780515, -0.04062942, -0.01183482)),
}

# 地球と月の質量比（地球/月）
EARTH_MOON_MASS_RATIO = 81.30056


# ---------------------------------------------------------------- 時刻

def jd_from_datetime(dt: datetime) -> float:
    """datetime（タイムゾーン付き推奨）をユリウス日に変換する。"""
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    dt = dt.astimezone(timezone.utc)
    unix = dt.timestamp()
    return unix / 86400.0 + 2440587.5


def jd_now() -> float:
    return jd_from_datetime(datetime.now(timezone.utc))


def datetime_from_jd(jd: float) -> datetime:
    """ユリウス日を UTC の datetime に変換する（西暦1年〜9999年の範囲）。"""
    # グレゴリオ暦への変換（Meeus のアルゴリズム）
    z = math.floor(jd + 0.5)
    f = jd + 0.5 - z
    if z < 2299161:
        a = z
    else:
        alpha = math.floor((z - 1867216.25) / 36524.25)
        a = z + 1 + alpha - math.floor(alpha / 4)
    b = a + 1524
    c = math.floor((b - 122.1) / 365.25)
    d = math.floor(365.25 * c)
    e = math.floor((b - d) / 30.6001)
    day_frac = b - d - math.floor(30.6001 * e) + f
    month = e - 1 if e < 14 else e - 13
    year = c - 4716 if month > 2 else c - 4715
    day = int(day_frac)
    secs = (day_frac - day) * 86400.0
    secs = min(max(secs, 0.0), 86399.999)
    hour = int(secs // 3600)
    minute = int((secs % 3600) // 60)
    second = int(secs % 60)
    year = min(max(year, 1), 9999)
    return datetime(int(year), int(month), day, hour, minute, second, tzinfo=timezone.utc)


def year_from_jd(jd: float) -> float:
    return 2000.0 + (jd - JD_J2000) / 365.25


def elements_valid(jd: float) -> bool:
    y = year_from_jd(jd)
    return VALID_FROM_YEAR <= y <= VALID_TO_YEAR


# ---------------------------------------------------------------- 惑星

def _elements_at(name: str, jd: float):
    base, rate = _ELEMENTS[name]
    t = (jd - JD_J2000) / 36525.0
    a, e, inc, mean_lon, peri, node = (b + r * t for b, r in zip(base, rate))
    return a, e, inc, mean_lon, peri, node


def _solve_kepler(m_rad: float, e: float) -> float:
    ecc = m_rad + e * math.sin(m_rad)
    for _ in range(30):
        d = (ecc - e * math.sin(ecc) - m_rad) / (1.0 - e * math.cos(ecc))
        ecc -= d
        if abs(d) < 1e-14:
            break
    return ecc


def _orbit_to_ecliptic(xp, yp, inc, peri, node):
    """軌道面内の座標 (xp, yp) を J2000 黄道座標に回転する。角度は度。"""
    w = math.radians(peri - node)  # 近日点引数
    o = math.radians(node)
    i = math.radians(inc)
    cw, sw = math.cos(w), math.sin(w)
    co, so = math.cos(o), math.sin(o)
    ci, si = math.cos(i), math.sin(i)
    x = (cw * co - sw * so * ci) * xp + (-sw * co - cw * so * ci) * yp
    y = (cw * so + sw * co * ci) * xp + (-sw * so + cw * co * ci) * yp
    z = (sw * si) * xp + (cw * si) * yp
    return x, y, z


def planet_position(name: str, jd: float) -> np.ndarray:
    """惑星（または地球・月系の重心 "emb"）の日心黄道座標 [AU]。"""
    a, e, inc, mean_lon, peri, node = _elements_at(name, jd)
    m = math.radians((mean_lon - peri + 180.0) % 360.0 - 180.0)
    ecc = _solve_kepler(m, e)
    xp = a * (math.cos(ecc) - e)
    yp = a * math.sqrt(1.0 - e * e) * math.sin(ecc)
    return np.array(_orbit_to_ecliptic(xp, yp, inc, peri, node), dtype=np.float64)


def orbit_path(name: str, jd: float, segments: int = 512) -> np.ndarray:
    """その時点の軌道要素での軌道（楕円）の点列 [AU]。"""
    a, e, inc, _mean_lon, peri, node = _elements_at(name, jd)
    b = a * math.sqrt(1.0 - e * e)
    ecc = np.linspace(0.0, 2.0 * math.pi, segments + 1)
    x, y, z = _orbit_to_ecliptic(a * (np.cos(ecc) - e), b * np.sin(ecc), inc, peri, node)
    return np.stack([x, y, z], axis=1)


# ---------------------------------------------------------------- 月

try:
    import ephem as _ephem
except ImportError:  # pragma: no cover
    _ephem = None


def moon_geocentric(jd: float) -> np.ndarray:
    """月の地心黄道座標（J2000）[AU]。

    PyEphem があればその月の理論（精度は数秒角）を使う。日食・月食をきちんと見せるため。
    なければ下の簡易式（精度は数分角程度）。
    """
    if _moon_cache[0] == jd:
        return _moon_cache[1].copy()
    if _ephem is not None:
        m = _ephem.Moon(_ephem.Date(jd - 2415020.0))
        ra, dec, r = float(m.a_ra), float(m.a_dec), float(m.earth_distance)
        v = np.array([math.cos(dec) * math.cos(ra), math.cos(dec) * math.sin(ra), math.sin(dec)]) * r
        out = equatorial_to_ecliptic(v)
    else:
        out = moon_geocentric_simple(jd)
    _moon_cache[0], _moon_cache[1] = jd, out
    return out.copy()


_moon_cache = [None, None]      # 同じ時刻で何度も呼ばれるので、最後の結果を覚えておく


def moon_geocentric_simple(jd: float) -> np.ndarray:
    """月の地心黄道座標（J2000）[AU]。簡易式で、精度は数分角程度。"""
    d = jd - 2451543.5
    rad = math.radians
    node = rad(125.1228 - 0.0529538083 * d)
    inc = rad(5.1454)
    w = rad(318.0634 + 0.1643573223 * d)
    a = 60.2666
    e = 0.054900
    mm = rad((115.3654 + 13.0649929509 * d) % 360.0)

    ecc = _solve_kepler(mm, e)
    xv = a * (math.cos(ecc) - e)
    yv = a * math.sqrt(1.0 - e * e) * math.sin(ecc)
    v = math.atan2(yv, xv)
    r = math.hypot(xv, yv)

    xh = r * (math.cos(node) * math.cos(v + w) - math.sin(node) * math.sin(v + w) * math.cos(inc))
    yh = r * (math.sin(node) * math.cos(v + w) + math.cos(node) * math.sin(v + w) * math.cos(inc))
    zh = r * (math.sin(v + w) * math.sin(inc))
    lon = math.atan2(yh, xh)
    lat = math.atan2(zh, math.hypot(xh, yh))

    # 主要な摂動
    ms = rad((356.0470 + 0.9856002585 * d) % 360.0)
    ws = rad(282.9404 + 4.70935e-5 * d)
    ls = ms + ws
    lm = mm + w + node
    dd = lm - ls
    f = lm - node
    s = math.sin
    dlon = (-1.274 * s(mm - 2 * dd) + 0.658 * s(2 * dd) - 0.186 * s(ms)
            - 0.059 * s(2 * mm - 2 * dd) - 0.057 * s(mm - 2 * dd + ms)
            + 0.053 * s(mm + 2 * dd) + 0.046 * s(2 * dd - ms) + 0.041 * s(mm - ms)
            - 0.035 * s(dd) - 0.031 * s(mm + ms) - 0.015 * s(2 * f - 2 * dd)
            + 0.011 * s(mm - 4 * dd))
    dlat = (-0.173 * s(f - 2 * dd) - 0.055 * s(mm - f - 2 * dd)
            - 0.046 * s(mm + f - 2 * dd) + 0.033 * s(f + 2 * dd) + 0.017 * s(2 * mm + f))
    c = math.cos
    dr = -0.58 * c(mm - 2 * dd) - 0.46 * c(2 * dd)

    # 日付の春分点 → J2000 の春分点（歳差の補正）
    t = (jd - JD_J2000) / 36525.0
    lon = lon + rad(dlon) - rad(1.396971 * t)
    lat = lat + rad(dlat)
    r = (r + dr) * EARTH_RADIUS_KM / AU_KM
    return np.array([r * math.cos(lat) * math.cos(lon),
                     r * math.cos(lat) * math.sin(lon),
                     r * math.sin(lat)], dtype=np.float64)


# ---------------------------------------------------------------- まとめ

def all_positions(jd: float) -> dict[str, np.ndarray]:
    """太陽・惑星・月の日心黄道座標 [AU] をまとめて返す。"""
    pos = {"sun": np.zeros(3)}
    for name in ("mercury", "venus", "mars", "jupiter", "saturn", "uranus", "neptune"):
        pos[name] = planet_position(name, jd)
    emb = planet_position("emb", jd)
    moon_geo = moon_geocentric(jd)
    pos["earth"] = emb - moon_geo / (1.0 + EARTH_MOON_MASS_RATIO)
    pos["moon"] = pos["earth"] + moon_geo
    return pos


def equatorial_to_ecliptic(v: np.ndarray) -> np.ndarray:
    """赤道座標（J2000）のベクトルを黄道座標（J2000）に変換する。"""
    c, s = math.cos(OBLIQUITY_J2000), math.sin(OBLIQUITY_J2000)
    x, y, z = v
    return np.array([x, c * y + s * z, -s * y + c * z])


def pole_vector(ra_deg: float, dec_deg: float) -> np.ndarray:
    """自転軸の北極の向き（赤経・赤緯）を黄道座標の単位ベクトルにする。"""
    ra, dec = math.radians(ra_deg), math.radians(dec_deg)
    v = np.array([math.cos(dec) * math.cos(ra), math.cos(dec) * math.sin(ra), math.sin(dec)])
    return equatorial_to_ecliptic(v)


def rotation_angle(jd: float, w0_deg: float, w_rate_deg_per_day: float) -> float:
    """IAU の自転角 W（本初子午線の位置）[度]。"""
    return (w0_deg + w_rate_deg_per_day * (jd - JD_J2000)) % 360.0


# ---------------------------------------------------------------- 地上の観測者

def gmst_deg(jd: float) -> float:
    """グリニッジ平均恒星時 [度]（UTC を UT1 とみなす）。"""
    t = (jd - JD_J2000) / 36525.0
    g = (280.46061837 + 360.98564736629 * (jd - JD_J2000)
         + 0.000387933 * t * t - t * t * t / 38710000.0)
    return g % 360.0


def precession_matrix(jd: float) -> np.ndarray:
    """J2000 の赤道座標 → その日の平均赤道座標 の回転行列（IAU 1976）。"""
    t = (jd - JD_J2000) / 36525.0
    asec = math.pi / 180.0 / 3600.0
    zeta = (2306.2181 * t + 0.30188 * t * t + 0.017998 * t ** 3) * asec
    z = (2306.2181 * t + 1.09468 * t * t + 0.018203 * t ** 3) * asec
    theta = (2004.3109 * t - 0.42665 * t * t - 0.041833 * t ** 3) * asec

    def rz(a):
        c, s = math.cos(a), math.sin(a)
        return np.array([[c, -s, 0], [s, c, 0], [0, 0, 1]])

    def ry(a):
        c, s = math.cos(a), math.sin(a)
        return np.array([[c, 0, -s], [0, 1, 0], [s, 0, c]])

    return rz(z) @ ry(theta) @ rz(zeta)


def observer_frame(jd: float, lat_deg: float, lon_deg: float):
    """地上の観測者の位置と向き（すべて J2000 黄道座標）。

    戻り値: (地球中心から観測者までのベクトル[AU], 天頂, 北, 東) の単位ベクトル
    """
    lst = math.radians(gmst_deg(jd) + lon_deg)
    lat = math.radians(lat_deg)
    # その日の赤道座標での天頂と天の北極
    zen_date = np.array([math.cos(lat) * math.cos(lst), math.cos(lat) * math.sin(lst), math.sin(lat)])
    pole_date = np.array([0.0, 0.0, 1.0])
    p_inv = precession_matrix(jd).T          # その日 → J2000
    zen = equatorial_to_ecliptic(p_inv @ zen_date)
    pole = equatorial_to_ecliptic(p_inv @ pole_date)
    east = np.cross(pole, zen)
    east /= np.linalg.norm(east)
    north = np.cross(zen, east)
    offset = zen * (EARTH_RADIUS_KM / AU_KM)
    return offset, zen, north, east


def alt_az(direction: np.ndarray, zen, north, east):
    """方向ベクトル → (高度, 方位) [度]。方位は北=0、東=90。"""
    d = direction / np.linalg.norm(direction)
    alt = math.degrees(math.asin(max(-1.0, min(1.0, float(np.dot(d, zen))))))
    az = math.degrees(math.atan2(float(np.dot(d, east)), float(np.dot(d, north)))) % 360.0
    return alt, az
