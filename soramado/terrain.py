"""月と火星の地形（本物の標高データ）と、降り立てる場所。

- 月: LRO（ルナー・リコネサンス・オービター）のレーザー高度計 LOLA の標高図 LDEM_16
  （1/16度ごと、約1.9km。NASA / MIT の LOLA PDS データノード）
- 火星: MGS（マーズ・グローバル・サーベイヤー）のレーザー高度計 MOLA の標高図 MEGDR
  （1/16度ごと、約3.7km。NASA PDS 地球科学ノード）

どちらも 横 5760 × 縦 2880 の 16bit 整数で、北緯90度から南へ、東経0度から東へ並ぶ。
ダウンロードしたら、メートル単位の int16 の .npy にして保存する。
"""

from __future__ import annotations

import math
import threading
import urllib.request
import zlib
from dataclasses import dataclass
from pathlib import Path

import numpy as np

from .cosmos import data_dir

W, H = 5760, 2880            # 詳しい版（1/16度ごと）
LEVELS = {4: (1440, 720), 16: (5760, 2880)}   # 1度あたりの点の数 → (横, 縦)


@dataclass(frozen=True)
class Source:
    body: str
    urls: dict             # 1度あたりの点の数 → URL の候補
    scale: float           # 値 × scale = 標高 [m]
    size_mb: dict          # 1度あたりの点の数 → 大きさ [MB]
    credit: str


SOURCES = {
    "moon": Source("moon", {
        4: ("https://imbrium.mit.edu/DATA/LOLA_GDR/CYLINDRICAL/IMG/LDEM_4.IMG",
            "https://pds-geosciences.wustl.edu/lro/lro-l-lola-3-rdr-v1/lrolol_1xxx/data/lola_gdr/cylindrical/img/ldem_4.img"),
        16: ("https://imbrium.mit.edu/DATA/LOLA_GDR/CYLINDRICAL/IMG/LDEM_16.IMG",
             "https://pds-geosciences.wustl.edu/lro/lro-l-lola-3-rdr-v1/lrolol_1xxx/data/lola_gdr/cylindrical/img/ldem_16.img"),
    }, 0.5, {4: 2.1, 16: 33.2}, "月の地形: NASA / LRO / LOLA（LDEM）"),
    "mars": Source("mars", {
        4: ("https://pds-geosciences.wustl.edu/mgs/urn-nasa-pds-mgs_mola_topography_derived/meg004/megt90n000cb.img",
            "https://pds-geosciences.wustl.edu/mgs/mgs-m-mola-5-megdr-l3-v1/mgsl_300x/meg004/megt90n000cb.img"),
        16: ("https://pds-geosciences.wustl.edu/mgs/urn-nasa-pds-mgs_mola_topography_derived/meg016/megt90n000eb.img",
             "https://pds-geosciences.wustl.edu/mgs/mgs-m-mola-5-megdr-l3-v1/mgsl_300x/meg016/megt90n000eb.img"),
    }, 1.0, {4: 2.1, 16: 33.2}, "火星の地形: NASA / MGS / MOLA（MEGDR）"),
}

# 降り立てる場所: (名前, 緯度, 東経)
PLACES = {
    "moon": [
        ("静かの海（アポロ11号）", 0.674, 23.473),
        ("ハドリー谷（アポロ15号）", 26.132, 3.634),
        ("タウルス・リットロウ谷（アポロ17号）", 20.191, 30.772),
        ("神酒の海のそば（SLIM）", -13.316, 25.251),
        ("コペルニクス・クレーターの中", 9.62, -20.08),
        ("ティコ・クレーターの中央の山", -43.31, -11.36),
        ("フォン・カルマン・クレーター（嫦娥4号・月の裏側）", -45.444, 177.588),
        ("月の南極（シャクルトン・クレーターのふち）", -89.45, 129.0),
    ],
    "mars": [
        ("ジェゼロ・クレーター（パーサヴィアランス）", 18.4447, 77.4508),
        ("ゲール・クレーター（キュリオシティ）", -4.5895, 137.4417),
        ("メリディアニ平原（オポチュニティ）", -1.9462, -5.5266),
        ("オリンポス山の山頂", 18.65, -133.8),
        ("マリネリス峡谷の底（メラス谷）", -10.0, -73.0),
        ("ヘラス盆地（火星でいちばん低い所）", -42.4, 70.5),
        ("北極冠", 85.0, 0.0),
    ],
}

