"""恒星と星座のデータ。"""

from __future__ import annotations

import json
import math
from dataclasses import dataclass
from pathlib import Path

import numpy as np

from . import astro
from .starnames import JA_NAMES, greek

DATA_DIR = Path(__file__).parent / "data"
PC_AU = 206264.806          # 1 パーセク [AU]
PC_LY = 3.26156             # 1 パーセク [光年]
UNKNOWN_DIST_PC = 99999.0   # HYG で距離不明の星は 100000 pc になっている


def _bv_to_rgb(bv: np.ndarray) -> np.ndarray:
    """B−V 色指数 → 星の色（RGB 0〜1）。"""
    bv = np.clip(bv, -0.4, 2.0)
    t = 4600.0 * (1.0 / (0.92 * bv + 1.7) + 1.0 / (0.92 * bv + 0.62))   # 表面温度 [K]
    t = t / 100.0
    r = np.where(t <= 66, 255.0, 329.698727446 * np.power(np.maximum(t - 60, 1e-6), -0.1332047592))
    g = np.where(t <= 66, 99.4708025861 * np.log(t) - 161.1195681661,
                 288.1221695283 * np.power(np.maximum(t - 60, 1e-6), -0.0755148492))
    b = np.where(t >= 66, 255.0, np.where(t <= 19, 0.0, 138.5177312231 * np.log(np.maximum(t - 10, 1e-6)) - 305.0447927307))
    rgb = np.clip(np.stack([r, g, b], axis=1) / 255.0, 0, 1)
    return rgb * 0.7 + 0.3          # 少し白に寄せて自然に見せる


@dataclass
class Constellation:
    id: str
    name: str
    center: np.ndarray       # 黄道座標の単位ベクトル
    segments: np.ndarray     # (n, 2, 3) 線分の両端（単位ベクトル）


def _radec_vec(ra_deg: float, dec_deg: float) -> np.ndarray:
    ra, dec = math.radians(ra_deg), math.radians(dec_deg)
    return astro.equatorial_to_ecliptic(
        np.array([math.cos(dec) * math.cos(ra), math.cos(dec) * math.sin(ra), math.sin(dec)]))


class StarCatalog:
    def __init__(self):
        d = np.load(DATA_DIR / "stars.npz")
        eq = d["xyz"].astype(np.float64)
        ecl = np.empty_like(eq)
        c, s = math.cos(astro.OBLIQUITY_J2000), math.sin(astro.OBLIQUITY_J2000)
        ecl[:, 0] = eq[:, 0]
        ecl[:, 1] = c * eq[:, 1] + s * eq[:, 2]
        ecl[:, 2] = -s * eq[:, 1] + c * eq[:, 2]
        self.pos_pc = ecl                       # 太陽中心・黄道座標 [pc]
        self.dist_pc = d["dist"].astype(np.float64)
        self.dir = ecl / np.maximum(self.dist_pc, 1e-9)[:, None]
        self.mag = d["mag"].astype(np.float64)
        self.rgb = _bv_to_rgb(d["ci"].astype(np.float64))
        self.hip = d["hip"]
        self.proper = d["proper"]
        self.bayer = d["bayer"]
        self.flam = d["flam"]
        self.con = d["con"]
        self.spect = d["spect"]
        self.count = len(self.mag)

        cj = json.load(open(DATA_DIR / "constellations.json", encoding="utf-8"))
        self.constellations: list[Constellation] = []
        self.con_names = {}
        for c in cj["constellations"]:
            segs = []
            for line in c["lines"]:
                pts = [_radec_vec(ra, dec) for ra, dec in line]
                segs += [(a, b) for a, b in zip(pts, pts[1:])]
            self.constellations.append(Constellation(
                c["id"], c["ja"], _radec_vec(c["ra"], c["dec"]),
                np.array(segs, dtype=np.float64).reshape(-1, 2, 3)))
            self.con_names[c["id"]] = c["ja"]

        # 名前を表示する星（固有名のある明るい星）
        self.labeled = [i for i in range(min(self.count, 3000))
                        if str(self.proper[i]) in JA_NAMES and self.mag[i] < 4.5]

    def vertex_data(self) -> np.ndarray:
        """GPU に送る頂点データ: 位置[AU](3), 等級(1), 太陽からの距離[AU](1), 色(3)"""
        pos_au = self.pos_pc * PC_AU
        dist_au = np.maximum(self.dist_pc * PC_AU, 1.0)
        return np.concatenate([pos_au, self.mag[:, None], dist_au[:, None], self.rgb], axis=1).astype(np.float32)

    def line_vertices(self) -> np.ndarray:
        segs = [c.segments.reshape(-1, 3) for c in self.constellations if len(c.segments)]
        return np.concatenate(segs).astype(np.float32)

    # ---------------------------------------------------------- 名前・情報

    def short_name(self, i: int) -> str:
        p = str(self.proper[i])
        if p:
            return JA_NAMES.get(p, p)
        return self.designation(i)

    def designation(self, i: int) -> str:
        con = str(self.con[i])
        cname = self.con_names.get(con, con)
        b, f = str(self.bayer[i]), str(self.flam[i])
        if b:
            return f"{cname}{greek(b)}星"
        if f:
            return f"{cname}{f}番星"
        if self.hip[i]:
            return f"HIP {self.hip[i]}"
        return f"星 #{i}"

    def describe(self, i: int, eye_au: np.ndarray | None = None) -> str:
        parts = [f"<b>{self.short_name(i)}</b>"]
        desig = self.designation(i)
        if self.proper[i] and desig not in parts[0]:
            parts.append(desig)
        parts.append(f"{self.mag[i]:.2f} 等（地球から見た明るさ）")
        d = self.dist_pc[i]
        if d < UNKNOWN_DIST_PC:
            ly = d * PC_LY
            parts.append(f"距離 {ly:,.1f} 光年" if ly < 100 else f"距離 {ly:,.0f} 光年")
        else:
            parts.append("距離 不明")
        if self.spect[i]:
            parts.append(f"スペクトル型 {self.spect[i]}")
        return "　｜　".join(parts)
