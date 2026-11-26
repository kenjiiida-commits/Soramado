"""たくさんの小惑星・彗星（NASA JPL の軌道要素表を、使う人のパソコンでダウンロードする）。

データ: JPL Solar System Dynamics "Orbital Elements" の表
  番号付き小惑星 https://ssd.jpl.nasa.gov/dat/ELEMENTS.NUMBR.gz
  彗星           https://ssd.jpl.nasa.gov/dat/ELEMENTS.COMET
（どちらも固定幅のテキスト。見出しの下の「-----」の行で列の幅がわかる）

位置はケプラー運動で計算する（惑星の引力による変化は入れていない）。表の元期から
離れた年ほどずれる。描画のときは、数十万個の位置をグラフィックの側（シェーダー）で計算する。
"""

from __future__ import annotations

import gzip
import io
import math
import threading
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

import numpy as np

from .cosmos import data_dir

URL_NUMBERED = "https://ssd.jpl.nasa.gov/dat/ELEMENTS.NUMBR.gz"
URL_COMETS = "https://ssd.jpl.nasa.gov/dat/ELEMENTS.COMET"
MP_FILE = "minorplanets.npz"

REF_JD = 2461000.5          # 計算の基準にする日（2025年9月）。平均近点角はこの日の値にそろえる
K_GAUSS = 0.01720209895     # ガウスの引力定数 [rad/日]（1 AU の円軌道）

# 分類（番号は npz に保存する）
KINDS = [
    ("nea", "地球に近い小惑星", (1.00, 0.50, 0.25)),
    ("main", "小惑星帯の小惑星", (0.70, 0.72, 0.80)),
    ("hilda", "ヒルダ群", (0.95, 0.85, 0.40)),
    ("trojan", "木星のトロヤ群", (0.45, 0.95, 0.45)),
    ("centaur", "ケンタウルス族", (0.85, 0.50, 0.95)),
    ("tno", "太陽系外縁天体", (0.45, 0.70, 1.00)),
    ("other", "その他の小惑星", (0.60, 0.60, 0.60)),
    ("comet", "彗星", (0.40, 0.95, 1.00)),
]
KIND_NOTE = {
    "nea": "近日点距離が 1.3 AU より小さく、地球の軌道に近づく小惑星です。",
    "main": "火星と木星のあいだ（太陽から約2〜3.3 AU）を回る、もっとも多い小惑星のなかまです。",
    "hilda": "木星が太陽を2周するあいだに3周する（3:2 の共鳴）小惑星のなかまです。",
    "trojan": "木星と同じ軌道を、木星の60度前と60度後ろに集まって回る小惑星です。",
    "centaur": "木星と海王星のあいだを回る天体です。彗星と小惑星の中間のような性質があります。",
    "tno": "海王星より外側を回る天体です。冥王星もこのなかまです。",
    "other": "上のどのなかまにも入らない軌道の小惑星です。",
    "comet": "氷とちりでできた天体です。太陽に近づくと、とけたガスやちりで尾ができます。",
}


def classify(a, e, q):
    """軌道長半径 a・離心率 e・近日点距離 q から分類の番号を決める（numpy 配列）。"""
    k = np.full(len(a), 6, np.uint8)
    k[(a > 5.5) & (a < 30.1)] = 4
    k[a >= 30.1] = 5
    k[(a > 5.05) & (a < 5.35) & (e < 0.3)] = 3
    k[(a > 3.7) & (a < 4.2) & (e < 0.35)] = 2
    k[(a > 1.78) & (a < 3.4) & (q >= 1.3)] = 1
    k[q < 1.3] = 0
    return k


# ---------------------------------------------------------------- 表の読み込み

def _columns(lines):
    """見出しの行と「-----」の行から、列の名前と範囲を求める。戻り値: (列の辞書, データの始まりの行番号)。"""
    for n, line in enumerate(lines[:20]):
        s = line.rstrip()
        if s.startswith("-") and set(s) <= {"-", " "} and n > 0:
            head = lines[n - 1]
            spans = []
            i = 0
            while i < len(s):
                if s[i] == "-":
                    j = i
                    while j < len(s) and s[j] == "-":
                        j += 1
                    spans.append([i, j])
                    i = j
                else:
                    i += 1
            # 列の境目は、次の列の始まりの直前まで広げる（値が少しはみ出しても読めるように）
            for k in range(len(spans) - 1):
                spans[k][1] = spans[k + 1][0]
            spans[-1][1] = 10_000
            cols = {}
            for a, b in spans:
                name = head[a:b].strip()
                if name:
                    cols[name.lower()] = (a, b)
            return cols, n + 1
    raise ValueError("表の見出しが見つかりません")


