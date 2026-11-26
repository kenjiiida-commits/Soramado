"""太陽系の天体データ。

半径・自転軸・自転角は IAU WGCCRE 報告（2015年版）の値を使う。
"""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(frozen=True)
class Body:
    key: str               # 内部名（astro.all_positions のキー）
    name: str              # 日本語名
    radius_km: float       # 平均半径
    color: tuple           # 遠くから見たときの点・軌道線の色 (r, g, b) 0〜1
    pole_ra: float         # 自転軸北極の赤経 [度]
    pole_dec: float        # 自転軸北極の赤緯 [度]
    w0: float              # 自転角 W の J2000 での値 [度]
    w_rate: float          # 自転角 W の変化率 [度/日]
    orbit: str | None      # 軌道線の種類（惑星の軌道要素名、"moon"、None）
    parent: str = "sun"
    ring: tuple | None = None   # 環の内側・外側の半径 [km]
    texture: str = ""            # 画像ファイル名（Solar System Scope の 2k 版）
    extra: dict = field(default_factory=dict)


BODIES = [
    Body("sun", "太陽", 695700.0, (1.0, 0.85, 0.45), 286.13, 63.87, 84.176, 14.1844000,
         None, parent="", texture="2k_sun.jpg"),
    Body("mercury", "水星", 2439.4, (0.72, 0.70, 0.68), 281.0103, 61.4155, 329.5988, 6.1385108,
         "mercury", texture="2k_mercury.jpg"),
    Body("venus", "金星", 6051.8, (0.95, 0.85, 0.60), 272.76, 67.16, 160.20, -1.4813688,
         "venus", texture="2k_venus_atmosphere.jpg"),
    Body("earth", "地球", 6371.0, (0.35, 0.60, 1.0), 0.0, 90.0, 190.147, 360.9856235,
         "emb", texture="2k_earth_daymap.jpg",
         extra={"night": "2k_earth_nightmap.jpg", "clouds": "2k_earth_clouds.jpg"}),
    Body("moon", "月", 1737.4, (0.80, 0.80, 0.78), 269.9949, 66.5392, 38.3213, 13.17635815,
         "moon", parent="earth", texture="2k_moon.jpg"),
    Body("mars", "火星", 3389.5, (0.95, 0.45, 0.25), 317.68143, 52.88650, 176.630, 350.89198226,
         "mars", texture="2k_mars.jpg"),
    Body("jupiter", "木星", 69911.0, (0.90, 0.75, 0.55), 268.056595, 64.495303, 284.95, 870.5360000,
         "jupiter", texture="2k_jupiter.jpg"),
    Body("saturn", "土星", 58232.0, (0.95, 0.85, 0.55), 40.589, 83.537, 38.90, 810.7939024,
         "saturn", ring=(74500.0, 136780.0), texture="2k_saturn.jpg",
         extra={"ring": "2k_saturn_ring_alpha.png"}),
    Body("uranus", "天王星", 25362.0, (0.60, 0.90, 0.95), 257.311, -15.175, 203.81, -501.1600928,
         "uranus", texture="2k_uranus.jpg"),
    Body("neptune", "海王星", 24622.0, (0.40, 0.55, 1.0), 299.36, 43.46, 249.978, 541.1397757,
         "neptune", texture="2k_neptune.jpg"),
]

def _add_satellites():
    from .satellites import SATELLITES
    parents = {b.key: b for b in BODIES}
    for sat in SATELLITES:
        par = parents[sat.parent]
        # 衛星は惑星と同じ向きの軸で、公転と同じ周期で自転する（いつも同じ面を惑星に向ける）
        BODIES.append(Body(sat.key, sat.name, sat.radius_km, sat.color, par.pole_ra, par.pole_dec,
                           0.0, 360.0 / sat.period, "sat", parent=sat.parent))


_add_satellites()

BY_KEY = {b.key: b for b in BODIES}

# 画像ファイルの入手先（Solar System Scope、CC BY 4.0）
TEXTURE_BASE_URL = "https://www.solarsystemscope.com/textures/download/"


def all_texture_files() -> list[str]:
    files = []
    for b in BODIES:
        if b.texture:
            files.append(b.texture)
        files.extend(b.extra.values())
    return files
