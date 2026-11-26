"""画面の言語（日本語・英語）。

言語は「表示」→「言語 / Language」で選び、次に起動したときから切り替わる。
tr() は画面の決まった文字（メニュー・ボタンなど）を、trx() は組み立てた文（下の欄の情報など）の
よく出る言い回しと単位を置きかえる。天体の解説・ツアーの字幕・説明書は、いまは日本語のみ。
"""

from __future__ import annotations

import re

try:
    from PySide6.QtCore import QSettings
    LANG = str(QSettings("Soramado", "Soramado").value("ui/lang", "ja"))
except Exception:  # noqa: BLE001
    LANG = "ja"

EN_MODE = LANG == "en"

EN = {
    # 時間の速さ
    "実時間": "Real time", "1分/秒": "1 min/s", "10分/秒": "10 min/s", "1時間/秒": "1 hour/s",
    "6時間/秒": "6 hours/s", "1日/秒": "1 day/s", "1週間/秒": "1 week/s", "1か月/秒": "1 month/s",
    "1年/秒": "1 year/s",
    # 観測地
    "札幌": "Sapporo", "仙台": "Sendai", "東京": "Tokyo", "三鷹（国立天文台）": "Mitaka (NAOJ)",
    "名古屋": "Nagoya", "大阪": "Osaka", "広島": "Hiroshima", "福岡": "Fukuoka", "那覇": "Naha",
    # ツールバー
    "操作": "Controls", " 見る天体 ": " Target ", "観測できる宇宙の果て": "Edge of the observable universe",
    "全体を見る": "Overview", "🔭 地上から見る": "🔭 View from ground", "緯度・経度を入力…": "Enter latitude/longitude…",
    "⏺ 録画": "⏺ Record", "画面を動画（MP4）に録画します": "Record the screen to a video (MP4)",
    "⏸ 停止": "⏸ Pause", "逆再生": "Reverse", "現在時刻": "Now", "惑星の大きさ": "Planet size",
    "×1（実寸）": "×1 (true size)", "星の数": "Stars", "▶ 再生": "▶ Play", "🚀 宇宙へ戻る": "🚀 Back to space",
    # メニュー
    "ファイル(&F)": "&File", "惑星の画像をダウンロード…": "Download planet images…",
    "画面を画像で保存": "Save screenshot", "録画の開始・停止": "Start/stop recording",
    "保存したフォルダを開く": "Open saved folder", "クエーサーのデータをダウンロード…": "Download quasar data…",
    "小惑星・彗星のデータをダウンロード…": "Download asteroid & comet data…",
    "小惑星・彗星のデータを手元のファイルから読み込む…": "Load asteroid & comet data from local files…",
    "人工衛星のデータ（ISS など）をダウンロード…": "Download satellite data (ISS etc.)…",
    "系外惑星のデータをダウンロード…": "Download exoplanet data…",
    "系外惑星のデータを手元のファイル（CSV）から読み込む…": "Load exoplanet data from a local file (CSV)…",
    "終了": "Quit", "表示(&V)": "&View", "軌道": "Orbits", "名前": "Labels", "恒星": "Stars",
    "星座線": "Constellation lines", "星座名": "Constellation names", "星の名前": "Star names",
    "星雲・星団": "Nebulae & clusters", "銀河": "Galaxies", "準惑星・小惑星・彗星": "Dwarf planets, asteroids & comets",
    "たくさんの小惑星・彗星（ダウンロードしたもの）": "Many asteroids & comets (downloaded)",
    "系外惑星を持つ恒星（ダウンロードしたもの）": "Stars with exoplanets (downloaded)",
    "天体を探す（星座・星雲・小惑星・系外惑星）…": "Find object (constellations, nebulae, asteroids, exoplanets)…",
    "天体を探す（星座・星雲・小惑星・系外惑星）": "Find object",
    "探査機の航路": "Spacecraft paths", "クエーサー": "Quasars", "宇宙マイクロ波背景放射": "Cosmic microwave background",
    "全画面表示": "Full screen", "天文現象(&E)": "&Events", "日食・月食…": "Eclipses…", "流星群…": "Meteor showers…",
    "人工衛星（ISS など）が見える時刻…": "Satellite passes (ISS etc.)…",
    "惑星・月の接近と見ごろ…": "Conjunctions & best views…", "地上モードで流星を流す": "Show meteors in ground view",
    "人工衛星を表示する": "Show satellites", "ツアー(&T)": "&Tours", "ツアーを動画にする": "Record a tour as video",
    "ツアーを終わる": "End tour", "ヘルプ(&H)": "&Help", "説明書": "Manual (Japanese)",
    "操作方法（早見表）": "Controls (quick reference)", "操作方法": "Controls", "そらみ窓について": "About Soramado",
    "そらみ窓": "Soramado", "そらみ窓 説明書": "Soramado manual", "説明書が見つかりません。": "Manual not found.",
    # ダイアログ
    "画像の保存": "Save image", "録画": "Recording", "⏹ 停止 0:00": "⏹ Stop 0:00", "フォルダを開く": "Open folder",
    "動画を保存できませんでした。\n\n": "Could not save the video.\n\n", "クエーサーのデータ": "Quasar data",
    "クエーサーのデータをダウンロードしています…": "Downloading quasar data…", "キャンセル": "Cancel",
    "ダウンロードできませんでした。\n\n": "Download failed.\n\n", "ダウンロード": "Downloads",
    "JPL の軌道要素の表を選ぶ（ELEMENTS.NUMBR(.gz) と ELEMENTS.COMET）":
        "Choose JPL orbital element tables (ELEMENTS.NUMBR(.gz) and ELEMENTS.COMET)",
    "軌道要素の表 (ELEMENTS.* *.gz *.txt);;すべてのファイル (*)": "Element tables (ELEMENTS.* *.gz *.txt);;All files (*)",
    "小惑星・彗星のデータ": "Asteroid & comet data", "準備しています…": "Preparing…",
    "点をダブルクリックすると、その天体の名前と軌道がわかります。": "Double-click a dot to see its name and orbit.",
    "「表示」→「小惑星・彗星を探す」（Ctrl+F）で名前から探せます。": "Find objects by name with Ctrl+F.",
    "読み込めませんでした。\n\n": "Could not load.\n\n",
    "NASA Exoplanet Archive の表（CSV）を選ぶ": "Choose the NASA Exoplanet Archive table (CSV)",
    "CSV (*.csv);;すべてのファイル (*)": "CSV (*.csv);;All files (*)", "系外惑星のデータ": "Exoplanet data",
    "系外惑星のデータを読み込んでいます…": "Loading exoplanet data…", "そこへ行く": "Go there",
    "%Y年%-m月%-d日 %H:%M": "%Y-%m-%d %H:%M",
    "皆既": "Total", "金環": "Annular", "部分日食": "Partial eclipse", "・最大のときは地平線の下": " (below horizon at maximum)",
    "途中まで見える（食の途中で月が沈む）": "Partly visible (Moon sets during the eclipse)",
    "途中から見える（欠けたまま月が昇る）": "Partly visible (Moon rises eclipsed)", "一部が見える": "Partly visible",
    "日食・月食": "Eclipses", "日食・月食を探すには PyEphem（python3-ephem）が必要です。": "PyEphem (python3-ephem) is required.",
    "日時（最大）": "Date (maximum)", "種類": "Type", "食分": "Magnitude", "宇宙から見る": "View from space",
    "地上から見る": "View from ground", "閉じる": "Close", "流星群": "Meteor showers",
    "PyEphem（python3-ephem）が必要です。": "PyEphem (python3-ephem) is required.",
    "このとき放射点は地平線の下です。": "The radiant is below the horizon at this time. ",
    "極大": "Peak", "見やすい時刻": "Best time", "見える数の目安": "Expected rate", "月明かり": "Moonlight",
    "くわしく": "Details", "人工衛星のデータをダウンロードしています…": "Downloading satellite data…",
    "人工衛星のデータ": "Satellite data", "人工衛星": "Satellites",
    "北": "N", "北北東": "NNE", "北東": "NE", "東北東": "ENE", "東": "E", "東南東": "ESE", "南東": "SE",
    "南南東": "SSE", "南": "S", "南南西": "SSW", "南西": "SW", "西南西": "WSW", "西": "W", "西北西": "WNW",
    "北西": "NW", "北北西": "NNW",
    "見える（夜空で太陽の光を反射）": "Visible (sunlit in a dark sky)", "見えない（昼間か、地球の影の中）":
        "Not visible (daytime or in Earth's shadow)",
    "昇る時刻": "Rises", "衛星": "Satellite", "動き（方角）": "Path (direction)", "見え方": "Visibility",
    "惑星・月の接近": "Conjunctions", "見えにくい（低い・明るい空）": "Hard to see (low or bright sky)",
    "見えない": "Not visible", "（地球のどこかで月が惑星をかくす惑星食）": " (an occultation somewhere on Earth)",
    "このとき、観測地では地平線の下です": "Below the horizon at your location at this time",
    "日時": "Date", "できごと": "Event",
    "そのとき、観測地では地平線の下です（地面を消すと見えます）": "Below the horizon at your location at this time",
    "解説": "Information", "<h3>おもな星</h3><ul>": "<h3>Main stars</h3><ul>",
    "<h2>地上から見た空</h2>": "<h2>The sky from the ground</h2>", "前": "ago", "後": "ahead",
    "<h2>観測できる宇宙の果て</h2>": "<h2>Edge of the observable universe</h2>", "◀ 前": "◀ Back", "次 ▶": "Next ▶",
    "観測地": "Location", "°（北緯が＋）": "° (north +)", "°（東経が＋）": "° (east +)", "緯度": "Latitude",
    "経度": "Longitude", "探査機": "Spacecraft", "打ち上げ前": "Before launch",
    "この画面で表示する航路はここまで": "End of the path shown", "※ 航路はおおよそ": "* approximate path",
    "※ 形は模式図": "* schematic shape", "※ 位置はおおよそ": "* approximate position",
    "クエーサーのデータは未ダウンロード（ファイルメニュー）": "Quasar data not downloaded (File menu)",
    "夜": "Night", "地平線の下": "Below horizon", "　｜　視点の距離 ": "  |  Viewpoint ", "準惑星": "Dwarf planet",
    "（逆行）": " (retrograde)", "惑星の画像": "Planet images",
    "画像はすべてダウンロード済みです。もう一度ダウンロードしますか？": "All images are downloaded. Download again?",
    "画像をダウンロードしています…": "Downloading images…", "太陽（太陽系）": "Sun (Solar System)",
    "宇宙マイクロ波背景放射（観測できる宇宙の果て・模式図）":
        "Cosmic microwave background (edge of the observable universe, schematic)",
    "画面の横幅 約 ": "Screen width ≈ ", "（影の中・明るい空で見えない）": " (in shadow / bright sky)",
    "<p>太陽系から宇宙の果てまでを旅する、Ubuntu 用の宇宙シミュレーター。</p>":
        "<p>A space simulator for Ubuntu, from the Solar System to the edge of the universe.</p>",
    "<p>作者: 飯田顕治 ／ ライセンス: MIT</p>": "<p>Author: Kenji Iida / License: MIT</p>",
    "<p>このソフトは国立天文台の Mitaka とは関係のない独自のソフトです。</p>":
        "<p>This software is independent and not affiliated with NAOJ's Mitaka.</p>",
    "<p><b>使用しているデータ</b><br>": "<p><b>Data used</b><br>",
}

