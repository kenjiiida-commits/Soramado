"""宇宙を描く 3D 画面（QOpenGLWidget）。"""

from __future__ import annotations

import math
import time

import numpy as np
from PySide6.QtCore import QPointF, QRect, QSize, Qt, QTimer, Signal
from PySide6.QtGui import (QBrush, QColor, QFont, QImage, QLinearGradient, QMatrix3x3, QMatrix4x4, QPainter, QPen, QPolygonF,
                           QVector2D, QVector3D, QVector4D)
from PySide6.QtOpenGL import (QOpenGLBuffer, QOpenGLFramebufferObject, QOpenGLFramebufferObjectFormat,
                              QOpenGLShader, QOpenGLShaderProgram, QOpenGLTexture, QOpenGLVertexArrayObject)
from PySide6.QtOpenGLWidgets import QOpenGLWidget

from . import astro, shaders, textures
from .stars import StarCatalog
from . import galaxies as gx
from .galaxy_catalog import GalaxyCatalog
from . import satellites as sats
from . import smallbodies as sbs
from . import cosmos
from . import spacecraft as crafts
from . import minorplanets as mpl
from . import exoplanets as exo
from . import eclipses
from . import nebulae as neb
from . import events as ev
from . import artsat
from . import dsoimages
from . import skyphoto
from .i18n import EN_MODE, tr, trx
from .bodies import BODIES, BY_KEY

# OpenGL の定数（PySide6 には定義が無いので数値で書く）
GL_DEPTH_TEST = 0x0B71
GL_BLEND = 0x0BE2
GL_COLOR_BUFFER_BIT = 0x4000
GL_DEPTH_BUFFER_BIT = 0x0100
GL_TRIANGLES = 0x0004
GL_TRIANGLE_STRIP = 0x0005
GL_LINE_STRIP = 0x0003
GL_FLOAT = 0x1406
GL_SRC_ALPHA = 0x0302
GL_ONE_MINUS_SRC_ALPHA = 0x0303
GL_ONE = 0x0001
GL_LEQUAL = 0x0203
GL_MULTISAMPLE = 0x809D
GL_POINTS = 0x0000
GL_LINES = 0x0001
GL_PROGRAM_POINT_SIZE = 0x8642
GL_RGBA16F = 0x881A
GL_FRAMEBUFFER = 0x8D40
GL_TEXTURE0 = 0x84C0
GL_TEXTURE_2D = 0x0DE1
GLOW_EXPOSURE = 1.3          # 星雲・銀河の明るさ（圧縮する前にかける倍率）
PHOTO_GAIN = 0.85            # 写真の明るさ
_c, _s = math.cos(astro.OBLIQUITY_J2000), math.sin(astro.OBLIQUITY_J2000)
ECL2EQ = np.array([[1.0, 0.0, 0.0], [0.0, _c, -_s], [0.0, _s, _c]])   # 黄道座標 → 赤道座標
# 光害（ボートル・スケール 1〜9）: 目で見える限界等級・天の川の見え方・空の明るさ
LIGHT_POLLUTION = [(1, "とても暗い空（山の上・離島）", "Very dark (mountains, islands)"),
                   (3, "暗い空（田舎）", "Dark (countryside)"), (5, "郊外の住宅地", "Suburban"),
                   (7, "街なか", "City"), (9, "都心", "City centre")]
NELM = {1: 7.5, 2: 7.1, 3: 6.6, 4: 6.1, 5: 5.6, 6: 5.1, 7: 4.6, 8: 4.2, 9: 4.0}
MW_VIS = {1: 1.0, 2: 1.0, 3: 0.9, 4: 0.6, 5: 0.35, 6: 0.15, 7: 0.04, 8: 0.0, 9: 0.0}
SKY_GLOW = {1: 0.0, 2: 0.02, 3: 0.06, 4: 0.12, 5: 0.22, 6: 0.35, 7: 0.55, 8: 0.75, 9: 1.0}
MW_GAINS = (0.25, 0.4, 0.65, 1.0)   # 天の川の写真の明るさ（控えめ・ふつう・明るめ・とても明るい）
PHOTO_FLIP = 1               # 写真の上下（テクスチャの向き）

FOV_DEG = 45.0
NEAR_AU = 1e-10
FAR_AU = 1e18
LOGC = astro.AU_KM            # 対数デプスは km 単位で計算する
MAX_DIST_AU = 8e15           # 約1300億光年（観測できる宇宙の外から眺められる）
LY_AU = gx.LY_AU
KM = 1.0 / astro.AU_KM


def format_length(au: float) -> str:
    """長さを分かりやすい単位で表す（km・AU・光年）。"""
    if EN_MODE:
        return _format_length_en(au)
    if au < 0.1:
        km = au * astro.AU_KM
        return f"{km / 1e4:,.1f} 万km" if km >= 1e4 else f"{km:,.0f} km"
    ly = au / gx.LY_AU
    if ly < 0.1:
        return f"{au:,.1f} AU" if au < 100 else f"{au:,.0f} AU"
    if ly < 1e4:
        return f"{ly:,.1f} 光年" if ly < 100 else f"{ly:,.0f} 光年"
    if ly < 1e8:
        return f"{ly / 1e4:,.1f} 万光年" if ly < 1e5 else f"{ly / 1e4:,.0f} 万光年"
    return f"{ly / 1e8:,.1f} 億光年"


def _format_length_en(au: float) -> str:
    if au < 0.1:
        return f"{au * astro.AU_KM:,.0f} km"
    ly = au / gx.LY_AU
    if ly < 0.1:
        return f"{au:,.1f} AU" if au < 100 else f"{au:,.0f} AU"
    if ly < 1e6:
        return f"{ly:,.1f} ly" if ly < 100 else f"{ly:,.0f} ly"
    if ly < 1e9:
        return f"{ly / 1e6:,.1f} million ly"
    return f"{ly / 1e9:,.1f} billion ly"


def _smooth(a, b, x):
    t = min(1.0, max(0.0, (x - a) / (b - a)))
    return t * t * (3 - 2 * t)


def _qmat(m: np.ndarray) -> QMatrix4x4:
    return QMatrix4x4(*[float(v) for v in m.reshape(-1)])


def _perspective(fov_deg, aspect, near, far):
    f = 1.0 / math.tan(math.radians(fov_deg) / 2)
    m = np.zeros((4, 4))
    m[0, 0] = f / aspect
    m[1, 1] = f
    m[2, 2] = (far + near) / (near - far)
    m[2, 3] = 2 * far * near / (near - far)
    m[3, 2] = -1.0
    return m


def _rz(t):
    c, s = math.cos(t), math.sin(t)
    return np.array([[c, s, 0], [-s, c, 0], [0, 0, 1]])


def _rx(t):
    c, s = math.cos(t), math.sin(t)
    return np.array([[1, 0, 0], [0, c, s], [0, -s, c]])


_EQ2ECL = _rx(astro.OBLIQUITY_J2000)


def body_orientation(body, jd) -> np.ndarray:
    """天体の座標軸（z=自転軸北極, x=本初子午線）→ 黄道座標 の回転行列。"""
    ra, dec = math.radians(body.pole_ra), math.radians(body.pole_dec)
    w = math.radians(astro.rotation_angle(jd, body.w0, body.w_rate))
    icrf_to_body = _rz(w) @ _rx(math.pi / 2 - dec) @ _rz(math.pi / 2 + ra)
    return _EQ2ECL @ icrf_to_body.T


def _sphere_mesh(slices=96, stacks=48) -> np.ndarray:
    verts = []
    for i in range(stacks):
        for j in range(slices):
            quad = []
            for di, dj in ((0, 0), (1, 0), (1, 1), (0, 1)):
                v = (i + di) / stacks          # 0=北極 1=南極
                u = (j + dj) / slices
                lat = math.pi / 2 - v * math.pi
                lon = -math.pi + u * 2 * math.pi
                quad.append((math.cos(lat) * math.cos(lon), math.cos(lat) * math.sin(lon),
                             math.sin(lat), u, v))
            a, b, c, d = quad
            verts += [a, b, c, a, c, d]
    return np.array(verts, dtype=np.float32)


def _ring_mesh(segments=256) -> np.ndarray:
    verts = []
    for k in range(segments + 1):
        t = 2 * math.pi * k / segments
        verts.append((math.cos(t), math.sin(t), 0.0))
        verts.append((math.cos(t), math.sin(t), 1.0))
    return np.array(verts, dtype=np.float32)


class _Mesh:
    """VAO と VBO のまとまり。"""

    def __init__(self, data: np.ndarray, layout: list[tuple[int, int]], mode: int):
        self.mode = mode
        self.count = len(data)
        self.vao = QOpenGLVertexArrayObject()
        self.vao.create()
        self.vao.bind()
        self.vbo = QOpenGLBuffer(QOpenGLBuffer.VertexBuffer)
        self.vbo.create()
        self.vbo.bind()
        raw = np.ascontiguousarray(data, dtype=np.float32).tobytes()
        self.vbo.allocate(raw, len(raw))
        stride = data.shape[1] * 4
        self._layout = layout
        offset = 0
        for loc, size in layout:
            self._f().glEnableVertexAttribArray(loc)
            self._prog_attrib(loc, offset, size, stride)
            offset += size * 4
        self.vao.release()
        self.vbo.release()

    @staticmethod
    def _f():
        from PySide6.QtGui import QOpenGLContext
        return QOpenGLContext.currentContext().functions()

    def _prog_attrib(self, loc, offset, size, stride):
        # glVertexAttribPointer の offset はポインタ扱いなので VoidPtr で渡す
        from shiboken6 import VoidPtr
        self._f().glVertexAttribPointer(loc, size, GL_FLOAT, False, stride, VoidPtr(offset))

    def update(self, data: np.ndarray):
        raw = np.ascontiguousarray(data, dtype=np.float32).tobytes()
        self.vbo.bind()
        self.vbo.allocate(raw, len(raw))
        self.vbo.release()
        self.count = len(data)

    def draw(self, f, count=None, first=0):
        self.vao.bind()
        f.glDrawArrays(self.mode, first, self.count if count is None else count)
        self.vao.release()


