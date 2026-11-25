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
FAR_AU = 1e16
LOGC = astro.AU_KM            # 対数デプスは km 単位で計算する
MAX_DIST_AU = 1.5e14         # 約24億光年
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
        self.gcat = GalaxyCatalog()

        # カメラ（注視点のまわりを回る）
        self.target = "sun"
        self.yaw = math.radians(-60.0)
        self.pitch = math.radians(28.0)
        self.dist = 4.0
        self._fly = None          # 移動中の情報
        self._drag = None

        self.positions = astro.all_positions(self.jd)
        self._orbit_jd = None
        self._screen = {}         # 天体の画面上の位置（ラベル・選択用）

        from PySide6.QtWidgets import QApplication
        QApplication.instance().aboutToQuit.connect(self._cleanup_gl)

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
        return key in gx.BY_KEY or key.startswith("c:")

    def set_target(self, key: str, fly: bool = True):
        if key not in BY_KEY and not self.is_galaxy(key):
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
              "from_dist": d0, "to_dist": d1, "arc": arc, "t0": time.monotonic(),
              "dur": min(4.5, 1.6 + 0.35 * max(0.0, math.log10(max(sep / max(min(d0, d1), 1e-12), 1.0))))}
        if view_dir is not None:
            yaw1 = math.atan2(view_dir[1], view_dir[0])
            dy = (yaw1 - self.yaw + math.pi) % (2 * math.pi) - math.pi
            fl.update(yaw0=self.yaw, dyaw=dy, pitch0=self.pitch,
                      pitch1=math.asin(max(-0.99, min(0.99, view_dir[2]))))
        self._fly = fl

    def _galaxy_view_dir(self, key):
        """銀河へ行くときの見下ろす向き（カメラが注視点のどちら側にいるか）。"""
        if not self.is_galaxy(key):
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
        if key.startswith("c:"):
            return float(self.gcat.radius[int(key[2:])])
        if key in gx.BY_KEY:
            return gx.BY_KEY[key].radius_kpc * gx.KPC_AU
        b = BY_KEY[key]
        m = min(self.magnify, 10.0) if key == "sun" else self.magnify
        return b.radius_km * KM * m

    def moon_scale(self) -> float:
        """拡大表示のとき、月が地球に埋もれないように月の軌道も広げる。"""
        return max(1.0, self.magnify / 30.0)

    def display_pos(self, key: str) -> np.ndarray:
        if key.startswith("c:"):
            return self.gcat.center[int(key[2:])]
        if key in gx.BY_KEY:
            return gx.BY_KEY[key].center
        if key == "moon":
            e = self.positions["earth"]
            return e + (self.positions["moon"] - e) * self.moon_scale()
        return self.positions[key]

    def _min_dist(self, key):
        if self.is_galaxy(key):
            return self.display_radius(key) * 0.05
        return self.display_radius(key) * 1.15

    def _default_dist(self, key):
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
            s = min(1.0, (time.monotonic() - fl["t0"]) / fl["dur"])
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

    def _tick(self):
        now = time.monotonic()
        dt = now - self._last_tick
        self._last_tick = now
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
        self.update()

    def _refresh_positions(self):
        self.positions = astro.all_positions(self.jd)
        if self._orbit_jd is None or abs(self.jd - self._orbit_jd) > 3650:
            self._orbit_dirty = True

    # ---------------------------------------------------------- OpenGL

    def initializeGL(self):
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
        self.m_stars = _Mesh(self.stars.vertex_data(), [(0, 3), (1, 1), (2, 1), (3, 3)], GL_POINTS)
        self.m_conlines = _Mesh(self.stars.line_vertices(), [(0, 3)], GL_LINES)
        self.p_galaxy = prog(shaders.GALAXY_VS, shaders.GALAXY_FS)
        self.m_galaxies = _Mesh(gx.build(), [(0, 3), (1, 1), (2, 1), (3, 3)], GL_POINTS)
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
        if not getattr(self, "tex", None) or self.context() is None:
            return
        self.makeCurrent()
        for t in self.tex.values():
            t.destroy()
        self.tex = {}
        self.doneCurrent()

    def reload_textures(self):
        """画像を読み込み直す（ダウンロード後に呼ぶ）。"""
        if self.context() is None:
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

    def _rebuild_orbits(self):
        for key in ("mercury", "venus", "earth", "mars", "jupiter", "saturn", "uranus", "neptune"):
            b = BY_KEY[key]
            pts = astro.orbit_path(b.orbit, self.jd, 2048)
            if key in self.m_orbits:
                self.m_orbits[key].update(pts)
            else:
                self.m_orbits[key] = _Mesh(pts, [(0, 3)], GL_LINE_STRIP)
        self._rebuild_moon_orbit()
        self._orbit_jd = self.jd
        self._orbit_dirty = False

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

    def _common(self, p, viewproj):
        p.setUniformValue("u_viewproj", _qmat(viewproj))
        p.setUniformValue1f("u_logc", float(LOGC))
        p.setUniformValue1f("u_fcoef", float(1.0 / math.log2(FAR_AU * LOGC + 1.0)))

    def paintGL(self):
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
        proj = _perspective(FOV_DEG, w / h, NEAR_AU, FAR_AU)
        viewproj = proj @ view
        self._viewproj = viewproj
        self._eye = eye

        rel = {b.key: self.display_pos(b.key) - eye for b in BODIES}
        sun_rel = rel["sun"]
        sun_far = float(np.linalg.norm(sun_rel))       # 太陽からカメラまで [AU]
        self._sun_far = sun_far
        focal = h / (2 * math.tan(math.radians(FOV_DEG) / 2))
        # 星座は太陽の近くから見たときだけ意味があるので、離れるほど薄くする
        self._con_fade = 1.0 - _smooth(2000.0, 0.8 * LY_AU, sun_far)

        # ---- 星空（いちばん奥なので最初に、奥行きなしで描く）
        f.glDisable(GL_DEPTH_TEST)
        f.glEnable(GL_BLEND)
        f.glBlendFunc(GL_ONE, GL_ONE)
        f.glEnable(GL_PROGRAM_POINT_SIZE)
        if self.show_galaxies:
            self._draw_galaxies(f, viewproj, eye, focal, h)
            p = self.p_gcat
            p.bind()
            p.setUniformValue("u_viewproj", _qmat(viewproj))
            p.setUniformValue("u_eye", QVector3D(*eye))
            p.setUniformValue("u_right", QVector3D(*right))
            p.setUniformValue("u_up", QVector3D(*up))
            p.setUniformValue1f("u_focal", float(focal))
            p.setUniformValue1f("u_gain", 0.7)
            self.m_gcat.draw(f)
            p.release()
        if self.show_con_lines and self._con_fade > 0.01:
            p = self.p_line
            p.bind()
            self._common(p, viewproj)
            p.setUniformValue("u_offset", QVector3D(0, 0, 0))
            p.setUniformValue1f("u_scale", 1000.0)
            k = self._con_fade
            p.setUniformValue("u_color", QVector4D(0.10 * k, 0.18 * k, 0.34 * k, 1.0))
            self.m_conlines.draw(f)
            p.release()
        if self.show_stars:
            f.glEnable(GL_PROGRAM_POINT_SIZE)
            p = self.p_star
            p.bind()
            p.setUniformValue("u_viewproj", _qmat(viewproj))
            p.setUniformValue("u_eye", QVector3D(*eye))
            p.setUniformValue1f("u_limit", float(self.limit_mag))
            p.setUniformValue1f("u_px", float(self.devicePixelRatioF()))
            p.setUniformValue1f("u_gain", 1.0)
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
            r = self.display_radius(b.key)
            pos = rel[b.key]
            d = np.linalg.norm(pos)
            # 画面上で 1 ピクセルより小さいものは球を描かない（点とラベルで表す）
            if r / d * h / (2 * math.tan(math.radians(FOV_DEG) / 2)) < 0.5:
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
        if self.show_orbits and sun_far < 2e5:
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
                else:
                    offset, scale = sun_rel, 1.0
                alpha = 0.8 if key == self.target else 0.5
                # 天体のすぐ近くでは、その天体の軌道線が手前を横切って邪魔なので薄くする
                for k2 in ((key,) if key != "earth" else ("earth", "moon")):
                    near = np.linalg.norm(rel[k2]) / (self.display_radius(k2) * 60.0)
                    alpha *= min(1.0, near * near)
                if alpha < 0.01:
                    continue
                p.setUniformValue("u_offset", QVector3D(*offset))
                p.setUniformValue1f("u_scale", float(scale))
                p.setUniformValue("u_color", QVector4D(*b.color, alpha))
                mesh.draw(f)
            p.release()

        # ---- 太陽の光芒
        clip = viewproj @ np.append(sun_rel, 1.0)
        if clip[3] > 0:
            ndc = clip[:2] / clip[3]
            pix_per_ndc = h / 2
            core_px = self.display_radius("sun") / clip[3] * (1 / math.tan(math.radians(FOV_DEG) / 2)) * pix_per_ndc
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
        focal = h / (2 * math.tan(math.radians(FOV_DEG) / 2))

        self._screen = {}
        # 優先順：注目している天体 → 太陽 → 大きい順
        order = sorted(BODIES, key=lambda b: (b.key != self.target, b.key != "sun", -b.radius_km))
        placed = []
        fm = painter.fontMetrics()
        far = getattr(self, "_sun_far", 0.0) > 3000.0
        for b in order:
            if far and b.key != "sun":
                continue          # 太陽系から遠く離れると惑星は太陽に重なるので出さない
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
                # 小さすぎて見えない天体は点で示す。月は地球に重なるときは省く
                if b.key == "moon" and "earth" in self._screen:
                    ex, ey, _ = self._screen["earth"]
                    if math.hypot(ex - x, ey - y) < 4:
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

        self._draw_galaxy_labels(painter, viewproj, w, h, placed, fm, focal)
        self._draw_sky_labels(painter, viewproj, w, h, placed, fm)
        self._draw_scale(painter, w, h)
        painter.end()

    def _draw_galaxy_labels(self, painter, viewproj, w, h, placed, fm, focal):
        if not self.show_galaxies:
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
        focal = h / (2 * math.tan(math.radians(FOV_DEG) / 2))
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
        width_au = 2 * self.dist * math.tan(math.radians(FOV_DEG) / 2) * w / h
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
        if self.selected_star >= 0 and self.show_stars:
            pr = self._sky_xy(star_dir(self.selected_star), viewproj, w, h)
            if pr:
                painter.setPen(QPen(QColor(120, 220, 255), 1.4))
                painter.setBrush(Qt.NoBrush)
                painter.drawEllipse(QPointF(pr[0], pr[1]), 9, 9)
        # 星座名
        if self.show_con_names and self._con_fade > 0.05:
            font = painter.font()
            painter.setPen(QPen(QColor(80, 115, 180, int(190 * self._con_fade))))
            for c in cat.constellations:
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
                pr = self._sky_xy(star_dir(i), viewproj, w, h)
                if not pr or not (0 < pr[0] < w and 0 < pr[1] < h):
                    continue
                name = cat.short_name(i)
                rect = fm.boundingRect(name).translated(int(pr[0] + 6), int(pr[1] - 4))
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
        self._drag = (e.position(), e.button(), self.yaw, self.pitch, self.dist)

    def mouseMoveEvent(self, e):
        if not self._drag:
            return
        p0, button, yaw0, pitch0, dist0 = self._drag
        d = e.position() - p0
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
        elif k in (Qt.Key_Plus, Qt.Key_Equal):
            self.dist = max(self._min_dist(self.target), self.dist * 0.8)
        elif k == Qt.Key_Minus:
            self.dist = min(MAX_DIST_AU, self.dist * 1.25)
        else:
            super().keyPressEvent(e)
        self.update()
