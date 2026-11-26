"""恒星と星座のデータ。"""

from __future__ import annotations

import json
import math
from dataclasses import dataclass
from pathlib import Path

import numpy as np

from .i18n import EN_MODE

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
        # 空間速度（黄道座標・パーセク/年）。古いデータファイルにはないので 0 にする
        if "vel" in d.files:
            ve = d["vel"].astype(np.float64)
            self.vel = np.stack([ve[:, 0], c * ve[:, 1] + s * ve[:, 2], -s * ve[:, 1] + c * ve[:, 2]], axis=1)
            self.vel[self.dist_pc >= UNKNOWN_DIST_PC] = 0.0
        else:
            self.vel = np.zeros_like(ecl)
        self.epoch = 0.0                         # 星の位置の時代（今から何年後か）
        self._pos0, self._dist0, self._mag0 = self.pos_pc.copy(), self.dist_pc.copy(), self.mag.copy()
        self._line_stars = None

        cj = json.load(open(DATA_DIR / "constellations.json", encoding="utf-8"))
        self.constellations: list[Constellation] = []
        self.con_names = {}
        for c in cj["constellations"]:
            segs = []
            for line in c["lines"]:
                pts = [_radec_vec(ra, dec) for ra, dec in line]
                segs += [(a, b) for a, b in zip(pts, pts[1:])]
            self.constellations.append(Constellation(
                c["id"], c["en"] if EN_MODE else c["ja"], _radec_vec(c["ra"], c["dec"]),
                np.array(segs, dtype=np.float64).reshape(-1, 2, 3)))
            self.con_names[c["id"]] = c["en"] if EN_MODE else c["ja"]

        # 名前を表示する星（固有名のある明るい星）
        self.labeled = [i for i in range(min(self.count, 3000))
                        if str(self.proper[i]) in JA_NAMES and self.mag[i] < 4.5]

    def set_epoch(self, years: float):
        """星の位置を、今から years 年後（負なら前）にする。星はまっすぐ等速で動くとして計算する。"""
        self.epoch = float(years)
        self.pos_pc = self._pos0 + self.vel * self.epoch
        known = self._dist0 < UNKNOWN_DIST_PC
        dist = np.linalg.norm(self.pos_pc, axis=1)
        self.dist_pc = np.where(known, dist, self._dist0)
        self.dir = self.pos_pc / np.maximum(self.dist_pc, 1e-9)[:, None]
        # 近づけば明るく、遠ざかれば暗く
        self.mag = np.where(known, self._mag0 + 5 * np.log10(np.maximum(self.dist_pc, 1e-6) / np.maximum(self._dist0, 1e-6)),
                            self._mag0)

    def _match_line_stars(self):
        """星座線の端の点が、どの星か（近くのいちばん明るい星）を調べておく。"""
        n = min(self.count, 9100)                # 6.5等くらいまで
        dirs = self._pos0[:n] / np.maximum(self._dist0[:n], 1e-9)[:, None]
        out = []
        for c in self.constellations:
            pts = c.segments.reshape(-1, 3)
            if not len(pts):
                out.append(np.zeros(0, int))
                continue
            dots = pts @ dirs.T
            best = np.argmax(dots, axis=1)
            ok = dots[np.arange(len(pts)), best] > math.cos(math.radians(0.4))
            out.append(np.where(ok, best, -1))
        self._line_stars = out

    def segments_at_epoch(self, ci: int) -> np.ndarray:
        """その時代の星座線（星が動いたぶんだけ、線の端も動かす）。"""
        c = self.constellations[ci]
        if self.epoch == 0.0 or not len(c.segments):
            return c.segments
        if self._line_stars is None:
            self._match_line_stars()
        pts = c.segments.reshape(-1, 3).copy()
        idx = self._line_stars[ci]
        m = idx >= 0
        pts[m] = self.dir[idx[m]]
        return pts.reshape(-1, 2, 3)

    def vertex_data(self) -> np.ndarray:
        """GPU に送る頂点データ: 位置[AU](3), 等級(1), 太陽からの距離[AU](1), 色(3)"""
        pos_au = self.pos_pc * PC_AU
        dist_au = np.maximum(self.dist_pc * PC_AU, 1.0)
        return np.concatenate([pos_au, self.mag[:, None], dist_au[:, None], self.rgb], axis=1).astype(np.float32)

    def line_vertices(self) -> np.ndarray:
        segs = [self.segments_at_epoch(i).reshape(-1, 3) for i, c in enumerate(self.constellations) if len(c.segments)]
        return np.concatenate(segs).astype(np.float32)

    # ---------------------------------------------------------- 名前・情報

    def short_name(self, i: int) -> str:
        p = str(self.proper[i])
        if p:
            return p if EN_MODE else JA_NAMES.get(p, p)
        return self.designation(i)

    def designation(self, i: int) -> str:
        con = str(self.con[i])
        cname = self.con_names.get(con, con)
        b, f = str(self.bayer[i]), str(self.flam[i])
        if b and EN_MODE:
            return f"{greek(b)} {cname}"
        if b:
            return f"{cname}{greek(b)}星"
        if f and EN_MODE:
            return f"{f} {cname}"
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
        parts.append(f"{self.mag[i]:.2f} mag (from Earth)" if EN_MODE else f"{self.mag[i]:.2f} 等（地球から見た明るさ）")
        d = self.dist_pc[i]
        if d < UNKNOWN_DIST_PC:
            ly = d * PC_LY
            parts.append(f"距離 {ly:,.1f} 光年" if ly < 100 else f"距離 {ly:,.0f} 光年")
        else:
            parts.append("距離 不明")
        if self.spect[i]:
            parts.append(f"スペクトル型 {self.spect[i]}")
        return "　｜　".join(parts)