EN_HELP = """<h3>Controls</h3>
<table cellpadding="3">
<tr><td><b>Left drag</b></td><td>Rotate the view</td></tr>
<tr><td><b>Wheel</b> / <b>Right drag</b></td><td>Zoom in / out</td></tr>
<tr><td><b>Double-click</b></td><td>Fly to a planet or galaxy / show star info / select a constellation (on its name)</td></tr>
<tr><td><b>Space</b></td><td>Pause / resume time</td></tr>
<tr><td><b>+ / −</b></td><td>Zoom in / out</td></tr>
<tr><td><b>F11</b></td><td>Full screen</td></tr>
<tr><td><b>Ctrl+S</b></td><td>Save a screenshot (Pictures/Soramado)</td></tr>
<tr><td><b>Ctrl+R</b></td><td>Start / stop recording (Videos/Soramado, needs ffmpeg)</td></tr>
<tr><td><b>Ctrl+E</b></td><td>List of eclipses</td></tr>
<tr><td><b>Ctrl+F</b></td><td>Find an object by name</td></tr>
</table>
<p><b>View from ground (planetarium)</b>: left drag to look around, wheel to change the field of view.</p>
<p><b>Tours</b>: choose one from the Tours menu (captions are in Japanese). Esc ends a tour.</p>
<p>Zoom out with the wheel to travel from nearby stars to the Milky Way, nearby galaxies, and the edge of the
observable universe.</p>"""


