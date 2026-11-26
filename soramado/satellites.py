"""惑星の衛星。

火星・木星・土星・天王星のおもな衛星は、PyEphem（XEphem の衛星理論）で位置を計算する。
PyEphem は「地球から見て惑星からどれだけ東西・南北・手前奥にずれているか」を返すので、
それを宇宙空間のベクトルに直して使う（光が届くのにかかる時間の分だけ、地球から見た姿になる）。

海王星のトリトンと、木星・土星の小さな衛星（v1.3 で追加）は PyEphem にないので、
NASA JPL Horizons で求めた 2026年11月26日の接触軌道要素（惑星中心・J2000 黄道座標）から、
ケプラー運動で計算する（2026年から離れるほど、おおよその位置になる）。
（JPL の "Planetary Satellite Mean Elements" の表は、そのままでは位置の向きが合わなかったので使わない）
"""

from __future__ import annotations

import math
from dataclasses import dataclass

import numpy as np

from . import astro

try:
    import ephem
except ImportError:      # PyEphem が無いときは衛星を出さない
    ephem = None

JD_EPOCH = 2451545.0


@dataclass(frozen=True)
class Satellite:
    key: str
    name: str
    parent: str
    a_km: float
    e: float
    w: float          # 近点引数 [度]
    m: float          # 平均近点角 [度]
    i: float          # 軌道傾斜角 [度]
    node: float       # 昇交点黄経 [度]
    period: float     # 公転周期 [日]
    p_apsis: float    # 近点の歳差周期 [年]（0 = なし）
    p_node: float     # 交点の歳差周期 [年]（0 = なし）
    pole_ra: float    # 基準面の極 [度]
    pole_dec: float
    radius_km: float
    color: tuple
    epoch: float = 2451545.0      # 軌道要素の元期 [JD]


HZ_EPOCH = 2461370.5            # Horizons から取った軌道要素の元期（2026-11-26 0h TDB）


def _h(key, name, parent, a, e, i, node, w, m, period, radius, color):
    """Horizons の黄道座標の接触軌道要素から衛星を作る（歳差なし）。"""
    return Satellite(key, name, parent, a, e, w, m, i, node, period, 0.0, 0.0, 270.0, 66.560708, radius, color,
                     HZ_EPOCH)


# 赤道面基準の衛星は、惑星の自転軸（IAU 2015）を極に使う
_URANUS = (257.311, -15.175)
_NEPTUNE = (299.36, 43.46)

