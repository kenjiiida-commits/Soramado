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
    pitch: float | None = None         # 見下ろす角度 [度]（None はそのまま）


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


def explorers() -> list[Step]:
    """探査機の旅（NASA JPL の位置から作った航路で、おもな探査機をめぐる）。"""
    from . import spacecraft as sc
    d = sc._jd
    WEEK, DAY = 6, 5                    # 時間の速さ（SPEEDS の番号）: 1週間/秒、1日/秒
    return [
        Step("宇宙探査の旅をたどりましょう。1972年、パイオニア10号が初めて小惑星帯をぬけて、木星へ向かいました。",
             "sc:pioneer10", dist=4.0, extra={"jd": d(1973, 6, 1), "speed_index": WEEK}, seconds=12),
        Step("1977年に打ち上げられたボイジャー2号は、木星・土星・天王星・海王星を次々に訪れました。"
             "惑星の引力で進路と速さを変える「スイングバイ」を繰り返しています。", "sc:voyager2", dist=45.0,
             extra={"jd": d(1989, 8, 25)}, seconds=12),
        Step("ガリレオは、金星と地球で2回ずつスイングバイして速さをつけ、1995年に初めて木星を回る探査機になりました。",
             "sc:galileo", dist=8.0, extra={"jd": d(1995, 12, 7)}, seconds=12),
        Step("カッシーニは2004年に土星に到着し、13年間、土星のまわりを回りながら環や衛星を調べました。"
             "時間を進めると、土星を回る細長い軌道が見えます。", "sc:cassini", dist=0.25,
             extra={"jd": d(2005, 1, 1), "speed_index": DAY}, seconds=14),
        Step("メッセンジャーは、地球・金星・水星で何度もスイングバイして速さを落とし、2011年に初めて水星を回りました。",
             "sc:messenger", dist=1.2, extra={"jd": d(2011, 3, 18)}, seconds=12),
        Step("ドーンは、イオンエンジンで小惑星ベスタを回ったあと、準惑星ケレスへ移りました。"
             "2つの天体を順に回った、ただ一つの探査機です。", "sc:dawn", dist=4.0,
             extra={"jd": d(2013, 6, 1), "speed_index": WEEK}, seconds=13),
        Step("ロゼッタは10年かけてチュリュモフ・ゲラシメンコ彗星に追いつき、2014年に着陸機フィラエを彗星に下ろしました。",
             "sc:rosetta", dist=0.05, extra={"jd": d(2014, 11, 12)}, seconds=12),
        Step("ニュー・ホライズンズは2015年に冥王星へ到着し、ハート形の地形を撮影しました。", "sc:newhorizons",
             dist=45.0, extra={"jd": d(2015, 7, 14)}, seconds=11),
        Step("ジュノーは2016年から、木星の極の上を通る細長い軌道で回り、雲の下の様子を調べています。",
             "sc:juno", dist=0.3, extra={"jd": d(2017, 1, 1), "speed_index": DAY}, seconds=13),
        Step("日本の「はやぶさ」は、イオンエンジンで小惑星イトカワへ向かい、2010年に地球へ帰ってきました。",
             "sc:hayabusa", dist=3.0, extra={"jd": d(2005, 9, 12)}, seconds=11),
        Step("「はやぶさ2」は小惑星リュウグウで試料を採取し、2020年にカプセルを地球へ届けました。",
             "sc:hayabusa2", dist=3.0, extra={"jd": d(2019, 7, 11)}, seconds=11),
        Step("オシリス・レックスは小惑星ベンヌの試料を2023年に地球へ届け、今は小惑星アポフィスへ向かっています。",
             "sc:osirisrex", dist=3.0, extra={"jd": d(2020, 10, 20)}, seconds=11),
        Step("パーカー・ソーラー・プローブは、金星の引力で軌道を小さくしながら、2024年12月、太陽の表面から"
             "約610万kmまで近づきました。人類が作ったもので、最も太陽に近く、最も速く動いたものです。",
             "sc:parker", dist=0.6, extra={"jd": d(2024, 12, 14), "speed_index": DAY}, seconds=14),
        Step("これから木星に着くのが、エウロパ・クリッパー（2030年）とJUICE（2031年）。"
             "氷の衛星の下の海に、生命がすめる環境があるかを調べます。", "sc:europaclipper", dist=8.0,
             extra={"jd": d(2027, 6, 1), "speed_index": WEEK}, seconds=13),
        Step("2026年11月、ボイジャー1号は地球から光で1日かかる距離（約173AU）に達しました。"
             "人類が作ったもので、いちばん遠くにある物体です。", "sun", dist=420.0,
             extra={"jd": d(2026, 11, 26)}, seconds=12),
    ]


