"""メインウィンドウ。"""

from __future__ import annotations

import math
from datetime import timezone
from pathlib import Path

import numpy as np
from PySide6.QtCore import QDateTime, QSettings, Qt, QTimer
from PySide6.QtGui import QAction, QIcon, QKeySequence
from PySide6.QtWidgets import (QCheckBox, QComboBox, QDateTimeEdit, QLabel, QMainWindow,
                               QMessageBox, QProgressDialog, QPushButton, QSlider, QToolBar,
                               QWidget, QHBoxLayout, QSizePolicy)

from . import __version__, astro, textures
from .bodies import BODIES, BY_KEY
from .view import SpaceView, format_length
from . import galaxies as gx

SPEEDS = [
    ("実時間", 1.0),
    ("1分/秒", 60.0),
    ("10分/秒", 600.0),
    ("1時間/秒", 3600.0),
    ("6時間/秒", 21600.0),
    ("1日/秒", 86400.0),
    ("1週間/秒", 604800.0),
    ("1か月/秒", 2629800.0),
    ("1年/秒", 31557600.0),
]
DEFAULT_SPEED = 5   # 1日/秒

TARGET_ORDER = ["sun", "mercury", "venus", "earth", "moon", "mars",
                "jupiter", "saturn", "uranus", "neptune"]

HELP_TEXT = """<h3>操作方法</h3>
<table cellpadding="3">
<tr><td><b>左ドラッグ</b></td><td>視点を回す</td></tr>
<tr><td><b>ホイール</b> / <b>右ドラッグ</b></td><td>近づく・離れる</td></tr>
<tr><td><b>ダブルクリック</b></td><td>惑星・銀河へ移動する／恒星の情報を見る</td></tr>
<tr><td><b>スペース</b></td><td>時間を止める・動かす</td></tr>
<tr><td><b>+ / −</b></td><td>近づく・離れる</td></tr>
<tr><td><b>F11</b></td><td>全画面表示</td></tr>
</table>
<p>「惑星の大きさ」を上げると、惑星を実際より大きく描きます（太陽は最大10倍）。
実寸（×1）では、遠くから見ると惑星は点と名前だけになります。</p>
<p>「星の数」で、何等星まで表示するかを変えられます。肉眼で見えるのは 6.5 等くらいまでです。</p>
<p>ホイールでどこまでも引いていくと、近くの恒星 → 天の川銀河 → 近くの銀河 と、宇宙の大きさを旅できます。
「見る天体」から銀河を選ぶと、その銀河まで飛んでいきます。銀河の形は模式図です。</p>"""


