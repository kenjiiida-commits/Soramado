"""太陽系の外の惑星（系外惑星）。NASA Exoplanet Archive の表を、使う人のパソコンでダウンロードする。

データ: NASA Exoplanet Archive "Planetary Systems Composite Parameters"（pscomppars）
  https://exoplanetarchive.ipac.caltech.edu/
TAP（データベースへの問い合わせ）で必要な列だけを CSV で受け取り、恒星ごとにまとめて JSON で保存する。

惑星の軌道の向きは、ほとんどの惑星でわかっていない。表示では「地球から見て真横を向いている」
（トランジットが見える向き）として描く模式図にする。公転の位置（どこを回っているか）も模式。
"""

from __future__ import annotations

import csv
import io
import json
import math
import threading
import urllib.parse
import urllib.request
import zlib
from pathlib import Path

import numpy as np

from . import astro
from .cosmos import data_dir

COLUMNS = ["hostname", "pl_name", "pl_letter", "ra", "dec", "sy_dist", "sy_vmag", "sy_pnum",
           "st_teff", "st_rad", "st_mass", "st_spectype",
           "pl_rade", "pl_bmasse", "pl_orbper", "pl_orbsmax", "pl_orbeccen", "pl_eqt", "pl_insol",
           "discoverymethod", "disc_year"]
TAP = "https://exoplanetarchive.ipac.caltech.edu/TAP/sync"
URL = TAP + "?" + urllib.parse.urlencode({"query": f"select {','.join(COLUMNS)} from pscomppars",
                                          "format": "csv"})
EXO_FILE = "exoplanets.json"
PC_AU = 206264.806
LY_AU = 63241.077

METHOD_JA = {
    "Transit": "トランジット法",
    "Radial Velocity": "視線速度法（ドップラー法）",
    "Microlensing": "重力マイクロレンズ法",
    "Imaging": "直接撮像",
    "Transit Timing Variations": "トランジット時刻変化法",
    "Eclipse Timing Variations": "食の時刻変化法",
    "Orbital Brightness Modulation": "公転による明るさの変化",
    "Pulsar Timing": "パルサー・タイミング法",
    "Pulsation Timing Variations": "脈動の時刻変化法",
    "Astrometry": "位置天文法",
    "Disk Kinematics": "原始惑星系円盤の動き",
}
METHOD_NOTE = {
    "Transit": "惑星が恒星の前を横切るとき、恒星がわずかに暗くなるのをとらえる方法。惑星の大きさがわかる。",
    "Radial Velocity": "惑星に引っぱられて恒星がわずかにゆれるのを、光の色（波長）のずれでとらえる方法。惑星の重さの目安がわかる。",
    "Microlensing": "手前の恒星の重力がレンズになって奥の星が明るくなるとき、惑星の重力による乱れをとらえる方法。",
    "Imaging": "恒星の光をさえぎって、惑星そのものを撮影する方法。",
}

# 種類（色は表示用）
TYPES = [
    ("rocky", "岩石惑星（地球に近い大きさ）", (0.85, 0.65, 0.45)),
    ("superearth", "スーパーアース", (0.80, 0.80, 0.45)),
    ("subneptune", "ミニ・ネプチューン", (0.45, 0.85, 0.85)),
    ("neptune", "海王星型惑星", (0.40, 0.60, 1.00)),
    ("jupiter", "木星型惑星（巨大ガス惑星）", (1.00, 0.70, 0.40)),
    ("hotjupiter", "ホット・ジュピター", (1.00, 0.40, 0.30)),
    ("unknown", "種類不明", (0.70, 0.70, 0.70)),
]
TYPE_INDEX = {t[0]: i for i, t in enumerate(TYPES)}


def _f(v):
    try:
        x = float(v)
        return x if math.isfinite(x) else None
    except (TypeError, ValueError):
        return None


def planet_type(p: dict) -> str:
    r, m, a = p.get("rade"), p.get("masse"), p.get("a")
    if r is not None:
        t = "rocky" if r < 1.25 else "superearth" if r < 2.0 else "subneptune" if r < 4.0 else \
            "neptune" if r < 8.0 else "jupiter"
    elif m is not None:
        t = "rocky" if m < 2.0 else "superearth" if m < 10.0 else "neptune" if m < 50.0 else "jupiter"
    else:
        return "unknown"
    if t == "jupiter" and a is not None and a < 0.1:
        t = "hotjupiter"
    return t


