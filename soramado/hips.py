"""HiPS（全天をタイルに分けた画像）から、天体のまわりの写真を切り出す。

HiPS は全天を HEALPix（NESTED）の区画に分け、区画ごとに 512×512 の JPEG タイルにしたもの。
ここでは、写真の各画素の赤経・赤緯から、どのタイルのどの画素かを計算して並べ直す
（接平面 TAN 投影、北が上・東が左）。
"""

from __future__ import annotations

import math

import numpy as np

TILE = 512                     # タイル1辺の画素数
TILE_BITS = 9                  # 2**9 = 512
MAX_ORDER = 9                  # DSS2 color のいちばん細かいタイルの階層

# DSS2 color（同じものを置いているサーバー。上から順に試す）
SERVERS = [
    "https://cdn.skies.esac.esa.int/DSSColor",
    "https://alasky.cds.unistra.fr/DSS/DSSColor",
]


def _spread_bits(v: np.ndarray) -> np.ndarray:
    """整数のビットを1つおきに広げる（xyf → NESTED 番号用）。"""
    v = v.astype(np.int64)
    out = np.zeros_like(v)
    for i in range(30):
        out |= ((v >> i) & 1) << (2 * i)
    return out


def ang2xyf(order: int, ra_deg, dec_deg):
    """赤経・赤緯 → HEALPix（nside = 2**order）の面番号 face と面の中の座標 ix, iy。"""
    nside = 1 << order
    phi = np.radians(np.asarray(ra_deg, dtype=np.float64)) % (2 * math.pi)
    z = np.sin(np.radians(np.asarray(dec_deg, dtype=np.float64)))
    za = np.abs(z)
    tt = (phi / (0.5 * math.pi)) % 4.0
    face = np.zeros(z.shape, np.int64)
    ix = np.zeros(z.shape, np.int64)
    iy = np.zeros(z.shape, np.int64)

    eq = za <= 2.0 / 3.0
    # 赤道の帯
    t1 = nside * (0.5 + tt[eq])
    t2 = nside * (z[eq] * 0.75)
    jp = (t1 - t2).astype(np.int64)
    jm = (t1 + t2).astype(np.int64)
    ifp = jp >> order
    ifm = jm >> order
    f = np.where(ifp == ifm, ifp | 4, np.where(ifp < ifm, ifp, ifm + 8))
    face[eq] = f
    ix[eq] = jm & (nside - 1)
    iy[eq] = nside - (jp & (nside - 1)) - 1

    po = ~eq
    # 極の近く
    ntt = np.minimum(3, tt[po].astype(np.int64))
    tp = tt[po] - ntt
    tmp = nside * np.sqrt(3.0 * (1.0 - za[po]))
    jp = np.minimum((tp * tmp).astype(np.int64), nside - 1)
    jm = np.minimum(((1.0 - tp) * tmp).astype(np.int64), nside - 1)
    north = z[po] >= 0
    face[po] = np.where(north, ntt, ntt + 8)
    ix[po] = np.where(north, nside - jm - 1, jp)
    iy[po] = np.where(north, nside - jp - 1, jm)
    return face, ix, iy


def nest_index(order: int, face, ix, iy):
    return (np.asarray(face, np.int64) << (2 * order)) + _spread_bits(ix) + (_spread_bits(iy) << 1)


def ang2pix_nest(order: int, ra_deg, dec_deg):
    face, ix, iy = ang2xyf(order, ra_deg, dec_deg)
    return nest_index(order, face, ix, iy)


def tile_url(base: str, order: int, ipix: int) -> str:
    return f"{base}/Norder{order}/Dir{(ipix // 10000) * 10000}/Npix{ipix}.jpg"


def tan_grid(ra0: float, dec0: float, fov_deg: float, size: int):
    """接平面（TAN）投影の画像の各画素の赤経・赤緯。北が上、東が左。"""
    half = math.tan(math.radians(fov_deg) / 2)
    c = (np.arange(size) + 0.5) / size * 2 - 1
    xi = -c[None, :] * half                 # 東が左なので、右へ行くほど西
    eta = -c[:, None] * half                # 上が北
    xi, eta = np.broadcast_arrays(xi, eta)
    a0, d0 = math.radians(ra0), math.radians(dec0)
    den = math.cos(d0) - eta * math.sin(d0)
    ra = a0 + np.arctan2(xi, den)
    dec = np.arctan2(math.sin(d0) + eta * math.cos(d0), np.hypot(xi, den))
    return np.degrees(ra) % 360.0, np.degrees(dec)


def choose_order(fov_deg: float, size: int) -> int:
    """写真の1画素の大きさに合うタイルの階層。"""
    want = fov_deg / size                                   # 1画素 [度]
    for k in range(0, MAX_ORDER + 1):
        px = math.degrees(math.sqrt(4 * math.pi / 12)) / (1 << (k + TILE_BITS))
        if px <= want * 1.2:
            return k
    return MAX_ORDER


def plan(ra0: float, dec0: float, fov_deg: float, size: int):
    """切り出しに要るタイルの階層と番号の一覧、各画素の (タイル番号, 行, 列)。"""
    k = choose_order(fov_deg, size)
    ra, dec = tan_grid(ra0, dec0, fov_deg, size)
    K = k + TILE_BITS
    face, ix, iy = ang2xyf(K, ra, dec)
    # タイルの番号は、面の中の座標の上位ビットから
    tix, tiy = ix >> TILE_BITS, iy >> TILE_BITS
    tiles = nest_index(k, face, tix, tiy)
    # タイルの JPEG の中では、行 = ix の下位ビット、列 = iy の下位ビット
    row = ix & (TILE - 1)
    col = iy & (TILE - 1)
    return k, tiles, row, col


def assemble(tiles_img: dict, tiles, row, col) -> np.ndarray:
    """タイルの画像（番号 → H×W×3 の配列）から、切り出し画像を組み立てる。"""
    out = np.zeros(tiles.shape + (3,), np.uint8)
    for t, img in tiles_img.items():
        m = tiles == t
        if img is not None and m.any():
            out[m] = img[row[m], col[m], :3]
    return out
