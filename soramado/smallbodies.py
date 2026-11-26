"""小天体（準惑星・小惑星・彗星）。

軌道要素（軌道長半径 a、離心率 e、軌道傾斜角 i、昇交点黄経 Ω、近日点引数 ω、近日点通過日）
から、ケプラー運動で位置を計算する。惑星の引力による変化（摂動）は計算していないので、
近日点通過日から離れた年ほどずれが大きくなる（おおよその位置）。

冥王星だけは NASA JPL "Approximate Positions of the Planets" Table 1 の要素を使う（astro.py）。
その他の要素は Wikipedia の各天体の記事（JPL Small-Body Database などを出典とする値）による。
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from datetime import datetime, timezone

import numpy as np

from . import astro

GAUSS_YEAR = 365.256898     # 1 AU の円軌道の公転周期 [日]


def _jd(y, m, d):
    return astro.jd_from_datetime(datetime(y, m, d, tzinfo=timezone.utc))


@dataclass(frozen=True)
class SmallBody:
    key: str
    name: str
    kind: str          # "dwarf" 準惑星, "asteroid" 小惑星, "comet" 彗星
    a: float           # 軌道長半径 [AU]
    e: float
    i: float           # [度]
    node: float        # 昇交点黄経 [度]
    peri: float        # 近日点引数 [度]
    tp: float          # 近日点通過 [JD]
    diameter_km: float
    color: tuple
    note: str = ""

    @property
    def period_days(self) -> float:
        return GAUSS_YEAR * self.a ** 1.5


KIND_JA = {"dwarf": "準惑星", "asteroid": "小惑星", "comet": "彗星"}

SMALL_BODIES = [
    SmallBody("eris", "エリス", "dwarf", 67.69, 0.44, 44.18, 36.02, 151.66, _jd(2257, 12, 6), 2326,
              (0.85, 0.85, 0.85), "冥王星とほぼ同じ大きさの準惑星"),
    SmallBody("makemake", "マケマケ", "dwarf", 45.499, 0.1604, 29.002, 79.441, 296.065, _jd(2186, 11, 17), 1430,
              (0.85, 0.65, 0.55)),
    SmallBody("haumea", "ハウメア", "dwarf", 43.116, 0.19642, 28.2137, 122.167, 239.041, _jd(2133, 6, 1), 1544,
              (0.85, 0.85, 0.90), "高速で自転する細長い準惑星"),
    SmallBody("ceres", "ケレス", "dwarf", 2.7675, 0.0785, 10.6, 80.3, 73.6, _jd(2027, 7, 11), 939.4,
              (0.65, 0.63, 0.60), "小惑星帯で最大の天体（準惑星）"),
    SmallBody("pallas", "パラス", "asteroid", 2.7720, 0.2302, 34.93, 172.9, 310.9, _jd(2023, 3, 7), 512,
              (0.62, 0.62, 0.62)),
    SmallBody("vesta", "ベスタ", "asteroid", 2.3615, 0.0894, 7.1422, 103.71, 151.66, _jd(2021, 12, 26), 525.4,
              (0.72, 0.70, 0.66)),
    SmallBody("itokawa", "イトカワ", "asteroid", 1.3241, 0.2801, 1.6214, 69.081, 162.82, 0.0, 0.33,
              (0.70, 0.66, 0.60), "探査機「はやぶさ」が試料を持ち帰った小惑星"),
    SmallBody("ryugu", "リュウグウ", "asteroid", 1.1896, 0.1902, 5.8837, 251.62, 211.43, 0.0, 0.9,
              (0.45, 0.42, 0.40), "探査機「はやぶさ2」が試料を持ち帰った小惑星"),
    SmallBody("bennu", "ベンヌ", "asteroid", 1.1264, 0.2038, 6.0349, 2.0609, 66.2231, 0.0, 0.49,
              (0.45, 0.43, 0.42), "探査機 OSIRIS-REx が試料を持ち帰った小惑星"),
    SmallBody("halley", "ハレー彗星", "comet", 17.737, 0.96658, 161.96, 59.396, 112.05, _jd(2061, 7, 28), 11,
              (0.80, 0.90, 1.0), "約76年ごとに戻ってくる彗星。次の回帰は2061年"),
    SmallBody("encke", "エンケ彗星", "comet", 2.218, 0.84711, 11.344, 334.01, 187.28, _jd(2027, 2, 10), 4.86,
              (0.80, 0.90, 1.0), "公転周期が約3.3年と最も短い彗星"),
    SmallBody("67p", "チュリュモフ・ゲラシメンコ彗星", "comet", 3.457, 0.64989, 3.8719, 36.33, 22.15,
              _jd(2021, 11, 2), 4.0, (0.80, 0.90, 1.0), "探査機ロゼッタが着陸した彗星（67P）"),
]

# 近日点通過日の代わりに「元期の平均近点角」で与えるもの: (元期 JD, 平均近点角)
_EPOCH_M = {"itokawa": (2458600.5, 288.88), "ryugu": (2455907.5, 3.9832), "bennu": (2455562.5, 101.7039)}

BY_KEY = {b.key: b for b in SMALL_BODIES}


def _mean_anomaly(b: SmallBody, jd: float) -> float:
    n = 360.0 / b.period_days
    if b.key in _EPOCH_M:
        ep, m0 = _EPOCH_M[b.key]
        return math.radians((m0 + n * (jd - ep)) % 360.0)
    return math.radians((n * (jd - b.tp)) % 360.0)


def _kepler(m: float, e: float) -> float:
    ecc = math.pi if e > 0.8 else m + e * math.sin(m)
    for _ in range(60):
        d = (ecc - e * math.sin(ecc) - m) / (1.0 - e * math.cos(ecc))
        ecc -= d
        if abs(d) < 1e-13:
            break
    return ecc


def position(b: SmallBody, jd: float) -> np.ndarray:
    """日心黄道座標（J2000）[AU]。"""
    ecc = _kepler(_mean_anomaly(b, jd), b.e)
    xp = b.a * (math.cos(ecc) - b.e)
    yp = b.a * math.sqrt(1 - b.e * b.e) * math.sin(ecc)
    node = b.node
    return np.array(astro._orbit_to_ecliptic(xp, yp, b.i, b.peri + node, node))


def orbit_path(b: SmallBody, segments: int = 1024) -> np.ndarray:
    ecc = np.linspace(0, 2 * math.pi, segments + 1)
    xp = b.a * (np.cos(ecc) - b.e)
    yp = b.a * math.sqrt(1 - b.e * b.e) * np.sin(ecc)
    x, y, z = astro._orbit_to_ecliptic(xp, yp, b.i, b.peri + b.node, b.node)
    return np.stack([x, y, z], axis=1)


def add_positions(pos: dict, jd: float) -> dict:
    pos["pluto"] = astro.planet_position("pluto", jd)
    for b in SMALL_BODIES:
        pos[b.key] = position(b, jd)
    return pos


def _english_names():
    from .i18n import EN_MODE, name_en
    if EN_MODE:
        for x in SMALL_BODIES:
            object.__setattr__(x, "name", name_en(x.key, x.name))


_english_names()