def temp_color(teff) -> tuple:
    """恒星の表面温度からおおよその色。"""
    if teff is None:
        return (1.0, 0.95, 0.85)
    t = max(2500.0, min(teff, 30000.0))
    pts = [(2500, (1.0, 0.55, 0.30)), (3500, (1.0, 0.70, 0.45)), (4500, (1.0, 0.82, 0.62)),
           (5800, (1.0, 0.96, 0.90)), (7500, (0.90, 0.93, 1.0)), (10000, (0.75, 0.83, 1.0)),
           (30000, (0.62, 0.72, 1.0))]
    for (t0, c0), (t1, c1) in zip(pts, pts[1:]):
        if t <= t1:
            k = (t - t0) / (t1 - t0)
            return tuple(a + (b - a) * k for a, b in zip(c0, c1))
    return pts[-1][1]


# ---------------------------------------------------------------- 表の読み込み

def parse_csv(text: str) -> list[dict]:
    """CSV を恒星ごとの「惑星系」のリストにする。"""
    rows = csv.DictReader(io.StringIO(text))
    if rows.fieldnames is None or "pl_name" not in rows.fieldnames or "hostname" not in rows.fieldnames:
        raise ValueError("系外惑星の表の形式がちがいます（pl_name・hostname の列がありません）")
    systems: dict[str, dict] = {}
    for r in rows:
        host = (r.get("hostname") or "").strip()
        ra, dec, dist = _f(r.get("ra")), _f(r.get("dec")), _f(r.get("sy_dist"))
        if not host or ra is None or dec is None:
            continue
        s = systems.get(host)
        if s is None:
            s = systems[host] = {
                "host": host, "ra": ra, "dec": dec, "dist_pc": dist, "vmag": _f(r.get("sy_vmag")),
                "teff": _f(r.get("st_teff")), "srad": _f(r.get("st_rad")), "smass": _f(r.get("st_mass")),
                "spec": (r.get("st_spectype") or "").strip(), "planets": []}
        for k_dst, k_src in (("dist_pc", "sy_dist"), ("vmag", "sy_vmag"), ("teff", "st_teff"),
                             ("srad", "st_rad"), ("smass", "st_mass")):
            if s[k_dst] is None:
                s[k_dst] = _f(r.get(k_src))
        p = {"name": (r.get("pl_name") or "").strip(), "letter": (r.get("pl_letter") or "").strip(),
             "rade": _f(r.get("pl_rade")), "masse": _f(r.get("pl_bmasse")), "per": _f(r.get("pl_orbper")),
             "a": _f(r.get("pl_orbsmax")), "e": _f(r.get("pl_orbeccen")), "eqt": _f(r.get("pl_eqt")),
             "insol": _f(r.get("pl_insol")), "method": (r.get("discoverymethod") or "").strip(),
             "year": int(_f(r.get("disc_year")) or 0)}
        s["planets"].append(p)
    out = []
    for s in systems.values():
        if s["dist_pc"] is None:
            continue          # 距離がわからない恒星は、宇宙の中に置けないので省く
        s["planets"].sort(key=lambda p: (p["a"] if p["a"] is not None else 1e9, p["name"]))
        out.append(s)
    out.sort(key=lambda s: s["dist_pc"])
    return out


