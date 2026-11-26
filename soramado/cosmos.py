"""宇宙論的な距離と、宇宙の果ての表示（クエーサー・宇宙マイクロ波背景放射）。

距離は「共動距離」（宇宙の膨張を差し引いた、今の時点での距離）で表す。
宇宙モデルは平坦な ΛCDM（H0 = 70 km/s/Mpc、Ωm = 0.3、ΩΛ = 0.7）。

クエーサーは SDSS DR16Q（Lyke et al. 2020、約75万個）を VizieR（カタログ VII/289）から
利用者のパソコンにダウンロードして使う（ソフトには同梱しない）。

宇宙マイクロ波背景放射（CMB）の球は、本物の観測地図ではなく、同じような「ゆらぎ」を
計算で作った模式図。
"""

from __future__ import annotations

import io
import math
import os
import threading
import urllib.parse
import urllib.request
from pathlib import Path

import numpy as np

from . import astro

C_KMS = 299792.458
H0 = 70.0
OM, OL = 0.3, 0.7
MPC_AU = 2.06264806e11
GLY_AU = 63241.077 * 1e9

# 共動距離の表（z → Mpc）
_Z = np.concatenate([np.linspace(0, 10, 4001), np.geomspace(10.01, 1100, 2000)])


def _comoving_table():
    ez = np.sqrt(OM * (1 + _Z) ** 3 + OL + 8.4e-5 * (1 + _Z) ** 4)   # 放射の寄与も少し入れる
    f = 1.0 / ez
    dc = np.concatenate([[0.0], np.cumsum((f[1:] + f[:-1]) / 2 * np.diff(_Z))])
    return dc * C_KMS / H0


_DC = _comoving_table()


def comoving_mpc(z):
    return np.interp(z, _Z, _DC)


# 宇宙の晴れ上がり（z ≈ 1090）までの共動距離 ≈ 観測できる宇宙の果て
CMB_Z = 1090.0
CMB_MPC = float(comoving_mpc(CMB_Z))
CMB_AU = CMB_MPC * MPC_AU


# ---------------------------------------------------------------- クエーサー

def data_dir() -> Path:
    base = os.environ.get("XDG_DATA_HOME") or os.path.expanduser("~/.local/share")
    return Path(base) / "soramado"


QSO_FILE = "quasars_dr16q.npz"


def load_quasars():
    p = data_dir() / QSO_FILE
    if not p.is_file():
        return None
    d = np.load(p)
    return d["ra"], d["dec"], d["z"]


def quasar_vertices(ra, dec, z) -> np.ndarray:
    """頂点データ: 位置[AU](3), 色(3)。色は赤方偏移で青→白→赤。"""
    r, dd = np.radians(ra), np.radians(dec)
    eq = np.stack([np.cos(dd) * np.cos(r), np.cos(dd) * np.sin(r), np.sin(dd)], axis=1)
    c, s = math.cos(astro.OBLIQUITY_J2000), math.sin(astro.OBLIQUITY_J2000)
    ecl = np.stack([eq[:, 0], c * eq[:, 1] + s * eq[:, 2], -s * eq[:, 1] + c * eq[:, 2]], axis=1)
    pos = ecl * (comoving_mpc(z) * MPC_AU)[:, None]
    t = np.clip(z / 4.0, 0, 1)[:, None]
    blue, white, red = np.array([0.55, 0.7, 1.0]), np.array([1.0, 0.95, 0.85]), np.array([1.0, 0.45, 0.35])
    col = np.where(t < 0.5, blue + (white - blue) * (t * 2), white + (red - white) * ((t - 0.5) * 2))
    return np.concatenate([pos, col], axis=1).astype(np.float32)


# VizieR の鏡サイト（どれかにつながればよい）
VIZIER_HOSTS = ["https://vizier.cds.unistra.fr", "https://vizier.cfa.harvard.edu"]
CATALOG = "VII/289/dr16q"


