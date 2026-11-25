"""実在の銀河のカタログ（OpenNGC から作った約1万個）。

1つの銀河を、円盤の面に置いた四角形（渦巻銀河などの円盤）と、
カメラの方を向いた四角形（楕円銀河・中心のふくらみ）で描く。
模様（渦巻きの腕など）はシェーダーで描くので、形は模式図。
"""

from __future__ import annotations

import math
from pathlib import Path

import numpy as np

from . import astro
from .galaxies import KPC_AU

DATA = Path(__file__).parent / "data" / "galaxies.npz"
MPC_AU = KPC_AU * 1000.0

KIND_JA = {0: "渦巻銀河", 1: "レンズ状銀河", 3: "楕円銀河", 4: "不規則銀河"}
COLORS = {0: (0.78, 0.84, 1.0), 1: (1.0, 0.90, 0.75), 3: (1.0, 0.86, 0.66), 4: (0.72, 0.82, 1.0)}
CORNERS = np.array([[-1, -1], [1, -1], [1, 1], [-1, -1], [1, 1], [-1, 1]], dtype=np.float32) * 1.4

# 頂点の並び: corner(2) center(3) ax1(3) ax2(3) mode(1) rgb(3) seed(1) flat(1) = 17
STRIDE = 17


class GalaxyCatalog:
    def __init__(self):
        d = np.load(DATA)
        self.ra, self.dec = d["ra"], d["dec"]
        self.mpc = d["mpc"].astype(np.float64)
        self.kind = d["kind"].astype(int)
        self.name = d["name"]
        self.messier = d["messier"]
        self.common = d["common"]
        n = len(self.ra)
        ra, dec = np.radians(self.ra), np.radians(self.dec)
        eq = np.stack([np.cos(dec) * np.cos(ra), np.cos(dec) * np.sin(ra), np.sin(dec)], axis=1)
        c, s = math.cos(astro.OBLIQUITY_J2000), math.sin(astro.OBLIQUITY_J2000)
        los = np.stack([eq[:, 0], c * eq[:, 1] + s * eq[:, 2], -s * eq[:, 1] + c * eq[:, 2]], axis=1)
        self.center = los * (self.mpc * MPC_AU)[:, None]
        # 見かけの長径（D25、分角）から半径 [AU]
        self.radius = np.tan(np.radians(d["maj"].astype(np.float64) / 60.0 / 2.0)) * self.mpc * MPC_AU
        self.radius_kly = self.radius / 63241.077 / 1000.0

        # 円盤の向き：位置角と、軸比から求めた傾き
        pole = np.array([0.0, s, c])          # 天の北極（黄道座標）
        east = np.cross(pole, los)
        east /= np.linalg.norm(east, axis=1)[:, None]
        north = np.cross(los, east)
        pa = np.radians(d["pa"].astype(np.float64))[:, None]
        major = np.cos(pa) * north + np.sin(pa) * east
        q = d["minr"].astype(np.float64)
        cos_i = np.sqrt(np.clip((q * q - 0.04) / 0.96, 0.0, 1.0))[:, None]
        sin_i = np.sqrt(1 - cos_i * cos_i)
        w = np.cross(los, major)
        normal = cos_i * los + sin_i * w
        second = np.cross(normal, major)
        self.major, self.second, self.q = major, second, q
        self.count = n

    def vertex_data(self) -> np.ndarray:
        rng = np.random.default_rng(7)
        quads = []
        r = self.radius[:, None]
        seed = rng.random(self.count) * 6.28
        for i_mode, sel in ((0, self.kind == 0), (1, self.kind == 1), (4, self.kind == 4)):
            quads.append(self._quads(sel, self.major * r, self.second * r, i_mode, seed, 1.0))
            if i_mode != 4:
                # 円盤銀河の中心のふくらみ（カメラを向く）
                quads.append(self._quads(sel, self.major * r * 0.22, self.second * r * 0.22, 2, seed,
                                         0.8))
        sel = self.kind == 3
        quads.append(self._quads(sel, self.major * r * 0.6, self.second * r * 0.6, 3, seed,
                                 np.maximum(self.q, 0.3)))
        return np.concatenate(quads).astype(np.float32)

    def _quads(self, sel, ax1, ax2, mode, seed, flat):
        idx = np.nonzero(sel)[0]
        m = len(idx)
        flat = np.broadcast_to(np.asarray(flat, dtype=np.float64), (self.count,))[idx]
        out = np.empty((m, 6, STRIDE), dtype=np.float64)
        out[:, :, 0:2] = CORNERS[None]
        out[:, :, 2:5] = self.center[idx, None, :]
        out[:, :, 5:8] = ax1[idx, None, :]
        out[:, :, 8:11] = ax2[idx, None, :]
        out[:, :, 11] = mode
        col = np.array(COLORS[3 if mode in (2, 3) else (1 if mode == 1 else 0 if mode == 0 else 4)])
        if mode == 2:
            col = np.array((1.0, 0.86, 0.62))
        out[:, :, 12:15] = col
        out[:, :, 15] = seed[idx, None]
        out[:, :, 16] = flat[:, None]
        return out.reshape(-1, STRIDE)

    def label(self, i: int) -> str:
        m = str(self.messier[i])
        if m:
            return f"M{m}"
        return str(self.common[i]) or str(self.name[i])

    def describe(self, i: int) -> str:
        ly = self.mpc[i] * 3.26156e6
        dist = f"{ly / 1e8:,.1f} 億光年" if ly >= 1e8 else f"{ly / 1e4:,.0f} 万光年"
        name = self.label(i)
        parts = [f"<b>{name}</b>"]
        if str(self.name[i]) != name:
            parts.append(str(self.name[i]))
        if self.common[i] and str(self.common[i]) != name:
            parts.append(str(self.common[i]))
        parts += [KIND_JA.get(int(self.kind[i]), "銀河"), f"距離 約{dist}",
                  f"直径 約{self.radius_kly[i] * 2 / 10:,.1f} 万光年", "※ OpenNGC、距離は後退速度から推定"]
        return "　｜　".join(parts)