def save(systems: list[dict], path: Path):
    tmp = path.with_suffix(".part")
    tmp.write_text(json.dumps(systems, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
    tmp.replace(path)


# ---------------------------------------------------------------- 使うとき

class Exoplanets:
    def __init__(self, systems: list[dict]):
        self.systems = systems
        n = len(systems)
        ra = np.radians([s["ra"] for s in systems])
        dec = np.radians([s["dec"] for s in systems])
        d = np.array([s["dist_pc"] for s in systems]) * PC_AU
        eq = np.stack([np.cos(dec) * np.cos(ra), np.cos(dec) * np.sin(ra), np.sin(dec)], axis=1)
        self.pos = np.array([astro.equatorial_to_ecliptic(v) for v in eq]) * d[:, None] if n else np.zeros((0, 3))
        self.dist_au = d
        self.count_planets = sum(len(s["planets"]) for s in systems)
        for s in systems:
            self._fill(s)

    def __len__(self):
        return len(self.systems)

    # 足りない値を、わかっている値から見積もる
    def _fill(self, s):
        lum = None
        if s["srad"] and s["teff"]:
            lum = s["srad"] ** 2 * (s["teff"] / 5772.0) ** 4
        if s["vmag"] is not None and s["dist_pc"]:
            s["absmag"] = s["vmag"] - 5 * math.log10(s["dist_pc"] / 10.0)
        elif lum:
            s["absmag"] = 4.83 - 2.5 * math.log10(lum)
        else:
            s["absmag"] = 5.0
        if lum is None:
            lum = 10 ** (-0.4 * (s["absmag"] - 4.83))
        s["lum"] = lum
        mass = s["smass"] or 1.0
        for p in s["planets"]:
            if p["a"] is None and p["per"]:
                p["a"] = (mass * (p["per"] / 365.25) ** 2) ** (1 / 3)
            if p["per"] is None and p["a"]:
                p["per"] = 365.25 * math.sqrt(p["a"] ** 3 / mass)
            if p["insol"] is None and p["a"]:
                p["insol"] = lum / p["a"] ** 2
            p["type"] = planet_type(p)

    def name(self, i: int) -> str:
        return self.systems[i]["host"]

    def find(self, text: str) -> list[int]:
        t = text.strip().lower()
        if not t:
            return []
        exact, part = [], []
        for i, s in enumerate(self.systems):
            names = [s["host"].lower()] + [p["name"].lower() for p in s["planets"]]
            if t in names:
                exact.append(i)
            elif any(t in n for n in names):
                part.append(i)
            if len(exact) + len(part) > 60:
                break
        return (exact + part)[:30]

    def orbit_basis(self, i: int):
        """模式図の軌道面（地球から見て真横を向いた面）の2つの軸。"""
        u = self.pos[i] / np.linalg.norm(self.pos[i])
        n = np.cross(u, [0.0, 0.0, 1.0])
        if np.linalg.norm(n) < 1e-6:
            n = np.array([1.0, 0.0, 0.0])
        n /= np.linalg.norm(n)
        return u, np.cross(n, u)       # 軌道面は u（視線の方向）と、それに垂直な面内の方向で張る

    def planet_offsets(self, i: int, jd: float) -> list[np.ndarray]:
        """惑星の、恒星からの位置 [AU]（模式。公転の始まりの位置は名前から決める）。"""
        ex, ey = self.orbit_basis(i)
        out = []
        for p in self.systems[i]["planets"]:
            a = p["a"] or 0.0
            if a <= 0:
                out.append(None)
                continue
            e = min(p["e"] or 0.0, 0.9)
            phase0 = (zlib.crc32(p["name"].encode()) % 3600) / 3600 * 2 * math.pi
            m = phase0 + 2 * math.pi * (jd - 2451545.0) / (p["per"] or 365.25)
            ecc = astro._solve_kepler(m % (2 * math.pi), e)
            x, y = a * (math.cos(ecc) - e), a * math.sqrt(1 - e * e) * math.sin(ecc)
            out.append(ex * x + ey * y)
        return out

    def orbit_path(self, i: int, k: int, segments: int = 180):
        p = self.systems[i]["planets"][k]
        a = p["a"] or 0.0
        if a <= 0:
            return None
        e = min(p["e"] or 0.0, 0.9)
        ex, ey = self.orbit_basis(i)
        t = np.linspace(0, 2 * math.pi, segments + 1)
        x = a * (np.cos(t) - e)
        y = a * math.sqrt(1 - e * e) * np.sin(t)
        return ex * x[:, None] + ey * y[:, None]

    def system_size(self, i: int) -> float:
        a = [p["a"] for p in self.systems[i]["planets"] if p["a"]]
        return max(a) if a else 1.0

    def in_hz(self, p: dict) -> bool:
        """ハビタブルゾーン（水が液体でいられるかもしれない範囲）のおおよその目安。"""
        return p.get("insol") is not None and 0.2 <= p["insol"] <= 1.8

    def describe_system(self, i: int) -> list[str]:
        s = self.systems[i]
        ly = s["dist_pc"] * 3.26156
        out = [f"距離 {ly:,.1f} 光年" if ly < 100 else f"距離 {ly:,.0f} 光年"]
        if s["spec"]:
            out.append(f"スペクトル型 {s['spec']}")
        if s["teff"]:
            out.append(f"表面温度 {s['teff']:,.0f} K")
        if s["srad"]:
            out.append(f"半径 太陽の{s['srad']:.2f}倍")
        out.append(f"惑星 {len(s['planets'])} 個")
        return out


def describe_planet(p: dict) -> str:
    bits = [TYPES[TYPE_INDEX[p["type"]]][1]]
    if p["rade"]:
        bits.append(f"半径 地球の{p['rade']:.2f}倍" if p["rade"] < 10 else f"半径 地球の{p['rade']:.0f}倍")
    if p["masse"]:
        bits.append(f"質量 地球の{p['masse']:.2f}倍" if p["masse"] < 10 else f"質量 地球の{p['masse']:,.0f}倍")
    if p["per"]:
        per = p["per"]
        bits.append(f"公転周期 {per * 24:.1f} 時間" if per < 1 else
                    f"公転周期 {per:,.1f} 日" if per < 1000 else f"公転周期 {per / 365.25:,.1f} 年")
    if p["a"]:
        bits.append(f"恒星から {p['a']:.3f} AU" if p["a"] < 1 else f"恒星から {p['a']:.2f} AU")
    if p["eqt"]:
        bits.append(f"推定温度 約{p['eqt'] - 273:,.0f}℃")
    if p["method"]:
        bits.append(f"発見 {p['year']}年・{METHOD_JA.get(p['method'], p['method'])}" if p["year"] else
                    METHOD_JA.get(p["method"], p["method"]))
    return "、".join(bits)


_cache = {"mtime": None, "obj": None}


def load() -> Exoplanets | None:
    path = data_dir() / EXO_FILE
    if not path.is_file():
        return None
    mt = path.stat().st_mtime
    if _cache["mtime"] != mt:
        try:
            _cache["obj"] = Exoplanets(json.loads(path.read_text(encoding="utf-8")))
            _cache["mtime"] = mt
        except Exception:  # noqa: BLE001
            return None
    return _cache["obj"]


class ExoplanetDownloader:
    """別スレッドでダウンロードして保存する。file を渡すと、手元の CSV を読む。"""

    def __init__(self, file: str | None = None):
        self.done = False
        self.ok = False
        self.message = ""
        self.bytes = 0
        self.count = 0
        self.planets = 0
        self.file = file
        self._cancel = threading.Event()
        self._thread = threading.Thread(target=self._run, daemon=True)

    def start(self):
        self._thread.start()

    def cancel(self):
        self._cancel.set()

    def _run(self):
        try:
            if self.file:
                text = Path(self.file).read_text(encoding="utf-8", errors="replace")
            else:
                req = urllib.request.Request(URL, headers={"User-Agent": "Soramado (space simulator)"})
                res = urllib.request.urlopen(req, timeout=120)
                buf = io.BytesIO()
                while chunk := res.read(65536):
                    if self._cancel.is_set():
                        raise RuntimeError("キャンセルしました")
                    buf.write(chunk)
                    self.bytes += len(chunk)
                text = buf.getvalue().decode("utf-8", errors="replace")
            systems = parse_csv(text)
            if len(systems) < 100:
                raise RuntimeError(f"読み込めた惑星系が少なすぎます（{len(systems)} 個）")
            dest = data_dir()
            dest.mkdir(parents=True, exist_ok=True)
            save(systems, dest / EXO_FILE)
            self.count = len(systems)
            self.planets = sum(len(s["planets"]) for s in systems)
            self.ok = True
        except Exception as exc:  # noqa: BLE001
            self.message = str(exc)
        self.done = True