def tr(s: str) -> str:
    """決まった文字を、選んだ言語にする。"""
    if not EN_MODE:
        return s
    if s.startswith("<h3>操作方法</h3>"):
        return EN_HELP
    return EN.get(s, s)


# 組み立てた文の言い回し（長いものから順に置きかえる）
_PHRASES = [
    ("天の川の写真をダウンロードしています…", "Downloading the Milky Way photo…"),
    ("星雲・銀河の写真をダウンロードしています…", "Downloading photos of nebulae & galaxies…"),
    ("個の天体の写真を用意しました。", " objects now have photos."),
    ("個はダウンロードできませんでした（もう一度実行すると、足りない分だけ取りに行きます）。",
     " could not be downloaded (run it again to fetch only the missing ones)."),
    ("観測できる宇宙の果て", "Edge of the observable universe"),
    ("（これから15年・観測地 ", " (next 15 years, "), ("（これから1年・観測地 ", " (next year, "),
    ("（これから10日・観測地 ", " (next 10 days, "), ("（これから1年あまり・観測地 ", " (next ~1 year, "),
    ("人工衛星が見える時刻", "Satellite passes"), ("惑星・月の接近と見ごろ", "Conjunctions & best views"),
    ("日食・月食", "Eclipses"), ("流星群", "Meteor showers"),
    ("で見えるものだけ", ": visible only"), ("での見え方", " visibility"), ("での見やすい時刻", " best time"),
    ("では見えない（月が地平線の下）", ": not visible (Moon below horizon)"), ("では見えない", ": not visible"),
    ("全部見える（最大のとき月の高度 ", "Fully visible (Moon altitude at maximum "),
    ("%がかくれる", "% covered"), ("太陽の", "Sun "), ("が見える", " visible"), ("最大 ", "max "),
    ("個/時", "/h"), ("放射点の高さ", "Radiant alt."), ("月 ", "Moon "), ("ごろ 高さ", " Alt"),
    ("から ", " from "), ("（星座）", " (constellation)"), ("（人工衛星）", " (satellite)"),
    ("（系外惑星 ", " (star with "), (" 個を持つ恒星）", " exoplanets)"),
    ("等まで（", " mag ("), ("個）", " stars)"),
    ("最近のできごと:", "Latest:"), ("地上から見た空", "Sky from ground"), ("北緯", "lat"), ("東経", "lon"),
    ("太陽の高度", "Sun altitude"), ("（昼）", " (day)"), ("（薄明）", " (twilight)"), ("（夜）", " (night)"),
    ("（共動距離）", " (comoving)"), ("個のクエーサーを表示中", " quasars shown"), ("クエーサー", "Quasars"),
    ("を表示中", " shown"), ("見ている方向:", "Looking:"), ("年の範囲外のため、惑星の位置は概算です", " – planet positions are approximate"),
    ("小惑星帯の小惑星", "Main-belt asteroid"), ("地球に近い小惑星", "Near-Earth asteroid"),
    ("木星のトロヤ群", "Jupiter trojan"), ("ヒルダ群", "Hilda"), ("ケンタウルス族", "Centaur"),
    ("太陽系外縁天体", "Trans-Neptunian object"), ("その他の小惑星", "Asteroid"), ("彗星", "Comet"),
    ("太陽からの距離", "Distance from Sun"), ("軌道傾斜角", "Inclination"), ("恒星から", "from star"),
    ("宇宙マイクロ波背景放射まで", "to the CMB"),
    ("視点の距離", "Viewpoint"), ("（表面から）", " (from surface)"), ("（恒星から）", " (from the star)"),
    ("太陽から", "from Sun"), ("地球から", "from Earth"), ("惑星から", "from planet"),
    ("半径 太陽の", "Radius ×Sun "), ("半径 地球の", "Radius ×Earth "), ("質量 地球の", "Mass ×Earth "),
    ("半径 約", "Radius ≈"), ("半径", "Radius"), ("直径 約", "Diameter ≈"), ("直径", "Diameter"),
    ("公転周期", "Orbital period"), ("自転周期", "Rotation"), ("見かけの大きさ", "Apparent size"),
    ("大きさ 約", "Size ≈"), ("距離 約", "Distance ≈"), ("距離", "Distance"), ("明るさ", "Magnitude"),
    ("表面温度", "Temperature"), ("スペクトル型", "Spectral type"), ("惑星 ", "Planets: "),
    ("高度 約", "Altitude ≈"), ("高度", "Altitude"), ("1周 約", "Orbit ≈"), ("見ごろ：", "Best season: "),
    ("の衛星", " moon"), ("推定", "est."), ("等", " mag"), ("個", ""),
    ("散開星団", "Open cluster"), ("球状星団", "Globular cluster"), ("散光星雲（輝線星雲）", "Emission nebula"),
    ("反射星雲", "Reflection nebula"), ("惑星状星雲", "Planetary nebula"), ("超新星残がい", "Supernova remnant"),
    ("渦巻銀河", "Spiral galaxy"), ("楕円銀河", "Elliptical galaxy"), ("不規則銀河", "Irregular galaxy"),
    ("写真（DSS2）と模式図", "Photo (DSS2) and model"), ("※ 形は模式図", "* schematic"), ("※ 位置はおおよそ", "* approximate"), ("※ 航路はおおよそ", "* approximate"),
    ("見ている方向", "Looking"), ("方位", "Az"), ("高度", "Alt"), ("視野", "FOV"),
    ("時間", " h"), ("日", " d"), ("年", " yr"), ("分", " min"),
    ("約", "≈"), ("｜", "|"), ("　", " "), ("、", ", "), ("（", " ("), ("）", ")"), ("・", "/"),
]


