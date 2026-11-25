"""銀河（天の川銀河と近くの銀河）。

銀河は写真ではなく、粒子（点の集まり）で作った「模式図」として描く。
位置（赤経・赤緯）・距離・大きさ・円盤の傾きは、文献のおおよその値を使っている。
"""

from __future__ import annotations

import math
from dataclasses import dataclass

import numpy as np

from . import astro

KPC_AU = 2.06264806e8          # 1 キロパーセク [AU]
LY_AU = 63241.077              # 1 光年 [AU]
KPC_LY = 3261.56

# 天の川銀河の向き（J2000 赤道座標）
_GC_RA, _GC_DEC = 266.40500, -28.93617      # 銀河中心の方向
_NGP_RA, _NGP_DEC = 192.85948, 27.12825     # 銀河北極の方向
SUN_GC_KPC = 8.2                             # 太陽から銀河中心までの距離
SUN_Z_KPC = 0.02                             # 太陽は円盤面より少し北
SURFACE = 1.6                                # 銀河の表面の明るさ（見た目の調整用）


def _eq_vec(ra_deg, dec_deg):
    ra, dec = math.radians(ra_deg), math.radians(dec_deg)
    return np.array([math.cos(dec) * math.cos(ra), math.cos(dec) * math.sin(ra), math.sin(dec)])


def _ecl(ra_deg, dec_deg):
    return astro.equatorial_to_ecliptic(_eq_vec(ra_deg, dec_deg))


def galactic_frame() -> np.ndarray:
    """銀河座標の軸（X=銀河中心方向, Y=銀経90度, Z=銀河北極）を黄道座標で表した行列（列ベクトル）。"""
    x = _ecl(_GC_RA, _GC_DEC)
    z = _ecl(_NGP_RA, _NGP_DEC)
    z = z - x * np.dot(x, z)
    z /= np.linalg.norm(z)
    y = np.cross(z, x)
    return np.stack([x, y, z], axis=1)


@dataclass
class Galaxy:
    key: str
    name: str
    kind: str              # "milkyway" "spiral" "barred" "irregular" "elliptical" "lenticular"
    kind_ja: str
    ra: float              # 赤経 [度]
    dec: float             # 赤緯 [度]
    dist_kpc: float        # 距離
    radius_kpc: float      # 半径（見た目の大きさ）
    incl: float = 0.0      # 円盤の傾き [度]（0=正面向き、90=真横）
    pa: float = 0.0        # 長軸の位置角 [度]（北から東回り）
    count: int = 12000     # 粒子の数
    flat: float = 0.15     # 楕円銀河の扁平さ（短軸/長軸）
    in_menu: bool = True

    # 計算で埋めるもの
    center: np.ndarray | None = None     # 太陽中心・黄道座標 [AU]
    rot: np.ndarray | None = None        # 銀河の座標軸（列ベクトル）
    first: int = 0                       # 頂点バッファの中の位置
    n: int = 0
    k: float = 1.0                       # 明るさの係数


