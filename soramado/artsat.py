"""人工衛星（国際宇宙ステーションなど）。

軌道要素（TLE）は CelesTrak (https://celestrak.org/) から、使う人のパソコンでダウンロードする。
位置の計算は PyEphem（SGP4）。TLE は数日で古くなる（ISS は高度を保つためにエンジンを噴かすことがある）ので、
1週間より古いときは注意を出す。
"""

from __future__ import annotations

import datetime as _dt
import math
import threading
import urllib.request
from dataclasses import dataclass

import numpy as np

from . import astro
from .cosmos import data_dir

try:
    import ephem
except ImportError:  # pragma: no cover
    ephem = None

URLS = ["https://celestrak.org/NORAD/elements/gp.php?GROUP=stations&FORMAT=tle",
        "https://celestrak.org/NORAD/elements/gp.php?GROUP=visual&FORMAT=tle"]
TLE_FILE = "satellites.tle"
DJD = 2415020.0
EARTH_R_KM = 6378.137

# 名前を出す、おもな衛星（NORAD 番号: 日本語の名前, 解説）
FEATURED = {
    25544: ("国際宇宙ステーション（ISS）", "日本・アメリカ・ロシア・ヨーロッパ・カナダが協力して運用している宇宙ステーション。"
                                     "高度約400kmを、約90分で地球を1周する。サッカー場くらいの大きさがあり、"
                                     "太陽の光を反射して、夜空をゆっくり動く明るい光として肉眼で見える。日本の実験棟「きぼう」がある。"),
    48274: ("中国宇宙ステーション（天宮）", "中国の宇宙ステーション。高度約380〜400kmを回っている。中心のモジュール「天和」。"),
    20580: ("ハッブル宇宙望遠鏡", "1990年に打ち上げられた宇宙望遠鏡。高度約530kmを回り、大気にじゃまされずに宇宙を観測している。"),
}


def available() -> bool:
    return ephem is not None


@dataclass
class ArtSat:
    num: int
    name: str
    body: object            # ephem.EarthSatellite
    epoch_jd: float
    rev_per_day: float

    @property
    def ja(self) -> str:
        from .i18n import EN_MODE, NAMES_EN
        if EN_MODE:
            return NAMES_EN.get(f"s:{self.num}", self.name.title())
        return FEATURED.get(self.num, (self.name.title(), ""))[0]

    @property
    def featured(self) -> bool:
        return self.num in FEATURED

    @property
    def note(self) -> str:
        return FEATURED.get(self.num, ("", "人工衛星。"))[1]


def parse(text: str) -> list[ArtSat]:
    lines = [ln.rstrip() for ln in text.splitlines() if ln.strip()]
    out, seen = [], set()
    i = 0
    while i <= len(lines) - 3:
        name, l1, l2 = lines[i], lines[i + 1], lines[i + 2]
        if not (l1.startswith("1 ") and l2.startswith("2 ")):
            i += 1
            continue
        try:
            num = int(l1[2:7])
            if num not in seen:
                body = ephem.readtle(name.strip(), l1, l2)
                yy = int(l1[18:20])
                year = 2000 + yy if yy < 57 else 1900 + yy
                day = float(l1[20:32])
                epoch = astro.jd_from_datetime(_dt.datetime(year, 1, 1, tzinfo=_dt.timezone.utc)) + day - 1
                out.append(ArtSat(num, name.strip(), body, epoch, float(l2[52:63])))
                seen.add(num)
        except (ValueError, IndexError):
            pass
        i += 3
    # おもな衛星を先頭に
    out.sort(key=lambda s: (not s.featured, list(FEATURED).index(s.num) if s.featured else 0, s.name))
    return out


def load() -> list[ArtSat]:
    if ephem is None:
        return []
    p = data_dir() / TLE_FILE
    if not p.is_file():
        return []
    try:
        return parse(p.read_text(encoding="utf-8", errors="replace"))
    except Exception:  # noqa: BLE001
        return []


def offset(s: ArtSat, jd: float) -> np.ndarray:
    """地球の中心から衛星までのベクトル（J2000 黄道座標）[AU]。"""
    s.body.compute(ephem.Date(jd - DJD))
    lat, lon = math.degrees(float(s.body.sublat)), math.degrees(float(s.body.sublong))
    r = EARTH_R_KM + float(s.body.elevation) / 1000.0
    _off, zen, _n, _e = astro.observer_frame(jd, lat, lon)
    return zen * r / astro.AU_KM