def asteroids(view) -> list[Step]:
    """小惑星の世界。ダウンロードした小惑星のデータがあれば、それも使う。"""
    from . import spacecraft as sc
    mp = view.mp
    steps = []
    if mp is None:
        steps.append(Step("小惑星の世界をめぐります。（「ファイル」→「小惑星・彗星のデータをダウンロード」をすると、"
                          "約90万個の小惑星が見えるようになります。）", "sun", dist=7.0, pitch=35, seconds=10))
    else:
        steps.append(Step(f"小惑星の世界をめぐりましょう。ここに見えている点は、番号の付いた小惑星と彗星、"
                          f"約{len(mp) // 10000}万個です。", "sun", dist=7.0, pitch=35, seconds=10))
    steps += [
        Step("火星と木星のあいだ、太陽から約2〜3.3 AU のところに、小惑星が集まった「小惑星帯」があります。"
             "これだけ多くても、全部合わせた重さは月の3%ほどしかありません。", "sun", dist=9.0, pitch=75, seconds=12),
        Step("小惑星帯で最大の天体ケレス。直径は約940kmで、自分の重さで丸くなっているため「準惑星」に分類されています。",
             "ceres", seconds=10),
        Step("ベスタは小惑星帯で2番目に重い天体です。NASAの探査機ドーンが、ケレスとベスタを訪れました。", "vesta",
             seconds=10),
        Step("木星の軌道の上、木星の60度前と60度後ろには「トロヤ群」と呼ばれる小惑星の集まりがあります（緑）。"
             "太陽と木星の引力がつり合う場所に、とらえられています。", "sun", dist=16.0, pitch=80, seconds=13),
        Step("小惑星帯の外側には、三角形のように並んだ「ヒルダ群」があります（黄）。"
             "木星が太陽を2周するあいだに、ちょうど3周しています。", "sun", dist=12.0, pitch=85, seconds=12),
        Step("地球の軌道に近づく小惑星もあります（橙）。世界中の望遠鏡で見張り、軌道を調べています。", "sun",
             dist=3.5, pitch=50, seconds=11),
        Step("「はやぶさ」が訪れた小惑星イトカワ。長さ約500mの、ラッコのような形の小惑星です。", "itokawa",
             dist=0.6, seconds=10),
        Step("「はやぶさ2」が訪れたリュウグウ。そろばんの玉のような形で、試料を地球に持ち帰りました。", "ryugu",
             dist=0.6, seconds=10),
    ]
    if mp is not None:
        hit = mp.find("Apophis")
        if hit:
            import numpy as np
            jd = sc._jd(2029, 4, 13) + 0.9
            # 計算した位置が地球から離れすぎているとき（軌道要素が古いなど）は、地球を中心に見る
            near = np.linalg.norm(mp.position(hit[0], jd) - astro.all_positions(jd)["earth"]) < 0.01
            steps.append(Step("小惑星アポフィス（直径約340m）は、2029年4月13日に地球から約3万8千kmのところを通ります。"
                              "静止衛星より内側で、日本からは見えませんが、ヨーロッパやアフリカでは肉眼でも見えると予想されています。"
                              "（この表示の位置は、おおよそです）", f"mp:{hit[0]}" if near else "earth",
                              dist=0.012 if near else 0.02, extra={"jd": jd}, seconds=14))
    steps += [
        Step("海王星の外側には「太陽系外縁天体」が広がっています（青）。冥王星やエリスもそのなかまです。", "sun",
             dist=140.0, pitch=40, seconds=12),
        Step("ハレー彗星は約76年ごとに太陽に近づきます。次に戻ってくるのは2061年です。", "halley", dist=40.0,
             seconds=11),
        Step("小惑星や彗星は、太陽系ができたころの材料が残った「化石」です。それを調べることで、"
             "地球の水や生命の材料がどこから来たのかがわかってきます。", "sun", dist=10.0, pitch=30, seconds=12),
    ]
    return steps


