"""探査機の航路。

探査機が実際に惑星や小惑星のそばを通った日付と、その日の天体の位置を「通過点」とし、
通過点のあいだをつないで航路を作る。

・エンジンを使わず惑星の引力で進む区間（ボイジャー、ニュー・ホライズンズの惑星間）は、
  「ランベルト問題」（2点と所要時間から、太陽の引力だけで進む軌道を求める）で計算する。
・イオンエンジンで少しずつ加速する区間（はやぶさ・はやぶさ2）は、出発天体の軌道から
  到着天体の軌道へなめらかに移っていく近似で描く。
・最後の惑星を通過したあと太陽系の外へ向かう区間は、2026年11月時点の距離・方向へ
  まっすぐ進むとして描く。

どれもおおよその航路で、実際の航路（NASA JPL Horizons など）とは細かい点で異なる。
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from datetime import datetime, timezone

import numpy as np

from . import astro

K = 0.01720209895            # ガウス重力定数
MU = K * K                    # 太陽の重力定数 [AU^3/日^2]


def _jd(y, m, d):
    return astro.jd_from_datetime(datetime(y, m, d, tzinfo=timezone.utc))


# ---------------------------------------------------------------- 2体問題

def _stumpff(z):
    if z > 1e-8:
        s = math.sqrt(z)
        return (1 - math.cos(s)) / z, (s - math.sin(s)) / (s ** 3)
    if z < -1e-8:
        s = math.sqrt(-z)
        return (math.cosh(s) - 1) / (-z), (math.sinh(s) - s) / (s ** 3)
    return 0.5, 1.0 / 6.0


def propagate(r0, v0, dt):
    """位置 r0・速度 v0 から dt 日後の位置（万有変数による2体問題）。"""
    r0n = np.linalg.norm(r0)
    vr0 = np.dot(r0, v0) / r0n
    alpha = 2.0 / r0n - np.dot(v0, v0) / MU
    sq = math.sqrt(MU)
    chi = sq * abs(alpha) * dt if abs(alpha) > 1e-12 else sq * dt / r0n
    for _ in range(80):
        z = alpha * chi * chi
        c, s = _stumpff(z)
        f = (r0n * vr0 / sq * chi * chi * c + (1 - alpha * r0n) * chi ** 3 * s + r0n * chi - sq * dt)
        df = (r0n * vr0 / sq * chi * (1 - alpha * chi * chi * s) + (1 - alpha * r0n) * chi * chi * c + r0n)
        step = f / df
        chi -= step
        if abs(step) < 1e-12:
            break
    z = alpha * chi * chi
    c, s = _stumpff(z)
    fl = 1 - chi * chi / r0n * c
    gl = dt - chi ** 3 / sq * s
    return fl * r0 + gl * v0


def lambert(r1, r2, tof):
    """r1 から r2 へ tof 日で行く軌道の出発速度（順行、1周未満）。"""
    r1n, r2n = np.linalg.norm(r1), np.linalg.norm(r2)
    cos_d = np.dot(r1, r2) / (r1n * r2n)
    dtheta = math.acos(max(-1.0, min(1.0, cos_d)))
    if np.cross(r1, r2)[2] < 0:          # 順行（反時計回り）になるよう遠回りを選ぶ
        dtheta = 2 * math.pi - dtheta
    a = math.sin(dtheta) * math.sqrt(r1n * r2n / (1 - math.cos(dtheta)))

    def y(z):
        c, s = _stumpff(z)
        return r1n + r2n + a * (z * s - 1) / math.sqrt(c)

    def time_of(z):
        c, s = _stumpff(z)
        yy = y(z)
        if yy < 0:
            return -1.0
        return ((yy / c) ** 1.5 * s + a * math.sqrt(yy)) / math.sqrt(MU)

    lo, hi = -2000.0, 4 * math.pi ** 2 - 1e-6    # 負の側は双曲線軌道（速い移動）
    while time_of(lo) < 0 or y(lo) < 0:          # y が負になる範囲を避ける
        lo += 0.1
    for _ in range(200):
        mid = (lo + hi) / 2
        if time_of(mid) > tof:
            hi = mid
        else:
            lo = mid
    z = (lo + hi) / 2
    c, s = _stumpff(z)
    yy = y(z)
    f = 1 - yy / r1n
    g = a * math.sqrt(yy / MU)
    return (r2 - f * r1) / g


# ---------------------------------------------------------------- 探査機

@dataclass
class Leg:
    kind: str          # "lambert" 弾道, "loop" 地球に戻る1年周回, "blend" イオンエンジン, "stay" 滞在, "out" 太陽系の外へ
    t0: float
    t1: float
    a: str = ""        # 出発天体
    b: str = ""        # 到着天体
    data: dict = field(default_factory=dict)


@dataclass
class Spacecraft:
    key: str
    name: str
    color: tuple
    events: list            # (JD, 説明)
    legs: list
    note: str = ""
    table: str = ""         # JPL Horizons の位置の表（data/spacecraft_paths.npz の名前）
    extrapolate: bool = False   # 表の終わりのあと、同じ速さでまっすぐ進み続ける（太陽系の外へ向かうもの）


def _body_pos(name: str, jd: float) -> np.ndarray:
    from . import smallbodies as sb
    if name == "earth":
        emb = astro.planet_position("emb", jd)
        return emb - astro.moon_geocentric(jd) / (1 + astro.EARTH_MOON_MASS_RATIO)
    if name in sb.BY_KEY:
        return sb.position(sb.BY_KEY[name], jd)
    return astro.planet_position(name, jd)


def _radec_dir(ra_h, dec_d):
    ra, dec = math.radians(ra_h * 15), math.radians(dec_d)
    return astro.equatorial_to_ecliptic(np.array([math.cos(dec) * math.cos(ra), math.cos(dec) * math.sin(ra),
                                                  math.sin(dec)]))


ANCHOR_JD = _jd(2026, 11, 26)


def _flyby_chain(points):
    legs = []
    for (ta, a), (tb, b) in zip(points, points[1:]):
        legs.append(Leg("lambert", ta, tb, a, b))
    return legs


def _T(key, name, color, table, events, note, extrapolate=False):
    return Spacecraft(key, name, color, [(_jd(*d), t) for d, t in events], [], note, table, extrapolate)


SPACECRAFT = [
    _T("sc:voyager1", "ボイジャー1号", (1.0, 0.85, 0.35), "voyager1",
       [((1977, 9, 5), "打ち上げ"), ((1979, 3, 5), "木星に最接近"), ((1980, 11, 12), "土星に最接近"),
        ((1990, 2, 14), "太陽系の家族写真（ペイル・ブルー・ドット）を撮影"),
        ((2012, 8, 25), "太陽圏を出て星間空間へ"), ((2026, 11, 18), "地球から1光日（約173AU）に到達")],
       "人類が作ったもので最も遠くにある探査機。1977年に打ち上げられ、木星と土星を調べたあと、"
       "2012年に太陽圏を出て星間空間に入った。2026年11月、地球から光で1日かかる距離に達した。", True),
    _T("sc:voyager2", "ボイジャー2号", (0.45, 0.85, 1.0), "voyager2",
       [((1977, 8, 20), "打ち上げ"), ((1979, 7, 9), "木星に最接近"), ((1981, 8, 25), "土星に最接近"),
        ((1986, 1, 24), "天王星に最接近"), ((1989, 8, 25), "海王星に最接近"), ((2018, 11, 5), "太陽圏を出て星間空間へ")],
       "木星・土星・天王星・海王星の4つの惑星を訪れた、ただ一つの探査機。天王星と海王星に近づいたのは、"
       "今もボイジャー2号だけ。2018年に太陽圏を出た。", True),
    _T("sc:pioneer10", "パイオニア10号", (0.85, 0.65, 0.45), "pioneer10",
       [((1972, 3, 3), "打ち上げ"), ((1973, 12, 4), "初めて木星に接近"), ((2003, 1, 23), "最後の信号を受信")],
       "初めて小惑星帯を通りぬけ、初めて木星に近づいた探査機。人類からのメッセージを描いた金属板を積んでいる。"
       "2003年に信号が途絶え、今もおうし座の方向へ進み続けている。", True),
    _T("sc:pioneer11", "パイオニア11号", (0.75, 0.75, 0.55), "pioneer11",
       [((1973, 4, 6), "打ち上げ"), ((1974, 12, 3), "木星に接近"), ((1979, 9, 1), "初めて土星に接近"),
        ((1995, 9, 30), "運用を終える")],
       "初めて土星に近づいた探査機。木星の強い引力で進路を大きく曲げて土星へ向かった。"
       "今はわし座の方向へ進み続けている。", True),
    _T("sc:galileo", "ガリレオ", (0.95, 0.6, 0.3), "galileo",
       [((1989, 10, 18), "打ち上げ"), ((1990, 2, 10), "金星スイングバイ"), ((1990, 12, 8), "地球スイングバイ"),
        ((1991, 10, 29), "小惑星ガスプラに接近"), ((1992, 12, 8), "地球スイングバイ（2回目）"),
        ((1993, 8, 28), "小惑星イダに接近（衛星ダクチルを発見）"), ((1995, 12, 7), "木星を回りはじめる・小型探査機が木星の大気へ"),
        ((2003, 9, 21), "木星の大気に突入して運用を終える")],
       "初めて木星を回る軌道に入った NASA の探査機。エウロパの氷の下に海があるらしいことや、"
       "イオの火山の活動を詳しく調べた。最後は衛星を汚さないように木星に突入した。"),
    _T("sc:cassini", "カッシーニ", (0.9, 0.8, 0.55), "cassini",
       [((1997, 10, 15), "打ち上げ"), ((1998, 4, 26), "金星スイングバイ"), ((1999, 6, 24), "金星スイングバイ（2回目）"),
        ((1999, 8, 18), "地球スイングバイ"), ((2000, 12, 30), "木星スイングバイ"), ((2004, 7, 1), "土星を回りはじめる"),
        ((2005, 1, 14), "小型探査機ホイヘンスがタイタンに着陸"), ((2017, 9, 15), "土星に突入して運用を終える（グランド・フィナーレ）")],
       "NASA と ESA の土星探査機。13年間土星を回り、エンケラドスの南極から水が噴き出していることを見つけた。"
       "ホイヘンスは、外惑星の衛星に初めて着陸した探査機。"),
    _T("sc:newhorizons", "ニュー・ホライズンズ", (0.70, 1.0, 0.60), "newhorizons",
       [((2006, 1, 19), "打ち上げ"), ((2007, 2, 28), "木星の引力で加速"),
        ((2015, 7, 14), "冥王星に最接近"), ((2019, 1, 1), "カイパーベルト天体アロコスに接近")],
       "冥王星を初めて間近から調べた NASA の探査機。2015年に冥王星、2019年にカイパーベルト天体アロコスに接近した。", True),
    _T("sc:juno", "ジュノー", (0.95, 0.85, 0.75), "juno",
       [((2011, 8, 5), "打ち上げ"), ((2013, 10, 9), "地球スイングバイ"), ((2016, 7, 5), "木星を回りはじめる")],
       "木星の極の上を通る細長い軌道で回り、雲の下の様子や、強い磁場、極のオーロラを調べている NASA の探査機。"
       "太陽電池で動く探査機として、初めて木星まで行った。"),
    _T("sc:parker", "パーカー・ソーラー・プローブ", (1.0, 0.45, 0.25), "parker",
       [((2018, 8, 12), "打ち上げ"), ((2018, 10, 3), "金星スイングバイ（1回目）"),
        ((2024, 11, 6), "金星スイングバイ（7回目・最後）"), ((2024, 12, 24), "太陽に最も近づく（太陽の表面から約610万km）")],
       "太陽のすぐ近くまで行って、コロナや太陽風を直接調べる NASA の探査機。金星の引力で何度も軌道を小さくし、"
       "人類が作ったもので最も太陽に近づき、最も速く動いた。"),
    _T("sc:messenger", "メッセンジャー", (0.75, 0.75, 0.85), "messenger",
       [((2004, 8, 3), "打ち上げ"), ((2005, 8, 2), "地球スイングバイ"), ((2006, 10, 24), "金星スイングバイ"),
        ((2008, 1, 14), "水星に接近（1回目）"), ((2011, 3, 18), "初めて水星を回りはじめる"), ((2015, 4, 30), "水星に落下して運用を終える")],
       "初めて水星を回った NASA の探査機。水星の北極の、太陽の光が当たらないクレーターの底に氷があることを確かめた。"),
    _T("sc:bepicolombo", "ベピコロンボ", (0.55, 0.85, 0.75), "bepicolombo",
       [((2018, 10, 20), "打ち上げ"), ((2020, 4, 10), "地球スイングバイ"), ((2020, 10, 15), "金星スイングバイ"),
        ((2021, 10, 1), "水星に接近（1回目）")],
       "日本（JAXA）とヨーロッパ（ESA）が共同で水星へ送った探査機。日本の「みお」とヨーロッパの探査機を"
       "合体させて運び、水星を2機で調べる。地球・金星・水星のスイングバイを重ねて水星へ近づいた。"),
    _T("sc:rosetta", "ロゼッタ", (0.6, 0.75, 1.0), "rosetta",
       [((2004, 3, 2), "打ち上げ"), ((2007, 2, 25), "火星スイングバイ"), ((2008, 9, 5), "小惑星シュテインスに接近"),
        ((2010, 7, 10), "小惑星ルテティアに接近"), ((2014, 8, 6), "チュリュモフ・ゲラシメンコ彗星に到着"),
        ((2014, 11, 12), "着陸機フィラエが彗星に着陸"), ((2016, 9, 30), "彗星に着陸して運用を終える")],
       "初めて彗星のまわりを回り、着陸機を下ろしたヨーロッパ（ESA）の探査機。彗星が太陽に近づいて"
       "ガスやちりを噴き出すようすを、2年間そばで見続けた。"),
    _T("sc:dawn", "ドーン", (0.65, 0.9, 0.95), "dawn",
       [((2007, 9, 27), "打ち上げ"), ((2009, 2, 17), "火星スイングバイ"), ((2011, 7, 16), "小惑星ベスタを回りはじめる"),
        ((2012, 9, 5), "ベスタを出発"), ((2015, 3, 6), "準惑星ケレスを回りはじめる"), ((2018, 11, 1), "運用を終える")],
       "イオンエンジンで、小惑星ベスタと準惑星ケレスの2つを順に回った NASA の探査機。ケレスでは、"
       "クレーターの中の明るい点が、塩の積もったものであることが分かった。"),
    _T("sc:osirisrex", "オシリス・レックス", (0.9, 0.7, 1.0), "osirisrex",
       [((2016, 9, 8), "打ち上げ"), ((2017, 9, 22), "地球スイングバイ"), ((2018, 12, 3), "小惑星ベンヌに到着"),
        ((2020, 10, 20), "ベンヌの表面の試料を採取"), ((2021, 5, 10), "ベンヌを出発"),
        ((2023, 9, 24), "試料のカプセルを地球に届ける（その後、アポフィスをめざす）")],
       "小惑星ベンヌの試料を持ち帰った NASA の探査機。はやぶさ2とならぶ、小惑星の試料の持ち帰り。"
       "カプセルを届けたあとは「オシリス・アペックス」と名前を変え、2029年に地球に近づく小惑星アポフィスへ向かっている。"),
    _T("sc:europaclipper", "エウロパ・クリッパー", (0.55, 0.8, 1.0), "europaclipper",
       [((2024, 10, 14), "打ち上げ"), ((2025, 3, 1), "火星スイングバイ"), ((2026, 12, 3), "地球スイングバイ（予定）"),
        ((2030, 4, 11), "木星に到着（予定）")],
       "木星の衛星エウロパの、厚い氷の下の海に、生命がすめる環境があるかを調べる NASA の探査機。"
       "木星を回りながら、エウロパのそばを何十回も通る予定。2026年12月以降の航路は予定の計算。"),
    _T("sc:juice", "ジュース（JUICE）", (0.95, 0.75, 0.55), "juice",
       [((2023, 4, 14), "打ち上げ"), ((2024, 8, 19), "月・地球スイングバイ"), ((2025, 8, 31), "金星スイングバイ"),
        ((2031, 7, 20), "木星に到着（予定）")],
       "ヨーロッパ（ESA）の木星の氷衛星探査機。ガニメデ・カリスト・エウロパを調べ、最後はガニメデを回る予定。"
       "日本も観測装置づくりに参加している。これからの航路は予定の計算。"),
    _T("sc:lucy", "ルーシー", (1.0, 0.85, 0.55), "lucy",
       [((2021, 10, 16), "打ち上げ"), ((2022, 10, 16), "地球スイングバイ"), ((2023, 11, 1), "小惑星ディンキネシュに接近"),
        ((2024, 12, 12), "地球スイングバイ（2回目）"), ((2025, 4, 20), "小惑星ドナルドジョハンソンに接近"),
        ((2027, 8, 12), "木星のトロヤ群に到着（予定）")],
       "木星と同じ軌道を回る「トロヤ群」の小惑星を、初めて調べる NASA の探査機。12年かけて8つの小惑星を訪れる。"
       "名前は、人類の祖先の化石「ルーシー」から。これからの航路は予定の計算。"),
    _T("sc:psyche", "サイキ", (0.8, 0.8, 0.95), "psyche",
       [((2023, 10, 13), "打ち上げ"), ((2026, 5, 15), "火星スイングバイ")],
       "金属でできているらしい小惑星プシケ（サイキ）を調べる NASA の探査機。惑星の芯（核）がむき出しになった"
       "ものかもしれず、惑星の中心を知る手がかりになる。2029年に到着予定（この画面では2029年2月までの航路）。"),
    _T("sc:hayabusa2", "はやぶさ2", (1.0, 0.70, 0.90), "hayabusa2",
       [((2014, 12, 3), "打ち上げ"), ((2015, 12, 3), "地球スイングバイ"), ((2018, 6, 27), "リュウグウに到着"),
        ((2019, 2, 22), "1回目のタッチダウン"), ((2019, 7, 11), "2回目のタッチダウン"), ((2019, 11, 13), "リュウグウを出発"),
        ((2020, 12, 6), "カプセルを地球に届ける（その後、延長ミッションへ）")],
       "はやぶさの後継機。小惑星リュウグウに2回タッチダウンし、人工クレーターを作って地下の物質も採取した。"
       "2020年に試料の入ったカプセルを地球に届け、その後は別の小惑星をめざす延長ミッションを続けている。"),
    Spacecraft(
        "sc:hayabusa", "はやぶさ", (1.0, 0.55, 0.55),
        [(_jd(2003, 5, 9), "打ち上げ"), (_jd(2004, 5, 19), "地球スイングバイ"),
         (_jd(2005, 9, 12), "イトカワに到着"), (_jd(2005, 11, 26), "イトカワに着陸"),
         (_jd(2007, 4, 25), "地球への帰路につく"), (_jd(2010, 6, 13), "地球に帰還（カプセル回収）")],
        [Leg("loop", _jd(2003, 5, 9), _jd(2004, 5, 19), "earth", "earth"),
         Leg("blend", _jd(2004, 5, 19), _jd(2005, 9, 12), "earth", "itokawa"),
         Leg("stay", _jd(2005, 9, 12), _jd(2007, 4, 25), "itokawa", "itokawa"),
         Leg("blend", _jd(2007, 4, 25), _jd(2010, 6, 13), "itokawa", "earth")],
        "日本の小惑星探査機。イオンエンジンで小惑星イトカワへ向かい、2005年に着陸。数々のトラブルを乗り越えて"
        "2010年に地球へ帰還し、世界で初めて小惑星の表面の粒子を持ち帰った。"),
]

BY_KEY = {s.key: s for s in SPACECRAFT}


# ---------------------------------------------------------------- 位置の計算

_cache: dict = {}
_TABLES = None


def _table(sc: Spacecraft):
    """JPL Horizons の位置の表 (JD の配列, 位置[AU] の配列)。"""
    global _TABLES
    if _TABLES is None:
        from pathlib import Path
        f = Path(__file__).resolve().parent / "data" / "spacecraft_paths.npz"
        d = np.load(f)
        _TABLES = {k[:-3]: (d[k], d[k[:-3] + "_xyz"].astype(np.float64)) for k in d.files if k.endswith("_jd")}
    return _TABLES[sc.table]


END_OUT = _jd(2100, 1, 1)


def _table_pos(sc: Spacecraft, jd: float):
    t, x = _table(sc)
    if jd < t[0]:
        return None
    if jd > t[-1]:
        if not sc.extrapolate or jd > END_OUT:
            return None
        v = (x[-1] - x[-2]) / (t[-1] - t[-2])
        return x[-1] + v * (jd - t[-1])
    i = int(np.searchsorted(t, jd))
    if i <= 0:
        return x[0].copy()
    # 3次のエルミート補間（速さは前後の点から）で、なめらかにつなぐ
    t0, t1 = t[i - 1], t[i]
    h = t1 - t0
    u = (jd - t0) / h
    p0, p1 = x[i - 1], x[i]
    m0 = (x[i] - x[i - 2]) / (t[i] - t[i - 2]) * h if i >= 2 else p1 - p0
    m1 = (x[i + 1] - x[i - 1]) / (t[i + 1] - t[i - 1]) * h if i + 1 < len(t) else p1 - p0
    u2, u3 = u * u, u * u * u
    return (2 * u3 - 3 * u2 + 1) * p0 + (u3 - 2 * u2 + u) * m0 + (-2 * u3 + 3 * u2) * p1 + (u3 - u2) * m1


def _lambert_state(leg: Leg):
    key = (leg.a, leg.b, leg.t0, leg.t1)
    if key not in _cache:
        r1 = _body_pos(leg.a, leg.t0)
        r2 = _body_pos(leg.b, leg.t1)
        _cache[key] = (r1, lambert(r1, r2, leg.t1 - leg.t0))
    return _cache[key]


def _out_line(leg: Leg):
    key = ("out", leg.a, leg.t0)
    if key not in _cache:
        p0 = _body_pos(leg.a, leg.t0)
        d = _radec_dir(*leg.data["dir"])
        p_now = d * leg.data["dist"]
        _cache[key] = (p0, p_now)
    return _cache[key]


def _polar(p):
    return math.hypot(p[0], p[1]), math.atan2(p[1], p[0]), p[2]


def leg_position(leg: Leg, jd: float) -> np.ndarray:
    tau = (jd - leg.t0) / (leg.t1 - leg.t0)
    if leg.kind == "lambert":
        r1, v1 = _lambert_state(leg)
        return propagate(r1, v1, jd - leg.t0)
    if leg.kind == "stay":
        return _body_pos(leg.a, jd)
    if leg.kind == "loop":
        # 地球からいったん離れて、1年後にまた地球に戻ってくる（イオンエンジンでの加速）
        e = _body_pos("earth", jd)
        return e * (1.0 + 0.12 * math.sin(math.pi * min(max(tau, 0), 1)))
    if leg.kind == "blend":
        s = tau * tau * (3 - 2 * tau)
        pa, pb = _body_pos(leg.a, jd), _body_pos(leg.b, jd)
        ra, tha, za = _polar(pa)
        rb, thb, zb = _polar(pb)
        dth = (thb - tha + math.pi) % (2 * math.pi) - math.pi
        r = ra + (rb - ra) * s
        th = tha + dth * s
        return np.array([r * math.cos(th), r * math.sin(th), za + (zb - za) * s])
    if leg.kind == "out":
        p0, p_now = _out_line(leg)
        # 2026年11月の位置を通り、毎年 speed AU ずつ遠ざかる
        years = (jd - ANCHOR_JD) / 365.25
        dist_now = leg.data["dist"]
        target = p_now / np.linalg.norm(p_now) * (dist_now + leg.data["speed"] * years)
        if jd >= ANCHOR_JD:
            return target
        # 最後の通過点から今の位置まで、なめらかにつなぐ
        u = (jd - leg.t0) / (ANCHOR_JD - leg.t0)
        return p0 + (p_now - p0) * u
    raise ValueError(leg.kind)


def span(sc: Spacecraft):
    if sc.table:
        t, _x = _table(sc)
        return float(t[0]), (END_OUT if sc.extrapolate else float(t[-1]))
    return sc.legs[0].t0, sc.legs[-1].t1


def position(sc: Spacecraft, jd: float):
    """探査機の位置 [AU]。打ち上げ前・航路の終わりより後は None。"""
    if sc.table:
        return _table_pos(sc, jd)
    t0, t1 = span(sc)
    if jd < t0 or jd > t1:
        return None
    for leg in sc.legs:
        if leg.t0 <= jd <= leg.t1:
            return leg_position(leg, jd)
    return None


def path(sc: Spacecraft, until: float | None = None, per_leg: int = 300) -> np.ndarray:
    if sc.table:
        t, x = _table(sc)
        pts = x
        if sc.extrapolate and until and until > t[-1]:
            pts = np.vstack([x, _table_pos(sc, min(until, END_OUT))[None, :]])
        return pts
    pts = []
    for leg in sc.legs:
        t1 = leg.t1
        if leg.kind == "out":
            t1 = min(leg.t1, until if until else ANCHOR_JD)
        if t1 <= leg.t0:
            break
        for t in np.linspace(leg.t0, t1, per_leg):
            pts.append(leg_position(leg, t))
    return np.array(pts)


def last_event(sc: Spacecraft, jd: float) -> str:
    done = [txt for t, txt in sc.events if t <= jd]
    return done[-1] if done else "打ち上げ前"


def _english_names():
    from .i18n import EN_MODE, name_en
    if EN_MODE:
        for x in SPACECRAFT:
            object.__setattr__(x, "name", name_en(x.key, x.name))


_english_names()
