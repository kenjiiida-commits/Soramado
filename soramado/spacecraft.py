"""探査機の航路。

探査機が実際に惑星や小惑星のそばを通った日付と、その日の天体の位置を「通過点」とし、
通過点のあいだをつないで航路を作る。

・エンジンを使わず惑星の引力で進む区間（ボイジャー、ニュー・ホライズンズの惑星間）は、
  「ランベルト問題」（2点と所要時間から、太陽の引力だけで進む軌道を求める）で計算する。
・イオンエンジンで少しずつ加速する区間（はやぶさ・はやぶさ2）は、出発天体の軌道から
  到着天体の軌道へなめらかに移っていく近似で描く。
・最後の惑星を通過したあと太陽系の外へ向かう区間は、2026年11月時点の距離・方向へ
  まっすぐ進むとして描く。

どれもおおよその航路で、実際の航路（NASA JPL Horizons など）とは細かい点で異なる。
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from datetime import datetime, timezone

import numpy as np

from . import astro

K = 0.01720209895            # ガウス重力定数
MU = K * K                    # 太陽の重力定数 [AU^3/日^2]


def _jd(y, m, d):
    return astro.jd_from_datetime(datetime(y, m, d, tzinfo=timezone.utc))


# ---------------------------------------------------------------- 2体問題

def _stumpff(z):
    if z > 1e-8:
        s = math.sqrt(z)
        return (1 - math.cos(s)) / z, (s - math.sin(s)) / (s ** 3)
    if z < -1e-8:
        s = math.sqrt(-z)
        return (math.cosh(s) - 1) / (-z), (math.sinh(s) - s) / (s ** 3)
    return 0.5, 1.0 / 6.0


def propagate(r0, v0, dt):
    """位置 r0・速度 v0 から dt 日後の位置（万有変数による2体問題）。"""
    r0n = np.linalg.norm(r0)
    vr0 = np.dot(r0, v0) / r0n
    alpha = 2.0 / r0n - np.dot(v0, v0) / MU
    sq = math.sqrt(MU)
    chi = sq * abs(alpha) * dt if abs(alpha) > 1e-12 else sq * dt / r0n
    for _ in range(80):
        z = alpha * chi * chi
        c, s = _stumpff(z)
        f = (r0n * vr0 / sq * chi * chi * c + (1 - alpha * r0n) * chi ** 3 * s + r0n * chi - sq * dt)
        df = (r0n * vr0 / sq * chi * (1 - alpha * chi * chi * s) + (1 - alpha * r0n) * chi * chi * c + r0n)
        step = f / df
        chi -= step
        if abs(step) < 1e-12:
            break
    z = alpha * chi * chi
    c, s = _stumpff(z)
    fl = 1 - chi * chi / r0n * c
    gl = dt - chi ** 3 / sq * s
    return fl * r0 + gl * v0


def lambert(r1, r2, tof):
    """r1 から r2 へ tof 日で行く軌道の出発速度（順行、1周未満）。"""
    r1n, r2n = np.linalg.norm(r1), np.linalg.norm(r2)
    cos_d = np.dot(r1, r2) / (r1n * r2n)
    dtheta = math.acos(max(-1.0, min(1.0, cos_d)))
    if np.cross(r1, r2)[2] < 0:          # 順行（反時計回り）になるよう遠回りを選ぶ
        dtheta = 2 * math.pi - dtheta
    a = math.sin(dtheta) * math.sqrt(r1n * r2n / (1 - math.cos(dtheta)))

    def y(z):
        c, s = _stumpff(z)
        return r1n + r2n + a * (z * s - 1) / math.sqrt(c)

    def time_of(z):
        c, s = _stumpff(z)
        yy = y(z)
        if yy < 0:
            return -1.0
        return ((yy / c) ** 1.5 * s + a * math.sqrt(yy)) / math.sqrt(MU)

    lo, hi = -2000.0, 4 * math.pi ** 2 - 1e-6    # 負の側は双曲線軌道（速い移動）
    while time_of(lo) < 0 or y(lo) < 0:          # y が負になる範囲を避ける
        lo += 0.1
    for _ in range(200):
        mid = (lo + hi) / 2
        if time_of(mid) > tof:
            hi = mid
        else:
            lo = mid
    z = (lo + hi) / 2
    c, s = _stumpff(z)
    yy = y(z)
    f = 1 - yy / r1n
    g = a * math.sqrt(yy / MU)
    return (r2 - f * r1) / g


# ---------------------------------------------------------------- 探査機

@dataclass
class Leg:
    kind: str          # "lambert" 弾道, "loop" 地球に戻る1年周回, "blend" イオンエンジン, "stay" 滞在, "out" 太陽系の外へ
    t0: float
    t1: float
    a: str = ""        # 出発天体
    b: str = ""        # 到着天体
    data: dict = field(default_factory=dict)


@dataclass
class Spacecraft:
    key: str
    name: str
    color: tuple
    events: list            # (JD, 説明)
    legs: list
    note: str = ""


def _body_pos(name: str, jd: float) -> np.ndarray:
    from . import smallbodies as sb
    if name == "earth":
        emb = astro.planet_position("emb", jd)
        return emb - astro.moon_geocentric(jd) / (1 + astro.EARTH_MOON_MASS_RATIO)
    if name in sb.BY_KEY:
        return sb.position(sb.BY_KEY[name], jd)
    return astro.planet_position(name, jd)


def _radec_dir(ra_h, dec_d):
    ra, dec = math.radians(ra_h * 15), math.radians(dec_d)
    return astro.equatorial_to_ecliptic(np.array([math.cos(dec) * math.cos(ra), math.cos(dec) * math.sin(ra),
                                                  math.sin(dec)]))


ANCHOR_JD = _jd(2026, 11, 26)


def _flyby_chain(points):
    legs = []
    for (ta, a), (tb, b) in zip(points, points[1:]):
        legs.append(Leg("lambert", ta, tb, a, b))
    return legs


SPACECRAFT = [
    Spacecraft(
        "sc:voyager1", "ボイジャー1号", (1.0, 0.85, 0.35),
        [(_jd(1977, 9, 5), "打ち上げ"), (_jd(1979, 3, 5), "木星に最接近"), (_jd(1980, 11, 12), "土星に最接近"),
         (_jd(2012, 8, 25), "太陽圏を出て星間空間へ"), (_jd(2026, 11, 18), "地球から1光日（約173AU）に到達")],
        _flyby_chain([(_jd(1977, 9, 5), "earth"), (_jd(1979, 3, 5), "jupiter"), (_jd(1980, 11, 12), "saturn")])
        + [Leg("out", _jd(1980, 11, 12), _jd(2100, 1, 1), "saturn", "",
               {"dir": (17 + 18 / 60, 12 + 14 / 60), "dist": 173.1, "speed": 3.569})],
        "人類が作ったもので最も遠くにある探査機。1977年に打ち上げられ、木星と土星を調べたあと、"
        "2012年に太陽圏を出て星間空間に入った。2026年11月18日、地球から光で1日かかる距離に達した。"),
    Spacecraft(
        "sc:voyager2", "ボイジャー2号", (0.45, 0.85, 1.0),
        [(_jd(1977, 8, 20), "打ち上げ"), (_jd(1979, 7, 9), "木星に最接近"), (_jd(1981, 8, 25), "土星に最接近"),
         (_jd(1986, 1, 24), "天王星に最接近"), (_jd(1989, 8, 25), "海王星に最接近"),
         (_jd(2018, 11, 5), "太陽圏を出て星間空間へ")],
        _flyby_chain([(_jd(1977, 8, 20), "earth"), (_jd(1979, 7, 9), "jupiter"), (_jd(1981, 8, 25), "saturn"),
                      (_jd(1986, 1, 24), "uranus"), (_jd(1989, 8, 25), "neptune")])
        + [Leg("out", _jd(1989, 8, 25), _jd(2100, 1, 1), "neptune", "",
               {"dir": (20 + 10 / 60, -(59 + 26 / 60)), "dist": 144.5, "speed": 3.219})],
        "木星・土星・天王星・海王星の4つの惑星を訪れた、ただ一つの探査機。天王星と海王星に近づいたのは、"
        "今もボイジャー2号だけ。2018年に太陽圏を出た。"),
    Spacecraft(
        "sc:newhorizons", "ニュー・ホライズンズ", (0.70, 1.0, 0.60),
        [(_jd(2006, 1, 19), "打ち上げ"), (_jd(2007, 2, 28), "木星の引力で加速"),
         (_jd(2015, 7, 14), "冥王星に最接近"), (_jd(2019, 1, 1), "カイパーベルト天体アロコスに接近")],
        _flyby_chain([(_jd(2006, 1, 19), "earth"), (_jd(2007, 2, 28), "jupiter"), (_jd(2015, 7, 14), "pluto")])
        + [Leg("out", _jd(2015, 7, 14), _jd(2100, 1, 1), "pluto", "",
               {"dir": (19 + 22 / 60, -(20 + 6 / 60)), "dist": 66.1, "speed": 2.867})],
        "冥王星を初めて間近から調べた NASA の探査機。2015年に冥王星、2019年にカイパーベルト天体アロコスに接近した。"),
    Spacecraft(
        "sc:hayabusa", "はやぶさ", (1.0, 0.55, 0.55),
        [(_jd(2003, 5, 9), "打ち上げ"), (_jd(2004, 5, 19), "地球スイングバイ"),
         (_jd(2005, 9, 12), "イトカワに到着"), (_jd(2005, 11, 26), "イトカワに着陸"),
         (_jd(2007, 4, 25), "地球への帰路につく"), (_jd(2010, 6, 13), "地球に帰還（カプセル回収）")],
        [Leg("loop", _jd(2003, 5, 9), _jd(2004, 5, 19), "earth", "earth"),
         Leg("blend", _jd(2004, 5, 19), _jd(2005, 9, 12), "earth", "itokawa"),
         Leg("stay", _jd(2005, 9, 12), _jd(2007, 4, 25), "itokawa", "itokawa"),
         Leg("blend", _jd(2007, 4, 25), _jd(2010, 6, 13), "itokawa", "earth")],
        "日本の小惑星探査機。イオンエンジンで小惑星イトカワへ向かい、2005年に着陸。数々のトラブルを乗り越えて"
        "2010年に地球へ帰還し、世界で初めて小惑星の表面の粒子を持ち帰った。"),
    Spacecraft(
        "sc:hayabusa2", "はやぶさ2", (1.0, 0.70, 0.90),
        [(_jd(2014, 12, 3), "打ち上げ"), (_jd(2015, 12, 3), "地球スイングバイ"),
         (_jd(2018, 6, 27), "リュウグウに到着"), (_jd(2019, 2, 22), "1回目のタッチダウン"),
         (_jd(2019, 7, 11), "2回目のタッチダウン"), (_jd(2019, 11, 13), "リュウグウを出発"),
         (_jd(2020, 12, 6), "カプセルを地球に届ける（その後、延長ミッションへ）")],
        [Leg("loop", _jd(2014, 12, 3), _jd(2015, 12, 3), "earth", "earth"),
         Leg("blend", _jd(2015, 12, 3), _jd(2018, 6, 27), "earth", "ryugu"),
         Leg("stay", _jd(2018, 6, 27), _jd(2019, 11, 13), "ryugu", "ryugu"),
         Leg("blend", _jd(2019, 11, 13), _jd(2020, 12, 6), "ryugu", "earth")],
        "はやぶさの後継機。小惑星リュウグウに2回タッチダウンし、人工クレーターを作って地下の物質も採取した。"
        "2020年に試料の入ったカプセルを地球に届け、その後は別の小惑星をめざす延長ミッションを続けている"
        "（この画面では、カプセル帰還までの航路を表示）。"),
]

BY_KEY = {s.key: s for s in SPACECRAFT}


# ---------------------------------------------------------------- 位置の計算

_cache: dict = {}


def _lambert_state(leg: Leg):
    key = (leg.a, leg.b, leg.t0, leg.t1)
    if key not in _cache:
        r1 = _body_pos(leg.a, leg.t0)
        r2 = _body_pos(leg.b, leg.t1)
        _cache[key] = (r1, lambert(r1, r2, leg.t1 - leg.t0))
    return _cache[key]


def _out_line(leg: Leg):
    key = ("out", leg.a, leg.t0)
    if key not in _cache:
        p0 = _body_pos(leg.a, leg.t0)
        d = _radec_dir(*leg.data["dir"])
        p_now = d * leg.data["dist"]
        _cache[key] = (p0, p_now)
    return _cache[key]


def _polar(p):
    return math.hypot(p[0], p[1]), math.atan2(p[1], p[0]), p[2]


def leg_position(leg: Leg, jd: float) -> np.ndarray:
    tau = (jd - leg.t0) / (leg.t1 - leg.t0)
    if leg.kind == "lambert":
        r1, v1 = _lambert_state(leg)
        return propagate(r1, v1, jd - leg.t0)
    if leg.kind == "stay":
        return _body_pos(leg.a, jd)
    if leg.kind == "loop":
        # 地球からいったん離れて、1年後にまた地球に戻ってくる（イオンエンジンでの加速）
        e = _body_pos("earth", jd)
        return e * (1.0 + 0.12 * math.sin(math.pi * min(max(tau, 0), 1)))
    if leg.kind == "blend":
        s = tau * tau * (3 - 2 * tau)
        pa, pb = _body_pos(leg.a, jd), _body_pos(leg.b, jd)
        ra, tha, za = _polar(pa)
        rb, thb, zb = _polar(pb)
        dth = (thb - tha + math.pi) % (2 * math.pi) - math.pi
        r = ra + (rb - ra) * s
        th = tha + dth * s
        return np.array([r * math.cos(th), r * math.sin(th), za + (zb - za) * s])
    if leg.kind == "out":
        p0, p_now = _out_line(leg)
        # 2026年11月の位置を通り、毎年 speed AU ずつ遠ざかる
        years = (jd - ANCHOR_JD) / 365.25
        dist_now = leg.data["dist"]
        target = p_now / np.linalg.norm(p_now) * (dist_now + leg.data["speed"] * years)
        if jd >= ANCHOR_JD:
            return target
        # 最後の通過点から今の位置まで、なめらかにつなぐ
        u = (jd - leg.t0) / (ANCHOR_JD - leg.t0)
        return p0 + (p_now - p0) * u
    raise ValueError(leg.kind)


def span(sc: Spacecraft):
    return sc.legs[0].t0, sc.legs[-1].t1


def position(sc: Spacecraft, jd: float):
    """探査機の位置 [AU]。打ち上げ前・航路の終わりより後は None。"""
    t0, t1 = span(sc)
    if jd < t0 or jd > t1:
        return None
    for leg in sc.legs:
        if leg.t0 <= jd <= leg.t1:
            return leg_position(leg, jd)
    return None


def path(sc: Spacecraft, until: float | None = None, per_leg: int = 300) -> np.ndarray:
    pts = []
    for leg in sc.legs:
        t1 = leg.t1
        if leg.kind == "out":
            t1 = min(leg.t1, until if until else ANCHOR_JD)
        if t1 <= leg.t0:
            break
        for t in np.linspace(leg.t0, t1, per_leg):
            pts.append(leg_position(leg, t))
    return np.array(pts)


def last_event(sc: Spacecraft, jd: float) -> str:
    done = [txt for t, txt in sc.events if t <= jd]
    return done[-1] if done else "打ち上げ前"


def _english_names():
    from .i18n import EN_MODE, name_en
    if EN_MODE:
        for x in SPACECRAFT:
            object.__setattr__(x, "name", name_en(x.key, x.name))


_english_names()
