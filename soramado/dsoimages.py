"""星雲・星団・銀河の写真（DSS2 color）をダウンロードして保存する。

写真は Digitized Sky Survey（パロマー天文台などの写真乾板を STScI がデジタル化したもの）を
CDS がカラーにした「DSS2 color」。ESA（ESASky）と CDS が、全天を HiPS のタイルにして配信している。
天体ごとに、まわりのタイルを集めて、北が上・東が左の写真に並べ直して保存する。
"""

from __future__ import annotations

import math
import threading
import urllib.request
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass
from pathlib import Path

import numpy as np
from PySide6.QtGui import QImage

from . import galaxies as gx
from . import hips
from . import nebulae as neb
from .cosmos import data_dir

SIZE = 1024                    # 保存する写真の1辺の画素数
CREDIT = "写真: DSS2 color（STScI・CDS、ESA ESASky / CDS の HiPS から）"
try:
    from .i18n import EN_MODE
    if EN_MODE:
        CREDIT = "Photo: DSS2 color (STScI, CDS; HiPS served by ESA ESASky / CDS)"
except Exception:  # noqa: BLE001
    pass


@dataclass
class Target:
    key: str                   # 表示側の天体の番号（"n:12"、"g:m31"）
    file: str                  # 保存するファイル名
    ra: float
    dec: float
    fov: float                 # 写真の1辺の角度 [度]


def photo_dir() -> Path:
    return data_dir() / "dso_photos"


def targets() -> list[Target]:
    out = []
    for i, n in enumerate(neb.NEBULAE):
        if n.maj < 3.0:
            continue           # 小さすぎるもの（環状星雲など）は、DSS では白くつぶれるので模式図のまま
        size = max(n.maj, n.min) / 60.0                       # 度
        fov = min(15.0, max(0.06, size * 1.7))
        out.append(Target(f"n:{i}", f"{n.id}.jpg", n.ra, n.dec, fov))
    for g in gx.GALAXIES:
        if g.kind == "milkyway":
            continue
        size = math.degrees(2 * g.radius_kpc / g.dist_kpc)
        fov = min(15.0, max(0.06, size * 1.25))
        out.append(Target(g.key, f"{g.key[2:]}.jpg", g.ra, g.dec, fov))
    return out


def path_for(t: Target) -> Path:
    return photo_dir() / t.file


def available() -> dict[str, tuple[Target, Path]]:
    """保存済みの写真（天体の番号 → (Target, ファイル)）。"""
    out = {}
    for t in targets():
        p = path_for(t)
        if p.is_file():
            out[t.key] = (t, p)
    return out


def _fetch(url: str, timeout=60) -> bytes:
    req = urllib.request.Request(url, headers={"User-Agent": "Soramado (space simulator)"})
    with urllib.request.urlopen(req, timeout=timeout) as res:
        return res.read()


def _decode(data: bytes) -> np.ndarray | None:
    img = QImage.fromData(data)
    if img.isNull():
        return None
    img = img.convertToFormat(QImage.Format.Format_RGB888)
    w, h = img.width(), img.height()
    arr = np.frombuffer(img.constBits(), np.uint8, count=img.bytesPerLine() * h).reshape(h, img.bytesPerLine())
    return arr[:, :w * 3].reshape(h, w, 3).copy()


def process(img: np.ndarray) -> np.ndarray:
    """空の明るさを引いて、天体のところだけが光るようにする（加算で重ねるため）。"""
    f = img.astype(np.float32)
    sky = np.percentile(f.reshape(-1, 3), 35, axis=0)          # 写真の大部分は空
    f = np.clip((f - sky * 1.15) / np.maximum(255.0 - sky * 1.15, 1.0), 0.0, 1.0)
    f = f ** 0.9
    return (f * 255.0 + 0.5).astype(np.uint8)


def save_jpeg(arr: np.ndarray, path: Path):
    h, w, _ = arr.shape
    buf = np.ascontiguousarray(arr)
    img = QImage(buf.data, w, h, w * 3, QImage.Format.Format_RGB888).copy()
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(".tmp.jpg")
    if not img.save(str(tmp), "JPEG", 90):
        raise RuntimeError(f"保存できませんでした: {path}")
    tmp.replace(path)


class PhotoDownloader:
    """別スレッドで、まだない写真をダウンロードする。"""

    def __init__(self, only_missing: bool = True):
        self.done = False
        self.ok = False
        self.message = ""
        self.todo = [t for t in targets() if not (only_missing and path_for(t).is_file())]
        self.total = len(self.todo)
        self.finished = 0
        self.failed = 0
        self.bytes = 0
        self.current = ""
        self._cancel = threading.Event()
        self._thread = threading.Thread(target=self._run, daemon=True)
        self._lock = threading.Lock()

    def start(self):
        self._thread.start()

    def cancel(self):
        self._cancel.set()

    def _tile(self, order: int, ipix: int):
        last = None
        for base in hips.SERVERS:
            if self._cancel.is_set():
                return None
            try:
                data = _fetch(hips.tile_url(base, order, ipix))
                with self._lock:
                    self.bytes += len(data)
                arr = _decode(data)
                if arr is not None and arr.shape[0] == hips.TILE:
                    return arr
            except Exception as exc:  # noqa: BLE001
                last = exc
        if last:
            raise last
        return None

    def _one(self, t: Target, pool: ThreadPoolExecutor):
        order, tiles, row, col = hips.plan(t.ra, t.dec, t.fov, SIZE)
        ids = [int(x) for x in np.unique(tiles)]
        imgs = dict(zip(ids, pool.map(lambda i: self._tile(order, i), ids)))
        if self._cancel.is_set():
            return
        if any(v is None for v in imgs.values()):
            raise RuntimeError("タイルが足りません")
        save_jpeg(process(hips.assemble(imgs, tiles, row, col)), path_for(t))

    def _run(self):
        try:
            with ThreadPoolExecutor(max_workers=6) as pool:
                for t in self.todo:
                    if self._cancel.is_set():
                        raise RuntimeError("キャンセルしました")
                    self.current = t.file[:-4]
                    try:
                        self._one(t, pool)
                    except Exception as exc:  # noqa: BLE001
                        self.failed += 1
                        self.message = str(exc)
                    self.finished += 1
            if self._cancel.is_set():
                raise RuntimeError("キャンセルしました")
            self.ok = self.failed < self.total or self.total == 0
        except Exception as exc:  # noqa: BLE001
            self.message = str(exc)
        self.done = True
