"""台本で自動上映する。

台本はふつうのテキストファイル（UTF-8）で、1行に1つの命令を書く。# から後ろはメモ。
命令は日本語でも英語でも書ける。例:

    時刻 2026-12-24 21:00
    地上 大阪
    字幕 大阪の夜空です
    待つ 4
    宇宙へ
    飛ぶ 月
    飛ぶ 土星 0.5
    回る 15 6
    引く 100億光年
    着陸 月 静かの海（アポロ11号）
    録画 終了

命令の一覧は COMMANDS（説明書の「台本で自動上映」にも同じ表がある）。
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from datetime import datetime

from . import astro
from .galaxies import LY_AU

# 命令: (日本語, 英語, 書き方, 説明)
COMMANDS = [
    ("時刻", "time", "時刻 2026-12-24 21:00", "日時を変える（パソコンの時刻帯で）。「時刻 今」で現在時刻、"
     "「時刻 日の入り」「時刻 日の出」で、いま立っている場所の夕方・明け方へ"),
    ("速さ", "speed", "速さ 1時間/秒", "時間の進む速さ（ツールバーの速さの表示と同じ書き方）。時間も動き出す"),
    ("止める", "pause", "止める", "時間を止める"),
    ("動かす", "play", "動かす", "時間を動かす"),
    ("場所", "place", "場所 大阪　／　場所 35.36 138.73", "地球の上の観測地（都市名か、緯度 経度）"),
    ("地上", "ground", "地上　／　地上 大阪", "すぐに地上から見る（場所も変えられる）"),
    ("宇宙へ", "launch", "宇宙へ", "地上から宇宙へ飛び立つ（着くまで待つ）"),
    ("着陸", "land", "着陸　／　着陸 月 静かの海（アポロ11号）", "地上へ降りる。月・火星なら場所も。行き先がなければ、いま見ている天体へ（着くまで待つ）"),
    ("飛ぶ", "fly", "飛ぶ 木星　／　飛ぶ 土星 0.5", "その天体へ飛ぶ。数字はふつうの距離の何倍か（0.5 なら半分まで近づく。着くまで待つ）"),
    ("引く", "zoom", "引く 100億光年　／　引く 30AU", "見ている天体からの距離を変える（km・AU・光年・万光年・億光年）"),
    ("回る", "orbit", "回る 15 6", "天体のまわりを回る（1秒に15度で6秒）"),
    ("向く", "look", "向く 土星　／　向く 南 30", "地上で、天体か方位・高度の方を向く"),
    ("視野", "fov", "視野 60", "地上で見る範囲 [度]"),
    ("待つ", "wait", "待つ 3", "秒数だけ待つ"),
    ("字幕", "caption", "字幕 大阪の夜空です", "画面の下に字幕を出す（「字幕」だけで消す）"),
    ("望遠鏡", "scope", "望遠鏡 dob200 9　／　望遠鏡 なし", "望遠鏡でのぞく（望遠鏡の記号と接眼レンズの mm）"),
    ("大気なし", "airless", "大気なし オン", "大気なしの見え方（オン／オフ）"),
    ("線", "lines", "線 黄道 オン", "空の線（黄道・赤道・子午線・目盛り）を出す・消す"),
    ("録画", "record", "録画 開始　／　録画 終了", "録画を始める・終える（ffmpeg が必要）"),
]
ALIASES = {}
for _ja, _en, _u, _d in COMMANDS:
    ALIASES[_ja] = _ja
    ALIASES[_en] = _ja
ALIASES.update({"待機": "待つ", "テロップ": "字幕", "降りる": "着陸", "移動": "飛ぶ", "距離": "引く"})

ON_WORDS = {"オン", "on", "はい", "出す", "true", "1"}
OFF_WORDS = {"オフ", "off", "いいえ", "消す", "false", "0"}
DIRECTIONS = {"北": 0, "北東": 45, "東": 90, "南東": 135, "南": 180, "南西": 225, "西": 270, "北西": 315,
              "n": 0, "ne": 45, "e": 90, "se": 135, "s": 180, "sw": 225, "w": 270, "nw": 315}
LINES = {"黄道": "show_ecliptic", "ecliptic": "show_ecliptic", "赤道": "show_equator", "天の赤道": "show_equator",
         "equator": "show_equator", "子午線": "show_meridian", "meridian": "show_meridian", "目盛り": "show_altaz",
         "grid": "show_altaz"}
UNITS = [("億光年", 1e8 * LY_AU), ("万光年", 1e4 * LY_AU), ("光年", LY_AU), ("ly", LY_AU), ("au", 1.0),
         ("万km", 1e4 / astro.AU_KM), ("km", 1.0 / astro.AU_KM)]


@dataclass
class Command:
    line: int
    op: str            # 日本語の命令名
    args: list
    text: str          # 命令の後ろの文（字幕などはそのまま使う）


class ScriptError(Exception):
    pass


def parse_distance(s: str) -> float:
    t = s.replace(",", "").replace(" ", "").lower()
    for unit, au in UNITS:
        if t.endswith(unit):
            num = t[: -len(unit)]
            try:
                return float(num) * au
            except ValueError:
                break
    raise ScriptError(f"距離が読めません: {s}（例: 100億光年、30AU、40万km）")


def parse_onoff(s: str) -> bool:
    t = s.strip().lower()
    if t in ON_WORDS:
        return True
    if t in OFF_WORDS:
        return False
    raise ScriptError(f"「オン」か「オフ」で書いてください: {s}")


def parse_time(s: str):
    t = s.strip()
    if t in ("今", "now", "現在"):
        return "now"
    if t in ("日の入り", "sunset", "日の出", "sunrise"):
        return t
    t = t.replace("/", "-").replace("　", " ")
    for fmt in ("%Y-%m-%d %H:%M:%S", "%Y-%m-%d %H:%M", "%Y-%m-%d"):
        try:
            dt = datetime.strptime(t, fmt)
            return astro.jd_from_datetime(dt.astimezone())
        except ValueError:
            pass
    raise ScriptError(f"日時が読めません: {s}（例: 2026-12-24 21:00）")


def parse(text: str) -> list[Command]:
    """台本の文を命令の列にする。書き方の間違いは、行番号つきでまとめて ScriptError にする。"""
    cmds, errors = [], []
    for n, raw in enumerate(text.splitlines(), 1):
        line = raw.split("#", 1)[0].strip() if not raw.lstrip().startswith(("字幕", "caption")) else raw.strip()
        if not line or line.startswith("#"):
            continue
        parts = line.replace("　", " ").split(None, 1)
        head = parts[0]
        op = ALIASES.get(head) or ALIASES.get(head.lower())
        if op is None:
            errors.append(f"{n}行目: 「{head}」という命令はありません")
            continue
        rest = parts[1].strip() if len(parts) > 1 else ""
        args = rest.split()
        try:
            _check(op, args, rest)
        except ScriptError as exc:
            errors.append(f"{n}行目: {exc}")
            continue
        cmds.append(Command(n, op, args, rest))
    if errors:
        raise ScriptError("\n".join(errors[:20]))
    if not cmds:
        raise ScriptError("命令が1つもありません")
    return cmds


def _check(op, args, rest):
    """命令ごとの書き方を、実行する前に確かめる。"""
    def need(k):
        if len(args) < k:
            raise ScriptError(f"「{op}」の後ろに書くことが足りません")

    if op == "時刻":
        need(1)
        parse_time(rest)
    elif op == "速さ":
        need(1)
    elif op in ("待つ", "視野"):
        need(1)
        try:
            float(args[0])
        except ValueError:
            raise ScriptError(f"数字で書いてください: {args[0]}")
    elif op == "回る":
        need(2)
        try:
            float(args[0]), float(args[1])
        except ValueError:
            raise ScriptError("「回る 速さ[度/秒] 秒数」と数字で書いてください")
    elif op == "引く":
        need(1)
        parse_distance(rest)
    elif op in ("飛ぶ", "場所", "向く"):
        need(1)
    elif op == "大気なし":
        need(1)
        parse_onoff(args[0])
    elif op == "線":
        need(2)
        if args[0].lower() not in LINES:
            raise ScriptError(f"線の名前は 黄道・赤道・子午線・目盛り のどれかです: {args[0]}")
        parse_onoff(args[1])
    elif op == "録画":
        need(1)
        if args[0] not in ("開始", "終了", "start", "stop"):
            raise ScriptError("「録画 開始」か「録画 終了」と書いてください")


def look_direction(args):
    """「向く 南 30」→ (方位, 高度) [度]。天体名なら None。"""
    a = args[0].lower()
    az = DIRECTIONS.get(a)
    if az is None:
        try:
            az = float(a)
        except ValueError:
            return None
    alt = 30.0
    if len(args) > 1:
        try:
            alt = float(args[1])
        except ValueError:
            pass
    return az % 360.0, max(-20.0, min(90.0, alt))


def ease_angle(rate_deg, dt):
    return math.radians(rate_deg) * dt


# 見本の台本（YouTube の紹介動画の流れ）
SAMPLE = """# そらみ窓の台本の見本：「Ubuntu で宇宙を旅する」紹介動画（約3分）
# 「ツアー」→「台本を再生」で動きます。「台本を再生して録画」なら、そのまま動画になります。
# 1行に1つの命令。# から後ろはメモです。命令の一覧は説明書の「台本で自動上映」にあります。

