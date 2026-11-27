"""天体望遠鏡モード：望遠鏡・双眼鏡と接眼レンズから、倍率・見える範囲・見える星の暗さを計算する。"""

from __future__ import annotations

import math
from dataclasses import dataclass

from .i18n import tr


@dataclass(frozen=True)
class Telescope:
    key: str
    name: str            # 表示名（日本語。tr() で英語に）
    aperture: float      # 口径 [mm]
    focal: float         # 焦点距離 [mm]（双眼鏡は 0）
    image: str           # 像の向きのふつうの値: "erect"（正立）/ "inverted"（倒立）/ "mirror"（左右反転）
    bino_mag: float = 0.0     # 双眼鏡の倍率
    bino_field: float = 0.0   # 双眼鏡の実視野 [度]


@dataclass(frozen=True)
class Eyepiece:
    focal: float         # 焦点距離 [mm]
    afov: float          # 見かけ視野 [度]


TELESCOPES = [
    Telescope("bino7", "双眼鏡 7×50", 50, 0, "erect", 7.0, 7.3),
    Telescope("bino10", "双眼鏡 10×50", 50, 0, "erect", 10.0, 6.5),
    Telescope("ref80", "屈折望遠鏡 口径80mm（焦点距離900mm）", 80, 900, "mirror"),
    Telescope("ref102", "屈折望遠鏡 口径102mm（焦点距離660mm）", 102, 660, "mirror"),
    Telescope("newt150", "反射望遠鏡 口径150mm（焦点距離750mm）", 150, 750, "inverted"),
    Telescope("dob200", "ドブソニアン 口径200mm（焦点距離1200mm）", 200, 1200, "inverted"),
    Telescope("sct203", "シュミットカセグレン 口径203mm（焦点距離2032mm）", 203, 2032, "mirror"),
    Telescope("dob300", "ドブソニアン 口径300mm（焦点距離1500mm）", 300, 1500, "inverted"),
]
BY_KEY = {t.key: t for t in TELESCOPES}

EYEPIECES = [
    Eyepiece(40, 44), Eyepiece(32, 52), Eyepiece(25, 52), Eyepiece(20, 68), Eyepiece(15, 52),
    Eyepiece(12, 60), Eyepiece(9, 52), Eyepiece(6, 60), Eyepiece(4, 60),
]

IMAGE_ORIENTATIONS = [
    ("erect", "正立（見たままの向き）"),
    ("inverted", "倒立（上下左右が逆）"),
    ("mirror", "左右反転（天頂プリズムを使ったとき）"),
]


@dataclass
class View:
    mag: float           # 倍率
    field: float         # 実視野 [度]
    limit: float         # 見える星の暗さの限界 [等級]（暗い空のとき）
    pupil: float         # ひとみ径 [mm]
    dawes: float         # 分解能 [秒角]（これより近い二重星は分かれて見えない）
    too_high: bool       # 倍率が高すぎて、ぼやける
    too_low: bool        # ひとみ径が7mmより大きく、光がむだになる


def compute(t: Telescope, e: Eyepiece | None) -> View:
    if t.bino_mag:
        mag, field = t.bino_mag, t.bino_field
    else:
        mag = t.focal / e.focal
        field = e.afov / mag
    pupil = t.aperture / mag
    # 口径が大きいほど暗い星まで見える（よく使われる目安の式）。ひとみ径が小さいと少し暗い星まで見える
    limit = 7.5 + 5.0 * math.log10(t.aperture / 10.0) - 0.4
    if pupil < 1.5:
        limit += 0.5
    return View(mag, field, limit, pupil, 116.0 / t.aperture, mag > 2.0 * t.aperture, pupil > 7.2)


def describe(t: Telescope, e: Eyepiece | None) -> str:
    v = compute(t, e)
    parts = [tr("{m:.0f}倍").format(m=v.mag), tr("実視野 {f}").format(f=_fmt_angle(v.field)),
             tr("見える星 {l:.1f}等まで").format(l=v.limit), tr("分解能 {d:.1f}″").format(d=v.dawes)]
    if v.too_high:
        parts.append(tr("⚠ 倍率が高すぎて、ぼやけます（口径mmの2倍まで）"))
    elif v.too_low:
        parts.append(tr("⚠ 倍率が低すぎて、光がむだになります"))
    return "・".join(parts)


def _fmt_angle(deg: float) -> str:
    if deg >= 1.0:
        return f"{deg:.1f}°"
    return f"{deg * 60:.0f}′"


def eyepiece_name(e: Eyepiece) -> str:
    return tr("{f:g}mm（見かけ視野 {a:g}°）").format(f=e.focal, a=e.afov)