_SORTED = sorted(_PHRASES, key=lambda p: -len(p[0]))     # 長い言い回しから先に置きかえる


def _num(s):
    return float(s.replace(",", ""))


def _ly(v):
    if v >= 1e9:
        return f"{v / 1e9:,.1f} billion ly"
    if v >= 1e6:
        return f"{v / 1e6:,.1f} million ly"
    return f"{v:,.0f} ly"


def trx(s: str) -> str:
    """組み立てた文（数字と単位を含む）を英語にする。"""
    if not EN_MODE or not s:
        return s
    s = re.sub(r"([\d,]+(?:\.\d+)?) ?億光年", lambda m: _ly(_num(m.group(1)) * 1e8), s)
    s = re.sub(r"([\d,]+(?:\.\d+)?) ?万光年", lambda m: _ly(_num(m.group(1)) * 1e4), s)
    s = re.sub(r"([\d,]+(?:\.\d+)?) ?万km", lambda m: f"{_num(m.group(1)) * 1e4:,.0f} km", s)
    s = s.replace("光年", "ly")
    for ja, en in _SORTED:
        s = s.replace(ja, en)
    return s


# ---------------------------------------------------------------- 天体の英語の名前
NAMES_EN = {
    "sun": "Sun", "moon": "Moon", "mercury": "Mercury", "venus": "Venus", "earth": "Earth", "mars": "Mars",
    "jupiter": "Jupiter", "saturn": "Saturn", "uranus": "Uranus", "neptune": "Neptune", "pluto": "Pluto",
    "halley": "Halley's Comet", "encke": "Comet Encke", "67p": "67P/Churyumov–Gerasimenko",
    "sc:voyager1": "Voyager 1", "sc:voyager2": "Voyager 2", "sc:newhorizons": "New Horizons",
    "sc:hayabusa": "Hayabusa", "sc:hayabusa2": "Hayabusa2",
    "g:mw": "Milky Way", "g:lmc": "Large Magellanic Cloud", "g:smc": "Small Magellanic Cloud",
    "g:m31": "Andromeda Galaxy (M31)", "g:m32": "M32", "g:m110": "M110", "g:m33": "Triangulum Galaxy (M33)",
    "g:m81": "Bode's Galaxy (M81)", "g:m82": "Cigar Galaxy (M82)", "g:cena": "Centaurus A",
    "g:m101": "Pinwheel Galaxy (M101)", "g:m51": "Whirlpool Galaxy (M51)", "g:m104": "Sombrero Galaxy (M104)",
    "g:m87": "M87",
    "s:25544": "International Space Station (ISS)", "s:48274": "Tiangong space station",
    "s:20580": "Hubble Space Telescope",
}