def height_km(s: ArtSat, jd: float) -> float:
    s.body.compute(ephem.Date(jd - DJD))
    return float(s.body.elevation) / 1000.0


def orbit_path(s: ArtSat, jd: float, segments: int = 120) -> np.ndarray:
    """いまの前後1周ぶんの軌道（地球中心、宇宙に対して止まった座標）[AU]。"""
    period = 1.0 / max(s.rev_per_day, 0.05)
    return np.array([offset(s, jd + period * (k / segments - 0.5)) for k in range(segments + 1)])


def topo(s: ArtSat, jd: float, lat: float, lon: float):
    """観測地から見た高度・方位 [度]、太陽の光が当たっているか。"""
    o = ephem.Observer()
    o.lat, o.lon = str(lat), str(lon)
    o.pressure = 0
    o.date = ephem.Date(jd - DJD)
    s.body.compute(o)
    return math.degrees(float(s.body.alt)), math.degrees(float(s.body.az)), not s.body.eclipsed


@dataclass
class Pass:
    sat: ArtSat
    rise_jd: float
    rise_az: float
    max_jd: float
    max_alt: float
    max_az: float
    set_jd: float
    set_az: float
    visible: bool          # 夜空で太陽の光を受けて見えるか


def passes(s: ArtSat, lat: float, lon: float, jd_start: float, days: float) -> list[Pass]:
    o = ephem.Observer()
    o.lat, o.lon = str(lat), str(lon)
    o.pressure = 0
    o.horizon = "10"            # 地平線すれすれは見えにくいので、高度10度から
    o.date = ephem.Date(jd_start - DJD)
    out = []
    end = jd_start + days
    for _ in range(200):
        try:
            tr, azr, tmax, altmax, ts, azs = o.next_pass(s.body)
        except (ValueError, TypeError):
            break
        if tr is None or ts is None or tmax is None:
            break
        jr, jm, js = float(tr) + DJD, float(tmax) + DJD, float(ts) + DJD
        if jr > end:
            break
        if math.degrees(float(altmax)) < 10:
            o.date = ts + ephem.minute * 5
            continue
        # 最大のときに、空が暗く（太陽が地平線の6度より下）、衛星に日が当たっていれば見える
        o2 = ephem.Observer()
        o2.lat, o2.lon, o2.pressure = o.lat, o.lon, 0
        o2.date = tmax
        sun_alt = math.degrees(float(ephem.Sun(o2).alt))
        s.body.compute(o2)
        vis = sun_alt < -6 and not s.body.eclipsed
        out.append(Pass(s, jr, math.degrees(float(azr)), jm, math.degrees(float(altmax)),
                        math.degrees(float(s.body.az)), js, math.degrees(float(azs)), vis))
        o.date = ts + ephem.minute * 5
    return out


def tle_age_days(sats: list[ArtSat], jd: float) -> float:
    if not sats:
        return 0.0
    return jd - max(s.epoch_jd for s in sats if s.featured) if any(s.featured for s in sats) else \
        jd - max(s.epoch_jd for s in sats)


class TleDownloader:
    def __init__(self):
        self.done = False
        self.ok = False
        self.message = ""
        self.count = 0
        self._thread = threading.Thread(target=self._run, daemon=True)

    def start(self):
        self._thread.start()

    def _run(self):
        try:
            texts = []
            for url in URLS:
                req = urllib.request.Request(url, headers={"User-Agent": "Soramado (space simulator)"})
                texts.append(urllib.request.urlopen(req, timeout=60).read().decode("utf-8", "replace"))
            text = "\n".join(texts)
            sats = parse(text)
            if len(sats) < 3:
                raise RuntimeError("人工衛星のデータを読み込めませんでした")
            d = data_dir()
            d.mkdir(parents=True, exist_ok=True)
            (d / TLE_FILE).write_text(text, encoding="utf-8")
            self.count = len(sats)
            self.ok = True
        except Exception as exc:  # noqa: BLE001
            self.message = str(exc)
        self.done = True