def _asu_url(host, params):
    return host + "/viz-bin/asu-tsv?" + urllib.parse.urlencode(params, safe="/,")


def parse_tsv(text: str):
    """VizieR の TSV（# のコメント、見出し、単位、--- の行、データ）を読む。"""
    lines = [ln for ln in text.splitlines() if ln.strip() and not ln.startswith("#")]
    if len(lines) < 3:
        return [], []
    header = [h.strip() for h in lines[0].split("\t")]
    start = 1
    while start < len(lines) and (set(lines[start].replace("\t", "").strip()) <= set("-") or
                                  not any(ch.isdigit() for ch in lines[start])):
        start += 1
    rows = [ln.split("\t") for ln in lines[start:]]
    return header, rows


def _pick(header, candidates):
    low = {h.lower(): h for h in header}
    for c in candidates:
        if c.lower() in low:
            return low[c.lower()]
    return None


def _sexa_to_deg(s: str, hours: bool) -> float:
    s = s.strip()
    try:
        return float(s)
    except ValueError:
        pass
    sign = -1.0 if s.startswith("-") else 1.0
    parts = [float(p) for p in s.lstrip("+-").replace(":", " ").split()]
    v = parts[0] + (parts[1] if len(parts) > 1 else 0) / 60 + (parts[2] if len(parts) > 2 else 0) / 3600
    return sign * v * (15.0 if hours else 1.0)


class QuasarDownloader:
    """別スレッドで DR16Q をダウンロードして npz に保存する。画面からは状態を見に来る。"""

    def __init__(self):
        self.done = False
        self.ok = False
        self.message = ""
        self.bytes = 0
        self.count = 0
        self._cancel = threading.Event()
        self._thread = threading.Thread(target=self._run, daemon=True)

    def start(self):
        self._thread.start()

    def cancel(self):
        self._cancel.set()

    def _get(self, url, stream=False):
        req = urllib.request.Request(url, headers={"User-Agent": "Soramado (space simulator)"})
        res = urllib.request.urlopen(req, timeout=60)
        if not stream:
            return res.read().decode("utf-8", "replace")
        buf = io.BytesIO()
        while chunk := res.read(262144):
            if self._cancel.is_set():
                raise RuntimeError("キャンセルしました")
            buf.write(chunk)
            self.bytes += len(chunk)
        return buf.getvalue().decode("utf-8", "replace")

    def _run(self):
        errors = []
        for host in VIZIER_HOSTS:
            try:
                self._fetch(host)
                self.ok = True
                break
            except Exception as exc:  # noqa: BLE001
                errors.append(f"{host}: {exc}")
                if self._cancel.is_set():
                    break
        if not self.ok:
            self.message = "\n".join(errors)
        self.done = True

    def _fetch(self, host):
        # 1) 列の名前を調べる（カタログによって RA/Dec/z の列名が違うことがあるため）
        head = self._get(_asu_url(host, {"-source": CATALOG, "-out.all": "", "-out.max": "2",
                                         "-oc.form": "dec"}))
        header, _ = parse_tsv(head)
        col_ra = _pick(header, ["RAJ2000", "RA_ICRS", "RAdeg", "RA", "_RAJ2000"])
        col_de = _pick(header, ["DEJ2000", "DE_ICRS", "DEdeg", "DEC", "DE", "_DEJ2000"])
        col_z = _pick(header, ["Z", "z", "zsp", "Z_PIPE"])
        if not (col_ra and col_de and col_z):
            raise RuntimeError(f"列が見つかりません（見出し: {', '.join(header[:12])} …）")
        # 2) 全件を、必要な3列だけダウンロード
        text = self._get(_asu_url(host, {"-source": CATALOG, "-out": f"{col_ra},{col_de},{col_z}",
                                         "-out.max": "unlimited", "-oc.form": "dec"}), stream=True)
        header, rows = parse_tsv(text)
        i_ra, i_de, i_z = (header.index(c) for c in (col_ra, col_de, col_z))
        ra, de, zz = [], [], []
        for r in rows:
            try:
                z = float(r[i_z])
                if not (0.0 < z < 8.0):
                    continue
                ra.append(_sexa_to_deg(r[i_ra], hours=":" in r[i_ra] or " " in r[i_ra].strip()))
                de.append(_sexa_to_deg(r[i_de], hours=False))
                zz.append(z)
            except (ValueError, IndexError):
                continue
        if len(zz) < 1000:
            raise RuntimeError(f"読み込めたクエーサーが少なすぎます（{len(zz)} 個）")
        self.count = len(zz)
        dest = data_dir()
        dest.mkdir(parents=True, exist_ok=True)
        tmp = dest / (QSO_FILE + ".part.npz")
        np.savez_compressed(tmp, ra=np.array(ra, np.float32), dec=np.array(de, np.float32),
                            z=np.array(zz, np.float32))
        tmp.replace(dest / QSO_FILE)


