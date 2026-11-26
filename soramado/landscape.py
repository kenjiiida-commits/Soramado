"""地上の風景（地平線の山・街・海・森、または自分の360°写真）。

風景は、全天を横 = 方位（左はしが北、右へ東・南・西）、縦 = 高度（上が天頂 +90°、下が -90°）
にした正距円筒図の画像として持つ。空のところは透明。
組み込みの風景は numpy で作る（街の窓の明かりは、夜だけ光る「発光」の画像に分ける）。
"""

from __future__ import annotations

import math

import numpy as np

W, H = 4096, 2048
PRESETS = [("none", "なし（平らな地面）", "None (flat ground)"), ("mountains", "山なみ", "Mountains"),
           ("city", "街（ビル）", "City"), ("sea", "海辺", "Seaside"), ("forest", "森", "Forest")]


class Landscape:
    def __init__(self, rgba: np.ndarray, emit: np.ndarray | None = None, name: str = ""):
        self.rgba = rgba                       # H×W×4 uint8
        self.emit = emit                       # H×W×3 uint8（夜に光るところ）または None
        self.name = name
        # 方位ごとの、風景のいちばん高いところの高度 [度]（星や名前を隠すのに使う）
        h, w = rgba.shape[:2]
        solid = rgba[..., 3] > 128
        top = np.where(solid.any(axis=0), solid.argmax(axis=0), h)
        self.profile = 90.0 - (top + 0.5) / h * 180.0          # 列ごと
        self.profile[~solid.any(axis=0)] = -90.0

    def height_at(self, az_deg: float) -> float:
        w = len(self.profile)
        return float(self.profile[int((az_deg % 360.0) / 360.0 * w) % w])


def _rows(alt_deg):
    return int(round((90.0 - alt_deg) / 180.0 * H))


def _ridge(rng, base, amp, octaves=6, rough=0.55, w=W):
    """方位にそってなめらかに上下する、山の稜線の高さ [度]。端と端がつながる。"""
    x = np.arange(w) / w * 2 * np.pi
    h = np.zeros(w)
    a = amp
    for o in range(octaves):
        k = 2 ** o + rng.integers(0, 2)
        h += a * np.sin(k * x + rng.uniform(0, 2 * np.pi)) * rng.uniform(0.6, 1.0)
        h += a * 0.5 * np.sin((k + 1) * x + rng.uniform(0, 2 * np.pi))
        a *= rough
    return base + h


def _fill_below(img, heights, color, noise=0.04, rng=None, ground_alt=-2.0):
    """方位ごとに、その高さより下を色でぬる（上から順に重ねると、手前のものが上に来る）。"""
    rows = ((90.0 - heights) / 180.0 * H).astype(int)
    bottom = _rows(ground_alt)
    yy = np.arange(H)[:, None]
    mask = (yy >= rows[None, :]) & (yy < bottom)
    col = np.array(color, np.float32)
    if rng is not None and noise > 0:
        n = rng.normal(0, noise, (H, W, 1)).astype(np.float32)
        tex = np.clip(col[None, None, :] * (1 + n), 0, 1)
        img[mask, :3] = tex[mask]
    else:
        img[mask, :3] = col
    img[mask, 3] = 1.0
    return mask


def _base():
    return np.zeros((H, W, 4), np.float32)


def make_mountains(seed=3):
    rng = np.random.default_rng(seed)
    img = _base()
    far = np.maximum(_ridge(rng, 3.0, 2.2, rough=0.6), 0.3)
    mid = np.maximum(_ridge(rng, 2.0, 1.8, rough=0.55), 0.2)
    near = np.maximum(_ridge(rng, 0.8, 1.2, rough=0.5), 0.1)
    _fill_below(img, far, (0.42, 0.50, 0.62), 0.03, rng)           # 遠い山は青っぽく明るい
    _fill_below(img, mid, (0.27, 0.34, 0.38), 0.04, rng)
    _fill_below(img, near, (0.14, 0.20, 0.13), 0.06, rng)          # 近くの山は緑で暗い
    return img, None


