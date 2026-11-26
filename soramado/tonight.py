"""今夜の空ガイド：その夜、観測地で何が見えるかをまとめる。

惑星・月・星座・人工衛星・流星群・天文現象を、日の入りから日の出までの間で調べる。
計算は PyEphem。表示（文章）は app.py で作る。
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from datetime import datetime, timedelta

import numpy as np

from . import astro

try:
    import ephem
except ImportError:  # pragma: no cover
    ephem = None

DJD = 2415020.0                # PyEphem の日付（1899-12-31 12:00 UT 起点）と JD の差
STEP = 10 / 1440               # 調べる間隔（10分）

PLANETS = [("mercury", "Mercury"), ("venus", "Venus"), ("mars", "Mars"),
           ("jupiter", "Jupiter"), ("saturn", "Saturn")]


def available() -> bool:
    return ephem is not None


@dataclass
class Night:
    date: datetime             # その夜の日付（夕方の日付、観測地の時刻帯）
    sunset: float | None       # JD
    dusk: float | None         # 空が暗くなる（太陽高度 -12°）
    dawn: float | None         # 空が明るくなり始める（太陽高度 -12°）
    sunrise: float | None


@dataclass
class BodyView:
    key: str
    mag: float
    con: str                   # 星座の略号
    start: float | None        # 見えはじめ（暗い空で高度8°より上）
    end: float | None          # 見えおわり
    best: float | None         # いちばん高いとき
    best_alt: float
    best_az: float
    when: str = ""             # evening / morning / night / all / late / none


@dataclass
class MoonView:
    age: float                 # 月齢
    illum: float               # 輝面比 0〜1
    rise: float | None
    set: float | None
    phase: str                 # 月の形の名前（日本語）
    bright_night: bool         # 暗い時間の多くで、明るい月が空にある
    best: float | None = None
    best_alt: float = -90.0
    best_az: float = 0.0


@dataclass
class ConView:
    index: int                 # StarCatalog.constellations の番号
    cid: str
    alt: float
    az: float


@dataclass
class Guide:
    night: Night
    moon: MoonView | None
    planets: list[BodyView]
    cons: list[ConView]
    con_jd: float               # 星座を調べた時刻
    passes: list = field(default_factory=list)
    showers: list = field(default_factory=list)
    events: list = field(default_factory=list)
    eclipses: list = field(default_factory=list)


def _obs(lat, lon, jd=None, horizon="0"):
    o = ephem.Observer()
    o.lat, o.lon = str(lat), str(lon)
    o.pressure = 0
    o.horizon = horizon
    if jd is not None:
        o.date = ephem.Date(jd - DJD)
    return o


def night_of(now_local: datetime) -> datetime:
    """いまの時刻から「今夜」の日付を決める（朝6時までは、前の日の夜のつづき）。"""
    d = now_local - timedelta(hours=6) if now_local.hour < 6 else now_local
    return d.replace(hour=12, minute=0, second=0, microsecond=0)


def night_window(date_noon_local: datetime, lat: float, lon: float) -> Night:
    jd_noon = astro.jd_from_datetime(date_noon_local)

    o = _obs(lat, lon, jd_noon, "-0:34")
    try:
        sunset = float(o.next_setting(ephem.Sun())) + DJD
    except (ephem.AlwaysUpError, ephem.NeverUpError):
        sunset = None
    o = _obs(lat, lon, jd_noon, "-12")
    try:
        dusk = float(o.next_setting(ephem.Sun(), use_center=True)) + DJD
        o.date = ephem.Date(dusk - DJD)
        dawn = float(o.next_rising(ephem.Sun(), use_center=True)) + DJD
    except (ephem.AlwaysUpError, ephem.NeverUpError):
        dusk = dawn = None
    o = _obs(lat, lon, sunset if sunset else jd_noon + 0.3, "-0:34")
    try:
        sunrise = float(o.next_rising(ephem.Sun())) + DJD
    except (ephem.AlwaysUpError, ephem.NeverUpError):
        sunrise = None
    return Night(date_noon_local, sunset, dusk, dawn, sunrise)


def _span(night: Night):
    a = night.sunset if night.sunset else astro.jd_from_datetime(night.date) + 0.25
    b = night.sunrise if night.sunrise and night.sunrise > a else a + 0.6
    return a, b


def _body(key):
    return {"moon": ephem.Moon}.get(key, getattr(ephem, dict(PLANETS).get(key, "Sun")))()


def _track(key, night: Night, lat, lon, sun_limit=-6.0, alt_limit=8.0):
    """日の入り〜日の出のあいだ、空が暗く（太陽高度 sun_limit 未満）天体が高度 alt_limit より上の時間。"""
    a, b = _span(night)
    o = _obs(lat, lon)
    body, sun = _body(key), ephem.Sun()
    start = end = best = None
    best_alt, best_az = -90.0, 0.0
    t = a
    while t <= b:
        o.date = ephem.Date(t - DJD)
        sun.compute(o)
        body.compute(o)
        alt = math.degrees(float(body.alt))
        if math.degrees(float(sun.alt)) < sun_limit and alt > alt_limit:
            if start is None:
                start = t
            end = t
            if alt > best_alt:
                best, best_alt, best_az = t, alt, math.degrees(float(body.az))
        t += STEP
    return start, end, best, best_alt, best_az


def _when(start, end, night: Night) -> str:
    if start is None:
        return "none"
    a, b = _span(night)
    mid = (a + b) / 2
    early = start - a < 0.08           # 日の入り後すぐ（2時間以内）から見える
    late = b - end < 0.08              # 日の出前まで見える
    if early and late:
        return "all"
    if early or end < mid:
        return "evening"
    if late and start > mid:
        return "morning"
    if late:
        return "night"             # 夜中に昇って明け方まで
    return "late"


def planets(night: Night, lat, lon) -> list[BodyView]:
    out = []
    for key, _ in PLANETS:
        start, end, best, alt, az = _track(key, night, lat, lon)
        b = _body(key)
        b.compute(ephem.Date((best or _span(night)[0]) - DJD))
        con = ephem.constellation(b)[0]
        out.append(BodyView(key, float(b.mag), con, start, end, best, alt, az, _when(start, end, night)))
    return out


MOON_PHASES = [(1.5, "新月"), (4.5, "三日月"), (6.0, "上弦前の月"), (9.0, "上弦の月"), (13.0, "十日夜〜十三夜の月"),
               (16.5, "満月"), (20.0, "満月すぎの月"), (24.0, "下弦の月"), (28.0, "有明の月"), (30.0, "新月")]


def moon(night: Night, lat, lon) -> MoonView:
    a, b = _span(night)
    mid = (a + b) / 2
    d = ephem.Date(mid - DJD)
    age = float(d - ephem.previous_new_moon(d))
    m = ephem.Moon()
    m.compute(d)
    illum = float(m.moon_phase)
    phase = next(name for lim, name in MOON_PHASES if age < lim)
    o = _obs(lat, lon, a - 0.25, "-0:34")
    try:
        rise = float(o.next_rising(ephem.Moon())) + DJD
    except (ephem.AlwaysUpError, ephem.NeverUpError):
        rise = None
    o = _obs(lat, lon, a - 0.25, "-0:34")
    try:
        mset = float(o.next_setting(ephem.Moon())) + DJD
    except (ephem.AlwaysUpError, ephem.NeverUpError):
        mset = None
    start, end, best, alt, az = _track("moon", night, lat, lon, sun_limit=-6.0, alt_limit=0.0)
    # 暗い時間（太陽 -12° より下）のうち、月が出ている割合
    dark_a, dark_b = (night.dusk or a), (night.dawn or b)
    up = 0
    n = 0
    o = _obs(lat, lon)
    t = dark_a
    while t <= dark_b:
        o.date = ephem.Date(t - DJD)
        m.compute(o)
        n += 1
        up += float(m.alt) > 0
        t += STEP
    bright = illum > 0.5 and n > 0 and up / n > 0.5
    return MoonView(age, illum, rise, mset, phase, bright, best, alt, az)


def constellations(cat, night: Night, lat, lon, seasons=None, count=6):
    """暗くなってから（夜9時か、空が暗くなるときの遅いほう）高く見える星座。"""
    a, b = _span(night)
    nine = astro.jd_from_datetime(night.date.replace(hour=21))
    jd = max(nine, night.dusk or a)
    if jd > b:
        jd = (a + b) / 2
    off, zen, north, east = astro.observer_frame(jd, lat, lon)
    out = []
    for i, c in enumerate(cat.constellations):
        if seasons is not None and "見えない" in seasons.get(c.id, ""):
            continue
        alt, az = astro.alt_az(np.asarray(c.center), zen, north, east)
        if alt > 25:
            out.append(ConView(i, c.id, alt, az))
    out.sort(key=lambda c: -c.alt)
    return out[:count], jd


def build(now_local: datetime, lat: float, lon: float, cat=None, seasons=None, artsats=None,
          with_events=True) -> Guide:
    """今夜のガイドをまとめて計算する。now_local は観測地の時刻帯の日時。"""
    from . import eclipses, events

    night = night_window(night_of(now_local), lat, lon)
    g = Guide(night, moon(night, lat, lon), planets(night, lat, lon), [], 0.0)
    if cat is not None:
        g.cons, g.con_jd = constellations(cat, night, lat, lon, seasons)
    a, b = _span(night)
    if artsats:
        from . import artsat
        for s in artsats:
            if s.featured and artsat.usable(s, a):
                try:
                    g.passes += [p for p in artsat.passes(s, lat, lon, a, b - a) if p.visible]
                except ValueError:
                    pass
        g.passes.sort(key=lambda p: p.rise_jd)
    if with_events:
        g.showers = [n for n in events.shower_nights(a - 4, 8, lat, lon)
                     if abs(n.jd_peak - (a + b) / 2) <= 2.5 and n.jd_best is not None and n.rate >= 2]
        g.events = events.find_events(a - 0.5, 7.5, lat, lon)
        g.eclipses = eclipses.search(a - 0.5, 31 / 365.25, lat, lon)
    return g
