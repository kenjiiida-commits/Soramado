"""天の川銀河の中の星雲・星団（メシエ天体などの有名なもの）。

位置・見かけの大きさ・種類は OpenNGC（CC BY-SA 4.0）、距離は代表的な値の目安（tools/make_nebula_data.py）。
形は模式図：星団は星の粒、星雲はぼんやり光るガスの粒を、見かけの大きさと向きに合わせて並べる。
"""

from __future__ import annotations

import json
import math
from dataclasses import dataclass
from pathlib import Path

import numpy as np

from . import astro
from .i18n import EN_MODE

LY_AU = 63241.077
ARCMIN = math.pi / (180 * 60)

TYPE_JA = {
    "ocl": "散開星団",
    "gcl": "球状星団",
    "emn": "散光星雲（輝線星雲）",
    "rfn": "反射星雲",
    "pn": "惑星状星雲",
    "snr": "超新星残がい",
}
TYPE_NOTE = {
    "ocl": "同じガスの雲から生まれた、数十〜数千個の若い星の集まり。時間がたつとばらばらになっていく。",
    "gcl": "数万〜数百万個の年老いた星が、ボールのように集まった星団。天の川銀河のまわりに約150個ある。"
           "年齢は100億年以上で、銀河とほぼ同じくらい古い。",
    "emn": "生まれたばかりの重い星の紫外線を受けて、水素ガスが赤く光っている星雲。中では今も星が生まれている。",
    "rfn": "近くの星の光を、ちりが反射して青く光る星雲。",
    "pn": "太陽くらいの重さの星が、一生の最後に外側のガスを放ってできた星雲。中心には白色矮星が残る。"
          "望遠鏡で惑星のように丸く見えたので、この名前が付いた（惑星とは関係ない）。",
    "snr": "重い星が一生の最後に超新星爆発を起こし、吹き飛んだガスが広がっているもの。",
}


@dataclass
class Nebula:
    id: str
    name: str
    m: int
    type: str
    ra: float
    dec: float
    maj: float          # 見かけの長径 [分角]
    min: float
    pa: float
    vmag: float | None
    ly: float
    note: str
    const: str
    name_en: str = ""
    pos: np.ndarray = None       # 太陽中心・黄道座標 [AU]
    radius_au: float = 0.0       # 実際の大きさ（半径）[AU]
    axes: tuple = None           # 見かけの形に合わせた軸（長軸・短軸・視線）

    @property
    def radius_ly(self) -> float:
        return self.radius_au / LY_AU


def _load() -> list[Nebula]:
    path = Path(__file__).parent / "data" / "nebulae.json"
    if not path.is_file():
        return []
    out = []
    for d in json.loads(path.read_text(encoding="utf-8")):
        n = Nebula(**d)
        if EN_MODE and n.name_en:
            n.name = n.name_en
        ra, dec = math.radians(n.ra), math.radians(n.dec)
        u_eq = np.array([math.cos(dec) * math.cos(ra), math.cos(dec) * math.sin(ra), math.sin(dec)])
        east_eq = np.array([-math.sin(ra), math.cos(ra), 0.0])
        north_eq = np.cross(u_eq, east_eq)
        pa = math.radians(n.pa)
        major_eq = north_eq * math.cos(pa) + east_eq * math.sin(pa)
        minor_eq = np.cross(u_eq, major_eq)
        conv = astro.equatorial_to_ecliptic
        n.pos = conv(u_eq) * n.ly * LY_AU
        n.radius_au = n.ly * LY_AU * math.tan(n.maj * ARCMIN / 2)
        n.axes = (conv(major_eq), conv(minor_eq), conv(u_eq))
        out.append(n)
    return out


NEBULAE = _load()