def _fmt_dist(au: float) -> str:
    if 0.1 <= au < 1000:
        return f"{au:,.3f} AU"
    return format_length(au)


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("そらみ窓")
        self.resize(1280, 800)
        self.settings = QSettings("Soramado", "Soramado")

        self.view = SpaceView(self)
        self.setCentralWidget(self.view)
        self.view.speed = SPEEDS[DEFAULT_SPEED][1]
        self.view.targetChanged.connect(self._on_target_changed)

        self._build_toolbar()
        self._build_menu()

        self.status_info = QLabel()
        self.status_warn = QLabel()
        self.status_warn.setStyleSheet("color: #e0a040;")
        self.statusBar().addWidget(self.status_info, 1)
        self.statusBar().addPermanentWidget(self.status_warn)

        self._ui_timer = QTimer(self)
        self._ui_timer.timeout.connect(self._refresh_ui)
        self._ui_timer.start(100)
        self._download = None

        QTimer.singleShot(600, self._maybe_offer_download)

    # ---------------------------------------------------------- 画面の部品

    def _build_toolbar(self):
        tb = QToolBar("操作")
        tb.setMovable(False)
        self.addToolBar(tb)

        tb.addWidget(QLabel(" 見る天体 "))
        self.cb_target = QComboBox()
        for key in TARGET_ORDER:
            self.cb_target.addItem(BY_KEY[key].name, key)
        self.cb_target.insertSeparator(self.cb_target.count())
        for g in gx.GALAXIES:
            if g.in_menu:
                self.cb_target.addItem(g.name, g.key)
        self.cb_target.setMaxVisibleItems(30)
        self.cb_target.activated.connect(lambda i: self.view.set_target(self.cb_target.itemData(i)))
        tb.addWidget(self.cb_target)

        btn_all = QPushButton("全体を見る")
        btn_all.clicked.connect(self.view.overview)
        tb.addWidget(btn_all)
        tb.addSeparator()

        self.btn_play = QPushButton("⏸ 停止")
        self.btn_play.setMinimumWidth(80)
        self.btn_play.clicked.connect(self._toggle_pause)
        tb.addWidget(self.btn_play)

        self.chk_reverse = QCheckBox("逆再生")
        self.chk_reverse.toggled.connect(self._apply_speed)
        tb.addWidget(self.chk_reverse)

        self.cb_speed = QComboBox()
        for label, _ in SPEEDS:
            self.cb_speed.addItem(label)
        self.cb_speed.setCurrentIndex(DEFAULT_SPEED)
        self.cb_speed.currentIndexChanged.connect(self._apply_speed)
        tb.addWidget(self.cb_speed)

        btn_now = QPushButton("現在時刻")
        btn_now.clicked.connect(lambda: self.view.set_jd(astro.jd_now()))
        tb.addWidget(btn_now)

        self.dt_edit = QDateTimeEdit()
        self.dt_edit.setDisplayFormat("yyyy/MM/dd HH:mm")
        self.dt_edit.setTimeSpec(Qt.LocalTime)
        self.dt_edit.setMinimumDateTime(QDateTime.fromString("1700-01-02T00:00:00", Qt.ISODate))
        self.dt_edit.setMaximumDateTime(QDateTime.fromString("2289-12-30T00:00:00", Qt.ISODate))
        self.dt_edit.setCalendarPopup(True)
        self.dt_edit.editingFinished.connect(self._on_date_edited)
        tb.addWidget(self.dt_edit)
        tb.addSeparator()

        box = QWidget()
        lay = QHBoxLayout(box)
        lay.setContentsMargins(6, 0, 6, 0)
        lay.addWidget(QLabel("惑星の大きさ"))
        self.sl_mag = QSlider(Qt.Horizontal)
        self.sl_mag.setRange(0, 300)          # 10^(値/100) 倍
        self.sl_mag.setFixedWidth(140)
        self.sl_mag.valueChanged.connect(self._on_magnify)
        lay.addWidget(self.sl_mag)
        self.lb_mag = QLabel("×1（実寸）")
        self.lb_mag.setMinimumWidth(80)
        lay.addWidget(self.lb_mag)
        tb.addWidget(box)

        box2 = QWidget()
        lay2 = QHBoxLayout(box2)
        lay2.setContentsMargins(6, 0, 6, 0)
        lay2.addWidget(QLabel("星の数"))
        self.sl_stars = QSlider(Qt.Horizontal)
        self.sl_stars.setRange(20, 100)        # 限界等級 ×10（2.0〜10.0等）
        self.sl_stars.setValue(65)
        self.sl_stars.setFixedWidth(120)
        self.sl_stars.valueChanged.connect(self._on_limit)
        lay2.addWidget(self.sl_stars)
        self.lb_stars = QLabel()
        self.lb_stars.setMinimumWidth(130)
        lay2.addWidget(self.lb_stars)
        tb.addWidget(box2)
        self._on_limit(self.sl_stars.value())

        spacer = QWidget()
        spacer.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Preferred)
        tb.addWidget(spacer)

    def _build_menu(self):
        mb = self.menuBar()
        m_file = mb.addMenu("ファイル(&F)")
        act_dl = QAction("惑星の画像をダウンロード…", self)
        act_dl.triggered.connect(lambda: self._start_download(force=True))
        m_file.addAction(act_dl)
        m_file.addSeparator()
        act_quit = QAction("終了", self)
        act_quit.setShortcut(QKeySequence.Quit)
        act_quit.triggered.connect(self.close)
        m_file.addAction(act_quit)

        m_view = mb.addMenu("表示(&V)")
        self.act_orbits = QAction("軌道", self, checkable=True, checked=True)
        self.act_orbits.toggled.connect(self._on_toggle_orbits)
        m_view.addAction(self.act_orbits)
        self.act_labels = QAction("名前", self, checkable=True, checked=True)
        self.act_labels.toggled.connect(self._on_toggle_labels)
        m_view.addAction(self.act_labels)
        m_view.addSeparator()
        self.act_stars = self._toggle(m_view, "恒星", "show_stars")
        self.act_conl = self._toggle(m_view, "星座線", "show_con_lines")
        self.act_conn = self._toggle(m_view, "星座名", "show_con_names")
        self.act_starn = self._toggle(m_view, "星の名前", "show_star_names")
        self.act_gal = self._toggle(m_view, "銀河", "show_galaxies")
        m_view.addSeparator()
        act_full = QAction("全画面表示", self, checkable=True)
        act_full.setShortcut(QKeySequence("F11"))
        act_full.toggled.connect(lambda on: self.showFullScreen() if on else self.showNormal())
        m_view.addAction(act_full)

        m_help = mb.addMenu("ヘルプ(&H)")
        act_howto = QAction("操作方法", self)
        act_howto.triggered.connect(lambda: QMessageBox.information(self, "操作方法", HELP_TEXT))
        m_help.addAction(act_howto)
        act_about = QAction("そらみ窓について", self)
        act_about.triggered.connect(self._about)
        m_help.addAction(act_about)

    # ---------------------------------------------------------- 動作

    def _toggle(self, menu, label, attr):
        act = QAction(label, self, checkable=True, checked=getattr(self.view, attr))

        def on(v):
            setattr(self.view, attr, v)
            self.view.update()
        act.toggled.connect(on)
        menu.addAction(act)
        return act

    def _on_limit(self, v):
        lim = v / 10.0
        self.view.limit_mag = lim
        n = int(np.searchsorted(self.view.stars.mag, lim, side="right"))
        self.lb_stars.setText(f"{lim:.1f}等まで（{n:,}個）")
        self.view.update()

    def _on_toggle_orbits(self, on):
        self.view.show_orbits = on
        self.view.update()

    def _on_toggle_labels(self, on):
        self.view.show_labels = on
        self.view.update()

    def _toggle_pause(self):
        self.view.paused = not self.view.paused

    def _apply_speed(self, *_):
        s = SPEEDS[self.cb_speed.currentIndex()][1]
        self.view.speed = -s if self.chk_reverse.isChecked() else s

    def _on_magnify(self, v):
        m = 10 ** (v / 100.0)
        if m < 1.05:
            m = 1.0
        self.view.set_magnify(m)
        self.lb_mag.setText("×1（実寸）" if m == 1.0 else f"×{m:,.0f}")

    def _on_target_changed(self, key):
        i = self.cb_target.findData(key)
        if i >= 0:
            self.cb_target.setCurrentIndex(i)
        else:
            self.cb_target.setCurrentIndex(-1)

    def _on_date_edited(self):
        dt = self.dt_edit.dateTime().toUTC()
        unix = dt.toSecsSinceEpoch()
        self.view.set_jd(unix / 86400.0 + 2440587.5)

    def _refresh_ui(self):
        v = self.view
        self.btn_play.setText("▶ 再生" if v.paused else "⏸ 停止")
        if not self.dt_edit.hasFocus():
            unix = (v.jd - 2440587.5) * 86400.0
            self.dt_edit.blockSignals(True)
            self.dt_edit.setDateTime(QDateTime.fromSecsSinceEpoch(int(round(unix)), Qt.LocalTime))
            self.dt_edit.blockSignals(False)

        if v.selected_star >= 0:
            self.status_info.setText("★ " + v.stars.describe(v.selected_star))
            self._refresh_warn(v)
            return
        key = v.target
        if key.startswith("c:"):
            self.status_info.setText(v.gcat.describe(int(key[2:])) + "　｜　視点の距離 "
                                     + format_length(v.dist))
            self._refresh_warn(v)
            return
        if key in gx.BY_KEY:
            self.status_info.setText(gx.describe(gx.BY_KEY[key]) + "　｜　視点の距離 "
                                     + format_length(v.dist))
            self._refresh_warn(v)
            return
        b = BY_KEY[key]
        parts = [f"<b>{b.name}</b>", f"半径 {b.radius_km:,.0f} km"]
        if key != "sun":
            parts.append(f"太陽から {_fmt_dist(np.linalg.norm(v.positions[key])):s}")
        if key not in ("earth", "sun"):
            parts.append(f"地球から {_fmt_dist(np.linalg.norm(v.positions[key] - v.positions['earth']))}")
        if key == "sun":
            parts.append(f"地球から {_fmt_dist(np.linalg.norm(v.positions['earth']))}")
        surface = v.dist - v.display_radius(key)
        parts.append(f"視点の距離 {_fmt_dist(max(surface, 0.0))}（表面から）")
        self.status_info.setText("　｜　".join(parts))
        self._refresh_warn(v)

    def _refresh_warn(self, v):
        if not astro.elements_valid(v.jd):
            self.status_warn.setText(f"※ {astro.VALID_FROM_YEAR}〜{astro.VALID_TO_YEAR}年の範囲外のため、惑星の位置は概算です")
        else:
            self.status_warn.setText("")

    # ---------------------------------------------------------- 画像のダウンロード

    def _maybe_offer_download(self):
        if not textures.missing_textures() or self.settings.value("asked_textures", False, type=bool):
            return
        self.settings.setValue("asked_textures", True)
        ans = QMessageBox.question(
            self, "惑星の画像",
            "惑星の表面の画像（Solar System Scope 提供、約10MB）をダウンロードしますか？\n\n"
            "ダウンロードしない場合は、簡易的な模様で表示します。\n"
            "あとからでも「ファイル」メニューからダウンロードできます。")
        if ans == QMessageBox.Yes:
            self._start_download()

    def _start_download(self, force=False):
        files = textures.missing_textures()
        if not files and force:
            ans = QMessageBox.question(self, "惑星の画像",
                                       "画像はすべてダウンロード済みです。もう一度ダウンロードしますか？")
            if ans != QMessageBox.Yes:
                return
            from .bodies import all_texture_files
            files = all_texture_files()
        if not files or self._download:
            return
        dlg = QProgressDialog("画像をダウンロードしています…", "キャンセル", 0, len(files), self)
        dlg.setWindowTitle("惑星の画像")
        dlg.setWindowModality(Qt.WindowModal)
        dlg.setMinimumDuration(0)
        dlg.setAutoClose(False)
        dlg.setAutoReset(False)
        worker = textures.TextureDownloader(files)
        dlg.canceled.connect(worker.cancel)

        # 進み具合はタイマーで見に行く（別スレッドから画面にさわらないため）
        timer = QTimer(self)

        def poll():
            if worker.current:
                dlg.setLabelText(f"画像をダウンロードしています…\n"
                                 f"{worker.current}（{worker.index + 1}/{worker.total}）")
            dlg.setValue(worker.index)
            if not worker.done:
                return
            timer.stop()
            dlg.close()
            self._download = None
            self.view.reload_textures()
            if worker.failed:
                QMessageBox.warning(self, "惑星の画像",
                                    f"{worker.ok} 個の画像をダウンロードしました。\n"
                                    f"次の {len(worker.failed)} 個はダウンロードできませんでした"
                                    "（インターネット接続を確認してください）:\n"
                                    + "\n".join(worker.failed))
            elif worker.ok:
                self.statusBar().showMessage(f"{worker.ok} 個の画像をダウンロードしました", 5000)

        timer.timeout.connect(poll)
        self._download = (worker, timer, dlg)
        worker.start()
        timer.start(100)

    def _about(self):
        QMessageBox.about(
            self, "そらみ窓について",
            f"<h3>そらみ窓（Soramado） v{__version__}</h3>"
            "<p>太陽系から宇宙の果てまでを旅する、Ubuntu 用の宇宙シミュレーター。</p>"
            "<p>作者: 飯田顕治 ／ ライセンス: MIT</p>"
            "<p><b>使用しているデータ</b><br>"
            "・惑星の軌道: NASA JPL「Approximate Positions of the Planets」<br>"
            "・月の位置: Paul Schlyter「How to compute planetary positions」<br>"
            "・天体の大きさ・自転軸: IAU WGCCRE 報告（2015年）<br>"
            "・恒星: HYG データベース v4.1（CC BY-SA 4.0）<br>"
            "・星座線・星座名: d3-celestial（© Olaf Frohn, BSD 3-Clause）<br>"
            "・銀河: 位置・距離・大きさは文献のおおよその値。形は粒子で作った模式図<br>"
            "・銀河カタログ（約1万個）: OpenNGC（CC BY-SA 4.0）。距離は後退速度から推定<br>"
            "・惑星の画像（ダウンロードした場合）: "
            "<a href='https://www.solarsystemscope.com/textures/'>Solar System Scope</a>"
            "（CC BY 4.0）</p>"
            "<p>このソフトは国立天文台の Mitaka とは関係のない独自のソフトです。</p>")

    def closeEvent(self, e):
        if self._download:
            worker, timer, _ = self._download
            timer.stop()
            worker.cancel()
            worker.wait(2)
        super().closeEvent(e)


def icon_path() -> Path | None:
    for p in (Path(__file__).parent / "soramado.svg",
              Path("/usr/share/icons/hicolor/scalable/apps/soramado.svg")):
        if p.is_file():
            return p
    return None


def make_window() -> MainWindow:
    w = MainWindow()
    ip = icon_path()
    if ip:
        w.setWindowIcon(QIcon(str(ip)))
    return w