GALAXIES = [
    Galaxy("g:mw", "天の川銀河", "milkyway", "棒渦巻銀河（わたしたちの銀河）", _GC_RA, _GC_DEC,
           SUN_GC_KPC, 15.0, count=170000),
    Galaxy("g:lmc", "大マゼラン雲", "irregular", "不規則銀河（天の川銀河の伴銀河）", 80.894, -69.756,
           50.0, 5.0, incl=35, pa=170, count=14000),
    Galaxy("g:smc", "小マゼラン雲", "irregular", "不規則銀河（天の川銀河の伴銀河）", 13.187, -72.829,
           62.0, 2.8, incl=60, pa=45, count=7000),
    Galaxy("g:m31", "アンドロメダ銀河（M31）", "spiral", "渦巻銀河", 10.6847, 41.2690,
           765.0, 23.0, incl=77, pa=38, count=60000),
    Galaxy("g:m32", "M32", "elliptical", "楕円銀河（アンドロメダ銀河の伴銀河）", 10.6743, 40.8652,
           763.0, 1.0, count=3000, flat=0.75, in_menu=False),
    Galaxy("g:m110", "M110", "elliptical", "楕円銀河（アンドロメダ銀河の伴銀河）", 10.0921, 41.6853,
           820.0, 2.5, pa=170, count=4000, flat=0.5, in_menu=False),
    Galaxy("g:m33", "さんかく座銀河（M33）", "spiral", "渦巻銀河", 23.4621, 30.6599,
           840.0, 9.0, incl=55, pa=23, count=25000),
    Galaxy("g:m81", "M81（ボーデの銀河）", "spiral", "渦巻銀河", 148.8882, 69.0653,
           3600.0, 14.0, incl=59, pa=157, count=25000),
    Galaxy("g:m82", "M82（葉巻銀河）", "irregular", "スターバースト銀河", 148.9685, 69.6797,
           3500.0, 6.0, incl=80, pa=65, count=8000),
    Galaxy("g:cena", "ケンタウルス座A", "elliptical", "楕円銀河（電波銀河）", 201.3651, -43.0191,
           3800.0, 9.0, pa=35, count=12000, flat=0.8),
    Galaxy("g:m101", "回転花火銀河（M101）", "spiral", "渦巻銀河", 210.8023, 54.3489,
           6400.0, 26.0, incl=18, pa=40, count=25000),
    Galaxy("g:m51", "子持ち銀河（M51）", "spiral", "渦巻銀河", 202.4696, 47.1952,
           8600.0, 12.0, incl=22, pa=163, count=20000),
    Galaxy("g:m104", "ソンブレロ銀河（M104）", "lenticular", "渦巻銀河（ほぼ真横向き）", 189.9976, -11.6231,
           9600.0, 8.0, incl=84, pa=90, count=15000),
    Galaxy("g:m87", "M87（おとめ座A）", "elliptical", "巨大楕円銀河（中心に巨大ブラックホール）", 187.7059, 12.3911,
           16400.0, 20.0, count=20000, flat=0.85),
]

BY_KEY = {g.key: g for g in GALAXIES}


# ---------------------------------------------------------------- 向き

def _orientation(g: Galaxy) -> np.ndarray:
    """銀河の座標軸（x=長軸, z=円盤の法線）を黄道座標で表した行列。"""
    if g.kind == "milkyway":
        return galactic_frame()
    n = _ecl(g.ra, g.dec)                                  # 視線方向
    pole = astro.equatorial_to_ecliptic(np.array([0.0, 0.0, 1.0]))
    east = np.cross(pole, n)
    east /= np.linalg.norm(east)
    north = np.cross(n, east)
    pa, inc = math.radians(g.pa), math.radians(g.incl)
    major = math.cos(pa) * north + math.sin(pa) * east
    w = np.cross(n, major)
    normal = math.cos(inc) * n + math.sin(inc) * w
    second = np.cross(normal, major)
    return np.stack([major, second, normal], axis=1)


def _place(g: Galaxy):
    g.rot = _orientation(g)
    if g.kind == "milkyway":
        # 銀河中心 = 太陽から銀河中心方向へ 8.2 kpc、少し南
        g.center = (g.rot[:, 0] * SUN_GC_KPC - g.rot[:, 2] * SUN_Z_KPC) * KPC_AU
    else:
        g.center = _ecl(g.ra, g.dec) * g.dist_kpc * KPC_AU


# ---------------------------------------------------------------- 粒子

def _spiral_arms(rng, n, r_min, r_max, n_arms, pitch_deg, phase, width, thick, clockwise=False):
    k = 1.0 / math.tan(math.radians(pitch_deg))
    arm = rng.integers(0, n_arms, n)
    r = r_min * np.exp(rng.random(n) * math.log(r_max / r_min))
    theta = np.log(r / r_min) * k + arm * (2 * math.pi / n_arms) + phase
    if clockwise:
        theta = -theta
    x = r * np.cos(theta)
    y = r * np.sin(theta)
    spread = width * (0.6 + 0.4 * r / r_max)
    x += rng.normal(0, 1, n) * spread
    y += rng.normal(0, 1, n) * spread
    z = rng.normal(0, 1, n) * thick
    return np.stack([x, y, z], axis=1)