def vertex_data(n: Nebula) -> np.ndarray:
    """模式図の粒（中心からの位置[AU] xyz、色 rgb、大きさ[AU]。大きさ 0 は星）。"""
    rng = np.random.default_rng(sum(map(ord, n.id)) * 7919)   # いつも同じ形になるように
    R = n.radius_au
    q = max(0.2, n.min / max(n.maj, 1e-6))          # 見かけの扁平さ
    a1, a2, a3 = n.axes
    depth = (1 + q) / 2

    def place(xyz):
        return xyz[:, :1] * a1 * R + xyz[:, 1:2] * a2 * R * q + xyz[:, 2:3] * a3 * R * depth

    parts = []

    def add(xyz, col, size):
        col = np.broadcast_to(np.asarray(col, np.float32), (len(xyz), 3)) if np.ndim(col) == 1 else col
        size = np.broadcast_to(np.asarray(size, np.float32), (len(xyz),)) if np.ndim(size) == 0 else size
        parts.append(np.column_stack([place(xyz), col, size]))

    if n.type == "ocl":
        k = 220
        xyz = rng.normal(0, 0.45, (k, 3))
        temp = rng.random(k)
        col = np.where(temp[:, None] < 0.75, [0.75, 0.85, 1.0], [1.0, 0.85, 0.6]) * rng.uniform(0.5, 1.2, (k, 1))
        add(xyz, col, 0.0)
        add(rng.normal(0, 0.4, (6, 3)), [0.012, 0.015, 0.025], R * 0.5)         # 星の光がにじんだもや
    elif n.type == "gcl":
        k = 900
        u = rng.uniform(0.0, 0.97, k)
        r = 0.3 * np.sqrt(u ** (2 / 3) / (1 - u ** (2 / 3)))                  # プラマー分布
        d = rng.normal(0, 1, (k, 3))
        d /= np.linalg.norm(d, axis=1, keepdims=True)
        xyz = d * np.minimum(r, 1.3)[:, None]
        col = np.array([1.0, 0.85, 0.6]) * rng.uniform(0.25, 1.0, (k, 1))
        add(xyz, col, 0.0)
        add(np.zeros((3, 3)), [0.05, 0.04, 0.025], R * np.array([0.2, 0.35, 0.6]))  # 中心の明るいところ
    elif n.type in ("emn", "rfn"):
        base = np.array([1.0, 0.28, 0.38]) if n.type == "emn" else np.array([0.35, 0.5, 1.0])
        clumps = rng.normal(0, 0.45, (14, 3))
        k = 320
        c = clumps[rng.integers(0, len(clumps), k)]
        xyz = c + rng.normal(0, 0.18, (k, 3))
        mixc = rng.random((k, 1))
        alt = np.array([1.0, 0.55, 0.55]) if n.type == "emn" else np.array([0.6, 0.7, 1.0])
        col = (base * (1 - mixc) + alt * mixc) * rng.uniform(0.04, 0.10, (k, 1))
        if n.type == "emn":
            core = np.linalg.norm(xyz, axis=1) < 0.25          # 中心近くは酸素の光で青緑がかる
            col[core] = col[core] * 0.5 + np.array([0.20, 0.45, 0.42]) * 0.08
        add(xyz, col, R * rng.uniform(0.12, 0.3, k))
        ks = 25
        add(rng.normal(0, 0.3, (ks, 3)), np.array([0.75, 0.85, 1.0]) * rng.uniform(0.4, 1.0, (ks, 1)), 0.0)
    elif n.type == "pn":
        k = 260
        d = rng.normal(0, 1, (k, 3))
        d /= np.linalg.norm(d, axis=1, keepdims=True)
        rad = rng.normal(0.75, 0.08, (k, 1))
        xyz = d * rad
        outer = rng.random(k) < 0.3
        col = np.where(outer[:, None], [1.0, 0.3, 0.3], [0.25, 0.95, 0.75]) * 0.09
        add(xyz, col, R * rng.uniform(0.18, 0.32, k))
        add(np.zeros((1, 3)), [0.8, 0.9, 1.0], 0.0)                              # 中心の白色矮星
    else:  # snr
        k = 360
        starts = rng.normal(0, 1, (36, 3))
        starts /= np.linalg.norm(starts, axis=1, keepdims=True)
        pts = []
        for s in starts:                                  # 殻の上をうねる糸のような筋
            p = s.copy()
            step = rng.normal(0, 1, 3)
            for _ in range(k // 36):
                step = step * 0.8 + rng.normal(0, 0.6, 3)
                p = p + 0.06 * step
                p = p / np.linalg.norm(p) * rng.normal(0.85, 0.05)
                pts.append(p.copy())
        xyz = np.array(pts)
        blue = rng.random(len(xyz)) < 0.3
        col = np.where(blue[:, None], [0.35, 0.75, 0.95], [1.0, 0.45, 0.3]) * 0.10
        add(xyz, col, R * rng.uniform(0.05, 0.11, len(xyz)))
        if n.id == "NGC1952":                             # かに星雲の中心の青白い光（シンクロトロン放射）
            add(rng.normal(0, 0.25, (20, 3)), [0.10, 0.14, 0.22], R * 0.35)
    return np.concatenate(parts).astype(np.float32)


TYPE_EN = {"ocl": "Open cluster", "gcl": "Globular cluster", "emn": "Emission nebula", "rfn": "Reflection nebula",
           "pn": "Planetary nebula", "snr": "Supernova remnant"}
if EN_MODE:
    TYPE_JA = TYPE_EN


def describe(n: Nebula) -> list[str]:
    out = [TYPE_JA[n.type], f"距離 約{n.ly:,.0f} 光年"]
    size = n.radius_ly * 2
    out.append(f"大きさ 約{size:,.1f} 光年" if size < 10 else f"大きさ 約{size:,.0f} 光年")
    out.append(f"見かけの大きさ {n.maj:.0f}′" if n.maj >= 2 else f"見かけの大きさ {n.maj * 60:.0f}″")
    if n.vmag:
        out.append(f"明るさ {n.vmag:.1f} 等")
    return out