BODY_NAMES = {"moon": "月", "mars": "火星"}
BODY_NAMES_EN = {"moon": "Moon", "mars": "Mars"}


def body_name(body: str) -> str:
    from .i18n import EN_MODE
    return (BODY_NAMES_EN if EN_MODE else BODY_NAMES)[body]
EYE_KM = 0.0017              # 目の高さ（1.7m）


def path(body: str, ppd: int = 16) -> Path:
    return data_dir() / f"terrain_{body}_{ppd}.npy"


def available(body: str, ppd: int | None = None) -> bool:
    """標高図があるか（ppd を省くと、どちらかがあれば True）。"""
    if ppd is None:
        return any(path(body, k).is_file() for k in LEVELS)
    return path(body, ppd).is_file()


def level(body: str) -> int:
    """手元にあるいちばん詳しい標高図の細かさ（1度あたりの点の数。無ければ 0）。"""
    for k in sorted(LEVELS, reverse=True):
        if path(body, k).is_file():
            return k
    return 0


_cache: dict = {}


def load(body: str):
    """標高図（int16、メートル）。詳しい版を優先。無ければ None。"""
    if body in _cache:
        return _cache[body]
    for k in sorted(LEVELS, reverse=True):
        p = path(body, k)
        if not p.is_file():
            continue
        try:
            a = np.load(p, mmap_mode="r")
        except Exception:  # noqa: BLE001
            continue
        if a.shape == LEVELS[k][::-1]:
            _cache[body] = a
            return a
    return None


def forget(body: str):
    _cache.pop(body, None)


