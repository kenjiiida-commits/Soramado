"""メインウィンドウ。"""

from __future__ import annotations

import math
from datetime import timezone
from pathlib import Path

import numpy as np
from PySide6.QtCore import QDateTime, QSettings, Qt, QTimer
from PySide6.QtGui import QAction, QIcon, QKeySequence
from PySide6.QtWidgets import (QCheckBox, QComboBox, QDateTimeEdit, QDialog, QDialogButtonBox, QDockWidget,
                               QFrame, QTextBrowser, QVBoxLayout,
                               QDoubleSpinBox, QFormLayout, QLabel, QLineEdit, QMainWindow,
                               QMessageBox, QProgressDialog, QPushButton, QSlider, QToolBar,
                               QWidget, QHBoxLayout, QSizePolicy)

from . import __version__, astro, textures
from .bodies import BODIES, BY_KEY
from .view import SpaceView, format_length
from . import galaxies as gx
from . import smallbodies as sbs
from . import tours
from . import cosmos
from .descriptions import KIND_DESCRIPTIONS, STAR_TEXT, text_for

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

PLACES = [
    ("札幌", 43.06, 141.35), ("仙台", 38.27, 140.87), ("東京", 35.68, 139.77),
    ("三鷹（国立天文台）", 35.67, 139.54), ("名古屋", 35.18, 136.91), ("大阪", 34.69, 135.50),
    ("広島", 34.39, 132.46), ("福岡", 33.59, 130.40), ("那覇", 26.21, 127.68),
]

TARGET_ORDER = ["sun", "mercury", "venus", "earth", "moon",
                "mars", "phobos", "deimos",
                "jupiter", "io", "europa", "ganymede", "callisto",
                "saturn", "mimas", "enceladus", "tethys", "dione", "rhea", "titan", "iapetus",
                "uranus", "miranda", "ariel", "umbriel", "titania", "oberon",
                "neptune", "triton"]
SMALL_ORDER = ["pluto", "eris", "makemake", "haumea", "ceres", "pallas", "vesta",
               "itokawa", "ryugu", "bennu", "halley", "encke", "67p"]