def _tp_to_jd(s: str) -> float:
    """YYYYMMDD.DDDDD を JD にする。"""
    v = float(s)
    y = int(v // 10000)
    m = int(v // 100) % 100
    d = v - y * 10000 - m * 100
    base = datetime(y, m, 1, tzinfo=timezone.utc).timestamp() / 86400.0 + 2440587.5
    return base + d - 1.0


def parse_asteroids(text: str) -> dict:
    lines = text.splitlines()
    cols, start = _columns(lines)
    need = ["epoch", "a", "e", "i", "w", "node", "m", "h"]
    for c in need:
        if c not in cols:
            raise ValueError(f"列「{c}」がありません（見出し: {', '.join(cols)}）")
    sl = {c: slice(*cols[c]) for c in need}
    s_num = slice(*cols["num"]) if "num" in cols else None
    s_name = slice(*cols["name"]) if "name" in cols else (slice(*cols["designation"]) if "designation" in cols else None)
    num, name, out = [], [], {c: [] for c in need}
    for line in lines[start:]:
        if len(line) < 40:
            continue
        try:
            vals = [float(line[sl[c]]) for c in need]
        except ValueError:
            continue
        if not (0.0 < vals[1] and 0.0 <= vals[2] < 1.0):
            continue
        for c, v in zip(need, vals):
            out[c].append(v)
        try:
            num.append(int(line[s_num]) if s_num else 0)
        except ValueError:
            num.append(0)
        name.append(line[s_name].strip() if s_name else "")
    r = {c: np.array(v, np.float64) for c, v in out.items()}
    r["num"] = np.array(num, np.int32)
    r["name"] = name
    return r


def parse_comets(text: str) -> dict:
    lines = text.splitlines()
    cols, start = _columns(lines)
    need = ["q", "e", "i", "w", "node", "tp"]
    for c in need:
        if c not in cols:
            raise ValueError(f"列「{c}」がありません（見出し: {', '.join(cols)}）")
    name_cols = [v for c, v in cols.items() if "name" in c or c.startswith("num")]
    sl = {c: slice(*cols[c]) for c in need}
    out = {c: [] for c in need}
    names = []
    for line in lines[start:]:
        if len(line) < 40:
            continue
        try:
            q, e, i, w, node = (float(line[sl[c]]) for c in ("q", "e", "i", "w", "node"))
            tp = _tp_to_jd(line[sl["tp"]].split()[0])
        except (ValueError, IndexError):
            continue
        if not (0.0 < q and 0.0 <= e < 0.985):
            continue          # 放物線・双曲線に近い彗星は、ずっと遠くにいるので省く
        for c, v in zip(need, (q, e, i, w, node, tp)):
            out[c].append(v)
        if name_cols:
            a0 = min(c[0] for c in name_cols)
            b0 = max(c[1] for c in name_cols)
            names.append(" ".join(line[a0:b0].split()))
        else:
            names.append("")
    r = {c: np.array(v, np.float64) for c, v in out.items()}
    r["name"] = names
    return r


def build_catalog(ast: dict, com: dict | None) -> dict:
    """読み込んだ表を、保存する形（基準日の平均近点角など）にまとめる。"""
    a = ast["a"]
    e = ast["e"]
    n = K_GAUSS / a ** 1.5
    epoch = ast["epoch"] + 2400000.5 if np.median(ast["epoch"]) < 2.0e6 else ast["epoch"]
    m0 = np.radians(ast["m"]) + n * (REF_JD - epoch)
    i, w, node, h = ast["i"], ast["w"], ast["node"], ast["h"]
    names = list(ast["name"])
    num = ast["num"]
    if com is not None and len(com["q"]):
        ca = com["q"] / (1.0 - com["e"])
        cn = K_GAUSS / ca ** 1.5
        a = np.concatenate([a, ca])
        e = np.concatenate([e, com["e"]])
        n = np.concatenate([n, cn])
        m0 = np.concatenate([m0, cn * (REF_JD - com["tp"])])
        i = np.concatenate([i, com["i"]])
        w = np.concatenate([w, com["w"]])
        node = np.concatenate([node, com["node"]])
        h = np.concatenate([h, np.full(len(ca), 99.0)])
        num = np.concatenate([num, np.zeros(len(ca), np.int32)])
        names += list(com["name"])
        ncom = len(ca)
    else:
        ncom = 0
    kind = classify(a, e, a * (1 - e))
    if ncom:
        kind[-ncom:] = 7
    return {"a": a, "e": e, "n": n, "m0": np.mod(m0, 2 * math.pi), "i": i, "w": w, "node": node,
            "h": h.astype(np.float32), "num": num, "kind": kind,
            "name": np.array([s.encode("utf-8")[:40] for s in names], dtype="S40")}


def save_catalog(cat: dict, path: Path):
    tmp = path.with_suffix(".part.npz")
    np.savez_compressed(tmp, **cat)
    tmp.replace(path)


# ---------------------------------------------------------------- 使うとき

class MinorPlanets:
    def __init__(self, d):
        self.a = d["a"]
        self.e = d["e"]
        self.n = d["n"]
        self.m0 = d["m0"]
        self.i = d["i"]
        self.w = d["w"]
        self.node = d["node"]
        self.h = d["h"]
        self.num = d["num"]
        self.kind = d["kind"]
        self.names = d["name"]
        self._low = None
        ii, ww, oo = np.radians(self.i), np.radians(self.w), np.radians(self.node)
        cw, sw, co, so, ci, si = np.cos(ww), np.sin(ww), np.cos(oo), np.sin(oo), np.cos(ii), np.sin(ii)
        self.P = np.stack([cw * co - sw * so * ci, cw * so + sw * co * ci, sw * si], axis=1)
        self.Q = np.stack([-sw * co - cw * so * ci, -sw * so + cw * co * ci, cw * si], axis=1)

    def __len__(self):
        return len(self.a)

    def count(self, kind: int) -> int:
        return int(np.count_nonzero(self.kind == kind))

    def vertex_data(self) -> np.ndarray:
        """シェーダーに渡す: P(3) Q(3) a e M0 n 色(3)。"""
        col = np.array([k[2] for k in KINDS], np.float32)[self.kind]
        # 明るい（大きい）ものほど明るく描く。彗星は等級がないので中くらい
        h = np.where(self.h > 50, 13.0, self.h)
        br = np.clip(0.18 * 10 ** (-0.2 * (h - 15.0)), 0.10, 1.6).astype(np.float32)
        br[self.kind == 7] = 0.9
        col *= br[:, None]
        return np.column_stack([self.P, self.Q, self.a, self.e, self.m0, self.n, col]).astype(np.float32)

    def _anomaly(self, idx, jd):
        m = np.mod(self.m0[idx] + self.n[idx] * (jd - REF_JD), 2 * math.pi)
        e = self.e[idx]
        ecc = np.where(e > 0.8, math.pi, m + e * np.sin(m))
        for _ in range(12 if np.ndim(ecc) and len(ecc) > 1000 else 40):
            ecc = ecc - (ecc - e * np.sin(ecc) - m) / (1.0 - e * np.cos(ecc))
        return ecc

    def positions(self, jd: float, idx=None) -> np.ndarray:
        """日心黄道座標（J2000）[AU]。"""
        if idx is None:
            idx = slice(None)
        ecc = self._anomaly(idx, jd)
        a, e = self.a[idx], self.e[idx]
        xp = a * (np.cos(ecc) - e)
        yp = a * np.sqrt(1 - e * e) * np.sin(ecc)
        return self.P[idx] * xp[..., None] + self.Q[idx] * yp[..., None]

    def position(self, i: int, jd: float) -> np.ndarray:
        return self.positions(jd, np.array([i]))[0]

    def orbit_path(self, i: int, segments: int = 720) -> np.ndarray:
        ecc = np.linspace(0, 2 * math.pi, segments + 1)
        a, e = self.a[i], self.e[i]
        xp = a * (np.cos(ecc) - e)
        yp = a * math.sqrt(1 - e * e) * np.sin(ecc)
        return self.P[i] * xp[:, None] + self.Q[i] * yp[:, None]

    def name(self, i: int) -> str:
        s = self.names[i].decode("utf-8", "replace")
        if self.kind[i] == 7:
            return s
        return f"({self.num[i]}) {s}" if self.num[i] else s

    def kind_name(self, i: int) -> str:
        return KINDS[int(self.kind[i])][1]

    def kind_note(self, i: int) -> str:
        return KIND_NOTE[KINDS[int(self.kind[i])][0]]

    def diameter_km(self, i: int) -> float:
        """絶対等級 H から直径を見積もる（反射率 0.14 と仮定）。わからないときは 0。"""
        h = float(self.h[i])
        if h > 50:
            return 0.0
        return 1329.0 / math.sqrt(0.14) * 10 ** (-h / 5.0)

    def find(self, text: str) -> list[int]:
        """名前か番号で探す（最大30件）。"""
        t = text.strip()
        if not t:
            return []
        if t.isdigit():
            hit = np.nonzero(self.num == int(t))[0]
            return [int(x) for x in hit[:30]]
        key = t.lower().encode("utf-8")
        if getattr(self, "_low", None) is None:
            self._low = np.char.lower(self.names)
        low = self._low
        exact = np.nonzero(low == key)[0]
        part = np.nonzero(np.char.find(low, key) >= 0)[0]
        out = list(dict.fromkeys([int(x) for x in exact] + [int(x) for x in part[:60]]))
        return out[:30]

    def describe(self, i: int, jd: float) -> list[str]:
        a, e = float(self.a[i]), float(self.e[i])
        parts = [self.kind_name(i)]
        d = self.diameter_km(i)
        if d > 0:
            parts.append(f"直径 約{d:,.0f} km（推定）" if d >= 10 else
                         (f"直径 約{d:,.1f} km（推定）" if d >= 1 else f"直径 約{d * 1000:,.0f} m（推定）"))
        parts.append(f"公転周期 {a ** 1.5:,.1f} 年" if a ** 1.5 < 1000 else f"公転周期 約{a ** 1.5:,.0f} 年")
        parts.append(f"太陽からの距離 {a * (1 - e):.2f}〜{a * (1 + e):.2f} AU")
        parts.append(f"軌道傾斜角 {float(self.i[i]):.1f}°")
        return parts


_cache = {"mtime": None, "obj": None}


def load() -> MinorPlanets | None:
    path = data_dir() / MP_FILE
    if not path.is_file():
        return None
    mt = path.stat().st_mtime
    if _cache["mtime"] != mt:
        try:
            with np.load(path) as d:
                _cache["obj"] = MinorPlanets({k: d[k] for k in d.files})
            _cache["mtime"] = mt
        except Exception:  # noqa: BLE001
            return None
    return _cache["obj"]


# ---------------------------------------------------------------- ダウンロード

class MinorPlanetDownloader:
    """別スレッドで JPL の表をダウンロードして npz に保存する。画面からは状態を見に来る。

    files を渡すと、ダウンロードの代わりに手元のファイル（.gz でもよい）を読む。
    """

    def __init__(self, files: list[str] | None = None):
        self.done = False
        self.ok = False
        self.message = ""
        self.stage = ""
        self.bytes = 0
        self.count = 0
        self.files = files
        self._cancel = threading.Event()
        self._thread = threading.Thread(target=self._run, daemon=True)

    def start(self):
        self._thread.start()

    def cancel(self):
        self._cancel.set()

    def _get(self, url) -> bytes:
        req = urllib.request.Request(url, headers={"User-Agent": "Soramado (space simulator)"})
        res = urllib.request.urlopen(req, timeout=60)
        buf = io.BytesIO()
        while chunk := res.read(262144):
            if self._cancel.is_set():
                raise RuntimeError("キャンセルしました")
            buf.write(chunk)
            self.bytes += len(chunk)
        return buf.getvalue()

    @staticmethod
    def _text(raw: bytes) -> str:
        if raw[:2] == b"\x1f\x8b":
            raw = gzip.decompress(raw)
        return raw.decode("latin-1")

    def _run(self):
        try:
            if self.files:
                ast, com = None, None
                for f in self.files:
                    self.stage = f"{Path(f).name} を読んでいます"
                    text = self._text(Path(f).read_bytes())
                    cols, _ = _columns(text.splitlines())
                    if "tp" in cols:
                        com = parse_comets(text)
                    else:
                        ast = parse_asteroids(text)
                if ast is None:
                    raise RuntimeError("小惑星の表（ELEMENTS.NUMBR）が選ばれていません")
            else:
                self.stage = "小惑星の表をダウンロードしています"
                text = self._text(self._get(URL_NUMBERED))
                self.stage = "小惑星の表を読んでいます"
                ast = parse_asteroids(text)
                del text
                com = None
                try:
                    self.stage = "彗星の表をダウンロードしています"
                    com = parse_comets(self._text(self._get(URL_COMETS)))
                except Exception as exc:  # noqa: BLE001
                    if self._cancel.is_set():
                        raise
                    self.message = f"彗星の表は読めませんでした（{exc}）"
            if len(ast["a"]) < 1000:
                raise RuntimeError(f"読み込めた小惑星が少なすぎます（{len(ast['a'])} 個）")
            self.stage = "保存しています"
            cat = build_catalog(ast, com)
            dest = data_dir()
            dest.mkdir(parents=True, exist_ok=True)
            save_catalog(cat, dest / MP_FILE)
            self.count = len(cat["a"])
            self.ok = True
        except Exception as exc:  # noqa: BLE001
            self.message = str(exc)
        self.done = True