def _exp_disk(rng, n, scale, thick, r_max):
    r = rng.gamma(2.0, scale, n)
    over = r > r_max
    r[over] = rng.random(int(over.sum())) * r_max     # 外にはみ出した分は内側に配り直す
    t = rng.random(n) * 2 * math.pi
    return np.stack([r * np.cos(t), r * np.sin(t), rng.normal(0, 1, n) * thick], axis=1)


def _ellipsoid(rng, n, a, b, c):
    p = rng.normal(0, 1, (n, 3)) * np.array([a, b, c])
    return p


def _colors(n, rgb, jitter, rng):
    base = np.tile(np.array(rgb, dtype=np.float64), (n, 1))
    return np.clip(base * (1 + rng.normal(0, jitter, (n, 1))), 0, 1)


def _milky_way(rng, n):
    """天の川銀河。X=銀河中心→太陽の逆向き（太陽は -X 側）、時計回りに回転（北から見て）。"""
    n_bulge, n_arm, n_disk = int(n * 0.16), int(n * 0.54), n - int(n * 0.16) - int(n * 0.54)
    parts, cols, sizes, weights = [], [], [], []
    # 棒（バー）とバルジ: 太陽から見て銀経の正の側に近い端がある
    bar = _ellipsoid(rng, n_bulge, 1.7, 0.6, 0.45)
    phi = math.radians(180 - 27)
    c, s = math.cos(phi), math.sin(phi)
    bar = bar @ np.array([[c, s, 0], [-s, c, 0], [0, 0, 1]])
    parts.append(bar)
    cols.append(_colors(n_bulge, (1.0, 0.82, 0.55), 0.08, rng))
    sizes.append(np.full(n_bulge, 0.25))
    weights.append(np.full(n_bulge, 1.3))
    # 4本の腕（ピッチ角12度）。太陽の位置（θ=180度）で半径 6.6kpc（いて腕）と 9.2kpc（ペルセウス腕）
    k = math.tan(math.radians(12.0))
    r_ref = 6.6
    phase = math.pi - math.log(r_ref / 3.0) / k
    arms = _spiral_arms(rng, n_arm, 3.0, 16.0, 4, 12.0, phase, 0.45, 0.10)
    parts.append(arms)
    ac = _colors(n_arm, (0.62, 0.74, 1.0), 0.1, rng)
    pink = rng.random(n_arm) < 0.035
    ac[pink] = (1.0, 0.45, 0.6)
    cols.append(ac)
    sizes.append(np.where(pink, 0.12, 0.2))
    weights.append(np.where(pink, 2.5, 1.0))
    # 円盤全体の淡い光
    disk = _exp_disk(rng, n_disk, 2.6, 0.25, 18.0)
    parts.append(disk)
    cols.append(_colors(n_disk, (1.0, 0.9, 0.75), 0.08, rng))
    sizes.append(np.full(n_disk, 0.45))
    weights.append(np.full(n_disk, 0.6))
    return np.concatenate(parts), np.concatenate(cols), np.concatenate(sizes), np.concatenate(weights)