時刻 2026-12-14 21:00
地上 大阪
大気なし オフ
向く 南 35
視野 100
止める
字幕 大阪の夜空。今夜はふたご座流星群の夜です
待つ 5

字幕 さあ、宇宙へ飛び立ちましょう
宇宙へ
待つ 2

字幕 月へ
飛ぶ 月
回る 12 3
字幕 赤い惑星、火星
飛ぶ 火星
待つ 2
字幕 太陽系最大の惑星、木星と4つの衛星
飛ぶ 木星
回る 10 3
字幕 環をもつ土星
飛ぶ 土星 0.6
回る 15 4
字幕 太陽系の果て、冥王星
飛ぶ 冥王星
待つ 2

字幕 どんどん引いていくと……
引く 100AU
待つ 1
引く 5万光年
待つ 2
字幕 天の川銀河を抜けて
引く 1000万光年
待つ 2
字幕 宇宙の果てまで
引く 900億光年
待つ 3

字幕 ソンブレロ銀河
飛ぶ ソンブレロ銀河
待つ 3
字幕 アンドロメダ銀河
飛ぶ アンドロメダ銀河
回る 8 3

字幕 地球へ帰って、大阪に着陸します
飛ぶ 地球
着陸
待つ 2

字幕 今度は月に降り立ちます。アポロ11号が着陸した、静かの海です
宇宙へ
着陸 月 静かの海（アポロ11号）
向く 地球
視野 70
待つ 3
字幕 月から見た地球は、空のほぼ同じ場所で満ち欠けします
視野 8
速さ 1日/秒
待つ 10
止める

字幕 火星のジェゼロ・クレーター。夕方の空は青くなります
宇宙へ
着陸 火星 ジェゼロ・クレーター（パーサヴィアランス）
時刻 日の入り
向く 西 10
視野 90
速さ 10分/秒
待つ 8
止める

字幕 そらみ窓 ― Ubuntu で動く、無料の宇宙シミュレーター
待つ 4
字幕
"""