SATELLITES = [
    Satellite("phobos", "フォボス", "mars", 9375, 0.015, 216.3, 189.7, 1.1, 169.2, 0.3187, 1.1, 2.3,
              317.7, 52.9, 11.08, (0.55, 0.50, 0.45)),
    Satellite("deimos", "ダイモス", "mars", 23457, 0.000, 0.0, 205.0, 1.8, 54.3, 1.2625, 0.0, 56.2,
              316.6, 53.5, 6.2, (0.62, 0.57, 0.50)),
    Satellite("io", "イオ", "jupiter", 421800, 0.004, 49.1, 330.9, 0.0, 0.0, 1.762732, 1.333, 0.0,
              268.1, 64.5, 1821.6, (0.95, 0.85, 0.45)),
    Satellite("europa", "エウロパ", "jupiter", 671100, 0.009, 45.0, 345.4, 0.5, 184.0, 3.525463, 1.394, 30.202,
              268.1, 64.5, 1560.8, (0.92, 0.88, 0.80)),
    Satellite("ganymede", "ガニメデ", "jupiter", 1070400, 0.001, 198.3, 324.8, 0.2, 58.5, 7.155588, 68.301, 137.812,
              268.2, 64.6, 2631.2, (0.70, 0.66, 0.60)),
    Satellite("callisto", "カリスト", "jupiter", 1882700, 0.007, 43.8, 87.4, 0.3, 309.1, 16.690440, 277.921, 577.264,
              268.7, 64.8, 2410.3, (0.50, 0.46, 0.42)),
    Satellite("mimas", "ミマス", "saturn", 186000, 0.020, 160.4, 275.3, 1.6, 66.2, 0.942422, 0.493, 0.986,
              40.6, 83.5, 198.2, (0.80, 0.80, 0.80)),
    Satellite("enceladus", "エンケラドゥス", "saturn", 238400, 0.005, 119.5, 57.0, 0.0, 0.0, 1.370218, 2.916, 0.0,
              40.6, 83.5, 252.1, (0.97, 0.98, 1.0)),
    Satellite("tethys", "テティス", "saturn", 295000, 0.001, 335.3, 0.0, 1.1, 273.0, 1.887802, 0.005, 4.982,
              40.6, 83.5, 531.1, (0.90, 0.90, 0.92)),
    Satellite("dione", "ディオネ", "saturn", 377700, 0.002, 116.0, 212.0, 0.0, 0.0, 2.736916, 11.698, 0.0,
              40.6, 83.5, 561.4, (0.85, 0.85, 0.86)),
    Satellite("rhea", "レア", "saturn", 527200, 0.001, 44.3, 31.5, 0.3, 133.7, 4.517503, 33.939, 35.775,
              40.6, 83.5, 763.8, (0.82, 0.82, 0.82)),
    Satellite("titan", "タイタン", "saturn", 1221900, 0.029, 78.3, 11.7, 0.3, 78.6, 15.945448, 346.680, 687.370,
              36.4, 84.0, 2574.7, (0.90, 0.65, 0.30)),
    Satellite("iapetus", "イアペトゥス", "saturn", 3561700, 0.028, 254.5, 74.8, 7.6, 86.5, 79.331002, 1662.900, 3130.302,
              288.7, 78.9, 734.5, (0.70, 0.62, 0.52)),
    # ---- ここから v1.3 で追加した衛星は、NASA JPL Horizons の接触軌道要素（2026-11-26 0h TDB、
    #      惑星中心・J2000 黄道座標）から計算する。軌道の向きは固定（歳差は入れていない）なので、
    #      2026年から離れるほど位置はおおよそになる
    _h("metis", "メティス", "jupiter", 128878.1, 0.006314, 2.2086, 337.7936, 99.4922, 4.8989, 0.29478, 21.5, (0.55, 0.45, 0.38)),
    _h("adrastea", "アドラステア", "jupiter", 129873.1, 0.006845, 2.2129, 337.6463, 117.7432, 4.7618, 0.29826, 8.2, (0.55, 0.45, 0.38)),
    _h("amalthea", "アマルテア", "jupiter", 181997.8, 0.006494, 1.8429, 339.4776, 354.1677, 16.1420, 0.498179, 83.5, (0.7, 0.38, 0.25)),
    _h("thebe", "テーベ", "jupiter", 222422.5, 0.019959, 2.4004, 4.1845, 291.2435, 3.9397, 0.674536, 49.3, (0.6, 0.45, 0.38)),
    _h("themisto", "テミスト", "jupiter", 7388221.1, 0.270480, 44.5877, 185.9965, 247.1994, 140.5914, 129.87, 4.0, (0.6, 0.58, 0.55)),
    _h("leda", "レダ", "jupiter", 11189308.7, 0.151243, 28.3145, 182.6651, 329.8723, 129.7694, 240.82, 10.8, (0.6, 0.58, 0.55)),
    _h("himalia", "ヒマリア", "jupiter", 11407203.9, 0.158990, 28.6525, 34.2330, 52.0525, 93.3095, 250.56, 85.0, (0.62, 0.6, 0.56)),
    _h("lysithea", "リシテア", "jupiter", 11761884.6, 0.115281, 27.2091, 332.3290, 121.1202, 258.1660, 259.2, 21.0, (0.6, 0.58, 0.55)),
    _h("elara", "エララ", "jupiter", 11748691.9, 0.219732, 29.2067, 82.5988, 225.2999, 223.3175, 259.64, 43.0, (0.62, 0.6, 0.56)),
    _h("ananke", "アナンケ", "jupiter", 21292722.4, 0.110018, 148.8361, 106.4751, 137.9148, 159.8528, 629.77, 14.5, (0.55, 0.52, 0.5)),
    _h("carme", "カルメ", "jupiter", 22952671.9, 0.241969, 162.1572, 233.0577, 158.9121, 356.0857, 734.17, 23.0, (0.55, 0.52, 0.5)),
    _h("pasiphae", "パシファエ", "jupiter", 23469705.3, 0.411961, 152.9121, 78.9420, 282.7469, 6.3695, 743.63, 30.0, (0.55, 0.52, 0.5)),
    _h("sinope", "シノーペ", "jupiter", 24290064.7, 0.202192, 159.4750, 52.5180, 79.5354, 167.0504, 758.9, 19.0, (0.55, 0.52, 0.5)),
    _h("callirrhoe", "カリロエ", "jupiter", 24534818.6, 0.310312, 148.6419, 37.3738, 113.0829, 113.7835, 758.77, 4.3, (0.55, 0.52, 0.5)),
    _h("pan", "パン", "saturn", 134263.7, 0.005056, 28.0513, 169.5236, 221.4577, 359.9809, 0.575051, 14.0, (0.82, 0.8, 0.76)),
    _h("atlas", "アトラス", "saturn", 138324.3, 0.006063, 28.0514, 169.5305, 268.0215, 0.2562, 0.601692, 15.1, (0.82, 0.8, 0.76)),
    _h("prometheus", "プロメテウス", "saturn", 140028.7, 0.006051, 28.0561, 169.5098, 12.2533, 341.4023, 0.612986, 43.1, (0.82, 0.8, 0.76)),
    _h("pandora", "パンドラ", "saturn", 142345.3, 0.000543, 28.0251, 169.4337, 41.4434, 302.1880, 0.628804, 40.7, (0.82, 0.8, 0.76)),
    _h("epimetheus", "エピメテウス", "saturn", 152020.8, 0.013462, 27.7626, 169.0884, 258.7538, 2.1902, 0.694333, 58.1, (0.8, 0.78, 0.74)),
    _h("janus", "ヤヌス", "saturn", 152065.0, 0.010240, 27.8866, 169.5418, 160.4796, 24.2873, 0.69466, 89.5, (0.8, 0.78, 0.74)),
    _h("aegaeon", "アイガイオン", "saturn", 168029.4, 0.002987, 28.0519, 169.5250, 298.5549, 358.7699, 0.80812, 0.3, (0.8, 0.78, 0.74)),
    _h("methone", "メトネ", "saturn", 194683.1, 0.002736, 28.0322, 169.5166, 263.9336, 23.6408, 1.009573, 1.6, (0.85, 0.85, 0.85)),
    _h("anthe", "アンテ", "saturn", 198113.6, 0.003337, 28.0590, 169.4919, 326.6033, 18.1383, 1.0365, 1.0, (0.85, 0.85, 0.85)),
    _h("pallene", "パレネ", "saturn", 212706.5, 0.005478, 28.0297, 169.1423, 129.6647, 34.4858, 1.153745, 2.5, (0.85, 0.85, 0.85)),
    _h("telesto", "テレスト", "saturn", 294976.6, 0.001197, 28.8906, 171.2631, 106.8259, 3.1442, 1.887802, 12.4, (0.9, 0.9, 0.9)),
    _h("calypso", "カリプソ", "saturn", 294958.5, 0.001118, 27.0938, 172.0199, 16.6117, 337.0099, 1.887802, 10.7, (0.9, 0.9, 0.9)),
    _h("helene", "ヘレネ", "saturn", 377830.6, 0.007768, 28.2539, 169.6411, 277.8089, 285.7391, 2.736915, 18.0, (0.9, 0.9, 0.9)),
    _h("polydeuces", "ポリデウケス", "saturn", 377860.8, 0.019957, 28.0787, 169.1511, 99.0189, 353.5374, 2.736915, 1.3, (0.9, 0.9, 0.9)),
    Satellite("hyperion", "ヒペリオン", "saturn", 1481500, 0.105, 214.0, 122.9, 0.6, 87.1, 21.276658, 0.0, 0.0,
              40.2, 83.6, 135.0, (0.78, 0.68, 0.55)),
    _h("kiviuq", "キビウク", "saturn", 11331094.9, 0.148572, 49.1287, 345.1836, 85.3505, 138.2465, 449.22, 8.0, (0.6, 0.55, 0.5)),
    _h("ijiraq", "イジラク", "saturn", 11339532.9, 0.433351, 48.8613, 141.9364, 68.3340, 314.7160, 451.42, 6.0, (0.6, 0.55, 0.5)),
    _h("phoebe", "フェーベ", "saturn", 12890874.8, 0.166398, 172.8345, 271.5011, 11.8296, 356.9819, 545.09, 106.5, (0.4, 0.38, 0.36)),
    _h("paaliaq", "パーリアク", "saturn", 15062225.4, 0.571500, 43.1883, 331.7908, 244.5221, 69.6096, 686.95, 11.0, (0.6, 0.55, 0.5)),
    _h("skathi", "スカディ", "saturn", 15637039.5, 0.275436, 148.6545, 297.0918, 222.2332, 287.3841, 728.2, 4.0, (0.55, 0.52, 0.5)),
    _h("albiorix", "アルビオリクス", "saturn", 16531877.4, 0.601755, 33.3775, 71.7119, 98.8236, 213.3847, 783.45, 16.0, (0.6, 0.5, 0.45)),
    _h("bebhionn", "ベフィオン", "saturn", 17074871.0, 0.462635, 42.1121, 181.8850, 36.6702, 72.9911, 834.84, 3.0, (0.6, 0.5, 0.45)),
    _h("erriapus", "エリアプス", "saturn", 17603516.5, 0.401067, 39.6290, 114.6024, 315.6472, 41.7031, 871.19, 5.0, (0.6, 0.5, 0.45)),
    _h("siarnaq", "シャルナク", "saturn", 17663151.4, 0.455260, 44.6800, 31.7373, 86.5832, 189.7808, 895.53, 19.5, (0.6, 0.55, 0.5)),
    _h("tarvos", "タルボス", "saturn", 18405991.3, 0.555280, 41.0915, 56.7748, 317.9451, 128.1532, 926.23, 7.5, (0.6, 0.5, 0.45)),
    _h("mundilfari", "ムンディルファリ", "saturn", 18365680.6, 0.242744, 168.6068, 104.2451, 344.1547, 195.9077, 952.77, 3.5, (0.55, 0.52, 0.5)),
    _h("narvi", "ナルビ", "saturn", 19116437.8, 0.277896, 139.9743, 196.8797, 205.5495, 26.2206, 1003.86, 3.5, (0.55, 0.52, 0.5)),
    _h("ymir", "イミル", "saturn", 22589219.3, 0.296247, 172.3969, 242.4349, 87.1565, 24.7871, 1315.14, 9.0, (0.55, 0.52, 0.5)),
    Satellite("miranda", "ミランダ", "uranus", 129846, 0.001, 154.8, 73.0, 4.4, 100.9, 1.413479, 8.939, 17.787,
              *_URANUS, 235.8, (0.75, 0.75, 0.75)),
    Satellite("ariel", "アリエル", "uranus", 190929, 0.001, 9.6, 193.5, 0.0, 0.0, 2.520379, 28.901, 0.0,
              *_URANUS, 578.9, (0.80, 0.80, 0.80)),
    Satellite("umbriel", "ウンブリエル", "uranus", 265986, 0.004, 183.4, 253.0, 0.1, 174.8, 4.144177, 64.126, 129.945,
              *_URANUS, 584.7, (0.55, 0.55, 0.55)),
    Satellite("titania", "チタニア", "uranus", 436298, 0.002, 184.0, 68.1, 0.1, 29.5, 8.705869, 579.928, 1644.649,
              *_URANUS, 788.9, (0.75, 0.73, 0.72)),
    Satellite("oberon", "オベロン", "uranus", 583511, 0.002, 132.2, 143.6, 0.1, 76.8, 13.463237, 158.604, 192.798,
              *_URANUS, 761.4, (0.68, 0.65, 0.63)),
    _h("triton", "トリトン", "neptune", 354766.4, 0.000137, 129.1231, 222.8992, 102.1143, 301.3586, 5.876854, 1353.4,
       (0.85, 0.80, 0.78)),
]

