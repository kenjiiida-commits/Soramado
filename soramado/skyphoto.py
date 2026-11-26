"""天の川の全天写真（Gaia DR2 の星の光の地図）をダウンロードして、全天の1枚の画像にする。

Gaia 衛星が測った約17億個の星の明るさと色から、CDS が作った全天のカラー画像
（HiPS「Gaia DR2 color flux map」）を使う。タイルを集めて、赤経・赤緯の正距円筒図
（横 = 赤経 0〜360°、縦 = 赤緯 +90〜-90°）に並べ直し、見やすく整えて保存する。
"""

from __future__ import annotations

import math
import threading
from pathlib import Path

import numpy as np

from . import hips
from .cosmos import data_dir
from .dsoimages import _decode, _fetch, save_jpeg  # noqa: F401

BASES = ["https://alasky.cds.unistra.fr/ancillary/GaiaDR2/color-Rp-G-Bp-flux-map"]
ORDER = 3                      # HiPS に必ずある階層。Allsky.jpg に全天が64画素のタイルでまとまっている
W, H = 4096, 2048              # 保存する画像の大きさ（1画素 約5.3′）
CREDIT = "天の川: ESA/Gaia/DPAC（Gaia DR2）、CDS の HiPS「Gaia DR2 color flux map」（CC BY-SA 3.0 IGO）"
try:
    from .i18n import EN_MODE
    if EN_MODE:
        CREDIT = "Milky Way: ESA/Gaia/DPAC (Gaia DR2), CDS HiPS \"Gaia DR2 color flux map\" (CC BY-SA 3.0 IGO)"
except Exception:  # noqa: BLE001
    pass


def path() -> Path:
    return data_dir() / "milkyway_gaia.jpg"


def raw_path() -> Path:
    return data_dir() / "milkyway_gaia_allsky.jpg"


def _blur(a: np.ndarray, r: int) -> np.ndarray:
    """箱型のぼかし（横はつながっているので回り込む）。"""
    for ax in (0, 1):
        mode = "wrap" if ax == 1 else "edge"
        pad = [(0, 0)] * a.ndim
        pad[ax] = (r + 1, r)
        c = np.cumsum(np.pad(a, pad, mode=mode), axis=ax)
        n = c.shape[ax]
        a = (np.take(c, np.arange(2 * r + 1, n), axis=ax) - np.take(c, np.arange(0, n - 2 * r - 1), axis=ax)) / (2 * r + 1)
    return a


def _pole_smooth(a: np.ndarray) -> np.ndarray:
    """正距円筒図は極に近いほど横に引き伸ばされるので、そのぶん横（赤経の方向）にならす。
    ならさないと、星のつぶつぶが天の北極・南極から放射状の筋に見える。"""
    h, w = a.shape[:2]
    out = a.copy()
    for i in range(h):
        dec = 90.0 - (i + 0.5) / h * 180.0
        stretch = 1.0 / max(math.cos(math.radians(dec)), 1e-3)
        r = int(min(w // 2 - 1, 8.0 * (stretch - 1.0)))
        if r < 2:
            continue
        row = a[i]
        c = np.cumsum(np.concatenate([row[-r - 1:], row, row[:r]]), axis=0)
        out[i] = (c[2 * r + 1:] - c[:-2 * r - 1]) / (2 * r + 1)
    return out


def process(img: np.ndarray) -> np.ndarray:
    """星の数のつぶつぶを少しならし、色を落ち着かせ、暗いところを沈める。"""
    a = img.astype(np.float32) / 255.0
    a = _blur(_blur(a, 2), 2)
    a = _pole_smooth(a)
    # 元の地図にある緑のしみ（データのむら）を消す: 緑が赤と青の平均より強く出ないように
    a[..., 1] = np.minimum(a[..., 1], (a[..., 0] + a[..., 2]) * 0.5 * 1.08 + 0.01)
    lum = a.mean(axis=-1, keepdims=True)
    a = lum + (a - lum) * 0.55
    a = np.clip((a - 0.36) / 0.64, 0.0, 1.0) ** 2.0
    return (a * 255.0 + 0.5).astype(np.uint8)


def sample_rows(get_tile, order: int, tile_px: int, rows: slice) -> np.ndarray:
    """正距円筒図の一部の行を、タイルから並べ直す。get_tile(番号) → タイルの画像。"""
    bits = int(np.log2(tile_px))
    r0, r1 = rows.start, rows.stop
    dec = 90.0 - (np.arange(r0, r1) + 0.5) / H * 180.0
    ra = (np.arange(W) + 0.5) / W * 360.0
    RA, DEC = np.meshgrid(ra, dec)
    face, ix, iy = hips.ang2xyf(order + bits, RA, DEC)
    tiles = hips.nest_index(order, face, ix >> bits, iy >> bits)
    row = ix & (tile_px - 1)
    col = iy & (tile_px - 1)
    out = np.zeros(RA.shape + (3,), np.uint8)
    for t in np.unique(tiles):
        m = tiles == t
        img = get_tile(int(t))
        if img is not None:
            out[m] = img[row[m], col[m], :3]
    return out


def build(get_tile, order: int, tile_px: int) -> np.ndarray:
    out = np.zeros((H, W, 3), np.uint8)
    step = 128
    for r in range(0, H, step):
        out[r:r + step] = sample_rows(get_tile, order, tile_px, slice(r, min(H, r + step)))
    return out


def allsky_getter(allsky: np.ndarray, tile_px: int = 64):
    """HiPS の Allsky.jpg（小さなタイルを横27枚ずつ並べた1枚）から、タイルを切り出す関数。"""
    per_row = allsky.shape[1] // tile_px

    def get(t):
        y, x = (t // per_row) * tile_px, (t % per_row) * tile_px
        return allsky[y:y + tile_px, x:x + tile_px]
    return get


class SkyDownloader:
    """別スレッドで、全天の画像（Allsky.jpg）をダウンロードして天の川の全天画像を作る。"""

    def __init__(self):
        self.done = False
        self.ok = False
        self.message = ""
        self.total = 1
        self.finished = 0
        self.bytes = 0
        self._cancel = threading.Event()
        self._thread = threading.Thread(target=self._run, daemon=True)

    def start(self):
        self._thread.start()

    def cancel(self):
        self._cancel.set()

    def _run(self):
        last = None
        for base in BASES:
            if self._cancel.is_set():
                break
            try:
                data = _fetch(f"{base}/Norder{ORDER}/Allsky.jpg", timeout=120)
                self.bytes = len(data)
                self.finished = 1
                img = _decode(data)
                if img is None:
                    raise RuntimeError("画像を読めませんでした")
                raw_path().parent.mkdir(parents=True, exist_ok=True)
                raw_path().write_bytes(data)      # 元の画像も残す（整え方を変えたとき作り直せるように）
                tile_px = img.shape[1] // 27
                if self._cancel.is_set():
                    break
                save_jpeg(process(build(allsky_getter(img, tile_px), ORDER, tile_px)), path())
                self.ok = True
                break
            except Exception as exc:  # noqa: BLE001
                last = exc
        if self._cancel.is_set():
            self.message = "キャンセルしました"
        elif not self.ok and last:
            self.message = str(last)
        self.done = True