def exoplanets(view) -> list[Step]:
    """系外惑星の世界。系外惑星のデータが必要。"""
    ex = view.exo
    LY = 63241.077
    if ex is None:
        return [Step("このツアーには系外惑星のデータが必要です。「ファイル」→「系外惑星のデータをダウンロード」を"
                     "してから、もう一度始めてください。", "sun", dist=40.0, seconds=10)]

    def sys_key(host):
        hit = [i for i in ex.find(host) if ex.name(i).lower() == host.lower()]
        return f"x:{hit[0]}" if hit else None

    run = {"speed_index": 4}      # 6時間/秒で、惑星が回る様子を見せる
    steps = [
        Step(f"太陽系の外にも、たくさんの惑星が見つかっています。いまわかっているのは、{len(ex):,}個の恒星をまわる"
             f"{ex.count_planets:,}個の惑星です。緑の丸が、惑星を持つ恒星です。", "sun", dist=40 * LY, pitch=30,
             seconds=12),
        Step("引いて見ると、見つかった惑星系は太陽のまわり、数千光年以内に集まっています。"
             "天の川銀河には数千億個の恒星があり、その多くが惑星を持っていると考えられています。", "sun",
             dist=4000 * LY, pitch=40, seconds=12),
    ]
    plan = [
        ("51 Peg", "ペガスス座51番星。1995年、太陽に似た恒星のまわりで初めて見つかった系外惑星です。"
                   "木星くらいの重さなのに、わずか4日で恒星を1周する「ホット・ジュピター」でした。"
                   "発見した2人は2019年にノーベル物理学賞を受けました。", 14),
        ("Proxima Cen", "プロキシマ・ケンタウリは、太陽にいちばん近い恒星（4.2光年）です。"
                        "小さな赤い恒星のハビタブルゾーンの中を、地球くらいの重さの惑星 b が回っています。", 13),
        ("TRAPPIST-1", "TRAPPIST-1 には、地球くらいの大きさの惑星が7つあります。そのうちのいくつかは"
                       "ハビタブルゾーン（緑の軌道）の中です。7つとも、水星の軌道よりずっと内側に収まっています。", 15),
        ("Kepler-452", "ケプラー452b は、太陽に似た恒星のまわりを、地球に近い距離（約1年）で回る惑星です。"
                       "地球より少し大きく、「地球のいとこ」と呼ばれました。約1400光年のかなたにあります。", 13),
        ("Kepler-90", "ケプラー90には、太陽系と同じ8つの惑星が見つかっています。ただし8つとも、"
                      "地球の軌道より内側にぎゅっと詰まっています。", 13),
        ("HR 8799", "HR 8799 では、4つの巨大な惑星が直接撮影されました。恒星の光をさえぎって、"
                    "惑星そのものの光をとらえています。", 13),
    ]
    for host, text, sec in plan:
        key = sys_key(host)
        if key:
            steps.append(Step(text, key, extra=dict(run), seconds=sec))
    steps.append(Step("そして、わたしたちの太陽系。ほかの惑星系とくらべると、太陽系はどんな特徴があるでしょうか。"
                      "生命を宿す惑星は、ほかにもあるのでしょうか。", "sun", dist=60.0, pitch=35, seconds=12))
    return steps


def star_life() -> list[Step]:
    """星の一生：星雲での誕生から、惑星状星雲・超新星残がいまで。"""
    from . import nebulae as neb
    idx = {n.id: i for i, n in enumerate(neb.NEBULAE)}
    LY = 63241.077

    def k(i):
        return f"n:{idx[i]}" if i in idx else None

    plan = [
        (None, "星にも一生があります。宇宙のあちこちで、星が生まれ、輝き、最後をむかえています。"
               "星雲や星団をめぐって、星の一生をたどってみましょう。", dict(target="sun", dist=1800 * LY, pitch=35), 12),
        ("NGC1976", "星は、ガスとちりの雲の中で生まれます。オリオン大星雲では、雲の濃いところが自分の重さで縮み、"
                    "中心が熱くなって新しい星が次々に生まれています。", {}, 13),
        ("NGC6611", "わし星雲の「創造の柱」も、星が生まれている場所です。生まれたばかりの重い星の光が、"
                    "まわりのガスを赤く光らせています。", {}, 12),
        ("Mel022", "同じ雲から生まれた星たちは、しばらく「散開星団」として集まっています。すばるは生まれて約1億年の"
                   "若い星団で、青白い高温の星が目立ちます。", {}, 13),
        ("C041", "ヒアデス星団は約6億年。時間がたつと、星団の星は少しずつ散らばっていきます。"
                 "太陽も、昔はどこかの星団の中で生まれたと考えられています。", {}, 12),
        (None, "わたしたちの太陽は、生まれて約46億年。水素を燃やして輝く、一生のちょうど半ばにいます。"
               "あと約50億年はこのまま輝き続けます。", dict(target="sun", dist=0.05, pitch=20), 12),
        ("NGC6720", "太陽くらいの重さの星は、最後に大きくふくらんで赤色巨星になり、外側のガスを宇宙へ放ちます。"
                    "それが環状星雲のような「惑星状星雲」です。中心には、地球くらいの大きさの白色矮星が残ります。", {}, 15),
        ("NGC6853", "あれい状星雲も惑星状星雲です。放たれたガスは数万年で広がって消え、白色矮星はゆっくり冷えていきます。", {}, 12),
        ("NGC1952", "太陽の8倍以上重い星は、最後に「超新星爆発」を起こします。かに星雲は、1054年に爆発した星の残がいです。"
                    "中心には、1秒に30回転する中性子星が残っています。さらに重い星はブラックホールになります。", {}, 15),
        ("NGC6960", "網状星雲は、約1万年前の超新星の残がいです。星の中や爆発で作られた炭素・酸素・鉄などが宇宙に広がり、"
                    "次の星や惑星の材料になります。", {}, 13),
        ("NGC6205", "ヘルクレス座球状星団の星は、約120億年前に生まれた、宇宙でもっとも古い星の仲間です。"
                    "重い星はとっくに一生を終え、軽い星だけが今も輝いています。", {}, 13),
        ("NGC1976", "わたしたちの体をつくる炭素や酸素、地球の鉄も、昔の星の中で作られました。"
                    "星の一生は、次の星と、わたしたちにつながっています。", {}, 13),
    ]
    steps = []
    for nid, text, opt, sec in plan:
        if nid is None:
            steps.append(Step(text, seconds=sec, **opt))
        elif k(nid):
            steps.append(Step(text, k(nid), seconds=sec, **opt))
    return steps


