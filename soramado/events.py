"""流星群と、惑星・月の接近などの天文現象を探す（PyEphem を使う）。

流星群の極大は、太陽黄経（J2000）で決まる。値は国際流星機構（IMO）の流星群カレンダーの代表値。
活動の強さ（ZHR）は、放射点が天頂にあり、とても暗い空での1時間あたりの数の目安。
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field

import numpy as np

from . import astro

try:
    import ephem
except ImportError:  # pragma: no cover
    ephem = None

DJD = 2415020.0


@dataclass(frozen=True)
class Shower:
    key: str
    name: str
    lam: float          # 極大の太陽黄経（J2000）[度]
    ra: float           # 放射点 [度]
    dec: float
    zhr: float
    speed: float        # 流星の速さ [km/s]
    width: float        # 活動の広がり（極大から ZHR が約 1/3 になるまでの日数）
    parent: str
    note: str = ""


SHOWERS = [
    Shower("qua", "しぶんぎ座流星群", 283.15, 230.0, 49.0, 80, 41, 0.6, "小惑星 2003 EH1",
           "三大流星群の一つ。極大の時間がとても短く、数時間で終わる。名前は今はない星座「壁面四分儀座」から。"),
    Shower("lyr", "4月こと座流星群", 32.32, 271.0, 34.0, 18, 49, 1.3, "サッチャー彗星（C/1861 G1）",
           "記録に残るもっとも古い流星群の一つ（紀元前687年の中国の記録）。"),
    Shower("eta", "みずがめ座η流星群", 45.5, 338.0, -1.0, 50, 66, 5.0, "ハレー彗星",
           "ハレー彗星が残したちりによる流星群。日本では夜明け前の短い時間に見える。"),
    Shower("sda", "みずがめ座δ南流星群", 127.0, 340.0, -16.0, 25, 41, 6.0, "マックホルツ彗星（96P）など",
           "ペルセウス座流星群の少し前に活動する、ゆっくりした流星群。"),
    Shower("per", "ペルセウス座流星群", 140.0, 48.0, 58.0, 100, 59, 2.5, "スイフト・タットル彗星（109P）",
           "三大流星群の一つ。夏休みの時期で、毎年たくさんの流星が見られる。"),
    Shower("dra", "10月りゅう座流星群", 195.4, 262.0, 54.0, 10, 20, 1.0, "ジャコビニ・ツィナー彗星（21P）",
           "「ジャコビニ流星群」とも呼ばれる。年によって突然たくさん流れることがある、ゆっくりした流星。"),
    Shower("ori", "オリオン座流星群", 208.0, 95.0, 16.0, 20, 66, 4.0, "ハレー彗星",
           "ハレー彗星が残したちりによる流星群。速い流星が多い。"),
    Shower("nta", "おうし座流星群（北群）", 230.0, 58.0, 22.0, 5, 27, 10.0, "エンケ彗星（2P）",
           "数は少ないが、活動期間が長く、ときどき明るい火球が流れる。"),
    Shower("leo", "しし座流星群", 235.27, 152.0, 22.0, 15, 71, 1.5, "テンペル・タットル彗星（55P）",
           "2001年には日本で1時間に数千個の大出現があった。とても速い流星。"),
    Shower("gem", "ふたご座流星群", 262.2, 112.0, 33.0, 150, 35, 1.5, "小惑星フェートン（3200）",
           "三大流星群の一つで、1年でもっとも多く流星が見られる。母天体が小惑星という珍しい流星群。"),
    Shower("urs", "こぐま座流星群", 270.7, 217.0, 76.0, 10, 33, 1.0, "タットル彗星（8P）",
           "冬至のころの流星群。放射点が北の空高くにあり、一晩中見られる。"),
]
BY_KEY = {s.key: s for s in SHOWERS}


def available() -> bool:
    return ephem is not None


def sun_longitude(jd: float) -> float:
    """地心から見た太陽の黄経（J2000）[度]。"""
    p = astro.all_positions(jd)["earth"]
    return math.degrees(math.atan2(-p[1], -p[0])) % 360.0


def jd_of_longitude(lam: float, jd_near: float) -> float:
    """太陽黄経が lam になる時刻（jd_near の前後 ±200日から探す）。"""
    def diff(t):
        return ((sun_longitude(t) - lam + 180.0) % 360.0) - 180.0
    t = jd_near - diff(jd_near) / 0.9856
    for _ in range(6):
        t -= diff(t) / 0.9856
    return t


def activity(shower: Shower, jd: float) -> float:
    """極大のときを 1 とした活動の強さ。"""
    d = ((sun_longitude(jd) - shower.lam + 180.0) % 360.0) - 180.0
    days = d / 0.9856
    return math.exp(-math.log(3) * (days / shower.width) ** 2)


def radiant_vector(shower: Shower) -> np.ndarray:
    ra, dec = math.radians(shower.ra), math.radians(shower.dec)
    return astro.equatorial_to_ecliptic(np.array([math.cos(dec) * math.cos(ra), math.cos(dec) * math.sin(ra),
                                                  math.sin(dec)]))


def _observer(lat, lon):
    o = ephem.Observer()
    o.lat, o.lon = str(lat), str(lon)
    o.pressure = 0
    return o


@dataclass
class ShowerNight:
    shower: Shower
    jd_peak: float
    jd_best: float | None          # 観測地で放射点がいちばん高く、空が暗いとき
    radiant_alt: float             # そのときの放射点の高度
    moon_illum: float              # 月の輝面比（0〜1）
    moon_alt: float                # そのときの月の高度
    rate: float                    # 見えそうな1時間あたりの数（目安）

    @property
    def condition(self) -> str:
        if self.jd_best is None:
            return "観測地では見えない（放射点が昇らない）"
        if self.moon_alt > 0 and self.moon_illum > 0.6:
            return "月明かりで条件が悪い"
        if self.moon_alt > 0 and self.moon_illum > 0.25:
            return "月明かりが少しじゃま"
        return "月明かりがなく条件が良い"


def shower_nights(jd_start: float, days: float, lat: float, lon: float) -> list[ShowerNight]:
    out = []
    obs = _observer(lat, lon)
    for sh in SHOWERS:
        t = jd_start
        while t < jd_start + days + 1:
            peak = jd_of_longitude(sh.lam, t + 180)
            if peak < jd_start - 1:
                t += 365
                continue
            if peak > jd_start + days:
                break
            out.append(_night(sh, peak, obs))
            t = peak + 200
    out.sort(key=lambda n: n.jd_peak)
    return out


def _night(sh: Shower, peak: float, obs) -> ShowerNight:
    body = ephem.FixedBody()
    body._ra, body._dec, body._epoch = math.radians(sh.ra), math.radians(sh.dec), ephem.J2000
    best, best_alt = None, -90.0
    t = peak - 0.5
    while t <= peak + 0.5:
        obs.date = ephem.Date(t - DJD)
        sun_alt = math.degrees(float(ephem.Sun(obs).alt))
        if sun_alt < -12:
            body.compute(obs)
            alt = math.degrees(float(body.alt))
            if alt > best_alt:
                best, best_alt = t, alt
        t += 10 / 1440
    if best is None or best_alt <= 0:
        obs.date = ephem.Date(peak - DJD)
        m = ephem.Moon(obs)
        return ShowerNight(sh, peak, None, best_alt, m.moon_phase, math.degrees(float(m.alt)), 0.0)
    obs.date = ephem.Date(best - DJD)
    m = ephem.Moon(obs)
    moon_alt = math.degrees(float(m.alt))
    rate = sh.zhr * math.sin(math.radians(best_alt)) * activity(sh, best)
    if moon_alt > 0:
        rate *= 1.0 - 0.6 * m.moon_phase
    rate *= 0.5                     # 町の明るさを少し考えた目安
    return ShowerNight(sh, peak, best, best_alt, m.moon_phase, moon_alt, rate)


# ---------------------------------------------------------------- 惑星・月の接近など

PLANETS = [("mercury", "水星", "Mercury"), ("venus", "金星", "Venus"), ("mars", "火星", "Mars"),
           ("jupiter", "木星", "Jupiter"), ("saturn", "土星", "Saturn")]
JA = {k: j for k, j, _ in PLANETS} | {"moon": "月"}


@dataclass
class Event:
    jd: float
    kind: str               # conj / occult / opposition / elong
    title: str
    keys: tuple             # 見る天体
    detail: str = ""
    sep: float = 0.0        # 離れ角 [度]
    local: dict = field(default_factory=dict)


def _body(key, t, obs=None):
    name = {"moon": "Moon", "sun": "Sun"}.get(key) or dict((k, e) for k, _, e in PLANETS)[key]
    b = getattr(ephem, name)()
    if obs is None:
        b.compute(ephem.Date(t - DJD))
    else:
        obs.date = ephem.Date(t - DJD)
        b.compute(obs)
    return b


def _sep(a, b, t):
    return math.degrees(float(ephem.separation(_body(a, t), _body(b, t))))


def _refine_min(fn, t0, step):
    a, b = t0 - step, t0 + step
    g = (math.sqrt(5) - 1) / 2
    c, d = b - g * (b - a), a + g * (b - a)
    fc, fd = fn(c), fn(d)
    while b - a > 1 / 1440:
        if fc < fd:
            b, d, fd = d, c, fc
            c = b - g * (b - a)
            fc = fn(c)
        else:
            a, c, fc = c, d, fd
            d = a + g * (b - a)
            fd = fn(d)
    return (a + b) / 2


def _elong(key, t):
    return math.degrees(float(ephem.separation(_body(key, t), _body("sun", t))))


def find_events(jd_start: float, days: float, lat: float, lon: float) -> list[Event]:
    out = []
    keys = [k for k, _, _ in PLANETS]
    # 惑星どうし（2度以内）
    for i in range(len(keys)):
        for j in range(i + 1, len(keys)):
            a, b = keys[i], keys[j]
            t = jd_start
            prev2, prev = None, None
            while t <= jd_start + days:
                s = _sep(a, b, t)
                if prev is not None and prev2 is not None and prev < prev2 and prev <= s and prev < 2.5:
                    tm = _refine_min(lambda x: _sep(a, b, x), t - 1, 1.0)
                    sm = _sep(a, b, tm)
                    if sm < 2.0:
                        out.append(Event(tm, "conj", f"{JA[a]}と{JA[b]}が接近", (a, b),
                                         f"{sm:.1f}°まで近づく", sm))
                prev2, prev = prev, s
                t += 1.0
    # 月と惑星（地心で4度以内）
    for a in keys:
        t = jd_start
        prev2, prev = None, None
        while t <= jd_start + days:
            s = _sep("moon", a, t)
            if prev is not None and prev2 is not None and prev < prev2 and prev <= s and prev < 8:
                tm = _refine_min(lambda x: _sep("moon", a, x), t - 0.125, 0.125)
                sm = _sep("moon", a, tm)
                if sm < 4.0:
                    kind = "occult" if sm < 0.9 else "conj"     # 地球のどこかで惑星食になるかもしれない
                    out.append(Event(tm, kind, f"月と{JA[a]}が接近", ("moon", a), f"{sm:.1f}°まで近づく（地心）", sm))
            prev2, prev = prev, s
            t += 0.125
    # 外惑星の衝（太陽の反対側に来て、一晩中見える見ごろ）
    for a in ("mars", "jupiter", "saturn"):
        t = jd_start
        prev2, prev = None, None
        while t <= jd_start + days:
            e = _elong(a, t)
            if prev is not None and prev2 is not None and prev > prev2 and prev >= e and prev > 150:
                tm = _refine_min(lambda x: -_elong(a, x), t - 2, 2.0)
                b = _body(a, tm)
                out.append(Event(tm, "opposition", f"{JA[a]}が衝（見ごろ）", (a,),
                                 f"一晩中見える。明るさ {b.mag:.1f} 等、地球から {b.earth_distance:.2f} AU"))
            prev2, prev = prev, e
            t += 2.0
    # 内惑星の最大離角（夕方・明け方に見やすい）
    for a in ("mercury", "venus"):
        t = jd_start
        prev2, prev = None, None
        while t <= jd_start + days:
            e = _elong(a, t)
            if prev is not None and prev2 is not None and prev > prev2 and prev >= e:
                tm = _refine_min(lambda x: -_elong(a, x), t - 1, 1.0)
                sun, b = _body("sun", tm), _body(a, tm)
                east = ((float(b.ra) - float(sun.ra) + math.pi) % (2 * math.pi) - math.pi) > 0
                when = "東方最大離角（夕方の西の空）" if east else "西方最大離角（明け方の東の空）"
                out.append(Event(tm, "elong", f"{JA[a]}が{when}", (a,),
                                 f"太陽から {_elong(a, tm):.0f}° 離れる", 0.0))
            prev2, prev = prev, e
            t += 1.0
    out = [e for e in out if jd_start <= e.jd <= jd_start + days]
    for e in out:
        _event_local(e, lat, lon)
    out.sort(key=lambda e: e.jd)
    return out


def _event_local(e: Event, lat, lon):
    """観測地で見やすい時刻（日の入り後・日の出前で、天体がいちばん高いとき）と高度。"""
    obs = _observer(lat, lon)
    best, best_alt = None, -90.0
    t = e.jd - 0.5
    while t <= e.jd + 0.5:
        obs.date = ephem.Date(t - DJD)
        sun_alt = math.degrees(float(ephem.Sun(obs).alt))
        if sun_alt < -6:
            alt = min(math.degrees(float(_body(k, t, obs).alt)) for k in e.keys)
            if alt > best_alt:
                best, best_alt = t, alt
        t += 10 / 1440
    if e.kind in ("conj", "occult") and "moon" in e.keys and best is not None:
        # 観測地から見た月との離れ角（月は近いので、場所によって見え方がかなり変わる）
        a = [k for k in e.keys if k != "moon"][0]
        e.local["sep"] = math.degrees(float(ephem.separation(_body("moon", best, obs), _body(a, best, obs))))
    e.local.update({"jd": best, "alt": best_alt, "visible": best is not None and best_alt > 5})