def name_en(key: str, ja: str) -> str:
    """英語のときの天体の名前（わからないときは、キーから作る）。"""
    if not EN_MODE:
        return ja
    if key in NAMES_EN:
        return NAMES_EN[key]
    return key.split(":")[-1].replace("_", " ").title()


EN.update({
    "皆既月食": "Total lunar eclipse", "部分月食": "Partial lunar eclipse", "半影月食": "Penumbral lunar eclipse",
    "部分日食": "Partial solar eclipse", "皆既日食": "Total solar eclipse", "金環日食": "Annular solar eclipse", "金環皆既日食": "Hybrid solar eclipse",
    "太陽系めぐり": "Solar System", "宇宙の大きさ": "Scale of the universe", "今夜の星空": "Tonight's sky",
    "探査機の旅": "Journeys of spacecraft", "小惑星の世界": "World of asteroids", "系外惑星の世界": "Exoplanets",
    "星の一生": "Life of stars", "宇宙の歴史": "History of the universe",
    "月明かりがなく条件が良い": "No moonlight – good", "月明かりが少しじゃま": "Some moonlight",
    "月明かりで条件が悪い": "Bright moonlight – poor", "観測地では見えない（放射点が昇らない）": "Not visible (radiant does not rise)",
})

EN.update({
    "日時は地球全体で食がいちばん大きくなるとき（このパソコンの時刻帯）。時刻は数分ずれることがあります。\n"
    "「宇宙から見る」は影の様子を宇宙から、「地上から見る」は観測地から空を見上げます（▶ 再生で食が進みます）。\n"
    "※ 太陽を直接見ると目を傷めます。本物の日食は、必ず日食グラスなどで観察してください。":
    "Times are the moment of greatest eclipse (in this computer's time zone) and may be off by a few minutes.\n"
    "\"View from space\" shows the shadow from space; \"View from ground\" shows the sky at your location (press ▶ Play to advance).\n"
    "* Never look directly at the Sun. Always use proper eclipse glasses for a real solar eclipse.",
    "見える数の目安は、空の暗い場所で放射点が高いときの1時間あたりの数です（町なかではもっと少なくなります）。"
    "流星は放射点から四方へ飛ぶので、放射点だけでなく空全体を広く見るのがこつです。\n"
    "「地上から見る」で、見やすい時刻の空に流星が流れます（流れる数は実際の約10倍に増やしています）。":
    "Expected rate is per hour under a dark sky with the radiant high (fewer in towns). "
    "Meteors fly out in all directions from the radiant, so watch the whole sky.\n"
    "\"View from ground\" shows meteors in the sky at the best time (about 10× more than real).",
    "高度10°より高く昇るときの一覧です（これから10日）。「見える」は、空が暗く、衛星に太陽の光が当たっているときで、"
    "明るい星のような光がゆっくり空を横切ります。「地上から見る」で、そのときの空を実時間で見られます。":
    "Passes higher than 10° (next 10 days). \"Visible\" means the sky is dark and the satellite is sunlit: "
    "it slowly crosses the sky like a bright star. \"View from ground\" shows that sky in real time.",
    "日時は、いちばん近づくとき（地球の中心から見た計算）です。月は地球に近いので、見る場所によって近づき方が"
    "少し変わります。「地上から見る」は、観測地で日の入り後・日の出前の、いちばん高く見える時刻の空を出します。":
    "Times are the closest approach (seen from Earth's centre). The Moon is close to Earth, so the approach "
    "varies a little by location. \"View from ground\" shows the sky when the objects are highest after sunset or before sunrise.",
    "名前か番号を入れてください。\n例: オリオン、すばる、M42、Itokawa、Ryugu、433、Halley、TRAPPIST-1\n"
    "（小惑星・系外惑星はダウンロードしたときだけ、英語の名前で探せます）":
    "Enter a name or number.\nExamples: Orion, Pleiades, M42, Itokawa, Ryugu, 433, Halley, TRAPPIST-1\n"
    "(Asteroids and exoplanets can be found only after downloading them.)",
})
EN.update({
    "星雲・銀河を写真で表示（ダウンロードしたもの）": "Show nebulae && galaxies as photos (downloaded)",
    "星雲・銀河の写真をダウンロード…": "Download photos of nebulae && galaxies…",
    "星雲・銀河の写真": "Photos of nebulae & galaxies",
    "写真はすべてダウンロード済みです。": "All photos have already been downloaded.",
    "星雲・星団・銀河の本物の写真（DSS2 color）をダウンロードします。\n"
    "ESA（ESASky）が配信している全天の写真から、天体ごとに切り出して保存します。\n\n"
    "通信量は約80MB、時間は回線によって数分〜十数分です。よろしいですか？":
    "Download real photos (DSS2 color) of nebulae, clusters and galaxies.\n"
    "Each object is cut out of the all-sky survey served by ESA (ESASky) and saved.\n\n"
    "About 80 MB will be downloaded (several minutes or more). Continue?",
    "星雲・銀河の写真をダウンロードしています…": "Downloading photos of nebulae & galaxies…",
    "星雲・銀河を地球の側から見ると、本物の写真で表示されます。横や裏に回ると、粒の模式図に切り替わります。\n"
    "「表示」→「星雲・銀河を写真で表示」で、写真を出さないようにもできます。":
    "Seen from Earth's side, nebulae and galaxies are shown as real photos; from the side or behind they switch to particle models.\n"
    "You can turn photos off in View → Show nebulae & galaxies as photos.",
    "ダウンロードできませんでした。\n\n": "Download failed.\n\n",
    "写真（DSS2）と模式図": "Photo (DSS2) and model",
    "天の川の写真（Gaia）をダウンロード…": "Download the Milky Way photo (Gaia)…",
    "天の川を写真で表示（ダウンロードしたもの）": "Show the Milky Way photo (downloaded)",
    "天の川の写真": "Milky Way photo",
    "星座の形の変化（星の動き）…": "Changing constellations (star motions)…", "星座の形の変化": "Changing constellations",
    "星は1つ1つが、それぞれの向きと速さで宇宙を動いています。近くの星ほど、空の上で大きく動きます。\n"
    "時代を変えると、星の位置だけが動いて、星座の形が変わっていくのを見られます（惑星や時計は変わりません）。":
    "Every star moves through space in its own direction and speed; nearby stars move most across the sky.\n"
    "Change the era to move only the stars and watch the constellations change shape (planets and the clock stay as they are).",
    "20万年前": "200,000 years ago", "今": "Now", "20万年後": "200,000 years ahead",
    "◀ 過去へ動かす": "◀ Into the past", "止める": "Stop", "未来へ動かす ▶": "Into the future ▶", "今に戻す": "Back to now",
    "見る星座:": "Constellation:", "明るい星の動いた跡を線で出す": "Show the paths of bright stars", "今の星の位置": "Star positions today",
    "大気の効果（地上モード：浮き上がり・減光・空の色）": "Atmosphere (ground mode: refraction, extinction, sky colour)",
    "地上の風景": "Landscape", "自分の360°写真を読み込む…": "Load my own 360° photo…",
    "風景は「地上から見る」のときに出ます": "The landscape appears in \"View from ground\"",
    "360°写真（正距円筒図）を選ぶ": "Choose a 360° photo (equirectangular)", "画像 (*.png *.jpg *.jpeg *.webp)": "Images (*.png *.jpg *.jpeg *.webp)",
    "画像を読めませんでした。": "Could not read the image.",
    "写真の左はしは、どの方位ですか？（北 = 0、東 = 90、南 = 180、西 = 270）\n"
    "空のところが透明な PNG にすると、星空が見えます。":
    "Which azimuth is the left edge of the photo? (N = 0, E = 90, S = 180, W = 270)\n"
    "Use a PNG with a transparent sky to see the stars.",
    "今夜の空ガイド…": "Tonight's sky guide…", "今夜の空ガイド": "Tonight's sky guide",
    "◀ 前の夜": "◀ Previous night", "今夜": "Tonight", "次の夜 ▶": "Next night ▶",
    "そらみ窓を起動したときに、今夜の空ガイドを出す": "Show tonight's sky guide when Soramado starts",
    "天の川の明るさ": "Milky Way brightness", "控えめ（暗い山の上の見え方）": "Subtle (as from a dark mountain site)",
    "ふつう": "Normal", "明るめ": "Bright", "とても明るい": "Very bright",
    "天の川の写真はダウンロード済みです。もう一度作り直しますか？\n\n": "The Milky Way photo is already downloaded. Make it again?\n\n",
    "ESA の Gaia 衛星が測った約17億個の星の光から作られた、全天の地図（CDS が配信）をダウンロードして、"
    "太陽系から見た空に天の川を表示します。\n\n通信量は約3MB です。よろしいですか？":
    "Download an all-sky map made from the light of about 1.7 billion stars measured by ESA's Gaia satellite "
    "(served by CDS), and show the Milky Way in the sky seen from the solar system.\n\nAbout 3 MB. Continue?",
    "天の川の写真をダウンロードしています…": "Downloading the Milky Way photo…",
    "全天の画像に並べ直しています…": "Building the all-sky image…",
    "天の川の写真を用意しました。\n\n太陽系の近くから見た空と、「地上から見る」の夜空に天の川が出ます。\n"
    "「表示」→「天の川を写真で表示」で、出さないようにもできます。":
    "The Milky Way photo is ready.\n\nIt appears in the sky seen from near the solar system and in the night sky of \"View from ground\".\n"
    "You can turn it off in View → Show the Milky Way photo.",
})
SHOWER_PARENTS_EN = {"qua": "Asteroid 2003 EH1", "lyr": "Comet Thatcher (C/1861 G1)", "eta": "Comet Halley",
                     "sda": "Comet 96P/Machholz", "per": "Comet 109P/Swift–Tuttle", "dra": "Comet 21P/Giacobini–Zinner",
                     "ori": "Comet Halley", "nta": "Comet 2P/Encke", "leo": "Comet 55P/Tempel–Tuttle",
                     "gem": "Asteroid 3200 Phaethon", "urs": "Comet 8P/Tuttle"}

SHOWERS_EN = {"qua": "Quadrantids", "lyr": "April Lyrids", "eta": "Eta Aquariids", "sda": "Southern Delta Aquariids",
              "per": "Perseids", "dra": "October Draconids", "ori": "Orionids", "nta": "Northern Taurids",
              "leo": "Leonids", "gem": "Geminids", "urs": "Ursids"}