def make_forest(seed=5):
    rng = np.random.default_rng(seed)
    img = _base()
    hill = np.maximum(_ridge(rng, 0.6, 0.6, rough=0.5), 0.0)
    _fill_below(img, hill, (0.12, 0.16, 0.10), 0.05, rng)
    # 針葉樹の三角形をたくさん並べる（層ごとに、いちばん高い木の輪郭をとる）
    for n, hmin, hmax, col in [(700, 2.0, 5.0, (0.10, 0.17, 0.11)), (450, 3.5, 9.0, (0.06, 0.11, 0.07))]:
        heights = np.full(W, -90.0)
        for _ in range(n):
            c = int(rng.integers(0, W))
            th = rng.uniform(hmin, hmax)
            half = max(th * rng.uniform(0.18, 0.28) / 360.0 * W, 1.0)   # 木の幅（半分）[画素]
            idx = np.arange(int(c - half), int(c + half) + 1) % W
            x = np.abs(((idx - c + W // 2) % W) - W // 2)
            top = hill[idx] + th * (1 - x / half)
            heights[idx] = np.maximum(heights[idx], top)
        _fill_below(img, heights, col, 0.06, rng)
    return img, None


def make_city(seed=7):
    rng = np.random.default_rng(seed)
    img = _base()
    emit = np.zeros((H, W, 3), np.float32)
    x = 0
    yy = np.arange(H)[:, None]
    while x < W:
        bw = int(rng.uniform(0.25, 1.8) / 360.0 * W)
        az_deg = x / W * 360.0
        # 方角によって、高いビルの多い所（街の中心）と低い家並みを分ける
        center = 0.5 + 0.5 * math.cos(math.radians(az_deg - 200))
        bh = rng.uniform(0.6, 2.0) + center ** 2 * rng.uniform(0.0, 9.0)
        if rng.random() < 0.04:
            bh += rng.uniform(6, 12)                                 # ときどき高い塔
        x1 = min(W, x + bw)
        top = _rows(bh)
        bottom = _rows(-2.0)
        g = rng.uniform(0.22, 0.38)
        img[top:bottom, x:x1, :3] = (g, g * 1.02, g * 1.06)
        img[top:bottom, x:x1, 3] = 1.0
        # 窓の明かり（夜だけ光る）
        rows_win = np.arange(top + 3, _rows(0.3), 6)
        cols_win = np.arange(x + 2, x1 - 2, 5)
        if len(cols_win) and len(rows_win):
            lit = rng.random((len(rows_win), len(cols_win))) < rng.uniform(0.15, 0.45)
            for i, r in enumerate(rows_win):
                for j, c in enumerate(cols_win):
                    if lit[i, j]:
                        warm = rng.uniform(0.7, 1.0)
                        emit[r:r + 2, c:c + 2] = (1.0 * warm, 0.82 * warm, 0.5 * warm)
        if bh > 8:                                                   # 航空障害灯（赤）
            cx = (x + x1) // 2
            emit[top:top + 3, cx - 1:cx + 2] = (1.0, 0.1, 0.05)
        x = x1 + int(rng.uniform(0, 0.15) / 360 * W)
    # 足もとの通り・家並み
    street = np.maximum(_ridge(rng, 0.5, 0.25), 0.15)
    _fill_below(img, street, (0.12, 0.12, 0.13), 0.05, rng)
    emit[_rows(0.3):_rows(0.0), :] += (rng.random((_rows(0.0) - _rows(0.3), W, 1)) < 0.08) * np.array([1.0, 0.75, 0.4])
    del yy
    return img, np.clip(emit, 0, 1)


def make_sea(seed=11):
    rng = np.random.default_rng(seed)
    img = _base()
    # 水平線より下は海（遠くほど明るく、手前ほど暗い）
    r0, r1 = _rows(0.0), H
    t = np.linspace(0, 1, r1 - r0)[:, None]
    sea = np.array([0.20, 0.30, 0.38]) * (1 - t) + np.array([0.05, 0.10, 0.16]) * t
    img[r0:r1, :, :3] = sea[:, None, :] * (1 + rng.normal(0, 0.03, (r1 - r0, W, 1)))
    img[r0:r1, :, 3] = 1.0
    # 遠くの島（いくつか）
    az = np.arange(W)
    for _ in range(4):
        c = rng.integers(0, W)
        wd = rng.uniform(3, 12) / 360 * W
        hh = rng.uniform(0.4, 1.5)
        xx = ((az - c + W // 2) % W - W // 2) / wd
        prof = np.where(np.abs(xx) < 1, hh * np.clip(1 - xx ** 2, 0, None) ** 0.7, -90.0)
        _fill_below(img, prof, (0.38, 0.45, 0.52), 0.02, rng, ground_alt=0.0)
    # 手前の浜辺（下のほう）
    _fill_below(img, np.full(W, -25.0), (0.36, 0.32, 0.25), 0.06, rng, ground_alt=-90.0)
    return img, None


def make(name: str) -> Landscape | None:
    fn = {"mountains": make_mountains, "forest": make_forest, "city": make_city, "sea": make_sea}.get(name)
    if fn is None:
        return None
    img, emit = fn()
    rgba = (np.clip(img, 0, 1) * 255 + 0.5).astype(np.uint8)
    em = None if emit is None else (np.clip(emit, 0, 1) * 255 + 0.5).astype(np.uint8)
    return Landscape(rgba, em, name)


def from_image(rgba: np.ndarray, north_deg: float = 0.0, name: str = "") -> Landscape:
    """自分の360°写真（正距円筒図・空は透明な PNG）。north_deg は写真の左はしの方位。"""
    h, w = rgba.shape[:2]
    shift = int(round(north_deg / 360.0 * w))
    rgba = np.roll(rgba, shift, axis=1)              # 左はしを北に合わせる
    if h != w // 2:                                    # 縦が半分でなければ、上下をそろえる（下半分だけなど）
        full = np.zeros((w // 2, w, 4), np.uint8)
        full[w // 2 - h:] = rgba[: w // 2]
        rgba = full
    return Landscape(np.ascontiguousarray(rgba), None, name)