HELP_TEXT = """<h3>操作方法</h3>
<table cellpadding="3">
<tr><td><b>左ドラッグ</b></td><td>視点を回す</td></tr>
<tr><td><b>ホイール</b> / <b>右ドラッグ</b></td><td>近づく・離れる</td></tr>
<tr><td><b>ダブルクリック</b></td><td>惑星・銀河へ移動する／恒星の情報を見る</td></tr>
<tr><td><b>スペース</b></td><td>時間を止める・動かす</td></tr>
<tr><td><b>+ / −</b></td><td>近づく・離れる</td></tr>
<tr><td><b>F11</b></td><td>全画面表示</td></tr>
</table>
<p><b>地上から見る（プラネタリウム）</b></p>
<table cellpadding="3">
<tr><td><b>左ドラッグ</b></td><td>見る方向を変える</td></tr>
<tr><td><b>ホイール</b> / <b>右ドラッグ</b></td><td>視野を広く・狭く（望遠鏡のように拡大）</td></tr>
<tr><td><b>見る天体</b></td><td>その天体の方を向く</td></tr>
</table>
<p><b>ツアー</b>：「ツアー」メニューから選ぶと、字幕つきで自動的に宇宙を案内します。
「次 ▶」で先へ、Esc キーで終わります。</p>
<table>
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
        central = QWidget()
        lay = QVBoxLayout(central)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(0)
        lay.addWidget(self.view, 1)
        self._build_tour_bar()
        lay.addWidget(self.tour_bar)
        self.setCentralWidget(central)
        self.view.speed = SPEEDS[DEFAULT_SPEED][1]
        self.view.targetChanged.connect(self._on_target_changed)
        self.view.starSelected.connect(lambda _i: self._update_panel(force=True))

        self._build_toolbar()
        self._build_panel()
        self._build_menu()
        self._tour = None
        self._tour_timer = QTimer(self)
        self._tour_timer.setSingleShot(True)
        self._tour_timer.timeout.connect(lambda: self._tour_go(+1))

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
        self._restore_place()

    # ---------------------------------------------------------- 画面の部品

    def _build_toolbar(self):
        tb = QToolBar("操作")
        tb.setMovable(False)
        self.addToolBar(tb)

        tb.addWidget(QLabel(" 見る天体 "))
        self.cb_target = QComboBox()
        for key in TARGET_ORDER:
            par = BY_KEY[key].parent
            # 衛星は字下げして、どの惑星の衛星か分かるようにする
            self.cb_target.addItem(("　" + BY_KEY[key].name) if par not in ("sun", "") else BY_KEY[key].name, key)
        self.cb_target.insertSeparator(self.cb_target.count())
        for key in SMALL_ORDER:
            self.cb_target.addItem(BY_KEY[key].name, key)
        self.cb_target.insertSeparator(self.cb_target.count())
        for g in gx.GALAXIES:
            if g.in_menu:
                self.cb_target.addItem(g.name, g.key)
        self.cb_target.insertSeparator(self.cb_target.count())
        self.cb_target.addItem("観測できる宇宙の果て", "u:cmb")
        self.cb_target.setMaxVisibleItems(30)
        self.cb_target.activated.connect(lambda i: self.view.set_target(self.cb_target.itemData(i)))
        tb.addWidget(self.cb_target)

        self.btn_all = QPushButton("全体を見る")
        self.btn_all.clicked.connect(self.view.overview)
        tb.addWidget(self.btn_all)
        tb.addSeparator()

        self.btn_ground = QPushButton("🔭 地上から見る")
        self.btn_ground.setCheckable(True)
        self.btn_ground.toggled.connect(self._on_ground)
        tb.addWidget(self.btn_ground)
        self.cb_place = QComboBox()
        for name, lat, lon in PLACES:
            self.cb_place.addItem(name, (name, lat, lon))
        self.cb_place.addItem("緯度・経度を入力…", None)
        self.cb_place.activated.connect(self._on_place)
        tb.addWidget(self.cb_place)
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
        act_q = QAction("クエーサーのデータをダウンロード…", self)
        act_q.triggered.connect(self._download_quasars)
        m_file.addAction(act_q)
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
        self.act_small = self._toggle(m_view, "準惑星・小惑星・彗星", "show_small")
        self.act_qso = self._toggle(m_view, "クエーサー", "show_quasars")
        self.act_cmb = self._toggle(m_view, "宇宙マイクロ波背景放射", "show_cmb")
        m_view.addSeparator()
        act_full = QAction("全画面表示", self, checkable=True)
        act_full.setShortcut(QKeySequence("F11"))
        act_full.toggled.connect(lambda on: self.showFullScreen() if on else self.showNormal())
        m_view.addAction(act_full)

        m_view.addSeparator()
        m_view.addAction(self.panel.toggleViewAction())

        m_tour = mb.addMenu("ツアー(&T)")
        for tid, title, _fn in tours.TOURS:
            act = QAction(title, self)
            act.triggered.connect(lambda _=False, t=tid: self.start_tour(t))
            m_tour.addAction(act)
        m_tour.addSeparator()
        act_stop = QAction("ツアーを終わる", self)
        act_stop.setShortcut(QKeySequence("Esc"))
        act_stop.triggered.connect(self.stop_tour)
        m_tour.addAction(act_stop)

        m_help = mb.addMenu("ヘルプ(&H)")
        act_howto = QAction("操作方法", self)
        act_howto.triggered.connect(lambda: QMessageBox.information(self, "操作方法", HELP_TEXT))
        m_help.addAction(act_howto)
        act_about = QAction("そらみ窓について", self)
        act_about.triggered.connect(self._about)
        m_help.addAction(act_about)

    # ---------------------------------------------------------- 動作

    # ---------------------------------------------------------- クエーサーのダウンロード

    def _download_quasars(self):
        if getattr(self, "_qso_dl", None):
            return
        ans = QMessageBox.question(
            self, "クエーサーのデータ",
            "SDSS の第16次クエーサーカタログ（DR16Q、約75万個）を、天文データセンター VizieR から"
            "ダウンロードします（通信量 約20〜40MB、数分かかることがあります）。よろしいですか？")
        if ans != QMessageBox.Yes:
            return
        dl = cosmos.QuasarDownloader()
        dlg = QProgressDialog("クエーサーのデータをダウンロードしています…", "キャンセル", 0, 0, self)
        dlg.setWindowTitle("クエーサーのデータ")
        dlg.setWindowModality(Qt.WindowModal)
        dlg.setMinimumDuration(0)
        dlg.canceled.connect(dl.cancel)
        timer = QTimer(self)

        def poll():
            dlg.setLabelText(f"クエーサーのデータをダウンロードしています…\n{dl.bytes / 1e6:,.1f} MB")
            if not dl.done:
                return
            timer.stop()
            dlg.close()
            self._qso_dl = None
            if dl.ok:
                self.view.reload_quasars()
                QMessageBox.information(self, "クエーサーのデータ", f"{dl.count:,} 個のクエーサーを読み込みました。\n"
                                        "数億光年より遠くまで引くと見えます。")
            else:
                QMessageBox.warning(self, "クエーサーのデータ", "ダウンロードできませんでした。\n\n" + dl.message)

        timer.timeout.connect(poll)
        self._qso_dl = (dl, timer, dlg)
        dl.start()
        timer.start(200)

    # ---------------------------------------------------------- 解説パネル

    def _build_panel(self):
        self.panel = QDockWidget("解説", self)
        self.panel.setObjectName("panel")
        self.panel_text = QTextBrowser()
        self.panel_text.setOpenExternalLinks(True)
        self.panel_text.setMinimumWidth(260)
        self.panel.setWidget(self.panel_text)
        self.addDockWidget(Qt.RightDockWidgetArea, self.panel)
        self.resizeDocks([self.panel], [300], Qt.Horizontal)
        self._panel_key = None

    def _update_panel(self, force=False):
        v = self.view
        key = ("star", v.selected_star) if v.selected_star >= 0 else ("body", v.target, v.ground)
        if key == self._panel_key and not force:
            return
        self._panel_key = key
        html = ["<div style='font-size:11pt; line-height:150%'>"]
        if v.selected_star >= 0:
            i = v.selected_star
            html.append(f"<h2>★ {v.stars.short_name(i)}</h2>")
            html.append("<p>" + v.stars.describe(i).replace("　｜　", "<br>") + "</p>")
            html.append(f"<p>{STAR_TEXT}</p>")
        elif v.ground:
            html.append("<h2>地上から見た空</h2>")
            html.append(f"<p>{v.place}（北緯 {v.lat:.2f}°・東経 {v.lon:.2f}°）から見上げた空です。</p>"
                        "<p>星は東から昇って南の空を通り、西に沈みます。これは地球が西から東へ自転しているためです。"
                        "北の空の星は、北極星のまわりを反時計回りに回って見えます。</p>")
            if v.target in BY_KEY and text_for(v.target):
                html.append(f"<h3>{BY_KEY[v.target].name}</h3><p>{text_for(v.target)}</p>")
        else:
            t = v.target
            if t.startswith("c:"):
                i = int(t[2:])
                html.append(f"<h2>{v.gcat.label(i)}</h2>")
                html.append("<p>" + v.gcat.describe(i).replace("　｜　", "<br>") + "</p>")
                html.append(f"<p>{KIND_DESCRIPTIONS.get(int(v.gcat.kind[i]), '')}</p>")
            elif t == "u:cmb":
                html.append("<h2>観測できる宇宙の果て</h2>")
                html.append(f"<p>{text_for('u:cmb')}</p>")
                html.append("<p style='color:#888'>" + self.status_info.text().replace("　｜　", "<br>") + "</p>")
            else:
                name = gx.BY_KEY[t].name if t in gx.BY_KEY else BY_KEY[t].name
                html.append(f"<h2>{name}</h2>")
                txt = text_for(t)
                if txt:
                    html.append(f"<p>{txt}</p>")
                html.append("<p style='color:#888'>" + self.status_info.text().replace("　｜　", "<br>") + "</p>")
        html.append("</div>")
        self.panel_text.setHtml("".join(html))

    # ---------------------------------------------------------- ツアー

    def _build_tour_bar(self):
        self.tour_bar = QFrame()
        self.tour_bar.setStyleSheet("QFrame { background: #10172a; } QLabel { color: #e8ecf5; }")
        lay = QHBoxLayout(self.tour_bar)
        lay.setContentsMargins(14, 8, 14, 8)
        self.tour_label = QLabel()
        self.tour_label.setWordWrap(True)
        f = self.tour_label.font()
        f.setPointSizeF(f.pointSizeF() * 1.3)
        self.tour_label.setFont(f)
        lay.addWidget(self.tour_label, 1)
        self.tour_count = QLabel()
        lay.addWidget(self.tour_count)
        for text, step in (("◀ 前", -1), ("次 ▶", +1)):
            b = QPushButton(text)
            b.clicked.connect(lambda _=False, d=step: self._tour_go(d))
            lay.addWidget(b)
        b = QPushButton("終了")
        b.clicked.connect(self.stop_tour)
        lay.addWidget(b)
        self.tour_bar.hide()

    def start_tour(self, tid):
        for t, title, fn in tours.TOURS:
            if t == tid:
                steps = fn(self.view) if tid == "tonight" else fn()
                self._tour = {"title": title, "steps": steps, "i": -1}
                self.tour_bar.show()
                self._tour_go(+1)
                return

    def stop_tour(self):
        if not self._tour:
            return
        self._tour = None
        self._tour_timer.stop()
        self.tour_bar.hide()

    def _tour_go(self, d):
        tr = self._tour
        if not tr:
            return
        i = tr["i"] + d
        if i < 0:
            i = 0
        if i >= len(tr["steps"]):
            self.stop_tour()
            return
        tr["i"] = i
        st = tr["steps"][i]
        v = self.view
        if st.ground:
            if not self.btn_ground.isChecked():
                self.btn_ground.setChecked(True)
            if "jd" in st.extra:
                v.set_jd(st.extra["jd"])
            if "speed_index" in st.extra:
                self.cb_speed.setCurrentIndex(st.extra["speed_index"])
                v.paused = False
            else:
                v.paused = True
            if st.look:
                v.look_at(st.look)
                v.g_fov = st.fov
            else:
                v.g_az, v.g_alt, v.g_fov = math.radians(st.az), math.radians(st.alt), st.fov
        else:
            if self.btn_ground.isChecked():
                self.btn_ground.setChecked(False)
            v.paused = True          # ツアー中は時間を止めて、場面を落ち着いて見られるようにする
            dist = st.dist
            if dist is None and st.dist_mult:
                dist = v._default_dist(st.target) * st.dist_mult
            v.fly_to(st.target, dist)
        self.tour_label.setText(st.text)
        self.tour_count.setText(f"{tr['title']}　{i + 1} / {len(tr['steps'])}")
        fly = v._fly["dur"] if v._fly else 0.0
        self._tour_timer.start(int((st.seconds + fly) * 1000))
        self._update_panel(force=True)
        v.update()

    # ---------------------------------------------------------- 地上モード

    def _on_ground(self, on):
        self.view.set_ground(on)
        self.btn_all.setEnabled(not on)
        self.sl_mag.setEnabled(not on)
        self.btn_ground.setText("🚀 宇宙へ戻る" if on else "🔭 地上から見る")
        # 1日/秒より速いと空がぐるぐる回って見づらいので、地上では少しゆっくりにする
        if on and self.cb_speed.currentIndex() > 3:
            self.cb_speed.setCurrentIndex(1)
        self.view.setFocus()

    def _restore_place(self):
        name = self.settings.value("place/name", "大阪")
        lat = float(self.settings.value("place/lat", 34.69))
        lon = float(self.settings.value("place/lon", 135.50))
        self.view.set_place(name, lat, lon)
        i = self.cb_place.findText(name)
        if i < 0:
            self.cb_place.insertItem(self.cb_place.count() - 1, name, (name, lat, lon))
            i = self.cb_place.findText(name)
        self.cb_place.setCurrentIndex(i)

    def _on_place(self, i):
        data = self.cb_place.itemData(i)
        if data is None:
            data = self._ask_place()
            if data is None:
                self.cb_place.setCurrentIndex(self.cb_place.findText(self.view.place))
                return
            j = self.cb_place.findText(data[0])
            if j < 0:
                self.cb_place.insertItem(self.cb_place.count() - 1, data[0], data)
                j = self.cb_place.findText(data[0])
            else:
                self.cb_place.setItemData(j, data)
            self.cb_place.setCurrentIndex(j)
        name, lat, lon = data
        self.view.set_place(name, lat, lon)
        self.settings.setValue("place/name", name)
        self.settings.setValue("place/lat", lat)
        self.settings.setValue("place/lon", lon)

    def _ask_place(self):
        dlg = QDialog(self)
        dlg.setWindowTitle("観測地")
        form = QFormLayout(dlg)
        ed_name = QLineEdit("観測地")
        sp_lat = QDoubleSpinBox()
        sp_lat.setRange(-90, 90)
        sp_lat.setDecimals(3)
        sp_lat.setValue(self.view.lat)
        sp_lat.setSuffix("°（北緯が＋）")
        sp_lon = QDoubleSpinBox()
        sp_lon.setRange(-180, 180)
        sp_lon.setDecimals(3)
        sp_lon.setValue(self.view.lon)
        sp_lon.setSuffix("°（東経が＋）")
        form.addRow("名前", ed_name)
        form.addRow("緯度", sp_lat)
        form.addRow("経度", sp_lon)
        bb = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        bb.accepted.connect(dlg.accept)
        bb.rejected.connect(dlg.reject)
        form.addRow(bb)
        if dlg.exec() != QDialog.Accepted:
            return None
        return (ed_name.text().strip() or "観測地", sp_lat.value(), sp_lon.value())

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
        self._ui_ticks = getattr(self, "_ui_ticks", 0) + 1
        if self.panel.isVisible():
            self._update_panel(force=(self._ui_ticks % 20 == 0))
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
        if key == "u:cmb":
            q = f"クエーサー {v.qso_count:,} 個を表示中" if v.qso_count else "クエーサーのデータは未ダウンロード（ファイルメニュー）"
            self.status_info.setText("<b>観測できる宇宙の果て</b>　｜　宇宙マイクロ波背景放射まで 約"
                                     f"{cosmos.CMB_MPC * 3.26156e6 / 1e8:,.0f} 億光年（共動距離）　｜　{q}"
                                     "　｜　視点の距離 " + format_length(v.dist))
            self._refresh_warn(v)
            return
        if v.ground:
            parts = [f"<b>地上から見た空</b>（{v.place}　北緯 {v.lat:.2f}°・東経 {v.lon:.2f}°）"]
            sun_alt, _ = v.ground_altaz("sun")
            if sun_alt > 0:
                parts.append(f"太陽の高度 {sun_alt:.0f}°（昼）")
            elif sun_alt > -18:
                parts.append(f"太陽の高度 {sun_alt:.0f}°（薄明）")
            else:
                parts.append("夜")
            if key in BY_KEY and key not in ("earth",):
                alt, az = v.ground_altaz(key)
                where = f"高度 {alt:.1f}°・方位 {az:.0f}°" if alt > 0 else "地平線の下"
                parts.append(f"{BY_KEY[key].name}: {where}")
            self.status_info.setText("　｜　".join(parts))
            self._refresh_warn(v)
            return
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
        if key in sbs.BY_KEY or key == "pluto":
            sb = sbs.BY_KEY.get(key)
            kind = sbs.KIND_JA[sb.kind] if sb else "準惑星"
            dia = b.radius_km * 2
            parts = [f"<b>{b.name}</b>", kind,
                     f"直径 約{dia:,.0f} km" if dia >= 10 else f"直径 約{dia * 1000:,.0f} m",
                     f"太陽から {_fmt_dist(np.linalg.norm(v.positions[key]))}",
                     f"地球から {_fmt_dist(np.linalg.norm(v.positions[key] - v.positions['earth']))}"]
            if sb and sb.note:
                parts.append(sb.note)
            parts.append("※ 位置はおおよそ")
            self.status_info.setText("　｜　".join(parts))
            self._refresh_warn(v)
            return
        parts = [f"<b>{b.name}</b>", f"半径 {b.radius_km:,.0f} km"]
        if b.parent not in ("sun", ""):
            par = BY_KEY[b.parent]
            d = np.linalg.norm(v.positions[key] - v.positions[b.parent]) * astro.AU_KM
            parts.append(f"{par.name}の衛星（{par.name}から {d / 1e4:,.1f} 万km）")
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
            "・衛星の位置: PyEphem（トリトンは NASA JPL の平均軌道要素）<br>"
            "・小天体の軌道: 冥王星は NASA JPL、その他は Wikipedia 各記事の軌道要素（JPL などが出典）<br>"
            "・天体の大きさ・自転軸: IAU WGCCRE 報告（2015年）<br>"
            "・恒星: HYG データベース v4.1（CC BY-SA 4.0）<br>"
            "・星座線・星座名: d3-celestial（© Olaf Frohn, BSD 3-Clause）<br>"
            "・銀河: 位置・距離・大きさは文献のおおよその値。形は粒子で作った模式図<br>"
            "・銀河カタログ（約1万個）: OpenNGC（CC BY-SA 4.0）。距離は後退速度から推定<br>"
            "・クエーサー（ダウンロードした場合）: SDSS DR16Q（Lyke et al. 2020）、VizieR VII/289<br>"
            "・宇宙マイクロ波背景放射: 計算で作った模式図（本物の観測地図ではありません）<br>"
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