BY_KEY = {s.key: s for s in SATELLITES}

# 「おもな衛星」（大きさで分ける）。惑星を拡大表示するときの間隔の計算などに使う
MAJOR_KM = 150.0


def is_major(s: Satellite) -> bool:
    return s.radius_km >= MAJOR_KM


def is_irregular(s: Satellite) -> bool:
    return s.a_km > 5e6 and s.parent in ("jupiter", "saturn")
BY_PARENT: dict[str, list[Satellite]] = {}
for _s in SATELLITES:
    BY_PARENT.setdefault(_s.parent, []).append(_s)


def _plane_axes(s: Satellite):
    """基準面の軸（x=ICRF赤道上の昇交点方向, z=極）を黄道座標で。"""
    ra, dec = math.radians(s.pole_ra), math.radians(s.pole_dec)
    pole = np.array([math.cos(dec) * math.cos(ra), math.cos(dec) * math.sin(ra), math.sin(dec)])
    x = np.cross([0.0, 0.0, 1.0], pole)
    x /= np.linalg.norm(x)
    y = np.cross(pole, x)
    to_ecl = astro.equatorial_to_ecliptic
    return to_ecl(x), to_ecl(y), to_ecl(pole)


_AXES = {s.key: _plane_axes(s) for s in SATELLITES}