# ---------------------------------------------------------------- CMB の模式図

def _noise3(p: np.ndarray, freq: float, seed: int) -> np.ndarray:
    """3次元の格子ノイズ（球面上で継ぎ目が出ないように、3次元の位置から作る）。"""
    rng = np.random.default_rng(seed)
    n = 64
    grid = rng.normal(0, 1, (n, n, n))
    q = (p * freq + 100.0) % n
    i0 = np.floor(q).astype(int)
    f = q - i0
    f = f * f * (3 - 2 * f)
    i1 = (i0 + 1) % n
    out = 0.0
    for dx in (0, 1):
        for dy in (0, 1):
            for dz in (0, 1):
                ix = i1[..., 0] if dx else i0[..., 0]
                iy = i1[..., 1] if dy else i0[..., 1]
                iz = i1[..., 2] if dz else i0[..., 2]
                wx = f[..., 0] if dx else 1 - f[..., 0]
                wy = f[..., 1] if dy else 1 - f[..., 1]
                wz = f[..., 2] if dz else 1 - f[..., 2]
                out = out + grid[ix, iy, iz] * wx * wy * wz
    return out


def cmb_texture(w=1024, h=512):
    """CMB のゆらぎに似た模様（青＝低温、赤＝高温）の正距円筒図。"""
    from PySide6.QtGui import QImage
    lat = np.linspace(math.pi / 2, -math.pi / 2, h)[:, None]
    lon = np.linspace(-math.pi, math.pi, w, endpoint=False)[None, :]
    p = np.stack([np.cos(lat) * np.cos(lon), np.cos(lat) * np.sin(lon), np.sin(lat) * np.ones_like(lon)],
                 axis=-1)
    field = np.zeros((h, w))
    # 角度で約1度の大きさのゆらぎが目立つように（本物の CMB の特徴）、いくつかの細かさを重ねる
    for k, (freq, amp) in enumerate([(4, 0.25), (9, 0.5), (18, 1.0), (36, 0.7), (60, 0.35)]):
        field += amp * _noise3(p, freq, 100 + k)
    field = (field - field.mean()) / field.std()
    t = np.clip(field / 3.0 * 0.5 + 0.5, 0, 1)
    stops = np.array([[0.0, 0.0, 0.25, 0.75], [0.35, 0.3, 0.6, 1.0], [0.5, 0.98, 0.95, 0.85],
                      [0.7, 1.0, 0.6, 0.2], [1.0, 0.75, 0.1, 0.05]])
    rgb = np.stack([np.interp(t, stops[:, 0], stops[:, c]) for c in (1, 2, 3)], axis=-1)
    arr = np.ascontiguousarray((rgb * 255).astype(np.uint8))
    img = QImage(arr.data, w, h, w * 3, QImage.Format_RGB888)
    return img.copy()
