"""宇宙を描く 3D 画面（QOpenGLWidget）。"""

from __future__ import annotations

import math
import time

import numpy as np
from PySide6.QtCore import QPointF, Qt, QTimer, Signal
from PySide6.QtGui import QColor, QFont, QMatrix3x3, QMatrix4x4, QPainter, QPen, QVector2D, QVector3D, QVector4D
from PySide6.QtOpenGL import (QOpenGLBuffer, QOpenGLShader, QOpenGLShaderProgram, QOpenGLTexture,
                              QOpenGLVertexArrayObject)
from PySide6.QtOpenGLWidgets import QOpenGLWidget

from . import astro, shaders, textures
from .stars import StarCatalog
from . import galaxies as gx
from .galaxy_catalog import GalaxyCatalog
from . import satellites as sats
from . import smallbodies as sbs
from . import cosmos
from . import spacecraft as crafts
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

FOV_DEG = 45.0
NEAR_AU = 1e-10
FAR_AU = 1e18
LOGC = astro.AU_KM            # 対数デプスは km 単位で計算する
MAX_DIST_AU = 8e15           # 約1300億光年（観測できる宇宙の外から眺められる）
LY_AU = gx.LY_AU
KM = 1.0 / astro.AU_KM


def format_length(au: float) -> str:
    """長さを分かりやすい単位で表す（km・AU・光年）。"""
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
        self.show_galaxies = True
        self.show_small = True
        self.show_craft = True
        self.show_quasars = True
        self.show_cmb = True
        self.qso_count = 0
        self.gcat = GalaxyCatalog()

        # 地上モード（プラネタリウム）
        self.ground = False
        self.place = "大阪"
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

    def is_galaxy(self, key: str) -> bool:
        return key in gx.BY_KEY or key.startswith("c:") or key == "u:cmb"

    def set_target(self, key: str, fly: bool = True):
        if key not in BY_KEY and not self.is_galaxy(key) and key not in crafts.BY_KEY:
            return
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
        if key not in BY_KEY or key == "earth":
            return False
        alt, az = self.ground_altaz(key)
        self.g_az = math.radians(az)
        self.g_alt = math.radians(max(alt, 5.0))
        self.target = key
        self.targetChanged.emit(key)
        self.update()
        return alt > 0

    def fly_to(self, key: str, dist: float | None = None):
        """ツアー用：その天体へ、指定した距離まで飛んでいく。"""
        if key not in BY_KEY and not self.is_galaxy(key) and key not in crafts.BY_KEY:
            return
        self.selected_star = -1
        new_dist = dist if dist is not None else self._default_dist(key)
        self._start_fly(key, max(new_dist, self._min_dist(key)), self._galaxy_view_dir(key))
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
            inner = min(s.a_km for s in sats.BY_PARENT[parent])
        return max(1.0, self.magnify * BY_KEY[parent].radius_km / (inner * 0.75))

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
        if key == "u:cmb":
            return 1.0
        if self.is_galaxy(key):
            return self.display_radius(key) * 0.05
        return self.display_radius(key) * 1.15

    def _default_dist(self, key):
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
        if not self.paused and self.speed != 0:
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
        elif not self.paused or self._fly or self._idle_frames < 2:
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
        self.m_galaxies = _Mesh(gx.build(), [(0, 3), (1, 1), (2, 1), (3, 3)], GL_POINTS)
        self.m_craft = {sc.key: _Mesh(crafts.path(sc, until=crafts.ANCHOR_JD + 365.25 * 5),
                                      [(0, 3)], GL_LINE_STRIP) for sc in crafts.SPACECRAFT}
        self.p_qso = prog(shaders.QSO_VS, shaders.QSO_FS)
        self.p_cmb = prog(shaders.CMB_VS, shaders.CMB_FS)
        self.m_qso = None
        self._load_quasars()
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
            p.setUniformValue1f("u_fade", float(fade))
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
        if self.ground:
            zen = self._gframe[0]
            sun_dir = sun_rel / np.linalg.norm(sun_rel)
            self._sun_alt = math.degrees(math.asin(max(-1.0, min(1.0, float(np.dot(sun_dir, zen))))))
            self._draw_sky(f, 0, w, h)
            # 空が明るいほど星は見えない
            night = 1.0 - _smooth(-15.0, -1.0, self._sun_alt)
            limit = self.limit_mag - (1.0 - night) * 7.0
        self._night = night

        # ---- 星空（いちばん奥なので最初に、奥行きなしで描く）
        f.glEnable(GL_BLEND)
        f.glBlendFunc(GL_ONE, GL_ONE)
        f.glEnable(GL_PROGRAM_POINT_SIZE)
        if not self.ground:
            self._draw_far_universe(f, viewproj, eye, sun_rel, sun_far)
        if self.show_galaxies and not self.ground:
            self._draw_galaxies(f, viewproj, eye, focal, h)
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

        # ---- 土星の環
        pos = rel["saturn"]
        if sat_r / np.linalg.norm(pos) * h > 0.3:
            p = self.p_ring
            p.bind()
            self._common(p, viewproj)
            model = np.eye(4)
            model[:3, :3] = sat_rot * sat_r
            model[:3, 3] = pos
            p.setUniformValue("u_model", _qmat(model))
            p.setUniformValue("u_radii", QVector2D(sat.ring[0] / sat.radius_km, sat.ring[1] / sat.radius_km))
            p.setUniformValue("u_sun", QVector3D(*sun_rel))
            p.setUniformValue("u_center", QVector3D(*pos))
            p.setUniformValue1f("u_planet_r", float(sat_r))
            p.setUniformValue1i("u_tex", 0)
            self.tex["saturn:ring"].bind(0)
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

        # ---- 探査機の航路
        if self.show_craft and not self.ground and sun_far < 2e5:
            p = self.p_line
            p.bind()
            self._common(p, viewproj)
            p.setUniformValue("u_offset", QVector3D(*sun_rel))
            p.setUniformValue1f("u_scale", 1.0)
            for sc in crafts.SPACECRAFT:
                alpha = 0.95 if sc.key == self.target else 0.6
                p.setUniformValue("u_color", QVector4D(*sc.color, alpha))
                self.m_craft[sc.key].draw(f)
            p.release()

        # ---- 太陽の光芒
        clip = viewproj @ np.append(sun_rel, 1.0)
        if clip[3] > 0:
            ndc = clip[:2] / clip[3]
            pix_per_ndc = h / 2
            core_px = self.display_radius("sun") / clip[3] * (1 / math.tan(math.radians(self._fov) / 2)) * pix_per_ndc
            # 太陽の明るさ（離れると暗い星になる）: 絶対等級 4.83
            m_sun = 4.83 + 5 * math.log10(max(clip[3], 1e-9) / 206264.806 / 10.0)
            li = -0.4 * (m_sun - self.limit_mag)
            glow_px = max(core_px * 3.0, min(28.0, 2.5 + 2.2 * li))
            glow_k = min(1.0, 0.3 + 0.35 * li)
        if clip[3] > 0 and glow_px > 1.5:
            f.glBlendFunc(GL_ONE, GL_ONE)
            p = self.p_glow
            p.bind()
            p.setUniformValue("u_center", QVector2D(*ndc))
            p.setUniformValue("u_size", QVector2D(glow_px / (w / 2), glow_px / (h / 2)))
            p.setUniformValue("u_color", QVector3D(1.0 * glow_k, 0.78 * glow_k, 0.45 * glow_k))
            p.setUniformValue1f("u_core", float(min(core_px / glow_px, 0.9)))
            depth = math.log2(1.0 + LOGC * clip[3]) / math.log2(FAR_AU * LOGC + 1.0)
            p.setUniformValue1f("u_depth", float(depth))
            self.m_glow.draw(f)
            p.release()

        f.glDepthMask(True)
        f.glDisable(GL_BLEND)
        f.glDisable(GL_DEPTH_TEST)

        if self.ground:
            self._draw_sky(f, 1, w, h)
        self._draw_overlay(rel, viewproj, w, h)

    # ---------------------------------------------------------- ラベル・点

    def _project(self, v, viewproj, w, h):
        c = viewproj @ np.append(v, 1.0)
        if c[3] <= 0:
            return None
        x = (c[0] / c[3] * 0.5 + 0.5) * w
        y = (1 - (c[1] / c[3] * 0.5 + 0.5)) * h
        return x, y, c[3]

    def _draw_overlay(self, rel, viewproj, w, h):
        painter = QPainter(self)
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
        for b in order:
            if far and b.key != "sun":
                continue          # 太陽系から遠く離れると惑星は太陽に重なるので出さない
            if self.ground and (b.key == "earth" or not self._above(rel[b.key], margin=0.01)):
                continue          # 地平線の下の天体は見えない
            if self._is_small(b.key) and (self.ground or not self.show_small):
                continue          # 小天体は暗いので、地上からは出さない
            pr = self._project(rel[b.key], viewproj, w, h)
            if pr is None:
                continue
            x, y, depth = pr
            rad_px = self.display_radius(b.key) / depth * focal
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
            painter.drawText(QPointF(x + off, y - off * 0.3), b.name if not far else "太陽（太陽系）")

        if self.ground:
            self._draw_compass(painter, viewproj, w, h, placed, fm)
        else:
            self._draw_galaxy_labels(painter, viewproj, w, h, placed, fm, focal)
        if self.show_cmb and getattr(self, "_sun_far", 0) > cosmos.CMB_AU * 1.05:
            top = rel["sun"] + self._basis[1] * cosmos.CMB_AU
            pr = self._project(top, viewproj, w, h)
            if pr:
                painter.setPen(QPen(QColor(255, 200, 150)))
                rect = fm.boundingRect("宇宙マイクロ波背景放射（観測できる宇宙の果て・模式図）")
                rect.moveCenter(QPointF(pr[0], pr[1] - 14).toPoint())
                painter.drawText(rect, Qt.AlignCenter, "宇宙マイクロ波背景放射（観測できる宇宙の果て・模式図）")
                placed.append(rect)
        if self.show_small and not self.ground and not far:
            self._draw_comet_tails(painter, rel, viewproj, w, h)
        if self.show_craft and not self.ground and getattr(self, "_sun_far", 0) < 2e5:
            self._draw_craft(painter, viewproj, w, h, placed, fm)
        self._draw_sky_labels(painter, viewproj, w, h, placed, fm)
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
        """地上モードで、その方向が地平線より上か。"""
        if not self.ground:
            return True
        d = np.asarray(direction, dtype=np.float64)
        return float(np.dot(d, self._gframe[0])) / max(float(np.linalg.norm(d)), 1e-30) > -margin

    def _draw_compass(self, painter, viewproj, w, h, placed, fm):
        """地平線上の方角（北・東・南・西など）。"""
        zen, north, east = self._gframe
        font = painter.font()
        big = QFont(font)
        big.setPointSizeF(font.pointSizeF() * 1.4)
        big.setBold(True)
        names = [("北", 0), ("北東", 45), ("東", 90), ("南東", 135), ("南", 180), ("南西", 225),
                 ("西", 270), ("北西", 315)]
        for name, az in names:
            a = math.radians(az)
            d = math.cos(a) * north + math.sin(a) * east
            pr = self._sky_xy(d, viewproj, w, h)
            if not pr or not (0 < pr[0] < w and 0 < pr[1] < h + 40):
                continue
            main = len(name) == 1
            painter.setFont(big if main else font)
            painter.setPen(QPen(QColor(255, 120, 90) if name == "北" else QColor(230, 200, 140)))
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
        if self.ground:
            alt = math.degrees(self.g_alt)
            az = math.degrees(self.g_az) % 360
            dirs = ["北", "北北東", "北東", "東北東", "東", "東南東", "南東", "南南東",
                    "南", "南南西", "南西", "西南西", "西", "西北西", "北西", "北北西"]
            txt = (f"{self.place}　見ている方向: {dirs[int((az + 11.25) // 22.5) % 16]}"
                   f"（方位 {az:.0f}°・高度 {alt:.0f}°）　視野 {self.g_fov:.2g}°")
            painter.setPen(QPen(QColor(200, 205, 215)))
            painter.drawText(QPointF(12, h - 12), txt)
            return
        width_au = 2 * self.dist * math.tan(math.radians(self._fov) / 2) * w / h
        painter.setPen(QPen(QColor(170, 180, 200)))
        painter.drawText(QPointF(12, h - 12), "画面の横幅 約 " + format_length(width_au))

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
        if self.show_con_names and con_k > 0.05:
            font = painter.font()
            painter.setPen(QPen(QColor(80, 115, 180, int(190 * con_k))))
            for c in cat.constellations:
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
        star = self.pick_star(x, y)
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