def _elements(s: Satellite, jd: float):
    t = jd - s.epoch
    w_rate = 360.0 / (s.p_apsis * 365.25) if s.p_apsis > 0 else 0.0
    n_rate = -360.0 / (s.p_node * 365.25) if s.p_node > 0 else 0.0
    w = s.w + w_rate * t
    node = s.node + n_rate * t
    # 公転周期は恒星周期なので、平均近点角の進み方は近点・交点の歳差の分だけ遅い
    m = s.m + (360.0 / s.period - w_rate - n_rate) * t
    return w, node, m


def _rotate(s, w, node, xp, yp):
    """軌道面内の座標 → 黄道座標 [km]。"""
    ax, ay, az = _AXES[s.key]
    wr, o, i = math.radians(w), math.radians(node), math.radians(s.i)
    cw, sw, co, so, ci, si = math.cos(wr), math.sin(wr), math.cos(o), math.sin(o), math.cos(i), math.sin(i)
    x = (cw * co - sw * so * ci) * xp + (-sw * co - cw * so * ci) * yp
    y = (cw * so + sw * co * ci) * xp + (-sw * so + cw * co * ci) * yp
    z = (sw * si) * xp + (cw * si) * yp
    return np.multiply.outer(x, ax) + np.multiply.outer(y, ay) + np.multiply.outer(z, az)