def decode(raw, scale: float) -> np.ndarray:
    """16bit の生データ → メートルの int16。大きさから細かさを決め、バイトの並びはなめらかなほうを選ぶ。"""
    n = len(raw)
    shape = next(((h, w) for w, h in LEVELS.values() if w * h * 2 == n), None)
    if shape is None:
        raise ValueError(f"大きさが違います（{n:,} バイト）")
    h, w = shape
    best = None
    for dt in ("<i2", ">i2"):
        a = np.frombuffer(raw, dtype=dt).reshape(h, w)
        s = a[h // 4: h // 4 + h // 7, : w // 3].astype(np.float32)
        rough = float(np.mean(np.abs(np.diff(s, axis=1))))
        if best is None or rough < best[0]:
            best = (rough, a)
    m = best[1].astype(np.float32) * scale
    return np.clip(np.round(m), -32768, 32767).astype(np.int16)


def height_km(dem, lat_deg, lon_deg):
    """緯度・東経 [度]（配列でもよい）の標高 [km]（となり4点から補間）。"""
    lat = np.asarray(lat_deg, dtype=np.float64)
    lon = np.mod(np.asarray(lon_deg, dtype=np.float64), 360.0)
    H, W = dem.shape
    ppd = W / 360.0
    y = np.clip((90.0 - lat) * ppd - 0.5, 0, H - 1.001)
    x = lon * ppd - 0.5
    y0 = np.floor(y).astype(np.int64)
    x0 = np.floor(x).astype(np.int64)
    fy, fx = y - y0, x - x0
    x0m, x1m = np.mod(x0, W), np.mod(x0 + 1, W)
    y1 = np.minimum(y0 + 1, H - 1)
    a = dem[y0, x0m].astype(np.float32)
    b = dem[y0, x1m].astype(np.float32)
    c = dem[y1, x0m].astype(np.float32)
    d = dem[y1, x1m].astype(np.float32)
    h = (a * (1 - fx) + b * fx) * (1 - fy) + (c * (1 - fx) + d * fx) * fy
    return h / 1000.0


def _unit(lat, lon):
    return np.stack([np.cos(lat) * np.cos(lon), np.cos(lat) * np.sin(lon), np.sin(lat)], axis=-1)


def _detail(lat, lon, radius_km):
    """標高図より細かい起伏（小さなクレーターや岩のでこぼこ）を足す [km]。場所ごとにいつも同じ形。"""
    x = np.radians(lon) * radius_km * np.cos(np.radians(lat))
    y = np.radians(lat) * radius_km
    h = np.zeros_like(x)
    amp, f = 0.012, 1.0 / 0.35
    for k in range(5):
        ph = 1.7 * k + 0.3
        h += amp * (np.sin(x * f + ph) * np.cos(y * f * 1.13 - ph) + 0.5 * np.sin((x + y) * f * 0.71 + 2 * ph))
        amp *= 0.5
        f *= 2.1
    return h


def build(body: str, lat0: float, lon0: float, radius_km: float, rings: int = 110, segs: int = 384):
    """観測地のまわりの地形の網目を作る。

    戻り値: (頂点の配列 [N, 8] = 目からの位置[km](天体の座標軸) + 法線 + テクスチャ座標,
             地平線の形（方位0.5度ごと、見上げる角度[度]の配列 720個）, 観測地の標高[km])
    天体の座標軸: z = 自転軸の北極, x = 本初子午線（東経0度）
    """
    dem = load(body)
    rmax = {"moon": 260.0, "mars": 420.0}.get(body, 300.0)
    la0, lo0 = math.radians(lat0), math.radians(lon0)

    def hgt(lat_d, lon_d):
        hk = height_km(dem, lat_d, lon_d) if dem is not None else np.zeros(np.shape(lat_d))
        return hk + _detail(lat_d, lon_d, radius_km)

    h0 = float(hgt(np.array([lat0]), np.array([lon0]))[0])
    eye = _unit(np.array(la0), np.array(lo0)) * (radius_km + h0 + EYE_KM)

    r = np.concatenate([[0.0], 0.004 * (rmax / 0.004) ** (np.arange(rings - 1) / (rings - 2))])
    az = np.linspace(0.0, 2 * math.pi, segs + 1)
    dlt = (r / radius_km)[:, None]
    A = az[None, :]
    lat = np.arcsin(np.clip(math.sin(la0) * np.cos(dlt) + math.cos(la0) * np.sin(dlt) * np.cos(A), -1, 1))
    dlon = np.arctan2(np.sin(A) * np.sin(dlt) * math.cos(la0), np.cos(dlt) - math.sin(la0) * np.sin(lat))
    lon = lo0 + dlon
    latd, lond = np.degrees(lat), np.degrees(lon)
    hk = hgt(latd, lond)
    hk[0, :] = h0
    P = _unit(lat, lon) * (radius_km + hk)[..., None] - eye          # 目からの位置 [km]

    # 法線: となりの点との差から
    dr = np.zeros_like(P)
    dr[1:-1] = P[2:] - P[:-2]
    dr[0] = P[1] - P[0]
    dr[-1] = P[-1] - P[-2]
    da = np.roll(P, -1, axis=1) - np.roll(P, 1, axis=1)
    da[:, 0] = P[:, 1] - P[:, -2]
    da[:, -1] = da[:, 0]
    n = np.cross(dr, da)
    up = _unit(lat, lon)
    bad = np.linalg.norm(n, axis=-1) < 1e-12
    n[bad] = up[bad]
    n /= np.linalg.norm(n, axis=-1, keepdims=True)
    flip = np.sum(n * up, axis=-1) < 0
    n[flip] *= -1

    # テクスチャ座標（天体の地図: 横は経度 -180〜180、縦は北極〜南極）。経度はつながるように
    u = (np.unwrap(lon, axis=1) + math.pi) / (2 * math.pi)
    v = (math.pi / 2 - lat) / math.pi
    V = np.concatenate([P, n, u[..., None], v[..., None]], axis=-1).astype(np.float32)

    # 三角形に並べる
    i0 = V[:-1, :-1]
    i1 = V[1:, :-1]
    i2 = V[1:, 1:]
    i3 = V[:-1, 1:]
    tri = np.stack([i0, i1, i2, i0, i2, i3], axis=2).reshape(-1, 8)

    # 地平線の形: 方位ごとに、いちばん高く見える地面の角度（大気差なし）
    up0 = eye / np.linalg.norm(eye)
    L = np.linalg.norm(P[1:], axis=-1)
    elev = np.degrees(np.arcsin(np.clip(np.sum(P[1:] * up0, axis=-1) / np.maximum(L, 1e-12), -1, 1)))
    prof = elev.max(axis=0)[:-1]                       # segs 個（方位 0〜360 度、北から東へ）
    az_deg = np.degrees(az[:-1])
    grid = np.arange(720) * 0.5
    horizon = np.interp(grid, np.concatenate([az_deg, [360.0]]), np.concatenate([prof, prof[:1]]))
    return tri, horizon.astype(np.float32), h0


class Downloader:
    """別スレッドで標高図をダウンロードして .npy にする。切れても、次は続きから受け取る。"""

    def __init__(self, body: str, ppd: int):
        self.src = SOURCES[body]
        self.body = body
        self.ppd = ppd
        self.done = False
        self.ok = False
        self.message = ""
        self.bytes = 0
        w, h = LEVELS[ppd]
        self.total = w * h * 2
        self._cancel = threading.Event()
        self._thread = threading.Thread(target=self._run, daemon=True)

    def start(self):
        self._thread.start()

    def cancel(self):
        self._cancel.set()

    def _part(self, url):
        return path(self.body, self.ppd).with_suffix(f".{zlib.crc32(url.encode()):08x}.part")

    def _get(self, url):
        part = self._part(url)
        part.parent.mkdir(parents=True, exist_ok=True)
        have = part.stat().st_size if part.is_file() else 0
        if have >= self.total:
            have = 0
            part.unlink()
        headers = {"User-Agent": "Soramado (space simulator)"}
        if have:
            headers["Range"] = f"bytes={have}-"
        req = urllib.request.Request(url, headers=headers)
        with urllib.request.urlopen(req, timeout=60) as res:
            if have and res.status != 206:       # 続きからを受けつけないサーバーなら、はじめから
                have = 0
            self.bytes = have
            with open(part, "ab" if have else "wb") as fp:
                while True:
                    if self._cancel.is_set():
                        raise RuntimeError("キャンセルしました")
                    b = res.read(1 << 17)
                    if not b:
                        break
                    fp.write(b)
                    self.bytes += len(b)
        if part.stat().st_size != self.total:
            raise RuntimeError("途中で切れました（次は続きから受け取ります）")
        raw = part.read_bytes()
        return raw, part

    def _run(self):
        last = None
        for url in self.src.urls[self.ppd]:
            if self._cancel.is_set():
                break
            try:
                raw, part = self._get(url)
                dem = decode(raw, self.src.scale)
                p = path(self.body, self.ppd)
                tmp = p.with_suffix(".tmp.npy")
                np.save(tmp, dem)
                tmp.replace(p)
                part.unlink(missing_ok=True)
                forget(self.body)
                self.ok = True
                break
            except Exception as exc:  # noqa: BLE001
                last = exc
                if "途中で切れました" in str(exc) or "timed out" in str(exc).lower():
                    break                      # 同じサーバーで続きから受け取れるよう、次の候補には移らない
        if self._cancel.is_set():
            self.message = "キャンセルしました"
        elif not self.ok and last:
            self.message = str(last)
        self.done = True
