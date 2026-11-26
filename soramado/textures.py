"""惑星の表面画像。

ダウンロード済みの画像（Solar System Scope、CC BY 4.0）があればそれを使い、
無ければプログラムで作った簡易的な模様を使う。
"""

from __future__ import annotations

import os
import threading
import urllib.request
from pathlib import Path

import numpy as np
from PySide6.QtGui import QImage

from .bodies import TEXTURE_BASE_URL, all_texture_files


def texture_dir() -> Path:
    base = os.environ.get("XDG_DATA_HOME") or os.path.expanduser("~/.local/share")
    return Path(base) / "soramado" / "textures"


def downloaded_path(filename: str) -> Path | None:
    p = texture_dir() / filename
    return p if p.is_file() and p.stat().st_size > 0 else None


def missing_textures() -> list[str]:
    return [f for f in all_texture_files() if downloaded_path(f) is None]


# ------------------------------------------------------------- 簡易模様

def _noise(w: int, h: int, seed: int, octaves: int = 5, base: int = 8) -> np.ndarray:
    """横方向に繋がる fBm ノイズ（0〜1）。"""
    rng = np.random.default_rng(seed)
    out = np.zeros((h, w))
    amp, total = 1.0, 0.0
    for o in range(octaves):
        gw, gh = base * 2 ** o, max(2, base * 2 ** o // 2)
        grid = rng.random((gh + 1, gw))
        grid = np.concatenate([grid, grid[:, :1]], axis=1)  # 経度方向に繋げる
        ys = np.linspace(0, gh, h)
        xs = np.linspace(0, gw, w, endpoint=False)
        y0 = np.clip(ys.astype(int), 0, gh - 1)
        x0 = xs.astype(int)
        fy = (ys - y0)[:, None]
        fx = (xs - x0)[None, :]
        fy = fy * fy * (3 - 2 * fy)
        fx = fx * fx * (3 - 2 * fx)
        a = grid[y0][:, x0]
        b = grid[y0][:, x0 + 1]
        c = grid[y0 + 1][:, x0]
        d = grid[y0 + 1][:, x0 + 1]
        out += amp * ((a * (1 - fx) + b * fx) * (1 - fy) + (c * (1 - fx) + d * fx) * fy)
        total += amp
        amp *= 0.5
    return out / total


def _to_image(rgb: np.ndarray) -> QImage:
    arr = np.ascontiguousarray((np.clip(rgb, 0, 1) * 255).astype(np.uint8))
    h, w, ch = arr.shape
    fmt = QImage.Format_RGBA8888 if ch == 4 else QImage.Format_RGB888
    img = QImage(arr.data, w, h, w * ch, fmt)
    return img.copy()  # numpy 配列から切り離す


def _mix(c1, c2, t):
    c1, c2 = np.array(c1), np.array(c2)
    return c1 * (1 - t[..., None]) + c2 * t[..., None]


def _lat(h: int, w: int) -> np.ndarray:
    return np.repeat(np.linspace(1, -1, h)[:, None], w, axis=1)  # 北極=+1


def procedural(key: str, w: int = 512, h: int = 256) -> QImage:
    lat = _lat(h, w)
    n = _noise(w, h, seed=sum(map(ord, key)))
    if key == "sun":
        rgb = _mix((1.0, 0.55, 0.1), (1.0, 0.92, 0.6), _noise(w, h, 11, 6, 16))
    elif key in ("mercury", "moon"):
        rgb = _mix((0.35, 0.34, 0.33), (0.75, 0.73, 0.70), n)
    elif key == "venus":
        t = 0.5 + 0.5 * np.sin(lat * 6 + n * 3)
        rgb = _mix((0.85, 0.72, 0.45), (0.98, 0.92, 0.75), t)
    elif key == "earth":
        rgb = _mix((0.05, 0.18, 0.45), (0.15, 0.35, 0.65), n)
        cap = np.clip((np.abs(lat) - 0.85) * 12, 0, 1)
        rgb = _mix(rgb, (0.95, 0.97, 1.0), cap)
    elif key == "mars":
        rgb = _mix((0.45, 0.20, 0.10), (0.85, 0.48, 0.28), n)
        cap = np.clip((np.abs(lat) - 0.9) * 15, 0, 1)
        rgb = _mix(rgb, (0.95, 0.93, 0.9), cap)
    elif key in ("jupiter", "saturn"):
        warp = _noise(w, h, 7, 4, 6) * 0.6
        bands = 0.5 + 0.5 * np.sin(lat * (14 if key == "jupiter" else 18) + warp * 4)
        if key == "jupiter":
            rgb = _mix((0.62, 0.45, 0.32), (0.95, 0.90, 0.80), bands)
        else:
            rgb = _mix((0.78, 0.68, 0.45), (0.96, 0.90, 0.70), bands)
    elif key == "uranus":
        rgb = _mix((0.55, 0.82, 0.86), (0.66, 0.90, 0.92), 0.5 + 0.5 * np.sin(lat * 4))
    elif key == "neptune":
        rgb = _mix((0.18, 0.32, 0.80), (0.35, 0.52, 0.95), 0.5 + 0.5 * np.sin(lat * 7 + n * 2))
    elif key == "io":
        rgb = _mix((0.85, 0.70, 0.25), (0.98, 0.92, 0.55), n)
        spots = _noise(w, h, 31, 3, 24) > 0.72
        rgb[spots] = (0.45, 0.22, 0.10)
    elif key == "europa":
        rgb = _mix((0.78, 0.70, 0.58), (0.95, 0.93, 0.88), n)
        lines = np.abs(np.sin(_noise(w, h, 41, 3, 6) * 40)) < 0.08
        rgb[lines] = (0.60, 0.42, 0.30)
    elif key == "titan":
        rgb = _mix((0.80, 0.52, 0.18), (0.95, 0.72, 0.35), 0.5 + 0.5 * np.sin(lat * 3 + n))
    elif key == "enceladus":
        rgb = _mix((0.88, 0.92, 0.96), (1.0, 1.0, 1.0), n)
    elif key == "iapetus":
        # 前側（公転の進行方向）が暗い二色の衛星
        lon = np.repeat(np.linspace(-1, 1, w)[None, :], h, axis=0)
        dark = np.clip((0.4 - np.hypot(lon - 0.5, lat * 0.8)) * 6, 0, 1)
        rgb = _mix(_mix((0.75, 0.72, 0.66), (0.88, 0.86, 0.80), n), (0.18, 0.12, 0.08), dark)
    elif key in ("ganymede", "callisto", "phobos", "deimos", "triton", "mimas", "tethys", "dione", "rhea",
                 "miranda", "ariel", "umbriel", "titania", "oberon"):
        from .satellites import BY_KEY as SAT
        c = np.array(SAT[key].color)
        rgb = _mix(c * 0.6, np.minimum(c * 1.15, 1.0), n)
    elif key == "pluto":
        rgb = _mix((0.55, 0.40, 0.30), (0.95, 0.88, 0.80), n)
        heart = np.clip((0.25 - np.hypot(np.repeat(np.linspace(-1, 1, w)[None, :], h, axis=0) - 0.0,
                                          lat - 0.1)) * 8, 0, 1)
        rgb = _mix(rgb, (0.98, 0.95, 0.92), heart)     # 「ハート」と呼ばれる明るい平原
    else:
        from .smallbodies import BY_KEY as SB
        from .satellites import BY_KEY as SAT
        if key in SAT:
            c = np.array(SAT[key].color)
            rgb = _mix(c * 0.6, np.minimum(c * 1.15, 1.0), n)
        elif key in SB:
            c = np.array(SB[key].color)
            rgb = _mix(c * 0.55, np.minimum(c * 1.1, 1.0), n)
        else:
            rgb = np.full((h, w, 3), 0.6)
    return _to_image(rgb)


def procedural_ring(w: int = 512) -> QImage:
    """土星の環（内側→外側）。RGBA、高さ 1。"""
    r = np.linspace(74500, 136780, w)
    alpha = np.zeros(w)
    alpha[(r >= 74500) & (r < 92000)] = 0.25          # C環
    alpha[(r >= 92000) & (r < 117580)] = 0.85         # B環
    alpha[(r >= 122170) & (r < 136780)] = 0.6         # A環
    alpha[(r >= 133400) & (r < 133700)] = 0.1         # エンケの間隙
    alpha *= 0.85 + 0.15 * np.sin(r / 900.0)
    rgb = np.stack([np.full(w, 0.85), np.full(w, 0.78), np.full(w, 0.62)], axis=1)
    rgba = np.concatenate([rgb, alpha[:, None]], axis=1)[None, :, :]
    return _to_image(np.repeat(rgba, 4, axis=0))


def _thin_rings(r_in, r_out, rings, color, w=1024):
    """細い環（半径・幅・不透明度のリスト）を、内側→外側の1行の画像にする。"""
    r = np.linspace(r_in, r_out, w)
    alpha = np.zeros(w)
    px = (r_out - r_in) / w
    for rr, width, a in rings:
        wd = max(width, px * 1.5)          # 細すぎる環も、少なくとも1ピクセルちょっとの幅で描く
        alpha = np.maximum(alpha, a * np.exp(-0.5 * ((r - rr) / (wd / 2)) ** 2))
    rgb = np.tile(np.array(color, float), (w, 1))
    rgba = np.concatenate([rgb, alpha[:, None]], axis=1)[None, :, :]
    return _to_image(np.repeat(rgba, 4, axis=0))


def procedural_ring_uranus() -> QImage:
    """天王星の環（1977年に恒星の掩蔽で発見された、暗く細い環）。ε環がいちばん目立つ。"""
    rings = [(41837, 40, 0.35), (42234, 40, 0.35), (42571, 40, 0.35), (44718, 60, 0.45), (45661, 60, 0.45),
             (47176, 40, 0.3), (47627, 40, 0.4), (48300, 50, 0.45), (50023, 30, 0.25), (51149, 100, 0.75)]
    return _thin_rings(41000, 51700, rings, (0.62, 0.62, 0.66))


def procedural_ring_neptune() -> QImage:
    """海王星の環（ガレ環・ルヴェリエ環・ラッセル環・アラゴ環・アダムズ環）。"""
    rings = [(41900, 2000, 0.10), (53200, 110, 0.45), (55200, 4000, 0.06), (57200, 100, 0.25),
             (62932, 50, 0.5)]
    return _thin_rings(40000, 63500, rings, (0.70, 0.62, 0.58))


def load_image(filename: str) -> QImage | None:
    p = downloaded_path(filename)
    if p is None:
        return None
    img = QImage(str(p))
    return None if img.isNull() else img


# ------------------------------------------------------------- ダウンロード

class TextureDownloader:
    """別スレッドで画像をダウンロードする。

    画面（Qt）にはこのスレッドから一切さわらない。画面側はタイマーで
    current / done などの状態を見に来て、進み具合を表示する。
    """

    def __init__(self, files: list[str]):
        self.files = list(files)
        self.total = len(self.files)
        self.index = 0
        self.current = ""
        self.ok = 0
        self.failed: list[str] = []
        self.done = False
        self._cancel = threading.Event()
        self._thread = threading.Thread(target=self._run, daemon=True)

    def start(self):
        self._thread.start()

    def cancel(self):
        self._cancel.set()

    def wait(self, timeout=None):
        self._thread.join(timeout)

    def _run(self):
        dest = texture_dir()
        dest.mkdir(parents=True, exist_ok=True)
        for i, name in enumerate(self.files):
            if self._cancel.is_set():
                self.failed.extend(self.files[i:])
                break
            self.index, self.current = i, name
            tmp = dest / (name + ".part")
            try:
                req = urllib.request.Request(TEXTURE_BASE_URL + name,
                                             headers={"User-Agent": "Mozilla/5.0 (X11; Linux x86_64) Soramado/0.1"})
                with urllib.request.urlopen(req, timeout=20) as res, open(tmp, "wb") as fp:
                    while chunk := res.read(65536):
                        if self._cancel.is_set():
                            raise RuntimeError("cancelled")
                        fp.write(chunk)
                if QImage(str(tmp)).isNull():
                    raise ValueError("画像として読み込めません")
                tmp.replace(dest / name)
                self.ok += 1
            except Exception:  # noqa: BLE001 - 失敗は一覧で知らせる
                tmp.unlink(missing_ok=True)
                self.failed.append(name)
        self.index, self.current = self.total, ""
        self.done = True


# ---------------------------------------------------------------- 作った模様の保存（起動を速くする）
CACHE_VER = 1                  # 模様の作り方を変えたら上げる（古い保存を使わないように）


def cache_dir():
    from pathlib import Path
    import os
    base = Path(os.environ.get("XDG_CACHE_HOME") or Path.home() / ".cache")
    return base / "soramado" / f"tex{CACHE_VER}"


def cached(name: str, make):
    """計算で作る模様を、一度作ったら保存しておき、次からはそれを読む。"""
    path = cache_dir() / f"{name}.png"
    if path.is_file():
        img = QImage(str(path))
        if not img.isNull():
            return img
    img = make()
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        img.save(str(path), "PNG")
    except OSError:
        pass
    return img