_EPHEM_MOON = {"phobos": "Phobos", "deimos": "Deimos", "io": "Io", "europa": "Europa",
               "ganymede": "Ganymede", "callisto": "Callisto", "mimas": "Mimas", "enceladus": "Enceladus",
               "tethys": "Tethys", "dione": "Dione", "rhea": "Rhea", "titan": "Titan", "iapetus": "Iapetus", "hyperion": "Hyperion",
               "miranda": "Miranda", "ariel": "Ariel", "umbriel": "Umbriel", "titania": "Titania",
               "oberon": "Oberon"}
_EPHEM_PLANET = {"mars": "Mars", "jupiter": "Jupiter", "saturn": "Saturn", "uranus": "Uranus"}


def uses_ephem(key: str) -> bool:
    """PyEphem の精密な理論で位置を計算している衛星か。"""
    return ephem is not None and key in _EPHEM_MOON


def available() -> bool:
    return ephem is not None


def _ephem_offsets(jd: float) -> dict:
    """PyEphem で、全衛星の惑星からのベクトル [AU]（黄道座標）を求める。"""
    out = {}
    date = ephem.Date(jd - 2415020.0)
    planets = {}
    for key, cls in _EPHEM_PLANET.items():
        p = getattr(ephem, cls)(date)
        ra, dec = float(p.a_ra), float(p.a_dec)
        toward = -np.array([math.cos(dec) * math.cos(ra), math.cos(dec) * math.sin(ra), math.sin(dec)])
        east = np.array([-math.sin(ra), math.cos(ra), 0.0])
        north = np.cross(-toward, east)
        planets[key] = (ra, dec, float(p.earth_distance), toward, east, north)
    for key, cls in _EPHEM_MOON.items():
        s = BY_KEY[key]
        ra, dec, d_au, toward, east, north = planets[s.parent]
        m = getattr(ephem, cls)(date)
        dra = (float(m.a_ra) - ra + math.pi) % (2 * math.pi) - math.pi
        dra *= math.cos(dec)
        ddec = float(m.a_dec) - dec
        # x, y, z は惑星半径単位。空での見かけのずれから縮尺を求め、奥行き z にも使う
        k = math.hypot(dra, ddec) * d_au / max(math.hypot(m.x, m.y), 1e-12)
        v = dra * d_au * east + ddec * d_au * north + m.z * k * toward
        out[key] = astro.equatorial_to_ecliptic(v)
    return out


def offset(s: Satellite, jd: float) -> np.ndarray:
    """惑星から衛星までのベクトル [AU]（黄道座標）。"""
    if ephem is not None and s.key in _EPHEM_MOON:
        return _ephem_offsets(jd)[s.key]
    return _mean_offset(s, jd)