def _generic(g: Galaxy, rng):
    n, R = g.count, g.radius_kpc
    if g.kind in ("spiral", "barred"):
        nb, na = int(n * 0.2), int(n * 0.5)
        nd = n - nb - na
        p = [_ellipsoid(rng, nb, R * 0.12, R * 0.12, R * 0.08),
             _spiral_arms(rng, na, R * 0.15, R, 2, 15.0, rng.random() * 6.28, R * 0.035, R * 0.01),
             _exp_disk(rng, nd, R * 0.22, R * 0.015, R * 1.1)]
        c = [_colors(nb, (1.0, 0.85, 0.6), 0.08, rng), _colors(na, (0.65, 0.76, 1.0), 0.1, rng),
             _colors(nd, (1.0, 0.92, 0.8), 0.08, rng)]
        s = [np.full(nb, R * 0.03), np.full(na, R * 0.02), np.full(nd, R * 0.04)]
        w = [np.full(nb, 1.4), np.full(na, 1.0), np.full(nd, 0.6)]
    elif g.kind == "lenticular":
        nb = int(n * 0.45)
        nd = n - nb
        p = [_ellipsoid(rng, nb, R * 0.28, R * 0.28, R * 0.2), _exp_disk(rng, nd, R * 0.3, R * 0.02, R)]
        c = [_colors(nb, (1.0, 0.88, 0.65), 0.06, rng), _colors(nd, (0.95, 0.88, 0.75), 0.06, rng)]
        s = [np.full(nb, R * 0.05), np.full(nd, R * 0.03)]
        w = [np.full(nb, 1.2), np.full(nd, 0.8)]
    elif g.kind == "irregular":
        blobs = rng.normal(0, 1, (7, 3)) * np.array([R * 0.4, R * 0.25, R * 0.08])
        idx = rng.integers(0, len(blobs), n)
        pts = blobs[idx] + rng.normal(0, 1, (n, 3)) * np.array([R * 0.22, R * 0.18, R * 0.08])
        if g.key == "g:lmc":   # 大マゼラン雲の棒状部分
            nbar = n // 4
            pts[:nbar] = rng.normal(0, 1, (nbar, 3)) * np.array([R * 0.35, R * 0.08, R * 0.05])
        p = [pts]
        cc = _colors(n, (0.75, 0.82, 1.0), 0.12, rng)
        pink = rng.random(n) < 0.04
        cc[pink] = (1.0, 0.45, 0.6)
        c = [cc]
        s = [np.full(n, R * 0.05)]
        w = [np.where(pink, 2.0, 1.0)]
    else:   # elliptical
        p = [_ellipsoid(rng, n, R * 0.35, R * 0.35 * max(g.flat, 0.3) ** 0.5, R * 0.35 * g.flat)]
        c = [_colors(n, (1.0, 0.86, 0.66), 0.05, rng)]
        s = [np.full(n, R * 0.06)]
        w = [np.full(n, 1.0)]
    return np.concatenate(p), np.concatenate(c), np.concatenate(s), np.concatenate(w)


def build() -> np.ndarray:
    """全銀河の粒子をまとめた頂点データ: 局所座標[kpc](3), 大きさ[kpc](1), 明るさ(1), 色(3)"""
    rng = np.random.default_rng(20261126)
    chunks = []
    first = 0
    for g in GALAXIES:
        _place(g)
        if g.kind == "milkyway":
            pos, col, size, wt = _milky_way(rng, g.count)
        else:
            pos, col, size, wt = _generic(g, rng)
        data = np.concatenate([pos, size[:, None], wt[:, None], col], axis=1).astype(np.float32)
        g.first, g.n = first, len(data)
        # 銀河をどの距離から見ても、表面の明るさがほぼ同じになるようにする
        g.k = SURFACE / float(np.sum((size / g.radius_kpc) ** 2 * wt))
        first += len(data)
        chunks.append(data)
    return np.concatenate(chunks)


def describe(g: Galaxy) -> str:
    def ly(kpc):
        v = kpc * KPC_LY
        if v >= 1e8:
            return f"{v / 1e8:,.1f} 億光年"
        if v >= 1e4:
            return f"{v / 1e4:,.0f} 万光年" if v >= 1e5 else f"{v / 1e4:,.1f} 万光年"
        return f"{v:,.0f} 光年"
    parts = [f"<b>{g.name}</b>", g.kind_ja]
    if g.kind == "milkyway":
        parts.append(f"太陽から中心まで 約{ly(g.dist_kpc)}")
    else:
        parts.append(f"距離 約{ly(g.dist_kpc)}")
    parts.append(f"直径 約{ly(g.radius_kpc * 2)}")
    parts.append("※ 形は模式図")
    return "　｜　".join(parts)