def cosmic_history() -> list[Step]:
    """宇宙の歴史：宇宙の果て（昔の宇宙）から、地球（いま）へ向かって。"""
    from . import nebulae as neb
    idx = {n.id: i for i, n in enumerate(neb.NEBULAE)}

    def n(i):
        return f"n:{idx[i]}" if i in idx else "sun"

    return [
        Step("宇宙の138億年の歴史をたどります。遠くを見ることは、昔を見ること。光が届くのに時間がかかるので、"
             "遠くの天体ほど、昔の姿が見えています。いちばん遠い、宇宙の果てから出発しましょう。", "u:cmb", seconds=13),
        Step("約138億年前、宇宙は「ビッグバン」で、とても熱く小さな状態から始まりました。この球は、"
             "宇宙が生まれて約38万年後に放たれた光「宇宙マイクロ波背景放射」です。それより前の宇宙は熱いガスで"
             "光がまっすぐ進めず、見ることができません（宇宙の晴れ上がり）。", "u:cmb", seconds=16),
        Step("宇宙が生まれて数億年後、ガスが集まって最初の星と銀河が生まれました。銀河の中心の巨大なブラックホールが"
             "まわりのガスを吸い込んで明るく輝くのがクエーサーです。ジェイムズ・ウェッブ宇宙望遠鏡は、"
             "宇宙が生まれて3億年ほどの銀河も見つけています。", "sun", dist=1.2e10 * LY_AU, pitch=30, seconds=15),
        Step("銀河は、目に見えない「暗黒物質」の重力に引かれて集まり、銀河団や、網の目のような大きな構造"
             "（宇宙の大規模構造）をつくりました。", "sun", dist=8e8 * LY_AU, pitch=40, seconds=13),
        Step("わたしたちの天の川銀河も、小さな銀河が合体をくり返して大きくなりました。もっとも古い星は"
             "130億年以上前に生まれています。", "g:mw", seconds=12),
        Step("ヘルクレス座球状星団の星は、約120億年前に生まれた、銀河の中でもとくに古い星たちです。",
             n("NGC6205"), seconds=11),
        Step("重い星は超新星爆発を起こし、星の中で作られた炭素・酸素・鉄などを宇宙にまき散らしました。"
             "宇宙は少しずつ、いろいろな元素を含むようになっていきました。", n("NGC1952"), seconds=13),
        Step("約46億年前、天の川銀河の片すみのガスとちりの雲の中で、太陽が生まれました。"
             "オリオン大星雲で今起きているのと同じように。", n("NGC1976"), seconds=12),
        Step("太陽のまわりの円盤の中で、ちりが集まって微惑星になり、ぶつかり合って惑星が育ちました。"
             "太陽系の誕生です。小惑星や彗星は、そのときの材料の残りです。", "sun", dist=40.0, pitch=35, seconds=13),
        Step("約45億年前、生まれたばかりの地球に火星くらいの天体がぶつかり、飛び散ったかけらから月ができたと"
             "考えられています（ジャイアント・インパクト説）。", "moon", seconds=12),
        Step("やがて地球に海ができ、約38億年前までには生命が生まれました。そして今、わたしたちは"
             "宇宙の歴史を調べています。", "earth", seconds=12),
        Step("宇宙は今も広がり続けています。しかも約50億年前からは、なぞの「暗黒エネルギー」によって、"
             "広がる速さが増していることがわかっています（1998年の発見、2011年ノーベル物理学賞）。", "sun",
             dist=3e9 * LY_AU, pitch=30, seconds=14),
    ]


TOURS = [
    ("solar", "太陽系めぐり", solar_system),
    ("scale", "宇宙の大きさ", scale_of_universe),
    ("tonight", "今夜の星空", tonight),
    ("explorers", "探査機の旅", explorers),
    ("asteroids", "小惑星の世界", asteroids),
    ("exoplanets", "系外惑星の世界", exoplanets),
    ("starlife", "星の一生", star_life),
    ("history", "宇宙の歴史", cosmic_history),
]
