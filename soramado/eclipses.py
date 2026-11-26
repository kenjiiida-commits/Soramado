"""日食・月食を探す（PyEphem の太陽・月の位置を使う）。

月食：満月のころ、月が地球の影（本影・半影）にどれだけ入るかを、地球中心から見た角度で調べる。
  本影の半径 = 1.02 ×（月の視差 + 太陽の視差 − 太陽の見かけの半径）
  半影の半径 = 1.02 ×（月の視差 + 太陽の視差 + 太陽の見かけの半径）
  （1.02 は地球の大気で影が少し大きくなる分。Danjon の方法）
日食：新月のころ、地球中心から見た太陽と月の離れ角が、月の視差などより小さければ、地球のどこかで日食になる。
  観測地での見え方は、その場所から見た太陽と月（地心視差を入れた位置）で調べる。
時刻の誤差は数分ほど（専門の予報とくらべて、おおよそ）。
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field

try:
    import ephem
except ImportError:  # pragma: no cover
    ephem = None

EARTH_R_KM = 6378.137
AU_KM = 149597870.7
DJD = 2415020.0          # ephem の日付 = JD − 2415020


@dataclass
class Eclipse:
    kind: str                 # "solar" / "lunar"
    type: str                 # total / annular / hybrid / partial / penumbral
    jd_max: float             # 食の最大（地球全体）
    magnitude: float          # 食分（日食は地心での目安、月食は本影食分。半影食は半影食分）
    local: dict = field(default_factory=dict)   # 観測地での見え方

    @property
    def type_ja(self) -> str:
        from .i18n import tr
        return tr(self._type_ja())

    def _type_ja(self) -> str:
        if self.kind == "lunar":
            return {"total": "皆既月食", "partial": "部分月食", "penumbral": "半影月食"}[self.type]
        return {"total": "皆既日食", "annular": "金環日食", "hybrid": "金環皆既日食",
                "partial": "部分日食"}[self.type]


def available() -> bool:
    return ephem is not None


def _bodies(jd, obs=None):
    d = ephem.Date(jd - DJD)
    if obs is None:
        s, m = ephem.Sun(d), ephem.Moon(d)
    else:
        obs.date = d
        s, m = ephem.Sun(obs), ephem.Moon(obs)
    return s, m


def _geo_params(jd):
    """地心での量 [rad]: 太陽と月の離れ角、太陽・月の見かけの半径、月・太陽の視差。"""
    s, m = _bodies(jd)
    sep = float(ephem.separation(s, m))
    rs = math.radians(s.size / 3600.0) / 2
    rm = math.radians(m.size / 3600.0) / 2
    pm = math.asin(EARTH_R_KM / (m.earth_distance * AU_KM))
    ps = math.asin(EARTH_R_KM / (s.earth_distance * AU_KM))
    return sep, rs, rm, pm, ps


def _minimize(fn, a, b, tol=1e-5):
    """黄金分割法で fn の最小の位置を探す。"""
    g = (math.sqrt(5) - 1) / 2
    c, d = b - g * (b - a), a + g * (b - a)
    fc, fd = fn(c), fn(d)
    while b - a > tol:
        if fc < fd:
            b, d, fd = d, c, fc
            c = b - g * (b - a)
            fc = fn(c)
        else:
            a, c, fc = c, d, fd
            d = a + g * (b - a)
            fd = fn(d)
    return (a + b) / 2


def _root(fn, a, b, tol=1e-5):
    """fn(a) と fn(b) の符号がちがうとき、fn = 0 の時刻を二分法で探す。"""
    fa = fn(a)
    for _ in range(60):
        mid = (a + b) / 2
        fm = fn(mid)
        if (fm < 0) == (fa < 0):
            a, fa = mid, fm
        else:
            b = mid
        if b - a < tol:
            break
    return (a + b) / 2


# ---------------------------------------------------------------- 月食

def _lunar_at(jd):
    sep, rs, rm, pm, ps = _geo_params(jd)
    d = math.pi - sep                          # 月と「地球の影の中心（太陽の反対）」の離れ角
    umbra = 1.02 * (pm + ps - rs)
    pen = 1.02 * (pm + ps + rs)
    return d, rm, umbra, pen


def lunar_eclipse_near(jd_full: float) -> Eclipse | None:
    jd = _minimize(lambda t: _lunar_at(t)[0], jd_full - 0.4, jd_full + 0.4)
    d, rm, umbra, pen = _lunar_at(jd)
    if d - rm >= pen:
        return None
    if d - rm < umbra:
        typ = "total" if d + rm < umbra else "partial"
        mag = (umbra - d + rm) / (2 * rm)
    else:
        typ = "penumbral"
        mag = (pen - d + rm) / (2 * rm)
    ec = Eclipse("lunar", typ, jd, mag)
    # 始まりと終わり（半影食・部分食・皆既食）
    span = 0.25
    contacts = {}
    for name, fn in (("pen", lambda t: (lambda x: x[0] - x[1] - x[3])(_lunar_at(t))),
                     ("umb", lambda t: (lambda x: x[0] - x[1] - x[2])(_lunar_at(t))),
                     ("tot", lambda t: (lambda x: x[0] + x[1] - x[2])(_lunar_at(t)))):
        if fn(jd) < 0:
            contacts[name] = (_root(fn, jd - span, jd), _root(fn, jd, jd + span))
    ec.local["contacts"] = contacts
    return ec


# ---------------------------------------------------------------- 日食

def solar_eclipse_near(jd_new: float) -> Eclipse | None:
    jd = _minimize(lambda t: _geo_params(t)[0], jd_new - 0.4, jd_new + 0.4)
    sep, rs, rm, pm, ps = _geo_params(jd)
    if sep >= pm - ps + rs + rm:
        return None
    # 月の影の軸が地球に当たるか（中心食）。地球の半径に相当する角度 = 月の視差 − 太陽の視差
    if sep < (pm - ps) * 0.997:
        # 地上から見ると、月は地心より約1〜2%大きく見える（地球の半径ぶん月に近いので）
        # 影の軸が地球の中心近くを通るほど、月の真下の地点は月に近い
        x = sep / max(pm - ps, 1e-9)
        rm_top = rm * (1 + math.sin(pm) * math.sqrt(max(0.0, 1 - x * x)))
        if rm >= rs:
            typ = "total"
        elif rm_top >= rs:
            typ = "hybrid"
        else:
            typ = "annular"
    else:
        typ = "partial"
    mag = (pm - ps + rs + rm - sep) / (2 * rs)
    return Eclipse("solar", typ, jd, min(mag, 1.0) if typ == "partial" else rm / rs)


def overlap_fraction(rs: float, rm: float, d: float) -> float:
    """太陽（半径 rs）が月（半径 rm）にかくされる面積の割合。d は中心の間の角度。"""
    if d >= rs + rm:
        return 0.0
    if d <= abs(rm - rs):
        return 1.0 if rm >= rs else (rm * rm) / (rs * rs)
    a = rs * rs * math.acos((d * d + rs * rs - rm * rm) / (2 * d * rs))
    b = rm * rm * math.acos((d * d + rm * rm - rs * rs) / (2 * d * rm))
    c = 0.5 * math.sqrt(max(0.0, (-d + rs + rm) * (d + rs - rm) * (d - rs + rm) * (d + rs + rm)))
    return (a + b - c) / (math.pi * rs * rs)


def _observer(lat, lon):
    o = ephem.Observer()
    o.lat, o.lon = str(lat), str(lon)
    o.elevation = 0
    o.pressure = 0          # 大気の浮き上がりは入れない
    return o


def solar_local(ec: Eclipse, lat: float, lon: float):
    """観測地での日食：見えるか、いちばん欠けるときの時刻・食分・面積の割合、太陽の高度。"""
    obs = _observer(lat, lon)

    def state(t):
        s, m = _bodies(t, obs)
        d = float(ephem.separation(s, m))
        rs = math.radians(s.size / 3600.0) / 2
        rm = math.radians(m.size / 3600.0) / 2
        return d, rs, rm, math.degrees(float(s.alt))

    best = None
    t = ec.jd_max - 0.15
    while t <= ec.jd_max + 0.15:
        d, rs, rm, alt = state(t)
        if d < rs + rm and (best is None or d < best[1]):
            best = (t, d)
        t += 2.0 / 1440
    if best is None:
        ec.local = {"visible": False}
        return
    tm = _minimize(lambda x: state(x)[0], best[0] - 3 / 1440, best[0] + 3 / 1440, 1e-6)
    d, rs, rm, alt = state(tm)
    mag = (rs + rm - d) / (2 * rs)
    frac = overlap_fraction(rs, rm, d)
    kind = "partial"
    if d <= abs(rm - rs):
        kind = "total" if rm >= rs else "annular"
    # 始まりと終わり
    f = lambda x: (lambda s: s[0] - s[1] - s[2])(state(x))
    t1 = _root(f, tm - 0.15, tm) if f(tm - 0.15) > 0 else None
    t2 = _root(f, tm, tm + 0.15) if f(tm + 0.15) > 0 else None
    alt1 = state(t1)[3] if t1 else None
    alt2 = state(t2)[3] if t2 else None
    vis = alt > 0 or (alt1 is not None and alt1 > 0) or (alt2 is not None and alt2 > 0)
    ec.local = {"visible": vis, "jd": tm, "mag": mag, "frac": frac, "alt": alt, "type": kind,
                "start": t1, "end": t2, "alt_start": alt1, "alt_end": alt2}


def lunar_local(ec: Eclipse, lat: float, lon: float):
    """観測地での月食：月が地平線の上にあるか。"""
    obs = _observer(lat, lon)

    def alt(t):
        obs.date = ephem.Date(t - DJD)
        return math.degrees(float(ephem.Moon(obs).alt))

    c = ec.local.get("contacts", {})
    key = "umb" if "umb" in c else "pen"
    t1, t2 = c.get(key, (ec.jd_max, ec.jd_max))
    a_max = alt(ec.jd_max)
    samples = [alt(t1 + (t2 - t1) * k / 20) for k in range(21)]
    ec.local.update({"visible": max(samples) > 0, "alt": a_max, "all": min(samples) > 0,
                     "start": t1, "end": t2, "alt_start": samples[0], "alt_end": samples[-1]})


# ---------------------------------------------------------------- まとめて探す

def search(jd_start: float, years: float, lat: float, lon: float) -> list[Eclipse]:
    if ephem is None:
        return []
    out = []
    end = jd_start + years * 365.25
    d = ephem.Date(jd_start - DJD)
    while True:
        fm = ephem.next_full_moon(d)
        nm = ephem.next_new_moon(d)
        jf, jn = float(fm) + DJD, float(nm) + DJD
        if min(jf, jn) > end:
            break
        if jf < jn:
            ec = lunar_eclipse_near(jf)
            if ec:
                lunar_local(ec, lat, lon)
                out.append(ec)
            d = ephem.Date(fm + 1)
        else:
            ec = solar_eclipse_near(jn)
            if ec:
                solar_local(ec, lat, lon)
                out.append(ec)
            d = ephem.Date(nm + 1)
    return [e for e in out if jd_start <= e.jd_max <= end]


def sun_light_fraction(p, sun, sun_r, occ, occ_r) -> float:
    """位置 p から見た太陽（中心 sun・半径 sun_r）が、occ（半径 occ_r）にかくされずに見える割合。"""
    import numpy as np
    ds = np.asarray(sun) - p
    do = np.asarray(occ) - p
    ls, lo = float(np.linalg.norm(ds)), float(np.linalg.norm(do))
    if lo >= ls or lo <= occ_r:
        return 1.0
    rs = math.asin(min(1.0, sun_r / ls))
    ro = math.asin(min(1.0, occ_r / lo))
    d = math.atan2(float(np.linalg.norm(np.cross(ds, do))), float(np.dot(ds, do)))
    return 1.0 - overlap_fraction(rs, ro, d)