class SpaceView(QOpenGLWidget):
    """太陽系を表示する画面。"""

    targetChanged = Signal(str)
    timeChanged = Signal(float)
    statusChanged = Signal(str)
    starSelected = Signal(int)      # 選んだ恒星の番号（-1 = 選択解除）
    conSelected = Signal(int)       # 選んだ星座の番号（-1 = 選択解除）

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFocusPolicy(Qt.StrongFocus)
        self.setMouseTracking(False)

        # 時間
        self.jd = astro.jd_now()
        self.speed = 1.0          # 1秒あたりに進む秒数
        self.paused = False
        self._last_tick = time.monotonic()

        # 表示
        self.magnify = 1.0
        self.show_orbits = True
        self.show_labels = True

        # 恒星
        self.stars = StarCatalog()
        self.show_stars = True
        self.show_con_lines = True
        self.show_con_names = True
        self.show_star_names = True
        self.limit_mag = 6.5
        self.selected_star = -1
        self.selected_con = -1       # 選んだ星座（線を明るくして解説を出す）
        self._con_screen = []        # 画面に出した星座名の位置（ダブルクリック用）
        self.m_con_sel = None
        self._con_sel_i = -1
        self.show_galaxies = True
        self.show_small = True
        self.show_craft = True
        self.show_quasars = True
        self.show_cmb = True
        self.qso_count = 0
        self.gcat = GalaxyCatalog()
        self._sunlight_sky = 1.0
        self.show_nebulae = True
        self.show_photos = True
        self.show_mwphoto = True
        self.show_atmosphere = True
        self.landscape = None          # 地上の風景（landscape.Landscape）
        self.bortle = 3                # 光害（ボートル・スケール）
        self.airless = False           # 大気なし（地上モード）: 黒い空・地面なし・大気の効果なし
        self.step_unit = None          # コマ送りの1コマ [日]（恒星日・太陽日）。None は普通の再生
        self.step_rate = 10.0          # コマ送りで1秒に進む日数
        self._step_acc = 0.0
        self.show_trails = True        # 地上モードで、惑星と月の通った跡を残す
        self._trails = {}              # 天体 → [(JD, 方向)]
        self._trail_jd = None
        self._land_dirty = False    # 地上モードで大気の効果（大気差・減光・空の色）をつける
        self.show_star_trails = True   # 星の位置の時代を変えたとき、今の位置からの動きを線で出す
        self.m_trails = None
        self.mw_level = 2              # 天の川の明るさ（0 控えめ 〜 3 とても明るい）
        self._mw_w = 0.0               # 天の川の写真の濃さ（模式図の天の川銀河はその分だけ薄くする）
        self._photo_w = {}             # 天体ごとの写真の濃さ（0〜1）。模式図はその分だけ薄くする
        self.reload_photos(gl=False)
        self.show_meteors = True
        self.show_artsat = True
        self.artsats = artsat.load()     # 人工衛星（TLE をダウンロードしたとき）
        self._meteors = []           # いま流れている流星
        self._meteor_live = False
        self._meteor_rng = np.random.default_rng()
        self.m_neb = []              # 星雲・星団ごとの粒
        self.show_exo = True
        self.exo = exo.load()        # 系外惑星（ダウンロードしたとき）
        self._exo_orbits = {}        # 惑星系の番号 → 軌道の線のリスト
        self.show_minor = True
        self.mp = mpl.load()         # たくさんの小惑星・彗星（ダウンロードしたとき）
        self.m_mp = None
        self.m_mp_orbit = None
        self._mp_orbit_i = -1
        self._exo_screen = None

        # 地上モード（プラネタリウム）
        self.ground = False
        self.place = tr("大阪")
        self.lat, self.lon = 34.69, 135.50
        self.g_az = math.radians(180.0)     # 見ている方位（北=0、東=90度）
        self.g_alt = math.radians(30.0)     # 見ている高度
        self.g_fov = 90.0
        self._fov = FOV_DEG
        self._saved_space = None

        # カメラ（注視点のまわりを回る）
        self.target = "sun"
        self.yaw = math.radians(-60.0)
        self.pitch = math.radians(28.0)
        self.dist = 4.0
        self._fly = None          # 移動中の情報
        self._drag = None

        self.positions = sbs.add_positions(sats.add_positions(astro.all_positions(self.jd), self.jd), self.jd)
        self._orbit_jd = None
        self._screen = {}         # 天体の画面上の位置（ラベル・選択用）

        from PySide6.QtWidgets import QApplication
        QApplication.instance().aboutToQuit.connect(self._cleanup_gl)

        self.gl_error = ""
        self.recording = False
        self._idle_frames = 0
        self._vclock = 0.0
        self._on_frame = None

        self._timer = QTimer(self)
        self._timer.timeout.connect(self._tick)
        self._timer.start(16)

    # ---------------------------------------------------------- 公開する操作

    def set_jd(self, jd: float):
        lo, hi = 2341972.5, 2557447.5          # 1700年〜2290年
        self.jd = min(max(jd, lo), hi)
        self._refresh_positions()
        self.timeChanged.emit(self.jd)
        self.update()

    def is_minor(self, key: str) -> bool:
        if not key.startswith("mp:") or self.mp is None:
            return False
        try:
            return 0 <= int(key[3:]) < len(self.mp)
        except ValueError:
            return False

    def is_exo(self, key: str) -> bool:
        if not key.startswith("x:") or self.exo is None:
            return False
        try:
            return 0 <= int(key[2:]) < len(self.exo)
        except ValueError:
            return False

    def is_neb(self, key: str) -> bool:
        if not key.startswith("n:"):
            return False
        try:
            return 0 <= int(key[2:]) < len(neb.NEBULAE)
        except ValueError:
            return False

    def is_artsat(self, key: str) -> bool:
        if not key.startswith("s:"):
            return False
        try:
            return 0 <= int(key[2:]) < len(self.artsats)
        except ValueError:
            return False

    def reload_artsats(self):
        self.artsats = artsat.load()
        self.update()

    def valid_key(self, key: str) -> bool:
        return (self.is_artsat(key) or self.is_neb(key) or key in BY_KEY or self.is_galaxy(key) or key in crafts.BY_KEY or self.is_minor(key)
                or self.is_exo(key))

    def is_galaxy(self, key: str) -> bool:
        return key in gx.BY_KEY or key.startswith("c:") or key == "u:cmb"

    def set_target(self, key: str, fly: bool = True):
        if not self.valid_key(key):
            return
        self.selected_con = -1
        if self.ground:
            self.look_at(key)
            return
        new_dist = self._default_dist(key)
        self.selected_star = -1
        if fly:
            self._start_fly(key, new_dist, self._galaxy_view_dir(key))
        else:
            self.dist = new_dist
        self.target = key
        self.targetChanged.emit(key)
        self.update()

    # ---------------------------------------------------------- 地上モード

    def set_ground(self, on: bool):
        if on == self.ground:
            return
        if on:
            self._saved_space = (self.target, self.dist, self.yaw, self.pitch, self.magnify)
            self._fly = None
            self.magnify = 1.0
            self.ground = True
        else:
            self.ground = False
            if self._saved_space:
                self.target, self.dist, self.yaw, self.pitch, self.magnify = self._saved_space
        self.selected_star = -1
        self.update()

    def set_place(self, name, lat, lon):
        self.place, self.lat, self.lon = name, lat, lon
        self.update()

    def ground_altaz(self, key):
        """地上モードで、天体の高度・方位 [度]。"""
        off, zen, north, east = astro.observer_frame(self.jd, self.lat, self.lon)
        eye = self.positions["earth"] + off
        return astro.alt_az(self.display_pos(key) - eye, zen, north, east)

    def look_at(self, key):
        """地上モードで、その天体の方を向く。地平線の下なら False。"""
        if (key not in BY_KEY and not self.is_minor(key)) or key == "earth":
            return False
        alt, az = self.ground_altaz(key)
        self.g_az = math.radians(az)
        self.g_alt = math.radians(max(alt, 5.0))
        self.target = key
        self.targetChanged.emit(key)
        self.update()
        return alt > 0

    def select_con(self, ci: int):
        """星座を選ぶ（線を明るくして、解説パネルに解説を出す）。"""
        self.selected_con = ci
        self.selected_star = -1
        self.conSelected.emit(ci)
        self.update()

    def look_dir(self, direction, fov=None):
        """地上モードで、その方向（黄道座標の向き）を向く。"""
        off, zen, north, east = astro.observer_frame(self.jd, self.lat, self.lon)
        alt, az = astro.alt_az(np.asarray(direction), zen, north, east)
        self.g_az = math.radians(az)
        self.g_alt = math.radians(max(alt, 5.0))
        if fov:
            self.g_fov = fov
        self.update()
        return alt > 0

    def fly_to(self, key: str, dist: float | None = None, pitch: float | None = None, view_dir=None):
        """ツアー用：その天体へ、指定した距離まで飛んでいく。pitch は見下ろす角度 [度]。"""
        if not self.valid_key(key):
            return
        self.selected_star = -1
        new_dist = dist if dist is not None else self._default_dist(key)
        if view_dir is None:
            view_dir = self._galaxy_view_dir(key)
        if pitch is not None:
            p = math.radians(pitch)
            view_dir = np.array([math.cos(p) * math.cos(self.yaw), math.cos(p) * math.sin(self.yaw), math.sin(p)])
        self._start_fly(key, max(new_dist, self._min_dist(key)), view_dir)
        self.target = key
        self.targetChanged.emit(key)
        self.update()

    def overview(self):
        self.selected_star = -1
        self._start_fly("sun", 70.0, None)
        self.target = "sun"
        self.targetChanged.emit("sun")

    def _start_fly(self, to_key, to_dist, view_dir):
        from_focus = self._focus()
        sep = float(np.linalg.norm(self.display_pos(to_key) - from_focus))
        d0, d1 = self.dist, to_dist
        # 遠くへ行くときは、いったん引いて両方が見える高さを通る
        arc = max(0.0, math.log(max(sep, 1e-12) * 1.3) - max(math.log(d0), math.log(d1)))
        fl = {"from_focus": from_focus, "from_key": self.target, "to": to_key,
              "from_dist": d0, "to_dist": d1, "arc": arc, "t0": self.now(),
              "dur": min(4.5, 1.6 + 0.35 * max(0.0, math.log10(max(sep / max(min(d0, d1), 1e-12), 1.0))))}
        if view_dir is not None:
            yaw1 = math.atan2(view_dir[1], view_dir[0])
            dy = (yaw1 - self.yaw + math.pi) % (2 * math.pi) - math.pi
            fl.update(yaw0=self.yaw, dyaw=dy, pitch0=self.pitch,
                      pitch1=math.asin(max(-0.99, min(0.99, view_dir[2]))))
        self._fly = fl

    def _galaxy_view_dir(self, key):
        """銀河へ行くときの見下ろす向き（カメラが注視点のどちら側にいるか）。"""
        if self.is_neb(key):
            # 星雲・星団は、写真と同じ形に見えるように地球の側から見る
            c = neb.NEBULAE[int(key[2:])].pos
            return -c / np.linalg.norm(c)
        if not self.is_galaxy(key) or key == "u:cmb":
            return None
        if key.startswith("c:"):
            i = int(key[2:])
            normal = np.cross(self.gcat.major[i], self.gcat.second[i])
            to_us = -self.gcat.center[i] / np.linalg.norm(self.gcat.center[i])
            if np.dot(normal, to_us) < 0:
                normal = -normal
            v = to_us * 0.85 + normal * 0.45
            return v / np.linalg.norm(v)
        g = gx.BY_KEY[key]
        if self.has_photo(key) and g.center is not None:
            return -g.center / np.linalg.norm(g.center)        # 写真があるときは地球から見た向きで
        normal = g.rot[:, 2]
        if g.kind == "milkyway":
            # 銀河北極の側から、太陽のある側を手前にして見下ろす
            v = normal * math.cos(math.radians(50)) - g.rot[:, 0] * math.sin(math.radians(50))
        else:
            to_us = -g.center / np.linalg.norm(g.center)
            if np.dot(normal, to_us) < 0:
                normal = -normal
            # 地球から見える向きに近い角度から、少しだけ傾けて見る
            v = to_us * 0.85 + normal * 0.45
        return v / np.linalg.norm(v)

    def set_magnify(self, m: float):
        self.magnify = m
        self.dist = max(self.dist, self._min_dist(self.target))
        self.update()

    # ---------------------------------------------------------- 大きさ・位置

    def display_radius(self, key: str) -> float:
        if key in crafts.BY_KEY:
            return 1e-10
        if key.startswith("s:"):
            return 0.06 * KM
        if key.startswith("n:"):
            return neb.NEBULAE[int(key[2:])].radius_au
        if key.startswith("x:"):
            if self.exo is None:
                return 1e-3
            return (self.exo.systems[int(key[2:])]["srad"] or 1.0) * 695700.0 * KM
        if key.startswith("mp:"):
            d = self.mp.diameter_km(int(key[3:])) if self.mp is not None else 0.0
            return max(d, 1.0) / 2 * KM * self.magnify
        if key == "u:cmb":
            return cosmos.CMB_AU
        if key.startswith("c:"):
            return float(self.gcat.radius[int(key[2:])])
        if key in gx.BY_KEY:
            return gx.BY_KEY[key].radius_kpc * gx.KPC_AU
        b = BY_KEY[key]
        m = min(self.magnify, 10.0) if key == "sun" else self.magnify
        return b.radius_km * KM * m

    _INNER_KM = {"earth": 384400.0}

    def sat_scale(self, parent: str) -> float:
        """拡大表示のとき、衛星が惑星に埋もれないように衛星の軌道も広げる倍率。"""
        if self.magnify <= 1.0:
            return 1.0
        inner = self._INNER_KM.get(parent)
        if inner is None:
            moons = [s for s in sats.BY_PARENT[parent] if sats.is_major(s)] or sats.BY_PARENT[parent]
            inner = min(s.a_km for s in moons)
        return max(1.0, self.magnify * BY_KEY[parent].radius_km / (inner * 0.75))

    def sat_hidden(self, key: str) -> bool:
        """惑星を拡大表示しているとき、拡大した惑星の中に埋もれてしまう小さな衛星は出さない。"""
        st = sats.BY_KEY.get(key)
        if st is None or sats.is_major(st) or self.magnify <= 1.0:
            return False
        return st.a_km * self.sat_scale(st.parent) < self.magnify * BY_KEY[st.parent].radius_km * 1.3

    def moon_scale(self) -> float:
        return self.sat_scale("earth")

    def craft_pos(self, key: str) -> np.ndarray:
        sc = crafts.BY_KEY[key]
        p = crafts.position(sc, self.jd)
        if p is None:
            t0, t1 = crafts.span(sc)
            p = crafts.position(sc, min(max(self.jd, t0), t1))
        return p

    def display_pos(self, key: str) -> np.ndarray:
        if key in crafts.BY_KEY:
            return self.craft_pos(key)
        if key.startswith("s:"):
            sa = self.artsats[int(key[2:])]
            if not artsat.usable(sa, self.jd):
                return self.positions["earth"].copy()
            return self.positions["earth"] + artsat.offset(sa, self.jd)
        if key.startswith("n:"):
            return neb.NEBULAE[int(key[2:])].pos
        if key.startswith("x:"):
            if self.exo is None:
                return self.positions["sun"]
            return self.exo.pos[int(key[2:])]
        if key.startswith("mp:"):
            if self.mp is None:
                return self.positions["sun"]
            return self.mp.position(int(key[3:]), self.jd)
        if key == "u:cmb":
            return self.positions["sun"]
        if key.startswith("c:"):
            return self.gcat.center[int(key[2:])]
        if key in gx.BY_KEY:
            return gx.BY_KEY[key].center
        par = BY_KEY[key].parent if key in BY_KEY else ""
        if par and par != "sun":
            e = self.positions[par]
            return e + (self.positions[key] - e) * self.sat_scale(par)
        return self.positions[key]

    def _min_dist(self, key):
        if key in crafts.BY_KEY:
            return 1e-6
        if key.startswith("s:"):
            return 1e-8
        if key.startswith("n:"):
            return self.display_radius(key) * 0.3
        if key.startswith("x:"):
            return self.display_radius(key) * 1.5
        if key.startswith("mp:"):
            return max(1e-6, self.display_radius(key) * 1.15)
        if key == "u:cmb":
            return 1.0
        if self.is_galaxy(key):
            return self.display_radius(key) * 0.05
        return self.display_radius(key) * 1.15

    def _default_dist(self, key):
        if key.startswith("s:"):
            return 2.5e-5                 # 約3700 km 離れて、地球の丸みと一緒に見る
        if key.startswith("n:"):
            return self.display_radius(key) * 3.2
        if key.startswith("x:") and self.exo is not None:
            return max(self.exo.system_size(int(key[2:])) * 3.0, 0.05)
        if key.startswith("mp:"):
            # 軌道の形と、まわりの小惑星が見えるくらいの距離から
            r = float(np.linalg.norm(self.display_pos(key)))
            return max(0.8, min(r * 0.9, 60.0))
        if key in crafts.BY_KEY:
            # 航路が見えるくらいの距離から（遠くへ行った探査機ほど引いて見る）
            r = float(np.linalg.norm(self.craft_pos(key)))
            return max(1.5, r * 0.6)
        if key == "u:cmb":
            return cosmos.CMB_AU * 2.6
        if self.is_galaxy(key):
            return self.display_radius(key) * (2.3 if key == "g:mw" else 2.8)
        if key == "sun":
            return max(5.0, self._min_dist("sun") * 4)
        r = self.display_radius(key)
        if BY_KEY[key].ring:
            r *= 2.4
        return r * 7.0

    def _focus(self) -> np.ndarray:
        if self._fly:
            fl = self._fly
            s = min(1.0, (self.now() - fl["t0"]) / fl["dur"])
            s = s * s * (3 - 2 * s)
            # 移動元の天体も動き続けるので、その時点の位置から補間する
            a = fl["from_focus"] if fl["from_key"] is None else self.display_pos(fl["from_key"])
            if fl.get("arc", 0) > 0.5:
                # 遠距離の移動：視点が十分に引いてから横へ動く
                s = min(1.0, max(0.0, (s - 0.25) / 0.5))
                s = s * s * (3 - 2 * s)
            return a + (self.display_pos(fl["to"]) - a) * s
        return self.display_pos(self.target)

    def _cam_dir(self) -> np.ndarray:
        cp = math.cos(self.pitch)
        return np.array([cp * math.cos(self.yaw), cp * math.sin(self.yaw), math.sin(self.pitch)])

    # ---------------------------------------------------------- 時間

    def update(self):
        self._idle_frames = 0
        super().update()

    def now(self) -> float:
        """アニメーションの時計。録画中は「1コマ = 1/30秒」で進む仮想の時計になる。"""
        return self._vclock if self.recording else time.monotonic()

    def start_recording(self, on_frame):
        """録画を始める。描画するたびに on_frame(画像) が呼ばれる。"""
        self._vclock = time.monotonic()
        if self._fly:      # 飛行中なら、仮想の時計に合わせて続ける
            self._fly["t0"] -= time.monotonic() - self._vclock
        self._on_frame = on_frame
        self.recording = True

    def stop_recording(self):
        if self.recording and self._fly:
            self._fly["t0"] += time.monotonic() - self._vclock
        self.recording = False
        self._on_frame = None
        self._last_tick = time.monotonic()

    def _tick(self):
        if self.recording:
            from .recorder import FPS
            self._vclock += 1.0 / FPS
            dt = 1.0 / FPS
        else:
            now = time.monotonic()
            dt = now - self._last_tick
            self._last_tick = now
        now = self.now()
        if not self.paused and self.step_unit:
            # コマ送り: 1恒星日（星が止まって見える）か1太陽日（太陽が止まって見える）ずつ飛ぶ
            self._step_acc += dt * self.step_rate * (1.0 if self.speed >= 0 else -1.0)
            n = int(self._step_acc)
            if n:
                self._step_acc -= n
                self.set_jd(self.jd + n * self.step_unit)
        elif not self.paused and self.speed != 0:
            self.set_jd(self.jd + dt * self.speed / 86400.0)
        if self._fly:
            fl = self._fly
            s = min(1.0, (now - fl["t0"]) / fl["dur"])
            e = s * s * (3 - 2 * s)
            self.dist = math.exp(math.log(fl["from_dist"]) * (1 - e) + math.log(fl["to_dist"]) * e
                                 + 4.0 * e * (1 - e) * fl.get("arc", 0.0))
            if "dyaw" in fl:
                self.yaw = fl["yaw0"] + fl["dyaw"] * e
                self.pitch = fl["pitch0"] + (fl["pitch1"] - fl["pitch0"]) * e
            if s >= 1.0:
                self._fly = None
        if self.recording and self._on_frame:
            # 1コマずつ確実に描いて、録画に渡す
            self._on_frame(self.grabFramebuffer())
        elif not self.paused or self._fly or self._idle_frames < 2 or self._meteor_live:
            QOpenGLWidget.update(self)
            self._idle_frames = 0 if (not self.paused or self._fly) else self._idle_frames + 1
        # 時間が止まっていて何も動いていないときは描き直さない（パソコンの負担を減らす）

    def _refresh_positions(self):
        self.positions = sbs.add_positions(sats.add_positions(astro.all_positions(self.jd), self.jd), self.jd)
        if self._orbit_jd is None or abs(self.jd - self._orbit_jd) > 30:
            self._orbit_dirty = True

    # ---------------------------------------------------------- OpenGL

    def initializeGL(self):
        fmt = self.context().format()
        if (fmt.majorVersion(), fmt.minorVersion()) < (3, 3):
            self.gl_error = (f"このパソコンの OpenGL は {fmt.majorVersion()}.{fmt.minorVersion()} です。"
                             "そらみ窓には OpenGL 3.3 以上が必要です。グラフィックのドライバーを確認してください。")
            return
        try:
            self._init_gl()
        except Exception as exc:  # noqa: BLE001
            self.gl_error = f"3D 描画の準備に失敗しました。\n\n{exc}"

    def _init_gl(self):
        f = self.context().functions()
        f.glClearColor(0.0, 0.0, 0.0, 1.0)

        def prog(vs, fs):
            p = QOpenGLShaderProgram(self)
            if not p.addShaderFromSourceCode(QOpenGLShader.Vertex, vs):
                raise RuntimeError(p.log())
            if not p.addShaderFromSourceCode(QOpenGLShader.Fragment, fs):
                raise RuntimeError(p.log())
            if not p.link():
                raise RuntimeError(p.log())
            return p

        self.p_sphere = prog(shaders.SPHERE_VS, shaders.SPHERE_FS)
        self.p_ring = prog(shaders.RING_VS, shaders.RING_FS)
        self.p_line = prog(shaders.LINE_VS, shaders.LINE_FS)
        self.p_glow = prog(shaders.GLOW_VS, shaders.GLOW_FS)
        self.p_star = prog(shaders.STAR_VS, shaders.STAR_FS)
        self.p_sky = prog(shaders.SKY_VS, shaders.SKY_FS)
        self.m_stars = _Mesh(self.stars.vertex_data(), [(0, 3), (1, 1), (2, 1), (3, 3)], GL_POINTS)
        self.m_conlines = _Mesh(self.stars.line_vertices(), [(0, 3)], GL_LINES)
        self.p_galaxy = prog(shaders.GALAXY_VS, shaders.GALAXY_FS)
        self.p_tone = prog(shaders.TONE_VS, shaders.TONE_FS)
        self.p_photo = prog(shaders.PHOTO_VS, shaders.PHOTO_FS)
        self.p_mwsky = prog(shaders.MWSKY_VS, shaders.MWSKY_FS)
        self.p_land = prog(shaders.SKY_VS, shaders.LAND_FS)
        self._land_tex = None
        self._mw_tex = None
        self.m_quad = _Mesh(np.array([[-1, -1], [1, -1], [-1, 1], [1, 1]], np.float32), [(0, 2)], GL_TRIANGLE_STRIP)
        self.m_full = _Mesh(np.array([[-1, -1], [3, -1], [-1, 3]], np.float32), [(0, 2)], GL_TRIANGLES)
        self._glow_fbo = None
        self.m_galaxies = _Mesh(gx.build(), [(0, 3), (1, 1), (2, 1), (3, 3)], GL_POINTS)
        self.m_craft = {sc.key: _Mesh(crafts.path(sc, until=crafts.ANCHOR_JD + 365.25 * 5),
                                      [(0, 3)], GL_LINE_STRIP) for sc in crafts.SPACECRAFT}
        self.p_qso = prog(shaders.QSO_VS, shaders.QSO_FS)
        self.p_cmb = prog(shaders.CMB_VS, shaders.CMB_FS)
        self.m_qso = None
        self._load_quasars()
        self.p_mp = prog(shaders.MP_VS, shaders.MP_FS)
        self.p_neb = prog(shaders.NEB_VS, shaders.NEB_FS)
        self.m_neb = [_Mesh(neb.vertex_data(n), [(0, 3), (1, 3), (2, 1)], GL_POINTS) for n in neb.NEBULAE]
        self._load_minor()
        self.p_gcat = prog(shaders.GCAT_VS, shaders.GCAT_FS)
        self.m_gcat = _Mesh(self.gcat.vertex_data(),
                            [(0, 2), (1, 3), (2, 3), (3, 3), (4, 1), (5, 3), (6, 1), (7, 1)], GL_TRIANGLES)

        self.m_sphere = _Mesh(_sphere_mesh(), [(0, 3), (1, 2)], GL_TRIANGLES)
        self.m_ring = _Mesh(_ring_mesh(), [(0, 3)], GL_TRIANGLE_STRIP)
        quad = np.array([[-1, -1], [1, -1], [-1, 1], [1, 1]], dtype=np.float32)
        self.m_glow = _Mesh(quad, [(0, 2)], GL_TRIANGLE_STRIP)
        self.m_orbits = {}
        self._orbit_dirty = True

        self.tex = {}
        self._load_textures()
        self.context().aboutToBeDestroyed.connect(self._cleanup_gl)

    def _cleanup_gl(self):
        if self.gl_error or not getattr(self, "tex", None) or self.context() is None:
            return
        self.makeCurrent()
        for t in self.tex.values():
            t.destroy()
        self.tex = {}
        self.doneCurrent()

    def reload_textures(self):
        """画像を読み込み直す（ダウンロード後に呼ぶ）。"""
        if self.context() is None or self.gl_error:
            return
        self.makeCurrent()
        self._load_textures()
        self.doneCurrent()
        self.update()

    def _load_textures(self):
        old = getattr(self, "tex", {})
        for t in old.values():
            t.destroy()
        self.tex = {}
        self.downloaded = {}

        def make(img, repeat=True):
            t = QOpenGLTexture(img.convertToFormat(img.Format.Format_RGBA8888))
            t.setMinificationFilter(QOpenGLTexture.LinearMipMapLinear)
            t.setMagnificationFilter(QOpenGLTexture.Linear)
            t.setWrapMode(QOpenGLTexture.DirectionS,
                          QOpenGLTexture.Repeat if repeat else QOpenGLTexture.ClampToEdge)
            t.setWrapMode(QOpenGLTexture.DirectionT, QOpenGLTexture.ClampToEdge)
            return t

        for b in BODIES:
            img = textures.load_image(b.texture)
            self.downloaded[b.key] = img is not None
            self.tex[b.key] = make(img if img is not None else textures.procedural(b.key))
            for kind, fname in b.extra.items():
                img = textures.load_image(fname)
                if img is not None:
                    self.tex[f"{b.key}:{kind}"] = make(img, repeat=(kind != "ring"))
        if "saturn:ring" not in self.tex:
            self.tex["saturn:ring"] = make(textures.procedural_ring(), repeat=False)
        if "uranus:ring" not in self.tex:
            self.tex["uranus:ring"] = make(textures.procedural_ring_uranus(), repeat=False)
        if "neptune:ring" not in self.tex:
            self.tex["neptune:ring"] = make(textures.procedural_ring_neptune(), repeat=False)
        if "cmb" not in self.tex:
            self.tex["cmb"] = make(cosmos.cmb_texture())

    def _load_quasars(self):
        q = cosmos.load_quasars()
        if q is None:
            return
        data = cosmos.quasar_vertices(*q)
        if self.m_qso is None:
            self.m_qso = _Mesh(data, [(0, 3), (1, 3)], GL_POINTS)
        else:
            self.m_qso.update(data)
        self.qso_count = len(data)

    def _draw_nebulae(self, f, viewproj, h):
        if not self.show_nebulae or self.ground or not self.m_neb:
            return
        # 天の川銀河の外まで離れたら、模式図の天の川銀河にまかせて出さない
        k = 1.0 - _smooth(2e4 * LY_AU, 8e4 * LY_AU, self._sun_far)
        if k <= 0.01:
            return
        focal = h / (2 * math.tan(math.radians(self._fov) / 2))
        p = self.p_neb
        p.bind()
        self._common(p, viewproj)
        p.setUniformValue1f("u_focal", float(focal))
        p.setUniformValue1f("u_px", float(self.devicePixelRatioF()))
        p.setUniformValue1f("u_haze_gain", float(k * 2.2))
        f.glBlendFunc(GL_ONE, GL_ONE)
        for i, (n, m) in enumerate(zip(neb.NEBULAE, self.m_neb)):
            pw = 1.0 - 0.92 * self._photo_w.get(f"n:{i}", 0.0)     # 写真を出すときは模式図を薄く
            p.setUniformValue1f("u_haze_gain", float(k * 2.2 * pw * (0.25 + 0.75 * self._lp_dim())))
            c = n.pos - self._eye
            d = float(np.linalg.norm(c))
            # 星団の星は、近づくほど明るく見える（地球から見たときを基準に）
            star = min(1.0, 0.35 * (n.ly * LY_AU / max(d, 1.0)) ** 1.2) * k * pw
            p.setUniformValue1f("u_star_gain", float(star))
            p.setUniformValue("u_center", QVector3D(*c))
            m.draw(f)
        p.release()

    def _draw_neb_labels(self, painter, viewproj, w, h, placed, fm, focal):
        if not self.show_nebulae or self.ground or self._sun_far > 5e4 * LY_AU:
            return
        if self._sun_far < 3000.0 and self.dist < 1.0 and not self.is_neb(self.target):
            return            # 惑星や衛星を近くで見ているときは、背景の星雲・星団の名前は出さない
        items = []
        for i, n in enumerate(neb.NEBULAE):
            c = n.pos - self._eye
            d = float(np.linalg.norm(c))
            if d < n.radius_au * 0.8:
                continue                      # 中にいるときは名前を出さない
            pr = self._project(c, viewproj, w, h)
            if not pr or not (0 < pr[0] < w and 0 < pr[1] < h):
                continue
            r_px = n.radius_au / d * focal
            key = f"n:{i}"
            self._screen[key] = (pr[0], pr[1], max(r_px, 8.0))
            # 大きく見えるもの・注目しているもの・解説のある有名なものから
            prio = (key != self.target, -r_px - (40 if n.note else 0))
            items.append((prio, key, n, pr[0], pr[1], r_px))
        items.sort(key=lambda t: t[0])
        shown = 0
        limit = 5 if self.is_neb(self.target) else 18     # 星雲・星団を見ているときは、名前を少なめに
        for _p, key, n, x, y, r_px in items:
            if shown >= limit and key != self.target:
                break
            if r_px < 3 and not n.note and key != self.target and self._sun_far < 50 * LY_AU:
                continue                      # 太陽系の近くからは、有名なものだけ名前を出す
            rect = fm.boundingRect(n.name)
            rect.moveCenter(QPointF(x, y + min(r_px, h * 0.4) * 0.6 + 12).toPoint())
            if any(rect.intersects(r) for r in placed):
                continue
            placed.append(rect)
            col = {"ocl": QColor(170, 200, 255), "gcl": QColor(255, 215, 150), "pn": QColor(130, 230, 210),
                   "snr": QColor(255, 160, 120)}.get(n.type, QColor(255, 150, 170))
            painter.setPen(QPen(QColor(0, 0, 0, 180)))
            painter.drawText(rect.translated(1, 1), Qt.AlignCenter, n.name)
            painter.setPen(QPen(col.lighter(125) if key == self.target else col))
            painter.drawText(rect, Qt.AlignCenter, n.name)
            shown += 1

    def _draw_glow(self, f, viewproj, w, h, rel, radius_au, absmag, color):
        """恒星の光芒（太陽や、よその惑星系の恒星）。"""
        if self._atm_on():
            t = self._atm_transmit(rel)
            color = (color[0] * t[0], color[1] * t[1], color[2] * t[2])
            rel = self._atm_refract(rel)
        clip = viewproj @ np.append(rel, 1.0)
        if clip[3] <= 0:
            return
        ndc = clip[:2] / clip[3]
        pix_per_ndc = h / 2
        core_px = radius_au / clip[3] * (1 / math.tan(math.radians(self._fov) / 2)) * pix_per_ndc
        # 離れると暗い星になる
        m = absmag + 5 * math.log10(max(clip[3], 1e-9) / 206264.806 / 10.0)
        li = -0.4 * (m - self.limit_mag)
        glow_px = max(core_px * 3.0, min(28.0, 2.5 + 2.2 * li))
        if self.ground and self.airless:
            glow_px = max(core_px * 1.6, 4.0)       # 大気なし: まぶしさを小さくして、そばの星も見えるように
        glow_k = min(1.0, 0.3 + 0.35 * li)
        if glow_px <= 1.5:
            return
        f.glBlendFunc(GL_ONE, GL_ONE)
        p = self.p_glow
        p.bind()
        p.setUniformValue("u_center", QVector2D(*ndc))
        p.setUniformValue("u_size", QVector2D(glow_px / (w / 2), glow_px / (h / 2)))
        p.setUniformValue("u_color", QVector3D(color[0] * glow_k, color[1] * glow_k, color[2] * glow_k))
        p.setUniformValue1f("u_core", float(min(core_px / glow_px, 0.9)))
        depth = math.log2(1.0 + LOGC * clip[3]) / math.log2(FAR_AU * LOGC + 1.0)
        p.setUniformValue1f("u_depth", float(depth))
        self.m_glow.draw(f)
        p.release()
        f.glBlendFunc(GL_SRC_ALPHA, GL_ONE_MINUS_SRC_ALPHA)

    def _exo_near(self) -> int:
        """いま見ている、よその惑星系の番号（なければ -1）。"""
        if not self.is_exo(self.target) or self.ground:
            return -1
        i = int(self.target[2:])
        if np.linalg.norm(self.exo.pos[i] - self._eye) > max(self.exo.system_size(i) * 400.0, 200.0):
            return -1
        return i

    def _draw_exo_system(self, f, viewproj, w, h):
        i = self._exo_near()
        if i < 0:
            return
        s = self.exo.systems[i]
        rel = self.exo.pos[i] - self._eye
        self._draw_glow(f, viewproj, w, h, rel, self.display_radius(self.target), s["absmag"],
                        exo.temp_color(s["teff"]))
        if not self.show_orbits:
            return
        if i not in self._exo_orbits:
            meshes = []
            for k in range(len(s["planets"])):
                pts = self.exo.orbit_path(i, k)
                meshes.append(None if pts is None else _Mesh(pts, [(0, 3)], GL_LINE_STRIP))
            self._exo_orbits[i] = meshes
        p = self.p_line
        p.bind()
        self._common(p, viewproj)
        p.setUniformValue("u_offset", QVector3D(*rel))
        p.setUniformValue1f("u_scale", 1.0)
        for k, m in enumerate(self._exo_orbits[i]):
            if m is None:
                continue
            pl = s["planets"][k]
            col = (0.35, 0.95, 0.45) if self.exo.in_hz(pl) else exo.TYPES[exo.TYPE_INDEX[pl["type"]]][2]
            p.setUniformValue("u_color", QVector4D(*col, 0.55))
            m.draw(f)
        p.release()

    # ---------------------------------------------------------- 星雲・銀河の写真

    PHOTO_SMALL = 256              # 小さく見えるときの写真の大きさ
    PHOTO_BIG_MAX = 12             # 大きい写真を同時に持っておく数

    def reload_photos(self, gl=True):
        old = getattr(self, "_ph", {})
        if gl and old:
            self.makeCurrent()
            for e in old.values():
                for k in ("small", "big"):
                    if e.get(k):
                        e[k].destroy()
            self.doneCurrent()
        self._ph = {key: {"t": t, "path": p, "small": None, "big": None, "used": 0.0}
                    for key, (t, p) in dsoimages.available().items()}
        self.update()

    def has_photo(self, key) -> bool:
        return key in getattr(self, "_ph", {})

    def _photo_tex(self, e, big):
        k = "big" if big else "small"
        if e[k] is None:
            if self._ph_budget <= 0:
                return e["small"] if big else None
            self._ph_budget -= 1
            img = QImage(str(e["path"]))
            if img.isNull():
                return None
            if not big:
                img = img.scaled(self.PHOTO_SMALL, self.PHOTO_SMALL, Qt.IgnoreAspectRatio, Qt.SmoothTransformation)
            t = QOpenGLTexture(img.convertToFormat(QImage.Format.Format_RGBA8888))
            t.setMinificationFilter(QOpenGLTexture.LinearMipMapLinear)
            t.setMagnificationFilter(QOpenGLTexture.Linear)
            t.setWrapMode(QOpenGLTexture.ClampToEdge)
            e[k] = t
            if big:                       # 大きい写真は、使っていないものから捨てる
                bigs = sorted((x for x in self._ph.values() if x["big"] is not None), key=lambda x: x["used"])
                for x in bigs[:max(0, len(bigs) - self.PHOTO_BIG_MAX)]:
                    x["big"].destroy()
                    x["big"] = None
        return e[k]

    def _photo_geom(self, e):
        """写真の板の中心（太陽中心 [AU]）と、右（西）・上（北）の向き × 半分の大きさ。"""
        if "geom" not in e:
            t = e["t"]
            if t.key.startswith("n:"):
                pos = neb.NEBULAE[int(t.key[2:])].pos
            else:
                pos = gx.BY_KEY[t.key].center
            if pos is None:
                return None
            ra, dec = math.radians(t.ra), math.radians(t.dec)
            east = astro.equatorial_to_ecliptic(np.array([-math.sin(ra), math.cos(ra), 0.0]))
            north = astro.equatorial_to_ecliptic(np.array([-math.sin(dec) * math.cos(ra),
                                                           -math.sin(dec) * math.sin(ra), math.cos(dec)]))
            half = float(np.linalg.norm(pos)) * math.tan(math.radians(t.fov) / 2)
            e["geom"] = (np.asarray(pos, float), -east * half, north * half, half)
        return e["geom"]

    def _update_photo_weights(self, eye, focal):
        """カメラが地球の側から見ているほど写真を濃く、横や裏から見るときは模式図にする。"""
        self._photo_w = {}
        if not self.show_photos or self.ground or not self._ph:
            return
        neb_k = 1.0 - _smooth(2e4 * LY_AU, 8e4 * LY_AU, self._sun_far)
        for key, e in self._ph.items():
            isneb = key.startswith("n:")
            if (isneb and (not self.show_nebulae or neb_k <= 0.01)) or (not isneb and not self.show_galaxies):
                continue
            if not isneb and self._sun_far < 0.5 * LY_AU:
                continue
            g = self._photo_geom(e)
            if g is None:
                continue
            pos, _a1, _a2, half = g
            c = pos - eye
            d = float(np.linalg.norm(c))
            if d <= 0:
                continue
            align = float(np.dot(c / d, pos / np.linalg.norm(pos)))
            w = _smooth(math.cos(math.radians(35)), math.cos(math.radians(12)), align)
            w *= _smooth(0.12 * half, 0.45 * half, d)          # 近づきすぎたら模式図に
            if isneb:
                w *= neb_k
            if w > 0.01 and half / d * focal > 1.5:
                self._photo_w[key] = w

    def _draw_photos(self, f, viewproj, eye, focal):
        if not self._photo_w:
            return
        self._ph_budget = 4                      # 1回の描画で読み込む写真の数（引っかからないように）
        p = self.p_photo
        p.bind()
        p.setUniformValue("u_viewproj", _qmat(viewproj))
        p.setUniformValue1i("u_tex", 0)
        p.setUniformValue1f("u_flip", float(PHOTO_FLIP))
        f.glDisable(GL_DEPTH_TEST)
        f.glBlendFunc(GL_ONE, GL_ONE)
        now = time.monotonic()
        for key, w in sorted(self._photo_w.items(), key=lambda kv: kv[1]):
            e = self._ph[key]
            pos, a1, a2, half = self._photo_geom(e)
            c = pos - eye
            d = float(np.linalg.norm(c))
            size_px = half / d * focal
            tex = self._photo_tex(e, size_px > self.PHOTO_SMALL * 0.6)
            if tex is None:
                continue
            e["used"] = now
            s = 1000.0 / d                          # 遠すぎる座標を float で扱えるように縮める
            p.setUniformValue("u_center", QVector3D(*(c * s)))
            p.setUniformValue("u_ax1", QVector3D(*(a1 * s)))
            p.setUniformValue("u_ax2", QVector3D(*(a2 * s)))
            p.setUniformValue1f("u_gain", float(w * PHOTO_GAIN * (0.25 + 0.75 * self._lp_dim())))
            f.glActiveTexture(GL_TEXTURE0)
            tex.bind(0)
            self.m_quad.draw(f)
        p.release()
        if any(e["big"] is None and e["small"] is None for k, e in self._ph.items() if k in self._photo_w):
            QTimer.singleShot(30, self.update)        # まだ読み込んでいない写真があれば、続けて描く

    # ---------------------------------------------------------- 天の川の全天写真

    def reload_mwphoto(self):
        if self._mw_tex:
            self.makeCurrent()
            self._mw_tex.destroy()
            self.doneCurrent()
        self._mw_tex = None
        self.update()

    def has_mwphoto(self) -> bool:
        return skyphoto.path().is_file()

    def _mw_weight(self, sun_far) -> float:
        """太陽系の近くほど濃く。数千光年離れると空の見え方が変わるので消す。"""
        if not self.show_mwphoto or not self.has_mwphoto():
            return 0.0
        w = 1.0 - _smooth(200 * LY_AU, 4000 * LY_AU, sun_far)
        if self.ground:
            w *= self._night * self._lp_dim()
        return w

    def _lp_on(self) -> bool:
        return self.ground and not self.airless

    def _lp_dim(self) -> float:
        """光害で、天の川・星雲・銀河がどれくらい見えるか（0〜1）。"""
        return MW_VIS[self.bortle] if self._lp_on() else 1.0

    def _draw_mwsky(self, f, viewproj, w):
        if w <= 0.005:
            return
        if self._mw_tex is None:
            img = QImage(str(skyphoto.path()))
            if img.isNull():
                self._mw_tex = False
                return
            t = QOpenGLTexture(img.convertToFormat(QImage.Format.Format_RGBA8888))
            t.setMinificationFilter(QOpenGLTexture.LinearMipMapLinear)
            t.setMagnificationFilter(QOpenGLTexture.Linear)
            t.setWrapMode(QOpenGLTexture.DirectionS, QOpenGLTexture.Repeat)
            t.setWrapMode(QOpenGLTexture.DirectionT, QOpenGLTexture.ClampToEdge)
            self._mw_tex = t
        if not self._mw_tex:
            return
        p = self.p_mwsky
        p.bind()
        inv = np.linalg.inv(viewproj)
        p.setUniformValue("u_inv", _qmat(inv))
        p.setUniformValue("u_ecl2eq", QMatrix3x3([float(x) for x in ECL2EQ.reshape(-1)]))
        p.setUniformValue1i("u_tex", 0)
        p.setUniformValue1f("u_gain", float(w * MW_GAINS[self.mw_level]))
        f.glActiveTexture(GL_TEXTURE0)
        self._mw_tex.bind(0)
        f.glDisable(GL_DEPTH_TEST)
        self.m_full.draw(f)
        p.release()

    # ---------------------------------------------------------- 星の位置の時代（固有運動）

    def set_star_epoch(self, years: float):
        """星の位置だけを、今から years 年後にする（惑星や時計は変えない）。"""
        years = float(years)
        if years == self.stars.epoch:
            return
        self.stars.set_epoch(years)
        self.makeCurrent()
        self.m_stars.update(self.stars.vertex_data())
        self.m_conlines.update(self.stars.line_vertices())
        self._con_sel_i = -2                      # 選んだ星座の線も作り直す
        # 明るい星の動いた跡（今の位置 → その時代の位置）
        n = int(np.searchsorted(self.stars._mag0, 4.0))
        if years != 0.0 and n > 0:
            a = self.stars._pos0[:n] / np.maximum(self.stars._dist0[:n], 1e-9)[:, None]
            b = self.stars.dir[:n]
            # 大きく動く星もあるので、空の上の弧（大円）として細かく区切って描く
            k = 12
            t = np.linspace(0.0, 1.0, k + 1)[None, :, None]
            pts = a[:, None, :] * (1 - t) + b[:, None, :] * t
            pts /= np.maximum(np.linalg.norm(pts, axis=2, keepdims=True), 1e-9)
            segs = np.stack([pts[:, :-1], pts[:, 1:]], axis=2).reshape(-1, 3).astype(np.float32)
            if self.m_trails is None:
                self.m_trails = _Mesh(segs, [(0, 3)], GL_LINES)
            else:
                self.m_trails.update(segs)
        self.doneCurrent()
        self.update()

    # ---------------------------------------------------------- 地上の風景

    def set_landscape(self, ls):
        self.landscape = ls
        self._land_dirty = True
        self.update()

    def _draw_landscape(self, f, w, h):
        ls = self.landscape
        if ls is None:
            return
        if self._land_dirty:
            if self._land_tex:
                for t in self._land_tex:
                    if t:
                        t.destroy()
            def tex(arr, fmt):
                img = QImage(np.ascontiguousarray(arr).data, arr.shape[1], arr.shape[0], arr.strides[0], fmt).copy()
                t = QOpenGLTexture(img)
                t.setMinificationFilter(QOpenGLTexture.LinearMipMapLinear)
                t.setMagnificationFilter(QOpenGLTexture.Linear)
                t.setWrapMode(QOpenGLTexture.DirectionS, QOpenGLTexture.Repeat)
                t.setWrapMode(QOpenGLTexture.DirectionT, QOpenGLTexture.ClampToEdge)
                return t
            self._land_tex = (tex(ls.rgba, QImage.Format.Format_RGBA8888),
                              tex(ls.emit, QImage.Format.Format_RGB888) if ls.emit is not None else None)
            self._land_dirty = False
        right, up, fwd = self._basis
        zen, north, east = self._gframe
        p = self.p_land
        p.bind()
        p.setUniformValue("u_fwd", QVector3D(*fwd))
        p.setUniformValue("u_right", QVector3D(*right))
        p.setUniformValue("u_up", QVector3D(*up))
        t = math.tan(math.radians(self._fov) / 2)
        p.setUniformValue1f("u_tx", float(t * w / h))
        p.setUniformValue1f("u_ty", float(t))
        p.setUniformValue("u_zen", QVector3D(*zen))
        p.setUniformValue("u_north", QVector3D(*north))
        p.setUniformValue("u_east", QVector3D(*east))
        # 太陽の高さで明るさと色を変える（夜は月明かりほどに暗く、朝夕は赤み）
        sa = self._sun_alt
        day = _smooth(-8.0, 6.0, sa) * (0.15 + 0.85 * self._sunlight_sky)
        warm = 1.0 - _smooth(0.0, 15.0, sa)
        light = np.array([1.0, 1.0 - 0.25 * warm, 1.0 - 0.5 * warm]) * (0.03 + 0.97 * day)
        light += np.array([0.10, 0.07, 0.04]) * SKY_GLOW[self.bortle] * (1 - day)   # 街明かりでうっすら照らされる
        p.setUniformValue("u_light", QVector3D(*light))
        p.setUniformValue1f("u_night", float(1.0 - _smooth(-6.0, 2.0, sa)))
        p.setUniformValue1i("u_tex", 0)
        p.setUniformValue1i("u_emit", 1)
        f.glActiveTexture(GL_TEXTURE0)
        self._land_tex[0].bind(0)
        if self._land_tex[1] is not None:
            self._land_tex[1].bind(1)
        p.setUniformValue1i("u_has_emit", int(self._land_tex[1] is not None))
        f.glEnable(GL_BLEND)
        f.glBlendFunc(GL_SRC_ALPHA, GL_ONE_MINUS_SRC_ALPHA)
        self.m_glow.draw(f)
        f.glDisable(GL_BLEND)
        f.glActiveTexture(GL_TEXTURE0)
        p.release()

    def reload_exo(self):
        self.exo = exo.load()
        self._exo_orbits = {}
        self.update()

    def pick_exo(self, x, y, radius=9.0) -> int:
        if self.exo is None or not self.show_exo or self.ground or not len(self.exo):
            return -1
        pr = self._exo_screen
        if pr is None:
            return -1
        idx, sx, sy = pr
        d2 = (sx - x) ** 2 + (sy - y) ** 2
        j = int(np.argmin(d2)) if len(d2) else -1
        return int(idx[j]) if j >= 0 and d2[j] < radius * radius else -1

    def _draw_exo_markers(self, painter, viewproj, w, h, placed, fm):
        """系外惑星を持つ恒星の印（緑の丸）と、近い恒星の名前。"""
        self._exo_screen = None
        if self.exo is None or not self.show_exo or self.ground or not len(self.exo):
            return
        if self._sun_far < 3000.0 and not self.is_exo(self.target):
            return            # 太陽系の中を見ているときは、惑星や衛星のじゃまになるので出さない
        rel = self.exo.pos - self._eye
        clip = np.column_stack([rel, np.ones(len(rel))]) @ viewproj.T
        ok = clip[:, 3] > 0
        cw = np.where(ok, clip[:, 3], 1.0)
        sx = (clip[:, 0] / cw * 0.5 + 0.5) * w
        sy = (0.5 - clip[:, 1] / cw * 0.5) * h
        ok &= (sx > -10) & (sx < w + 10) & (sy > -10) & (sy < h + 10)
        dist = np.linalg.norm(rel, axis=1)
        # 太陽系の中から見るときは、空いっぱいに散らばるので、近い恒星（約300光年まで）にしぼる
        sun_far = self._sun_far
        limit = max(300 * exo.LY_AU, sun_far * 3.0)
        ok &= dist < limit
        cur = self._exo_near()
        if cur >= 0:
            ok[cur] = False          # 見ている惑星系そのものには印をつけない
        idx = np.nonzero(ok)[0]
        if len(idx) > 2500:
            idx = idx[np.argsort(dist[idx])[:2500]]
        self._exo_screen = (idx, sx[idx], sy[idx])
        order = idx[np.argsort(dist[idx])]
        # 近い600個は丸、それより遠いものは点でまとめて描く（たくさんの丸を1つずつ描くと重いので）
        painter.setBrush(Qt.NoBrush)
        painter.setPen(QPen(QColor(90, 230, 130, 150), 1.0))
        for j in order[:600]:
            painter.drawEllipse(QPointF(sx[j], sy[j]), 3.5, 3.5)
        if len(order) > 600:
            pen = QPen(QColor(90, 230, 130, 120), 3.0)
            pen.setCapStyle(Qt.RoundCap)
            painter.setPen(pen)
            painter.drawPoints(QPolygonF([QPointF(sx[j], sy[j]) for j in order[600:]]))
        # 名前：近いものから（ほかの名前と重ならないものだけ）
        painter.setPen(QColor(120, 235, 150, 210))
        shown = 0
        max_labels = 0 if cur >= 0 else 12      # よその惑星系の中にいるときは、ほかの恒星の名前は出さない
        for j in order[:80]:
            if shown >= max_labels:
                break
            name = self.exo.name(int(j))
            rect = fm.boundingRect(name).translated(int(sx[j] + 6), int(sy[j] + 4))
            if any(rect.intersects(r) for r in placed):
                continue
            placed.append(rect)
            painter.drawText(QPointF(sx[j] + 6, sy[j] + 4), name)
            shown += 1

    def _draw_exo_planets(self, painter, viewproj, w, h, placed, fm):
        """見ている惑星系の、惑星の点と名前。"""
        i = self._exo_near()
        if i < 0:
            return
        s = self.exo.systems[i]
        host = self.exo.pos[i] - self._eye
        pr = self._project(host, viewproj, w, h)
        if pr:
            painter.setPen(QColor(255, 240, 200))
            painter.drawText(QPointF(pr[0] + 10, pr[1] - 8), s["host"])
        for pl, off in zip(s["planets"], self.exo.planet_offsets(i, self.jd)):
            if off is None:
                continue
            q = self._project(host + off, viewproj, w, h)
            if not q or not (0 < q[0] < w and 0 < q[1] < h):
                continue
            col = exo.TYPES[exo.TYPE_INDEX[pl["type"]]][2]
            painter.setPen(Qt.NoPen)
            painter.setBrush(QColor.fromRgbF(*col))
            painter.drawEllipse(QPointF(q[0], q[1]), 3.5, 3.5)
            label = pl["letter"] or pl["name"]
            painter.setPen(QColor(120, 235, 150) if self.exo.in_hz(pl) else QColor.fromRgbF(*col))
            painter.drawText(QPointF(q[0] + 6, q[1] + 4), label)

    def _load_minor(self):
        if self.mp is None:
            return
        data = self.mp.vertex_data()
        layout = [(0, 3), (1, 3), (2, 4), (3, 3), (4, 1)]
        if self.m_mp is None:
            self.m_mp = _Mesh(data, layout, GL_POINTS)
        else:
            self.m_mp.update(data)
        self._mp_orbit_i = -1

    def reload_minor(self):
        """小惑星のデータを読み込み直す（ダウンロードが終わったら呼ぶ）。"""
        self.mp = mpl.load()
        if self.context() is None or self.gl_error:
            return
        self.makeCurrent()
        self._load_minor()
        self.doneCurrent()
        self.update()

    def _draw_minor(self, f, viewproj, sun_rel, sun_far):
        """たくさんの小惑星・彗星の点と、選んだ小惑星の軌道。"""
        if self.ground or self.m_mp is None or not self.show_minor:
            return
        k = 1.0 - _smooth(400.0, 5000.0, sun_far)
        if k <= 0.01:
            return
        p = self.p_mp
        p.bind()
        self._common(p, viewproj)
        p.setUniformValue1f("u_dt", float(self.jd - mpl.REF_JD))
        p.setUniformValue("u_sun", QVector3D(*sun_rel))
        # 引いて見るほど点が重なって白くなりすぎるので、1つ1つを暗くする
        h = max(1, self.height())
        focal = h / (2 * math.tan(math.radians(self._fov) / 2))
        d = max(min(sun_far, self.dist), 3.0)
        p.setUniformValue1f("u_gain", float(k * 0.083 * (12.0 / d) ** (0.8 if d < 12.0 else 1.5) * (focal / 1000.0) ** 2))
        p.setUniformValue1f("u_far_gain", float(k * 0.06 * _smooth(25.0, 120.0, d) * (focal / 1000.0) ** 2))
        p.setUniformValue1f("u_px", float(self.devicePixelRatioF()))
        f.glBlendFunc(GL_ONE, GL_ONE)
        self.m_mp.draw(f)
        f.glBlendFunc(GL_SRC_ALPHA, GL_ONE_MINUS_SRC_ALPHA)
        p.release()
        if self.is_minor(self.target):
            i = int(self.target[3:])
            if i != self._mp_orbit_i:
                pts = self.mp.orbit_path(i)
                if self.m_mp_orbit is None:
                    self.m_mp_orbit = _Mesh(pts, [(0, 3)], GL_LINE_STRIP)
                else:
                    self.m_mp_orbit.update(pts)
                self._mp_orbit_i = i
            p = self.p_line
            p.bind()
            self._common(p, viewproj)
            p.setUniformValue("u_offset", QVector3D(*sun_rel))
            p.setUniformValue1f("u_scale", 1.0)
            col = mpl.KINDS[int(self.mp.kind[i])][2]
            p.setUniformValue("u_color", QVector4D(*col, 0.8))
            self.m_mp_orbit.draw(f)
            p.release()

    def pick_minor(self, x, y, radius=7.0) -> int:
        """画面上の位置に近い小惑星の番号（なければ -1）。"""
        if self.mp is None or not self.show_minor or self.ground or self._sun_far > 5000.0:
            return -1
        pos = self.mp.positions(self.jd) - self._eye
        w, h = max(1, self.width()), max(1, self.height())
        clip = np.column_stack([pos, np.ones(len(pos))]) @ self._viewproj.T
        ok = clip[:, 3] > 0
        sx = (clip[:, 0] / np.where(ok, clip[:, 3], 1) * 0.5 + 0.5) * w
        sy = (0.5 - clip[:, 1] / np.where(ok, clip[:, 3], 1) * 0.5) * h
        d2 = np.where(ok, (sx - x) ** 2 + (sy - y) ** 2, 1e18)
        # 近いものの中から、明るい（大きい）ものを優先する
        near = np.nonzero(d2 < radius * radius)[0]
        if len(near) == 0:
            return -1
        hh = np.where(self.mp.h[near] > 50, 14.0, self.mp.h[near])
        score = d2[near] / (radius * radius) * 3.0 + hh
        return int(near[np.argmin(score)])

    def reload_quasars(self):
        """ダウンロードが終わったら呼ぶ。"""
        if self.context() is None or self.gl_error:
            return
        self.makeCurrent()
        self._load_quasars()
        self.doneCurrent()
        self.update()

    def _rebuild_orbits(self):
        for key in ("mercury", "venus", "earth", "mars", "jupiter", "saturn", "uranus", "neptune", "pluto"):
            b = BY_KEY[key]
            pts = astro.orbit_path(b.orbit, self.jd, 2048)
            if key in self.m_orbits:
                self.m_orbits[key].update(pts)
            else:
                self.m_orbits[key] = _Mesh(pts, [(0, 3)], GL_LINE_STRIP)
        self._rebuild_moon_orbit()
        for sb in sbs.SMALL_BODIES:
            if sb.key not in self.m_orbits:
                self.m_orbits[sb.key] = _Mesh(sbs.orbit_path(sb), [(0, 3)], GL_LINE_STRIP)
        if not hasattr(self, "_sat_orbit_jd"):
            self._rebuild_sat_orbits()
        self._orbit_jd = self.jd
        self._orbit_dirty = False

    def _rebuild_sat_orbits(self):
        """衛星の軌道線。計算に時間がかかるので、必要なときだけ作り直す。"""
        for key, pts in sats.orbit_paths(self.jd, 120).items():
            if key in self.m_orbits:
                self.m_orbits[key].update(pts)
            else:
                self.m_orbits[key] = _Mesh(pts, [(0, 3)], GL_LINE_STRIP)
        self._sat_orbit_jd = self.jd
        self._sat_orbit_at = time.monotonic()

    def _rebuild_moon_orbit(self):
        """月の軌道（地球中心、約27.3日で1周）。摂動で形が変わるので時々作り直す。"""
        n = 720
        pts = np.array([astro.moon_geocentric(self.jd + 27.321661 * (k / n - 0.5)) for k in range(n + 1)])
        if "moon" in self.m_orbits:
            self.m_orbits["moon"].update(pts)
        else:
            self.m_orbits["moon"] = _Mesh(pts, [(0, 3)], GL_LINE_STRIP)
        self._moon_orbit_jd = self.jd
        self._moon_orbit_at = time.monotonic()

    def _draw_far_universe(self, f, viewproj, eye, sun_rel, sun_far):
        """宇宙マイクロ波背景放射の球と、クエーサー。"""
        gly = cosmos.GLY_AU
        if self.show_cmb:
            k = _smooth(3 * gly, 25 * gly, sun_far)
            if k > 0.01:
                p = self.p_cmb
                p.bind()
                p.setUniformValue("u_viewproj", _qmat(viewproj))
                model = np.eye(4)
                model[:3, :3] *= cosmos.CMB_AU
                model[:3, 3] = sun_rel
                p.setUniformValue("u_model", _qmat(model))
                # 球の内側にいるときは背景として淡く、外から見るときははっきり
                inside = sun_far < cosmos.CMB_AU
                p.setUniformValue1f("u_alpha", float(k * (0.22 if inside else 0.45)))
                p.setUniformValue1i("u_tex", 0)
                self.tex["cmb"].bind(0)
                self.m_sphere.draw(f)
                p.release()
        if self.show_quasars and self.m_qso is not None:
            k = _smooth(0.05 * gly, 1.0 * gly, sun_far)
            if k > 0.01:
                p = self.p_qso
                p.bind()
                p.setUniformValue("u_viewproj", _qmat(viewproj))
                p.setUniformValue("u_eye", QVector3D(*eye))
                # 遠くから見ると点が重なって真っ白になるので、離れるほど一つ一つを暗くする
                crowd = min(1.0, 8 * gly / max(sun_far, 1.0))
                p.setUniformValue1f("u_gain", float(0.55 * k * crowd))
                p.setUniformValue1f("u_px", float(self.devicePixelRatioF()))
                self.m_qso.draw(f)
                p.release()

    def _glow_begin(self, f, w, h) -> bool:
        """星雲・銀河を描く浮動小数点の画面を用意する。使えないパソコンでは False（そのまま描く）。"""
        if self._glow_fbo is False:
            return False
        dpr = self.devicePixelRatioF()
        size = QSize(int(w * dpr), int(h * dpr))
        if self._glow_fbo is None or self._glow_fbo.size() != size:
            fmt = QOpenGLFramebufferObjectFormat()
            fmt.setAttachment(QOpenGLFramebufferObject.NoAttachment)
            fmt.setInternalTextureFormat(GL_RGBA16F)
            fbo = QOpenGLFramebufferObject(size, fmt)
            if not fbo.isValid():
                self._glow_fbo = False
                f.glBindFramebuffer(GL_FRAMEBUFFER, self.defaultFramebufferObject())
                return False
            self._glow_fbo = fbo
        self._glow_fbo.bind()
        f.glDisable(GL_DEPTH_TEST)
        f.glClearColor(0.0, 0.0, 0.0, 0.0)
        f.glClear(GL_COLOR_BUFFER_BIT)
        f.glClearColor(0.0, 0.0, 0.0, 1.0)
        return True

    def _glow_end(self, f):
        f.glBindFramebuffer(GL_FRAMEBUFFER, self.defaultFramebufferObject())
        f.glDisable(GL_DEPTH_TEST)
        p = self.p_tone
        p.bind()
        f.glActiveTexture(GL_TEXTURE0)
        f.glBindTexture(GL_TEXTURE_2D, self._glow_fbo.texture())
        p.setUniformValue1i("u_tex", 0)
        p.setUniformValue1f("u_exp", float(GLOW_EXPOSURE))
        self.m_full.draw(f)
        p.release()
        f.glEnable(GL_DEPTH_TEST)

    def _draw_galaxies(self, f, viewproj, eye, focal, h):
        p = self.p_galaxy
        p.bind()
        p.setUniformValue("u_viewproj", _qmat(viewproj))
        p.setUniformValue1f("u_kpc", float(gx.KPC_AU))
        p.setUniformValue1f("u_focal", float(focal))
        p.setUniformValue1f("u_px", float(self.devicePixelRatioF()))
        for g in gx.GALAXIES:
            c = g.center - eye
            d = float(np.linalg.norm(c))
            fade = 1.0
            if g.kind == "milkyway":
                # 太陽系のすぐ近くでは天の川銀河の模式図は出さない（本物の星を見せる）
                fade = _smooth(3 * LY_AU, 300 * LY_AU, self._sun_far)
                # 銀河の中（太陽の近く）から見る帯は、模式図の粒が目立つので控えめに
                fade *= 0.35 + 0.65 * _smooth(3000 * LY_AU, 30000 * LY_AU, self._sun_far)
            elif self._sun_far < 0.5 * LY_AU:
                continue          # 太陽系の中からは、よその銀河の模式図は小さすぎて見えないので描かない
            if fade <= 0.01:
                continue
            # 列ベクトルが銀河の軸。kpc の局所座標を AU に直す行列
            m3 = QMatrix3x3([float(v) for v in (g.rot * gx.KPC_AU).reshape(-1)])
            p.setUniformValue("u_rot", m3)
            p.setUniformValue("u_center", QVector3D(*c))
            # 画面上で小さい銀河は、点が重なりにくく暗く見えるので明るくする（見やすさのため）
            r_px = g.radius_kpc * gx.KPC_AU / max(d, 1.0) * focal
            boost = min(8.0, max(1.0, (60.0 / max(r_px, 1e-3)) ** 1.2))
            p.setUniformValue1f("u_boost", float(boost))
            p.setUniformValue1f("u_floor", float(4.0 / g.n * (1.0 - _smooth(2.0, 10.0, r_px))))
            p.setUniformValue1f("u_k", float(g.k))
            fade *= 1.0 - 0.92 * self._photo_w.get(g.key, 0.0)
            if g.kind == "milkyway":
                fade *= 1.0 - 0.9 * self._mw_w
            p.setUniformValue1f("u_fade", float(fade))
            # 天の川銀河の中にいるときは、すぐ近くの粒（大きくぼやける）を出さず、遠くの帯だけを見せる
            p.setUniformValue1f("u_near", 2.5 if g.kind == "milkyway" else 0.0)
            self.m_galaxies.draw(f, g.n, g.first)
        p.release()

    def _ground_dir(self, az, alt):
        zen, north, east = self._gframe if hasattr(self, "_gframe") else \
            astro.observer_frame(self.jd, self.lat, self.lon)[1:]
        return (math.cos(alt) * (math.cos(az) * north + math.sin(az) * east) + math.sin(alt) * zen)

    def _draw_sky(self, f, mode, w, h):
        right, up, fwd = self._basis
        p = self.p_sky
        p.bind()
        p.setUniformValue("u_fwd", QVector3D(*fwd))
        p.setUniformValue("u_right", QVector3D(*right))
        p.setUniformValue("u_up", QVector3D(*up))
        t = math.tan(math.radians(self._fov) / 2)
        p.setUniformValue1f("u_tx", float(t * w / h))
        p.setUniformValue1f("u_ty", float(t))
        zen = self._gframe[0]
        sun = self.positions["sun"] - self._eye
        p.setUniformValue("u_zen", QVector3D(*zen))
        p.setUniformValue("u_sun", QVector3D(*(sun / np.linalg.norm(sun))))
        p.setUniformValue1f("u_sunalt", float(self._sun_alt))
        p.setUniformValue1f("u_sunlight", float(self._sunlight_sky))
        p.setUniformValue1f("u_lp", float(SKY_GLOW[self.bortle]))
        p.setUniformValue1i("u_mode", mode)
        self.m_glow.draw(f)
        p.release()

    def _common(self, p, viewproj):
        p.setUniformValue("u_viewproj", _qmat(viewproj))
        p.setUniformValue1f("u_logc", float(LOGC))
        p.setUniformValue1f("u_fcoef", float(1.0 / math.log2(FAR_AU * LOGC + 1.0)))

    def paintGL(self):
        if self.gl_error:
            return
        f = self.context().functions()
        if self._orbit_dirty:
            self._rebuild_orbits()

        w, h = max(1, self.width()), max(1, self.height())
        dpr = self.devicePixelRatioF()
        f.glViewport(0, 0, int(w * dpr), int(h * dpr))
        f.glClear(GL_COLOR_BUFFER_BIT | GL_DEPTH_BUFFER_BIT)
        f.glEnable(GL_DEPTH_TEST)
        f.glDepthFunc(GL_LEQUAL)
        f.glEnable(GL_MULTISAMPLE)

        if self.ground:
            # 地上モード：観測地に立って、方位・高度の方向を見る
            self._fov = self.g_fov
            off, zen, north, east = astro.observer_frame(self.jd, self.lat, self.lon)
            self._gframe = (zen, north, east)
            self._record_trails()
            eye = self.positions["earth"] + off
            fwd = self._ground_dir(self.g_az, self.g_alt)
            up0 = zen
        else:
            self._fov = FOV_DEG
            focus = self._focus()
            if not self._fly:
                self.dist = max(self.dist, self._min_dist(self.target))
            eye = focus + self._cam_dir() * self.dist

            # ビュー行列（回転のみ。位置はカメラ原点の座標で渡す）
            fwd = focus - eye
            fwd /= np.linalg.norm(fwd)
            up0 = np.array([0.0, 0.0, 1.0])
        right = np.cross(fwd, up0)
        if np.linalg.norm(right) < 1e-9:
            right = np.array([1.0, 0.0, 0.0])
        right /= np.linalg.norm(right)
        up = np.cross(right, fwd)
        view = np.eye(4)
        view[0, :3], view[1, :3], view[2, :3] = right, up, -fwd
        proj = _perspective(self._fov, w / h, NEAR_AU, FAR_AU)
        viewproj = proj @ view
        self._set_atm_uniforms()
        self._viewproj = viewproj
        self._eye = eye
        self._basis = (right, up, fwd)

        rel = {b.key: self.display_pos(b.key) - eye for b in BODIES}
        sun_rel = rel["sun"]
        sun_far = float(np.linalg.norm(sun_rel))       # 太陽からカメラまで [AU]
        self._sun_far = sun_far
        focal = h / (2 * math.tan(math.radians(self._fov) / 2))
        # 星座は太陽の近くから見たときだけ意味があるので、離れるほど薄くする
        self._con_fade = 1.0 - _smooth(2000.0, 0.8 * LY_AU, sun_far)

        # ---- 地上モードの空の色
        night = 1.0
        limit = self.limit_mag
        f.glDisable(GL_DEPTH_TEST)
        self._sunlight_sky = 1.0
        if self.ground:
            # 日食のときは、太陽がかくれた割合に応じて空を暗くする（9割以上欠けると目に見えて暗くなる）
            if self.magnify <= 1.0001:
                light = eclipses.sun_light_fraction(eye, self.display_pos("sun"), self.display_radius("sun"),
                                                    self.display_pos("moon"), self.display_radius("moon"))
                self._sunlight_sky = _smooth(0.0, 0.08, light)
            zen = self._gframe[0]
            sun_dir = sun_rel / np.linalg.norm(sun_rel)
            self._sun_alt = math.degrees(math.asin(max(-1.0, min(1.0, float(np.dot(sun_dir, zen))))))
            if not self.airless:
                self._draw_sky(f, 0, w, h)
                # 空が明るいほど星は見えない
                night = 1.0 - _smooth(-15.0, -1.0, self._sun_alt) * self._sunlight_sky
                limit = self.limit_mag - (1.0 - night) * 7.0
                # 光害: 暗い空（限界等級6.5）を基準に、見える星の限界を変える
                limit = min(limit, self.limit_mag - (6.5 - NELM[self.bortle]))
        self._night = night

        # ---- 星空（いちばん奥なので最初に、奥行きなしで描く）
        f.glEnable(GL_BLEND)
        f.glBlendFunc(GL_ONE, GL_ONE)
        f.glEnable(GL_PROGRAM_POINT_SIZE)
        self._mw_w = self._mw_weight(sun_far)
        self._draw_mwsky(f, viewproj, self._mw_w)
        f.glBlendFunc(GL_ONE, GL_ONE)
        if not self.ground:
            self._draw_far_universe(f, viewproj, eye, sun_rel, sun_far)
        self._update_photo_weights(eye, focal)
        glow = self._glow_begin(f, w, h)
        if self.show_galaxies and not self.ground:
            self._draw_galaxies(f, viewproj, eye, focal, h)
        self._draw_nebulae(f, viewproj, h)
        f.glBlendFunc(GL_ONE, GL_ONE)
        if glow:
            self._glow_end(f)
        self._draw_photos(f, viewproj, eye, focal)
        f.glEnable(GL_DEPTH_TEST)
        if self.show_galaxies and not self.ground:
            p = self.p_gcat
            p.bind()
            p.setUniformValue("u_viewproj", _qmat(viewproj))
            p.setUniformValue("u_eye", QVector3D(*eye))
            p.setUniformValue("u_right", QVector3D(*right))
            p.setUniformValue("u_up", QVector3D(*up))
            p.setUniformValue1f("u_focal", float(focal))
            # 太陽系の中から見るときは、遠くの銀河は暗すぎて見えないので出さない
            crowd = min(1.0, 1.5e9 * LY_AU / max(sun_far, 1.0))
            gain = 0.7 * _smooth(30 * LY_AU, 3000 * LY_AU, sun_far) * crowd
            p.setUniformValue1f("u_gain", float(gain))
            if gain > 0.005:
                self.m_gcat.draw(f)
            p.release()
        if self.show_con_lines and self._con_fade > 0.01:
            p = self.p_line
            p.bind()
            self._common(p, viewproj)
            p.setUniformValue("u_offset", QVector3D(0, 0, 0))
            p.setUniformValue1f("u_scale", 1000.0)
            k = self._con_fade * (night if self.ground else 1.0)
            p.setUniformValue("u_color", QVector4D(0.10 * k, 0.18 * k, 0.34 * k, 1.0))
            self.m_conlines.draw(f)
            if self.selected_con >= 0:
                if self._con_sel_i != self.selected_con:
                    segs = self.stars.segments_at_epoch(self.selected_con).reshape(-1, 3).astype(np.float32)
                    if self.m_con_sel is None:
                        self.m_con_sel = _Mesh(segs, [(0, 3)], GL_LINES)
                    else:
                        self.m_con_sel.update(segs)
                    self._con_sel_i = self.selected_con
                kk = max(k, 0.6)
                p.setUniformValue("u_color", QVector4D(0.35 * kk, 0.65 * kk, 1.0 * kk, 1.0))
                self.m_con_sel.draw(f)
            p.release()
        if self.show_star_trails and self.m_trails is not None and self.stars.epoch != 0.0:
            p = self.p_line
            p.bind()
            self._common(p, viewproj)
            p.setUniformValue("u_offset", QVector3D(0, 0, 0))
            p.setUniformValue1f("u_scale", 1000.0)
            k = self._con_fade * (night if self.ground else 1.0)
            p.setUniformValue("u_color", QVector4D(0.45 * k, 0.3 * k, 0.12 * k, 1.0))
            self.m_trails.draw(f)
            p.release()
        if self.show_stars:
            f.glEnable(GL_PROGRAM_POINT_SIZE)
            p = self.p_star
            p.bind()
            p.setUniformValue("u_viewproj", _qmat(viewproj))
            p.setUniformValue("u_eye", QVector3D(*eye))
            p.setUniformValue1f("u_limit", float(limit))
            p.setUniformValue1f("u_px", float(self.devicePixelRatioF()))
            p.setUniformValue1f("u_gain", float(0.3 + 0.7 * night))
            p.setUniformValue1i("u_hide_unknown", int(sun_far > 3000.0))
            # よその惑星系のそばでは、カタログの星の位置の誤差（数AU）が目立つので、すぐ近くの星は描かない
            p.setUniformValue1f("u_near", float(30000.0 if (self.is_exo(self.target) and sun_far > 1e5) else 0.0))
            self.m_stars.draw(f)
            p.release()
        f.glDisable(GL_BLEND)
        f.glEnable(GL_DEPTH_TEST)

        # ---- 天体（球）
        p = self.p_sphere
        p.bind()
        self._common(p, viewproj)
        p.setUniformValue1i("u_tex", 0)
        p.setUniformValue1i("u_night", 1)
        p.setUniformValue1i("u_clouds", 2)
        p.setUniformValue("u_sun", QVector3D(*sun_rel))
        sat = BY_KEY["saturn"]
        sat_r = self.display_radius("saturn")
        sat_rot = body_orientation(sat, self.jd)
        for b in BODIES:
            if self.ground and b.key == "earth":
                continue          # 地上モードでは自分の立っている地球は描かない
            if self._is_small(b.key) and (self.ground or not self.show_small):
                continue
            if self.sat_hidden(b.key):
                continue
            r = self.display_radius(b.key)
            pos = rel[b.key]
            d = np.linalg.norm(pos)
            # 画面上で 1 ピクセルより小さいものは球を描かない（点とラベルで表す）
            if r / d * h / (2 * math.tan(math.radians(self._fov) / 2)) < 0.5:
                continue
            rot = body_orientation(b, self.jd)
            model = np.eye(4)
            model[:3, :3] = rot * r
            model[:3, 3] = pos
            p.setUniformValue("u_model", _qmat(model))
            mode = 1 if b.key == "sun" else (2 if b.key == "earth" else 0)
            p.setUniformValue1i("u_mode", mode)
            has_night = "earth:night" in self.tex and mode == 2
            has_clouds = "earth:clouds" in self.tex and mode == 2
            p.setUniformValue1i("u_has_night", int(has_night))
            p.setUniformValue1i("u_has_clouds", int(has_clouds))
            p.setUniformValue1i("u_has_ring", int(b.key == "saturn"))
            # 日食（地球に落ちる月の影）と月食（月に落ちる地球の影）。拡大表示のときは位置関係が変わるので出さない
            occ = {"earth": "moon", "moon": "earth"}.get(b.key) if self.magnify <= 1.0001 else None
            if occ:
                occ_r = self.display_radius(occ) * (1.02 if occ == "earth" else 1.0)   # 地球は大気のぶん少し大きな影
                p.setUniformValue("u_occ", QVector4D(*rel[occ], occ_r))
                p.setUniformValue1f("u_sun_r", float(self.display_radius("sun")))
            else:
                p.setUniformValue("u_occ", QVector4D(0, 0, 0, 0))
            p.setUniformValue1i("u_occ_red", int(b.key == "moon"))
            if b.key == "saturn":
                p.setUniformValue("u_shadow_c", QVector3D(*pos))
                p.setUniformValue("u_ring_n", QVector3D(*sat_rot[:, 2]))
                p.setUniformValue("u_ring_r", QVector2D(sat.ring[0] / sat.radius_km * sat_r,
                                                        sat.ring[1] / sat.radius_km * sat_r))
            self.tex[b.key].bind(0)
            if has_night:
                self.tex["earth:night"].bind(1)
            if has_clouds:
                self.tex["earth:clouds"].bind(2)
            self.m_sphere.draw(f)
        p.release()

        f.glEnable(GL_BLEND)
        f.glBlendFunc(GL_SRC_ALPHA, GL_ONE_MINUS_SRC_ALPHA)
        f.glDepthMask(False)

        # ---- 環（土星・天王星・海王星）
        for rk in ("saturn", "uranus", "neptune"):
            rb = BY_KEY[rk]
            pos = rel[rk]
            pr_r = self.display_radius(rk)
            if pr_r / np.linalg.norm(pos) * h <= 0.3:
                continue
            rot = sat_rot if rk == "saturn" else body_orientation(rb, self.jd)
            p = self.p_ring
            p.bind()
            self._common(p, viewproj)
            model = np.eye(4)
            model[:3, :3] = rot * pr_r
            model[:3, 3] = pos
            p.setUniformValue("u_model", _qmat(model))
            p.setUniformValue("u_radii", QVector2D(rb.ring[0] / rb.radius_km, rb.ring[1] / rb.radius_km))
            p.setUniformValue("u_sun", QVector3D(*sun_rel))
            p.setUniformValue("u_center", QVector3D(*pos))
            p.setUniformValue1f("u_planet_r", float(pr_r))
            p.setUniformValue1i("u_tex", 0)
            self.tex[f"{rk}:ring"].bind(0)
            self.m_ring.draw(f)
            p.release()

        # ---- 軌道
        if self.show_orbits and sun_far < 2e5 and not self.ground:
            p = self.p_line
            p.bind()
            self._common(p, viewproj)
            for key, mesh in self.m_orbits.items():
                b = BY_KEY[key]
                if key == "moon":
                    offset, scale = rel["earth"], self.moon_scale()
                    # 遠くから見るときは月の軌道を描かない
                    if np.linalg.norm(offset) > 0.08 * scale:
                        continue
                    if (abs(self.jd - self._moon_orbit_jd) > 1.0
                            and time.monotonic() - self._moon_orbit_at > 0.2):
                        self._rebuild_moon_orbit()
                elif key in sbs.BY_KEY or key == "pluto":
                    if not self.show_small:
                        continue
                    offset, scale = sun_rel, 1.0
                elif key in sats.BY_KEY:
                    st = sats.BY_KEY[key]
                    if self.sat_hidden(key):
                        continue
                    scale = self.sat_scale(st.parent)
                    offset = rel[st.parent]
                    # 惑星から遠いときは衛星の軌道を描かない（惑星の点に重なるだけなので）
                    if np.linalg.norm(offset) > st.a_km / astro.AU_KM * scale * 250:
                        continue
                    # 衛星の軌道は少しずつ変わるので、見えているときだけ時々作り直す
                    if (abs(self.jd - self._sat_orbit_jd) > 20
                            and time.monotonic() - self._sat_orbit_at > 2.0):
                        self._rebuild_sat_orbits()
                else:
                    offset, scale = sun_rel, 1.0
                alpha = 0.8 if key == self.target else (0.35 if (key in sats.BY_KEY or key in sbs.BY_KEY)
                                                         else 0.5)
                if key != self.target and key in sats.BY_KEY and not sats.is_major(sats.BY_KEY[key]):
                    alpha *= 0.45          # 小さな衛星の軌道は控えめに
                # 天体のすぐ近くでは、その天体の軌道線が手前を横切って邪魔なので薄くする
                for k2 in ((key,) if key != "earth" else ("earth", "moon")):
                    near = np.linalg.norm(rel[k2]) / (self.display_radius(k2) * 300.0)
                    alpha *= min(1.0, near * near)
                if alpha < 0.01:
                    continue
                p.setUniformValue("u_offset", QVector3D(*offset))
                p.setUniformValue1f("u_scale", float(scale))
                p.setUniformValue("u_color", QVector4D(*b.color, alpha))
                mesh.draw(f)
            p.release()

        # ---- たくさんの小惑星・彗星
        self._draw_minor(f, viewproj, sun_rel, sun_far)

        # ---- 探査機の航路
        if self.show_craft and not self.ground and sun_far < 2e5:
            p = self.p_line
            p.bind()
            self._common(p, viewproj)
            p.setUniformValue("u_offset", QVector3D(*sun_rel))
            p.setUniformValue1f("u_scale", 1.0)
            for sc in crafts.SPACECRAFT:
                # 航路が多いので、いま飛んでいる探査機（と選んでいる探査機）だけ描く
                t0, t1 = crafts.span(sc)
                if sc.key != self.target and not (t0 <= self.jd <= t1):
                    continue
                alpha = 0.95 if sc.key == self.target else (0.35 if crafts.BY_KEY.get(self.target) else 0.5)
                p.setUniformValue("u_color", QVector4D(*sc.color, alpha))
                self.m_craft[sc.key].draw(f)
            p.release()

        # ---- 太陽の光芒
        k = self._sunlight_sky        # 皆既日食のときは光芒を弱め、白っぽいコロナのように見せる
        sun_col = tuple(c * (0.25 + 0.75 * k) + 0.2 * (1 - k) for c in (1.0, 0.78, 0.45))
        self._draw_glow(f, viewproj, w, h, sun_rel, self.display_radius("sun"), 4.83, sun_col)

        # ---- よその惑星系（選んでいるとき）
        self._draw_exo_system(f, viewproj, w, h)

        f.glDepthMask(True)
        f.glDisable(GL_BLEND)
        f.glDisable(GL_DEPTH_TEST)

        if self.ground and not self.airless:
            self._draw_sky(f, 1, w, h)
            self._draw_landscape(f, w, h)
        self._draw_overlay(rel, viewproj, w, h)

    # ---------------------------------------------------------- ラベル・点

    # ---------------------------------------------------------- 大気（地上モード）

    def _atm_on(self) -> bool:
        return self.ground and self.show_atmosphere and not self.airless

    def _atm_refract(self, rel):
        """大気差: 地平線近くの天体を少し浮き上がらせる（シェーダーの atmRefract と同じ計算）。"""
        L = float(np.linalg.norm(rel))
        if L <= 0:
            return rel
        zen = self._gframe[0]
        d = np.asarray(rel, float) / L
        sn = max(-1.0, min(1.0, float(np.dot(d, zen))))
        h = math.degrees(math.asin(sn))
        if h < -3.0:
            return rel
        hc = max(h, -1.5)
        R = min(max(1.02 / math.tan(math.radians(hc + 10.3 / (hc + 5.11))) / 60.0, 0.0), 0.75)
        perp = zen - d * sn
        pl = float(np.linalg.norm(perp))
        if pl < 1e-9:
            return rel
        r = math.radians(R)
        return (d * math.cos(r) + perp / pl * math.sin(r)) * L

    def _atm_transmit(self, rel):
        zen = self._gframe[0]
        sn = max(float(np.dot(np.asarray(rel, float) / max(np.linalg.norm(rel), 1e-30), zen)), 0.0)
        X = min(1.0 / (sn + 0.025 * math.exp(-11.0 * sn)), 30.0)
        t = np.exp(-(X - 1.0) * np.array([0.05, 0.08, 0.14]))
        m = max(float(t[0]), 1e-4)
        return t / m * m ** 0.2            # シェーダーの atmTransmit と同じ

    def _set_atm_uniforms(self):
        """大気の効果を使うシェーダーに、天頂の向きとオン・オフを渡す。"""
        on = self._atm_on()
        zen = self._gframe[0] if self.ground else np.array([0.0, 0.0, 1.0])
        for p in (self.p_sphere, self.p_line, self.p_star, self.p_mwsky):
            p.bind()
            p.setUniformValue("u_atm_zen", QVector3D(*zen))
            p.setUniformValue1f("u_atm", 1.0 if on else 0.0)
            p.release()

    def _project(self, v, viewproj, w, h):
        if self._atm_on() and getattr(self, "_gframe", None) is not None:
            v = self._atm_refract(v)
        c = viewproj @ np.append(v, 1.0)
        if c[3] <= 0:
            return None
        x = (c[0] / c[3] * 0.5 + 0.5) * w
        y = (1 - (c[1] / c[3] * 0.5 + 0.5)) * h
        return x, y, c[3]

    def _draw_overlay(self, rel, viewproj, w, h):
        painter = QPainter(self)
        try:
            self._draw_overlay_body(painter, rel, viewproj, w, h)
        finally:
            if painter.isActive():          # 途中で失敗しても、描き終えておかないとアプリが落ちる
                painter.end()

    def _draw_overlay_body(self, painter, rel, viewproj, w, h):
        painter.setRenderHint(QPainter.Antialiasing)
        font = QFont()
        font.setPointSizeF(10.5)
        painter.setFont(font)
        focal = h / (2 * math.tan(math.radians(self._fov) / 2))

        self._screen = {}
        # 優先順：注目している天体 → 太陽 → 大きい順
        order = sorted(BODIES, key=lambda b: (b.key != self.target, b.key != "sun", -b.radius_km))
        placed = []
        fm = painter.fontMetrics()
        far = getattr(self, "_sun_far", 0.0) > 3000.0
        # 大きく見えている天体の円（この後ろにある天体や星の名前は出さない）
        discs = []
        for b in BODIES:
            pr = self._project(rel[b.key], viewproj, w, h)
            if pr and not self.sat_hidden(b.key):
                r = self.display_radius(b.key) / pr[2] * focal
                if r > 6:
                    discs.append((b.key, pr[0], pr[1], r, pr[2]))
        for b in order:
            if far and b.key != "sun":
                continue          # 太陽系から遠く離れると惑星は太陽に重なるので出さない
            if self.ground and (b.key == "earth" or not self._above(rel[b.key], margin=0.01)):
                continue          # 地平線の下の天体は見えない
            if self._is_small(b.key) and (self.ground or not self.show_small):
                continue          # 小天体は暗いので、地上からは出さない
            if self.sat_hidden(b.key):
                continue
            if self.ground and b.key in sats.BY_KEY and not sats.is_major(sats.BY_KEY[b.key]) \
                    and b.parent in ("jupiter", "saturn"):
                continue          # 地上からは見えない小さな衛星の名前は出さない
            pr = self._project(rel[b.key], viewproj, w, h)
            if pr is None:
                continue
            x, y, depth = pr
            rad_px = self.display_radius(b.key) / depth * focal
            if any(k != b.key and dd < depth and math.hypot(x - dx, y - dy) < dr * 0.97
                   for k, dx, dy, dr, dd in discs):
                continue          # 手前の天体の後ろにかくれている
            self._screen[b.key] = (x, y, rad_px)
            if not (-50 < x < w + 50 and -50 < y < h + 50):
                continue
            col = QColor.fromRgbF(*b.color)
            if rad_px < 2.5 and b.key != "sun":
                # 小さすぎて見えない天体は点で示す。衛星が惑星に重なるときは省く
                if b.parent not in ("sun", "") and b.parent in self._screen:
                    ex, ey, er = self._screen[b.parent]
                    if math.hypot(ex - x, ey - y) < max(4.0, er):
                        continue
                painter.setPen(Qt.NoPen)
                painter.setBrush(col)
                painter.drawEllipse(QPointF(x, y), 2.6, 2.6)
            if not self.show_labels:
                continue
            off = max(rad_px * 0.75, 4.0) + 4
            rect = fm.boundingRect(b.name).translated(int(x + off), int(y - off * 0.3)).adjusted(-3, -2, 3, 2)
            if any(rect.intersects(r) for r in placed):
                continue
            placed.append(rect)
            painter.setPen(QPen(QColor(0, 0, 0, 180)))
            painter.drawText(QPointF(x + off + 1, y - off * 0.3 + 1), b.name)
            painter.setPen(QPen(col.lighter(130) if b.key == self.target else col))
            painter.drawText(QPointF(x + off, y - off * 0.3), b.name if not far else tr("太陽（太陽系）"))

        # 大きな天体の円の中には、ほかの名前（星・彗星など）を置かない
        for _k, dx, dy, dr, _dd in discs:
            if dr > 20 and not (self.ground and _k == "earth"):
                a = dr * 0.7
                placed.append(QRect(int(dx - a), int(dy - a), int(2 * a), int(2 * a)))
        if self.ground:
            self._draw_trails(painter, viewproj, w, h)
            self._draw_compass(painter, viewproj, w, h, placed, fm)
        else:
            self._draw_neb_labels(painter, viewproj, w, h, placed, fm, focal)
            self._draw_galaxy_labels(painter, viewproj, w, h, placed, fm, focal)
        if self.show_cmb and getattr(self, "_sun_far", 0) > cosmos.CMB_AU * 1.05:
            top = rel["sun"] + self._basis[1] * cosmos.CMB_AU
            pr = self._project(top, viewproj, w, h)
            if pr:
                painter.setPen(QPen(QColor(255, 200, 150)))
                rect = fm.boundingRect(tr("宇宙マイクロ波背景放射（観測できる宇宙の果て・模式図）"))
                rect.moveCenter(QPointF(pr[0], pr[1] - 14).toPoint())
                painter.drawText(rect, Qt.AlignCenter, tr("宇宙マイクロ波背景放射（観測できる宇宙の果て・模式図）"))
                placed.append(rect)
        if self.show_small and not self.ground and not far:
            self._draw_comet_tails(painter, rel, viewproj, w, h)
        if self.show_craft and not self.ground and getattr(self, "_sun_far", 0) < 2e5:
            self._draw_craft(painter, viewproj, w, h, placed, fm)
        if self.is_minor(self.target):
            self._draw_minor_marker(painter, viewproj, w, h, placed, fm)
        self._draw_exo_planets(painter, viewproj, w, h, placed, fm)
        self._draw_exo_markers(painter, viewproj, w, h, placed, fm)
        self._draw_sky_labels(painter, viewproj, w, h, placed, fm)
        self._draw_meteors(painter, viewproj, w, h, placed, fm)
        self._draw_artsats(painter, viewproj, w, h, placed, fm)
        self._draw_scale(painter, w, h)
        painter.end()

    def _draw_craft(self, painter, viewproj, w, h, placed, fm):
        """探査機の現在位置（ひし形の印と名前）。"""
        for sc in crafts.SPACECRAFT:
            p = crafts.position(sc, self.jd)
            if p is None:
                continue
            pr = self._project(p - self._eye, viewproj, w, h)
            if not pr or not (0 < pr[0] < w and 0 < pr[1] < h):
                continue
            x, y, _ = pr
            self._screen[sc.key] = (x, y, 6.0)
            col = QColor.fromRgbF(*sc.color)
            painter.setPen(QPen(col, 1.5))
            painter.setBrush(col.darker(150))
            painter.drawPolygon([QPointF(x, y - 5), QPointF(x + 5, y), QPointF(x, y + 5), QPointF(x - 5, y)])
            rect = fm.boundingRect(sc.name).translated(int(x + 9), int(y + 4))
            if any(rect.intersects(r) for r in placed):
                continue
            placed.append(rect)
            painter.drawText(QPointF(x + 9, y + 4), sc.name)

    def _draw_minor_marker(self, painter, viewproj, w, h, placed, fm):
        """選んでいる小惑星・彗星の印（丸と名前）。"""
        i = int(self.target[3:])
        pr = self._project(self.mp.position(i, self.jd) - self._eye, viewproj, w, h)
        if not pr or not (0 < pr[0] < w and 0 < pr[1] < h):
            return
        x, y, _ = pr
        col = QColor.fromRgbF(*mpl.KINDS[int(self.mp.kind[i])][2])
        painter.setPen(QPen(col, 1.5))
        painter.setBrush(Qt.NoBrush)
        painter.drawEllipse(QPointF(x, y), 7, 7)
        name = self.mp.name(i)
        rect = fm.boundingRect(name).translated(int(x + 11), int(y + 4))
        if any(rect.intersects(r) for r in placed):
            return            # 同じ天体の名前がもう出ているとき（ハレー彗星など）
        placed.append(rect)
        painter.drawText(QPointF(x + 11, y + 4), name)

    @staticmethod
    def _is_small(key: str) -> bool:
        return key == "pluto" or key in sbs.BY_KEY

    def _draw_comet_tails(self, painter, rel, viewproj, w, h):
        """彗星の尾（太陽と反対向き）。太陽に近いほど長く明るい。"""
        from PySide6.QtGui import QLinearGradient
        for sb in sbs.SMALL_BODIES:
            if sb.kind != "comet":
                continue
            r = float(np.linalg.norm(self.positions[sb.key]))
            if r > 4.0:
                continue
            k = min(1.0, (4.0 - r) / 3.0)
            anti = self.positions[sb.key] / r
            length = min(0.5, 0.12 / max(r * r, 0.05)) * (0.4 + 0.6 * k)
            p0 = self._project(rel[sb.key], viewproj, w, h)
            p1 = self._project(rel[sb.key] + anti * length, viewproj, w, h)
            if not p0 or not p1:
                continue
            grad = QLinearGradient(QPointF(p0[0], p0[1]), QPointF(p1[0], p1[1]))
            grad.setColorAt(0.0, QColor(200, 225, 255, int(200 * k)))
            grad.setColorAt(1.0, QColor(120, 170, 255, 0))
            painter.setPen(QPen(grad, 2.5 + 3 * k, Qt.SolidLine, Qt.RoundCap))
            painter.drawLine(QPointF(p0[0], p0[1]), QPointF(p1[0], p1[1]))
            painter.setPen(Qt.NoPen)
            painter.setBrush(QColor(220, 235, 255, int(150 * k)))
            painter.drawEllipse(QPointF(p0[0], p0[1]), 3 + 2 * k, 3 + 2 * k)

    def _above(self, direction, margin=0.0) -> bool:
        """地上モードで、その方向が地平線（風景があれば、山や建物）より上か。"""
        if not self.ground or self.airless:
            return True                 # 大気なしでは地面がないので、地平線の下も見える
        d = np.asarray(direction, dtype=np.float64)
        d = d / max(float(np.linalg.norm(d)), 1e-30)
        sn = float(np.dot(d, self._gframe[0]))
        if self.landscape is None:
            return sn > -margin
        zen, north, east = self._gframe
        az = math.degrees(math.atan2(float(np.dot(d, east)), float(np.dot(d, north))))
        alt = math.degrees(math.asin(max(-1.0, min(1.0, sn))))
        if self.show_atmosphere:
            alt += 1.02 / math.tan(math.radians(max(alt, -1.5) + 10.3 / (max(alt, -1.5) + 5.11))) / 60.0 if alt > -3 else 0.0
        return alt > max(self.landscape.height_at(az), -math.degrees(margin))

    TRAIL_KEYS = ("mercury", "venus", "mars", "jupiter", "saturn", "uranus", "neptune", "moon")

    def clear_trails(self):
        self._trails = {}
        self._trail_jd = None
        self.update()

    def _record_trails(self):
        """地球から見た惑星・月の方向を記録する（星座の中を動いていく通り道）。"""
        if not (self.ground and self.show_trails):
            return
        last = self._trail_jd
        if last is not None and abs(self.jd - last) > 45:      # 日付を大きく変えたら、跡を消してやり直す
            self._trails = {}
            last = None
        if last is not None and abs(self.jd - last) < 0.5:
            return
        earth = self.positions["earth"]
        for k in self.TRAIL_KEYS:
            d = self.display_pos(k) - earth
            pts = self._trails.setdefault(k, [])
            pts.append(d / np.linalg.norm(d))
            if len(pts) > 1500:
                del pts[0]
        self._trail_jd = self.jd

    def _draw_trails(self, painter, viewproj, w, h):
        if not (self.ground and self.show_trails and self._trails):
            return
        for k, pts in self._trails.items():
            if len(pts) < 2:
                continue
            col = QColor.fromRgbF(*BY_KEY[k].color)
            col.setAlpha(170)
            painter.setPen(QPen(col, 1.4))
            prev = None
            for d in pts:
                pr = self._sky_xy(d, viewproj, w, h) if self._above(d) else None
                if pr and prev and k != "moon" and abs(pr[0] - prev[0]) < w / 4 and abs(pr[1] - prev[1]) < h / 4:
                    painter.drawLine(QPointF(prev[0], prev[1]), QPointF(pr[0], pr[1]))
                elif pr and k == "moon":
                    painter.drawEllipse(QPointF(pr[0], pr[1]), 1.6, 1.6)
                prev = pr

    def _draw_compass(self, painter, viewproj, w, h, placed, fm):
        """地平線上の方角（北・東・南・西など）。"""
        zen, north, east = self._gframe
        if self.airless:
            # 地面がないので、地平線を細い線で引く
            painter.setPen(QPen(QColor(120, 160, 110, 170), 1.2))
            prev = None
            for k in range(0, 361, 2):
                a = math.radians(k)
                pr = self._sky_xy(math.cos(a) * north + math.sin(a) * east, viewproj, w, h)
                if pr and prev and abs(pr[0] - prev[0]) < w and abs(pr[1] - prev[1]) < h:
                    painter.drawLine(QPointF(prev[0], prev[1]), QPointF(pr[0], pr[1]))
                prev = pr
        font = painter.font()
        big = QFont(font)
        big.setPointSizeF(font.pointSizeF() * 1.4)
        big.setBold(True)
        names = [(tr("北"), 0), (tr("北東"), 45), (tr("東"), 90), (tr("南東"), 135), (tr("南"), 180), (tr("南西"), 225),
                 (tr("西"), 270), (tr("北西"), 315)]
        for name, az in names:
            a = math.radians(az)
            d = math.cos(a) * north + math.sin(a) * east
            pr = self._sky_xy(d, viewproj, w, h)
            if not pr or not (0 < pr[0] < w and 0 < pr[1] < h + 40):
                continue
            main = len(name) == 1
            painter.setFont(big if main else font)
            painter.setPen(QPen(QColor(255, 120, 90) if name == tr("北") else QColor(230, 200, 140)))
            rect = painter.fontMetrics().boundingRect(name)
            rect.moveCenter(QPointF(pr[0], min(pr[1] + 18, h - 12)).toPoint())
            painter.drawText(rect, Qt.AlignCenter, name)
            placed.append(rect)
        painter.setFont(font)

    def _draw_galaxy_labels(self, painter, viewproj, w, h, placed, fm, focal):
        if not self.show_galaxies or self._sun_far < 30 * LY_AU:
            return
        eye = self._eye
        self._draw_catalog_labels(painter, viewproj, w, h, placed, fm, focal)
        for g in gx.GALAXIES:
            c = g.center - eye
            d = float(np.linalg.norm(c))
            if d < g.radius_kpc * gx.KPC_AU * 0.6:
                continue          # 銀河の中にいるときは名前を出さない
            if g.kind == "milkyway" and self._sun_far < 300 * LY_AU:
                continue
            pr = self._project(c, viewproj, w, h)
            if not pr:
                continue
            x, y, _ = pr
            r_px = g.radius_kpc * gx.KPC_AU / d * focal
            self._screen[g.key] = (x, y, max(r_px, 6.0))
            if not (0 < x < w and 0 < y < h):
                continue
            rect = fm.boundingRect(g.name)
            ty = y + min(r_px, h * 0.4) * 0.55 + 14
            rect.moveCenter(QPointF(x, ty).toPoint())
            if any(rect.intersects(r) for r in placed):
                continue
            placed.append(rect)
            painter.setPen(QPen(QColor(0, 0, 0, 180)))
            painter.drawText(rect.translated(1, 1), Qt.AlignCenter, g.name)
            painter.setPen(QPen(QColor(235, 200, 255) if g.key == self.target else QColor(200, 170, 235)))
            painter.drawText(rect, Qt.AlignCenter, g.name)

    def _catalog_screen(self, viewproj, w, h):
        """カタログの銀河の画面上の位置 (x, y, 見かけの半径px, 見えているか)。"""
        rel = self.gcat.center - self._eye
        d = np.maximum(np.linalg.norm(rel, axis=1), 1.0)
        clip = rel @ viewproj[:3, :3].T + viewproj[:3, 3]
        wc = rel @ viewproj[3, :3] + viewproj[3, 3]
        ok = wc > 0
        wc = np.where(ok, wc, 1.0)
        x = (clip[:, 0] / wc * 0.5 + 0.5) * w
        y = (1 - (clip[:, 1] / wc * 0.5 + 0.5)) * h
        focal = h / (2 * math.tan(math.radians(self._fov) / 2))
        return x, y, self.gcat.radius / d * focal, ok & (x > 0) & (x < w) & (y > 0) & (y < h)

    def _draw_catalog_labels(self, painter, viewproj, w, h, placed, fm, focal):
        x, y, rpx, vis = self._catalog_screen(viewproj, w, h)
        # 見かけの大きい順に、メシエ番号か通称のある銀河・大きく見える銀河に名前を付ける
        cand = np.nonzero(vis & ((rpx > 25) | ((self.gcat.messier != "") & (rpx > 2))
                                 | ((self.gcat.common != "") & (rpx > 6))))[0]
        cand = cand[np.argsort(-rpx[cand])][:40]
        painter.setPen(QPen(QColor(185, 160, 220)))
        for i in cand:
            name = self.gcat.label(int(i))
            rect = fm.boundingRect(name)
            rect.moveCenter(QPointF(x[i], y[i] + min(rpx[i], h * 0.3) * 0.6 + 12).toPoint())
            if any(rect.intersects(r) for r in placed):
                continue
            placed.append(rect)
            painter.drawText(rect, Qt.AlignCenter, name)

    def pick_catalog_galaxy(self, px, py) -> int:
        if not self.show_galaxies or getattr(self, "_viewproj", None) is None:
            return -1
        x, y, rpx, vis = self._catalog_screen(self._viewproj, self.width(), self.height())
        dist = np.hypot(x - px, y - py)
        hit = np.nonzero(vis & (dist < np.maximum(rpx, 10.0)))[0]
        if len(hit) == 0:
            return -1
        return int(hit[np.argmax(rpx[hit])])

    def _draw_scale(self, painter, w, h):
        """画面の横幅がどれくらいの長さかを左下に出す。"""
        ep = self.stars.epoch
        if ep != 0.0:
            y = abs(ep)
            if EN_MODE:
                txt = f"Star positions: {y:,.0f} years {'from now' if ep > 0 else 'ago'}"
            else:
                txt = f"星の位置：{y:,.0f} 年{'後' if ep > 0 else '前'}"
            f0 = painter.font()
            f1 = QFont(f0)
            f1.setPointSizeF(f0.pointSizeF() * 1.4)
            f1.setBold(True)
            painter.setFont(f1)
            painter.setPen(QPen(QColor(255, 200, 120)))
            painter.drawText(QPointF(12, h - 40), txt)
            painter.setFont(f0)
        if self.ground:
            alt = math.degrees(self.g_alt)
            az = math.degrees(self.g_az) % 360
            dirs = [tr("北"), tr("北北東"), tr("北東"), tr("東北東"), tr("東"), tr("東南東"), tr("南東"), tr("南南東"),
                    tr("南"), tr("南南西"), tr("南西"), tr("西南西"), tr("西"), tr("西北西"), tr("北西"), tr("北北西")]
            fov = f"{self.g_fov:.0f}" if self.g_fov >= 10 else f"{self.g_fov:.2g}"
            txt = trx(f"{self.place}　見ている方向: {dirs[int((az + 11.25) // 22.5) % 16]}"
                      f"（方位 {az:.0f}°・高度 {alt:.0f}°）　視野 {fov}°")
            painter.setPen(QPen(QColor(200, 205, 215)))
            painter.drawText(QPointF(12, h - 12), txt)
            return
        width_au = 2 * self.dist * math.tan(math.radians(self._fov) / 2) * w / h
        painter.setPen(QPen(QColor(170, 180, 200)))
        painter.drawText(QPointF(12, h - 12), tr("画面の横幅 約 ") + format_length(width_au))

    def _draw_artsats(self, painter, viewproj, w, h, placed, fm):
        """人工衛星（宇宙から見るときは地球のまわりに、地上から見るときは空に）。"""
        if not self.artsats or not self.show_artsat:
            return
        earth = self.positions["earth"]
        eye = self._eye
        if self.ground:
            dark = self._night > 0.5
            off, zen, north, east = astro.observer_frame(self.jd, self.lat, self.lon)
            for i, s in enumerate(self.artsats):
                if not artsat.usable(s, self.jd):
                    continue
                try:
                    alt, az, lit = artsat.topo(s, self.jd, self.lat, self.lon)
                except ValueError:
                    continue
                if alt <= 0:
                    continue
                a, z = math.radians(alt), math.radians(az)
                d = zen * math.sin(a) + (north * math.cos(z) + east * math.sin(z)) * math.cos(a)
                pr = self._sky_xy(d, viewproj, w, h)
                if not pr or not (0 < pr[0] < w and 0 < pr[1] < h):
                    continue
                bright = lit and dark
                if not bright and not s.featured:
                    continue
                col = QColor(255, 255, 240) if bright else QColor(150, 150, 150, 160)
                painter.setPen(Qt.NoPen)
                painter.setBrush(col)
                rr = 3.2 if (bright and s.featured) else 2.0
                painter.drawEllipse(QPointF(pr[0], pr[1]), rr, rr)
                self._screen[f"s:{i}"] = (pr[0], pr[1], 8.0)
                if s.featured:
                    painter.setPen(QPen(QColor(150, 230, 255) if bright else QColor(140, 150, 160)))
                    txt = s.ja + ("" if bright else tr("（影の中・明るい空で見えない）"))
                    painter.drawText(QPointF(pr[0] + 8, pr[1] - 6), txt)
            return
        # 宇宙から：地球の近く（約60万km以内）にいるときだけ
        if np.linalg.norm(eye - earth) > 0.004:
            return
        er = self.display_radius("earth")
        tgt = int(self.target[2:]) if self.is_artsat(self.target) else -1
        if tgt >= 0:
            # 選んでいる衛星の軌道（1周ぶん）
            pts = artsat.orbit_path(self.artsats[tgt], self.jd, 90) if artsat.usable(self.artsats[tgt], self.jd) else []
            prev = None
            painter.setPen(QPen(QColor(120, 220, 255, 150), 1.2))
            for o in pts:
                q = self._project(earth + o - eye, viewproj, w, h)
                if q and prev and not self._behind_earth(earth + o, earth, er):
                    painter.drawLine(QPointF(prev[0], prev[1]), QPointF(q[0], q[1]))
                prev = q if (q and not self._behind_earth(earth + o, earth, er)) else None
        for i, s in enumerate(self.artsats):
            if not artsat.usable(s, self.jd):
                continue
            pos = earth + artsat.offset(s, self.jd)
            if self._behind_earth(pos, earth, er):
                continue
            pr = self._project(pos - eye, viewproj, w, h)
            if not pr or not (0 < pr[0] < w and 0 < pr[1] < h):
                continue
            painter.setPen(Qt.NoPen)
            painter.setBrush(QColor(255, 255, 255) if s.featured else QColor(170, 170, 190))
            painter.drawEllipse(QPointF(pr[0], pr[1]), 3.0 if s.featured else 1.8, 3.0 if s.featured else 1.8)
            if s.featured:
                self._screen[f"s:{i}"] = (pr[0], pr[1], 8.0)
                painter.setPen(QPen(QColor(150, 230, 255)))
                painter.drawText(QPointF(pr[0] + 8, pr[1] - 6), s.ja)

    def _behind_earth(self, pos, earth, er) -> bool:
        """カメラから見て、その点が地球の向こう側にかくれているか。"""
        eye = self._eye
        d = pos - eye
        L = float(np.linalg.norm(d))
        if L <= 0:
            return False
        u = d / L
        t = float(np.dot(earth - eye, u))
        if t <= 0 or t >= L:
            return False
        return float(np.linalg.norm(eye + u * t - earth)) < er

    METEOR_BOOST = 10.0       # 流れる数は実際の何倍に増やして見せるか

    def active_showers(self):
        """いま活動している流星群と、その強さ（極大=1）。"""
        p = self.positions["earth"]
        lam = math.degrees(math.atan2(-p[1], -p[0])) % 360.0
        out = []
        for sh in ev.SHOWERS:
            days = (((lam - sh.lam + 180.0) % 360.0) - 180.0) / 0.9856
            a = math.exp(-math.log(3) * (days / sh.width) ** 2)
            if a > 0.03:
                out.append((sh, a))
        return out

    def _draw_meteors(self, painter, viewproj, w, h, placed, fm):
        """地上モードで、活動中の流星群の放射点と、流れる流星。"""
        self._meteor_live = False
        if not self.ground or not self.show_meteors:
            self._meteors = []
            return
        zen = self._gframe[0]
        now = time.monotonic()
        dt = min(0.2, now - getattr(self, "_meteor_t", now))
        self._meteor_t = now
        rng = self._meteor_rng
        dark = self._night
        for sh, act in self.active_showers():
            r = ev.radiant_vector(sh)
            alt = float(np.dot(r, zen))
            # 放射点の印
            if alt > 0:
                pr = self._sky_xy(r, viewproj, w, h)
                if pr and 0 < pr[0] < w and 0 < pr[1] < h:
                    painter.setPen(QPen(QColor(255, 210, 120, 200), 1.2))
                    x, y = pr[0], pr[1]
                    painter.drawLine(QPointF(x - 7, y), QPointF(x + 7, y))
                    painter.drawLine(QPointF(x, y - 7), QPointF(x, y + 7))
                    label = f"{sh.name} radiant" if EN_MODE else f"{sh.name}の放射点"
                    placed.append(fm.boundingRect(label).translated(int(x + 10), int(y - 6)))
                    painter.drawText(QPointF(x + 10, y - 6), label)
            if alt <= 0 or dark < 0.5:
                continue
            # 1秒あたりに流す数（実際の数 × METEOR_BOOST）
            rate = sh.zhr * act * alt * dark * self.METEOR_BOOST / 3600.0
            self._meteor_live = True
            n = rng.poisson(rate * dt)
            for _ in range(n):
                # 放射点から 15〜80度はなれたところで光り、放射点から遠ざかる向きに流れる
                rho = math.radians(rng.uniform(15, 80))
                t = rng.normal(0, 1, 3)
                t -= np.dot(t, r) * r
                t /= np.linalg.norm(t)
                start = r * math.cos(rho) + t * math.sin(rho)
                if float(np.dot(start, zen)) < 0.05:
                    continue
                length = math.radians(rng.uniform(4, 18) * (0.6 + 0.4 * 66 / max(sh.speed, 20)))
                dur = rng.uniform(0.25, 0.8) * (60 / sh.speed) ** 0.5
                self._meteors.append({"r": r, "t": t, "rho": rho, "len": length, "t0": now, "dur": dur,
                                      "b": rng.uniform(0.4, 1.0)})
        if self._meteors:
            self._meteor_live = True
        keep = []
        for m in self._meteors:
            k = (now - m["t0"]) / m["dur"]
            if k > 1.0:
                continue
            keep.append(m)
            head = m["rho"] + m["len"] * k
            tail = m["rho"] + m["len"] * max(0.0, k - 0.45)
            d1 = m["r"] * math.cos(head) + m["t"] * math.sin(head)
            d0 = m["r"] * math.cos(tail) + m["t"] * math.sin(tail)
            p1, p0 = self._sky_xy(d1, viewproj, w, h), self._sky_xy(d0, viewproj, w, h)
            if not p1 or not p0:
                continue
            fade = math.sin(math.pi * min(1.0, k)) * m["b"]
            grad = QLinearGradient(QPointF(p0[0], p0[1]), QPointF(p1[0], p1[1]))
            grad.setColorAt(0.0, QColor(255, 255, 255, 0))
            grad.setColorAt(1.0, QColor(255, 250, 230, int(255 * fade)))
            painter.setPen(QPen(QBrush(grad), 1.6 + 1.2 * m["b"]))
            painter.drawLine(QPointF(p0[0], p0[1]), QPointF(p1[0], p1[1]))
        self._meteors = keep

    def _sky_xy(self, direction, viewproj, w, h):
        return self._project(direction * 1000.0, viewproj, w, h)

    def _draw_sky_labels(self, painter, viewproj, w, h, placed, fm):
        cat = self.stars
        eye = self._eye

        def star_dir(i):
            v = cat.pos_pc[i] * 206264.806 - eye
            return v / np.linalg.norm(v)

        def star_mag(i):
            v = cat.pos_pc[i] * 206264.806 - eye
            return cat.mag[i] + 5 * math.log10(max(np.linalg.norm(v), 1.0) / max(cat.dist_pc[i] * 206264.806, 1.0))

        # 選んだ星の印
        if self.selected_star >= 0 and self.show_stars and self._above(star_dir(self.selected_star)):
            pr = self._sky_xy(star_dir(self.selected_star), viewproj, w, h)
            if pr:
                painter.setPen(QPen(QColor(120, 220, 255), 1.4))
                painter.setBrush(Qt.NoBrush)
                painter.drawEllipse(QPointF(pr[0], pr[1]), 9, 9)
        # 星座名
        con_k = self._con_fade * (self._night if self.ground else 1.0)
        self._con_screen = []
        if self.show_con_names and con_k > 0.05:
            font = painter.font()
            for ci, c in sorted(enumerate(cat.constellations), key=lambda t: t[0] != self.selected_con):
                if not self._above(c.center):
                    continue
                pr = self._sky_xy(c.center, viewproj, w, h)
                if not pr or not (0 < pr[0] < w and 0 < pr[1] < h):
                    continue
                rect = fm.boundingRect(c.name)
                rect.moveCenter(QPointF(pr[0], pr[1]).toPoint())
                if any(rect.intersects(r) for r in placed):
                    continue
                placed.append(rect)
                self._con_screen.append((rect.adjusted(-4, -4, 4, 4), ci))
                if ci == self.selected_con:
                    painter.setPen(QPen(QColor(140, 200, 255, max(200, int(255 * con_k)))))
                else:
                    painter.setPen(QPen(QColor(80, 115, 180, int(190 * con_k))))
                painter.drawText(rect, Qt.AlignCenter, c.name)
            painter.setFont(font)
        # 星の名前（明るい順）
        if self.show_star_names and self.show_stars and self._sun_far < 40 * LY_AU:
            painter.setPen(QPen(QColor(200, 200, 170, 220)))
            far = self._sun_far > 3000.0
            for i in cat.labeled:
                if far and cat.dist_pc[i] > 99999:
                    continue
                if (star_mag(i) if far else cat.mag[i]) > self.limit_mag:
                    if far:
                        continue
                    break
                if self.ground and (not self._above(star_dir(i))
                                    or cat.mag[i] > self.limit_mag - (1.0 - self._night) * 7.0):
                    continue
                pr = self._sky_xy(star_dir(i), viewproj, w, h)
                if not pr or not (0 < pr[0] < w and 0 < pr[1] < h):
                    continue
                name = cat.short_name(i)
                rect = fm.boundingRect(name).translated(int(pr[0] + 6), int(pr[1] - 4)).adjusted(-4, -2, 4, 2)
                if any(rect.intersects(r) for r in placed):
                    continue
                placed.append(rect)
                painter.drawText(QPointF(pr[0] + 6, pr[1] - 4), name)

    def pick_star(self, x, y, radius=12.0) -> int:
        """画面上の位置に近い、いちばん明るい星を探す。"""
        vp = getattr(self, "_viewproj", None)
        if vp is None or not self.show_stars:
            return -1
        cat = self.stars
        rel = cat.pos_pc * 206264.806 - self._eye
        dist = np.maximum(np.linalg.norm(rel, axis=1), 1.0)
        app = cat.mag + 5 * np.log10(dist / np.maximum(cat.dist_pc * 206264.806, 1.0))
        vis = app <= self.limit_mag
        if self._sun_far > 3000.0:
            vis &= cat.dist_pc < 99999
        idx = np.nonzero(vis)[0]
        if len(idx) == 0:
            return -1
        d = rel[idx] / dist[idx, None] * 1000.0
        clip = d @ vp[:3, :3].T + vp[:3, 3]
        wc = d @ vp[3, :3] + vp[3, 3]
        ok = wc > 0
        sx = (clip[:, 0] / np.where(ok, wc, 1) * 0.5 + 0.5) * self.width()
        sy = (1 - (clip[:, 1] / np.where(ok, wc, 1) * 0.5 + 0.5)) * self.height()
        dist = np.hypot(sx - x, sy - y)
        dist[~ok] = 1e9
        near = np.nonzero(dist < radius)[0]
        if len(near) == 0:
            return -1
        return int(idx[near[np.argmin(app[idx[near]])]])   # 近くでいちばん明るい星

    # ---------------------------------------------------------- マウス・キー

    def mousePressEvent(self, e):
        self._drag = (e.position(), e.button(), self.yaw, self.pitch, self.dist, self.g_az, self.g_alt,
                      self.g_fov)

    def mouseMoveEvent(self, e):
        if not self._drag:
            return
        p0, button, yaw0, pitch0, dist0, az0, alt0, fov0 = self._drag
        d = e.position() - p0
        if self.ground:
            if button == Qt.LeftButton:
                # 画面をつかんで動かす感覚（視野が狭いほどゆっくり）
                k = math.radians(self.g_fov) / max(self.height(), 1)
                self.g_az = az0 - d.x() * k
                self.g_alt = max(math.radians(-20), min(math.radians(90), alt0 + d.y() * k))
            else:
                self.g_fov = max(0.1, min(120.0, fov0 * math.exp(d.y() * 0.01)))
            self.update()
            return
        if button == Qt.LeftButton:
            self.yaw = yaw0 - d.x() * 0.006
            self.pitch = max(-1.55, min(1.55, pitch0 + d.y() * 0.006))
        else:
            self._fly = None
            self.dist = min(MAX_DIST_AU, max(self._min_dist(self.target), dist0 * math.exp(d.y() * 0.01)))
        self.update()

    def mouseReleaseEvent(self, e):
        self._drag = None

    def wheelEvent(self, e):
        steps = e.angleDelta().y() / 120.0
        if self.ground:
            self.g_fov = max(0.1, min(120.0, self.g_fov * (0.88 ** steps)))
            self.update()
            return
        if self._fly:
            self._fly = None
        self.dist = min(MAX_DIST_AU, max(self._min_dist(self.target), self.dist * (0.85 ** steps)))
        self.update()

    def mouseDoubleClickEvent(self, e):
        x, y = e.position().x(), e.position().y()
        best, best_d = None, 1e9
        for key, (sx, sy, r) in self._screen.items():
            dd = math.hypot(sx - x, sy - y)
            if dd < max(r, 14) and dd < best_d:
                best, best_d = key, dd
        if best:
            self.set_target(best)
            return
        xi = self.pick_exo(x, y)
        if xi >= 0:
            self.set_target(f"x:{xi}")
            return
        mi = self.pick_minor(x, y)
        if mi >= 0:
            self.set_target(f"mp:{mi}")
            return
        for rect, ci in self._con_screen:
            if rect.contains(int(x), int(y)):
                self.select_con(ci)
                return
        star = self.pick_star(x, y)
        if star >= 0 and self.selected_con >= 0:
            self.selected_con = -1
        if self.ground:
            self.selected_star = star
            self.starSelected.emit(star)
            self.update()
            return
        if star < 0:
            gi = self.pick_catalog_galaxy(x, y)
            if gi >= 0:
                self.set_target(f"c:{gi}")
                return
        self.selected_star = star
        self.starSelected.emit(self.selected_star)
        self.update()

    def keyPressEvent(self, e):
        k = e.key()
        if k == Qt.Key_Space:
            self.paused = not self.paused
            self.statusChanged.emit("")
        elif self.ground and k in (Qt.Key_Plus, Qt.Key_Equal, Qt.Key_Minus):
            self.g_fov = max(0.1, min(120.0, self.g_fov * (0.8 if k != Qt.Key_Minus else 1.25)))
        elif k in (Qt.Key_Plus, Qt.Key_Equal):
            self.dist = max(self._min_dist(self.target), self.dist * 0.8)
        elif k == Qt.Key_Minus:
            self.dist = min(MAX_DIST_AU, self.dist * 1.25)
        else:
            super().keyPressEvent(e)
        self.update()