def _mean_offset(s: Satellite, jd: float) -> np.ndarray:
    w, node, m = _elements(s, jd)
    ecc = astro._solve_kepler(math.radians(m % 360.0), s.e)
    xp = s.a_km * (math.cos(ecc) - s.e)
    yp = s.a_km * math.sqrt(1 - s.e * s.e) * math.sin(ecc)
    return _rotate(s, w, node, xp, yp) / astro.AU_KM


def orbit_paths(jd: float, segments: int = 180) -> dict:
    """全衛星の軌道（1周ぶん）の点列 [AU]（惑星中心）。"""
    out = {}
    if ephem is not None:
        samples = {k: [] for k in _EPHEM_MOON}
        # 周期がばらばらなので、衛星ごとにその周期で 1 周ぶんを計算する
        for key in _EPHEM_MOON:
            s = BY_KEY[key]
            for i in range(segments + 1):
                t = jd + s.period * (i / segments - 0.5)
                samples[key].append(_single(key, t))
        out.update({k: np.array(v) for k, v in samples.items()})
    for s in SATELLITES:
        if s.key not in out:
            out[s.key] = _mean_orbit(s, jd, segments)
    return out


def _single(key: str, jd: float) -> np.ndarray:
    s = BY_KEY[key]
    date = ephem.Date(jd - 2415020.0)
    p = getattr(ephem, _EPHEM_PLANET[s.parent])(date)
    m = getattr(ephem, _EPHEM_MOON[key])(date)
    ra, dec = float(p.a_ra), float(p.a_dec)
    toward = -np.array([math.cos(dec) * math.cos(ra), math.cos(dec) * math.sin(ra), math.sin(dec)])
    east = np.array([-math.sin(ra), math.cos(ra), 0.0])
    north = np.cross(-toward, east)
    d_au = float(p.earth_distance)
    dra = ((float(m.a_ra) - ra + math.pi) % (2 * math.pi) - math.pi) * math.cos(dec)
    ddec = float(m.a_dec) - dec
    k = _radius_au(s.parent, jd)
    return astro.equatorial_to_ecliptic(dra * d_au * east + ddec * d_au * north + m.z * k * toward)


_K_CACHE = {}


def _radius_au(parent: str, jd: float) -> float:
    """PyEphem の衛星の x, y, z（惑星の半径が単位）を AU に直す係数。

    以前は衛星ごとに「見かけの離れ角 ÷ x,y」で求めていたが、衛星が惑星の真ん前や真後ろ
    （x, y がほぼ 0）にいると割り算が不安定になり、軌道の線に段差ができていた。
    そこで、惑星ごとに離れた位置の衛星で何度か測った中央値を使う。
    """
    k = _K_CACHE.get(parent)
    if k is not None:
        return k
    vals = []
    for key, s in BY_KEY.items():
        if s.parent != parent or key not in _EPHEM_MOON:
            continue
        for i in range(24):
            date = ephem.Date(jd + s.period * i / 24 - 2415020.0)
            p = getattr(ephem, _EPHEM_PLANET[parent])(date)
            m = getattr(ephem, _EPHEM_MOON[key])(date)
            r = math.hypot(m.x, m.y)
            if r < 1.0:
                continue
            ra, dec = float(p.a_ra), float(p.a_dec)
            dra = ((float(m.a_ra) - ra + math.pi) % (2 * math.pi) - math.pi) * math.cos(dec)
            ddec = float(m.a_dec) - dec
            vals.append(math.hypot(dra, ddec) * float(p.earth_distance) / r)
    k = float(np.median(vals)) if vals else 60000.0 / astro.AU_KM
    _K_CACHE[parent] = k
    return k


def _mean_orbit(s: Satellite, jd: float, segments: int) -> np.ndarray:
    w, node, _ = _elements(s, jd)
    ecc = np.linspace(0, 2 * math.pi, segments + 1)
    xp = s.a_km * (np.cos(ecc) - s.e)
    yp = s.a_km * math.sqrt(1 - s.e * s.e) * np.sin(ecc)
    return _rotate(s, w, node, xp, yp) / astro.AU_KM


def add_positions(pos: dict, jd: float) -> dict:
    eo = _ephem_offsets(jd) if ephem is not None else {}
    for s in SATELLITES:
        if s.key in eo:
            pos[s.key] = pos[s.parent] + eo[s.key]
        elif ephem is not None or s.key not in _EPHEM_MOON:
            pos[s.key] = pos[s.parent] + _mean_offset(s, jd)
        else:
            pos[s.key] = pos[s.parent] + _mean_offset(s, jd)
    return pos
