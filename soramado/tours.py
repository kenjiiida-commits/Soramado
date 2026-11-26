"""ツアー（決まった順に宇宙を巡る）。

1つの場面（Step）は、どこを見るか・どれくらいの距離から見るか・字幕で構成する。
「今夜の星空」だけは、その日の夜に見える惑星を計算して場面を作る。
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timedelta

from . import astro
from .bodies import BY_KEY
from .galaxies import LY_AU


@dataclass
class Step:
    text: str
    target: str = "sun"
    dist: float | None = None          # 視点の距離 [AU]（None は天体ごとの標準）
    dist_mult: float | None = None     # 標準の距離の何倍か
    ground: bool = False
    az: float = 180.0                  # 地上モードで見る方位・高度・視野 [度]
    alt: float = 30.0
    fov: float = 90.0
    look: str | None = None            # 地上モードで向く天体
    seconds: float = 9.0               # 次の場面へ進むまでの時間
    extra: dict = field(default_factory=dict)


def solar_system() -> list[Step]:
    return [
        Step("太陽系めぐりへようこそ。まずは、わたしたちの太陽系の中心、太陽です。", "sun", dist=0.05),
        Step("太陽から3番目の惑星、地球。わたしたちの住む星です。", "earth"),
        Step("地球のまわりを回る月。いつも同じ面を地球に向けています。", "moon"),
        Step("赤い惑星、火星。2つの小さな衛星フォボスとダイモスをもっています。", "mars", dist_mult=6),
        Step("太陽系最大の惑星、木星。まわりを回っているのは、ガリレオが見つけた4つの大きな衛星です。",
             "jupiter", dist_mult=60, seconds=11),
        Step("木星の衛星イオ。太陽系でもっとも火山活動が活発な天体です。", "io"),
        Step("美しい環をもつ土星。環は無数の氷のかけらでできています。", "saturn", dist_mult=2.2, seconds=11),
        Step("土星最大の衛星タイタン。濃い大気と、メタンの湖があります。", "titan"),
        Step("横倒しで回る天王星。", "uranus"),
        Step("太陽系でいちばん外側の惑星、海王星。", "neptune"),
        Step("かつて第9惑星とされた冥王星。今は準惑星に分類されています。", "pluto"),
        Step("太陽系の全体です。惑星は太陽のまわりを、ほぼ同じ平面の上で回っています。", "sun", dist=80.0,
             seconds=11),
    ]


def scale_of_universe() -> list[Step]:
    au = 1.0
    return [
        Step("宇宙の大きさを感じる旅に出かけましょう。出発点は地球です。", "earth", seconds=8),
        Step("地球と月。光の速さなら、わずか1.3秒の距離です。", "earth", dist=0.006),
        Step("太陽系の惑星たち。海王星まで、光でも約4時間かかります。", "sun", dist=60 * au, seconds=10),
        Step("太陽系を離れると、太陽もほかの星と同じ、ひとつの星になります。"
             "いちばん近い恒星まで、光で約4.2年かかります。", "sun", dist=25 * LY_AU, seconds=11),
        Step("数千光年まで引くと、わたしたちが天の川の中にいることが分かってきます。", "sun", dist=4000 * LY_AU,
             seconds=10),
        Step("天の川銀河。直径約10万光年の中に、数千億個の星があります。", "g:mw", seconds=11),
        Step("天の川銀河のまわりには、大マゼラン雲・小マゼラン雲などの伴銀河が回っています。", "sun",
             dist=600000 * LY_AU, seconds=10),
        Step("約250万光年先のアンドロメダ銀河。天の川銀河と同じくらいの大きさの、お隣の大きな銀河です。", "g:m31",
             seconds=11),
        Step("数億光年まで引くと、銀河が集まった「銀河団」や、銀河の少ない空間が見えてきます。ひときわ銀河が密集しているのが、"
             "おとめ座銀河団です。", "sun", dist=1.2e8 * LY_AU, seconds=12),
        Step("さらに引くと、約1万個の銀河が網の目のように広がっています。これが宇宙の大規模構造の一端です。", "sun",
             dist=1.2e9 * LY_AU, seconds=12),
        Step("そして、観測できる宇宙の果て。約450億光年かなたにある、宇宙が生まれて約38万年後の光"
             "（宇宙マイクロ波背景放射）の壁です。わたしたちは、この球の中心から宇宙を見ています。", "u:cmb",
             seconds=14),
    ]


def tonight(view) -> list[Step]:
    """観測地で、今夜21時に見える空を案内する。"""
    now = datetime.now().astimezone()
    t = now.replace(hour=21, minute=0, second=0, microsecond=0)
    if now.hour >= 23:
        t += timedelta(days=1)
    jd = astro.jd_from_datetime(t)
    off, zen, north, east = astro.observer_frame(jd, view.lat, view.lon)
    pos = astro.all_positions(jd)
    eye = pos["earth"] + off
    steps = [Step(f"{view.place}で、{t.month}月{t.day}日の夜9時に見える星空を案内します。まずは南の空です。",
                  ground=True, az=180, alt=35, fov=100, extra={"jd": jd}, seconds=10)]
    seen = []
    for key in ("venus", "mars", "jupiter", "saturn", "moon", "mercury"):
        alt, az = astro.alt_az(pos[key] - eye, zen, north, east)
        if alt > 5:
            seen.append((key, alt, az))
    for key, alt, az in seen:
        d = ["北", "北東", "東", "南東", "南", "南西", "西", "北西"][int((az + 22.5) // 45) % 8]
        name = BY_KEY[key].name
        if key == "moon":
            steps.append(Step(f"{d}の空、高さ{alt:.0f}度のところに月が出ています。拡大すると満ち欠けの形が分かります。",
                              ground=True, look="moon", fov=3, extra={"jd": jd}))
        elif key == "jupiter":
            steps.append(Step(f"{d}の空、高さ{alt:.0f}度に明るく見えるのが木星です。望遠鏡で見るように拡大すると、"
                              "まわりに4つのガリレオ衛星が並んでいます。", ground=True, look="jupiter", fov=0.3,
                              extra={"jd": jd}, seconds=11))
        elif key == "saturn":
            steps.append(Step(f"{d}の空、高さ{alt:.0f}度に土星が見えます。拡大すると環が見えます"
                              "（環の傾きは年によって変わり、細い線のように見える年もあります）。", ground=True,
                              look="saturn", fov=0.15, extra={"jd": jd}))
        else:
            steps.append(Step(f"{d}の空、高さ{alt:.0f}度に{name}が見えます。", ground=True, look=key, fov=40,
                              extra={"jd": jd}))
    if not seen:
        steps.append(Step("今夜9時には、明るい惑星は地平線の上にありません。星座を探してみましょう。",
                          ground=True, az=90, alt=30, fov=100, extra={"jd": jd}))
    steps.append(Step("北の空です。北極星（ポラリス）は、一晩じゅうほとんど動きません。", ground=True,
                      az=0, alt=max(10.0, view.lat * 0.9), fov=100, extra={"jd": jd}))
    steps.append(Step("時間を進めると、星は北極星を中心に回って見えます。地球が自転しているためです。", ground=True,
                      az=0, alt=max(10.0, view.lat * 0.9), fov=100,
                      extra={"jd": jd, "speed_index": 3}, seconds=12))
    return steps


TOURS = [
    ("solar", "太陽系めぐり", solar_system),
    ("scale", "宇宙の大きさ", scale_of_universe),
    ("tonight", "今夜の星空", tonight),
]
