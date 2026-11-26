"""メインウィンドウ。"""

from __future__ import annotations

import math
from pathlib import Path

import numpy as np
from PySide6.QtCore import QDateTime, QSettings, Qt, QTimer, QUrl
from PySide6.QtGui import QAction, QColor, QDesktopServices, QIcon, QKeySequence
from PySide6.QtWidgets import (QCheckBox, QComboBox, QDateTimeEdit, QDialog, QDialogButtonBox, QDockWidget,
                               QFrame, QTextBrowser, QVBoxLayout,
                               QDoubleSpinBox, QFormLayout, QLabel, QLineEdit, QMainWindow,
                               QMessageBox, QProgressDialog, QPushButton, QSlider, QToolBar,
                               QWidget, QHBoxLayout, QSizePolicy, QFileDialog, QListWidget, QListWidgetItem,
                               QTableWidget, QTableWidgetItem, QAbstractItemView, QHeaderView)

from . import __version__, astro, textures
from .i18n import EN_MODE, tr, trx
from .bodies import BY_KEY
from .view import SpaceView, format_length
from . import galaxies as gx
from . import smallbodies as sbs
from . import tours
from . import cosmos
from . import spacecraft as crafts
from . import recorder
from . import minorplanets as mpl
from . import exoplanets as exo
from . import eclipses
from . import nebulae as neb
from . import events as evt
from . import artsat
from . import dsoimages
from . import skyphoto
from . import satellites as sats
from .descriptions import KIND_DESCRIPTIONS, STAR_TEXT, text_for

SPEEDS = [
    (tr("実時間"), 1.0),
    (tr("1分/秒"), 60.0),
    (tr("10分/秒"), 600.0),
    (tr("1時間/秒"), 3600.0),
    (tr("6時間/秒"), 21600.0),
    (tr("1日/秒"), 86400.0),
    (tr("1週間/秒"), 604800.0),
    (tr("1か月/秒"), 2629800.0),
    (tr("1年/秒"), 31557600.0),
]
DEFAULT_SPEED = 5   # 1日/秒

PLACES = [
    (tr("札幌"), 43.06, 141.35), (tr("仙台"), 38.27, 140.87), (tr("東京"), 35.68, 139.77),
    (tr("三鷹（国立天文台）"), 35.67, 139.54), (tr("名古屋"), 35.18, 136.91), (tr("大阪"), 34.69, 135.50),
    (tr("広島"), 34.39, 132.46), (tr("福岡"), 33.59, 130.40), (tr("那覇"), 26.21, 127.68),
]

def _target_order():
    """惑星のあとに、その衛星を惑星に近い順に並べる。"""
    from . import satellites as _sats
    out = ["sun", "mercury", "venus", "earth", "moon"]
    for planet in ("mars", "jupiter", "saturn", "uranus", "neptune"):
        out.append(planet)
        out += [s.key for s in sorted(_sats.BY_PARENT.get(planet, []), key=lambda s: s.a_km)]
    return out


TARGET_ORDER = _target_order()
SMALL_ORDER = ["pluto", "eris", "makemake", "haumea", "ceres", "pallas", "vesta",
               "itokawa", "ryugu", "bennu", "halley", "encke", "67p"]

HELP_TEXT = tr("""<h3>操作方法</h3>
<table cellpadding="3">
<tr><td><b>左ドラッグ</b></td><td>視点を回す</td></tr>
<tr><td><b>ホイール</b> / <b>右ドラッグ</b></td><td>近づく・離れる</td></tr>
<tr><td><b>ダブルクリック</b></td><td>惑星・銀河へ移動する／恒星の情報を見る</td></tr>
<tr><td><b>スペース</b></td><td>時間を止める・動かす</td></tr>
<tr><td><b>+ / −</b></td><td>近づく・離れる</td></tr>
<tr><td><b>F11</b></td><td>全画面表示</td></tr>
<tr><td><b>Ctrl+S</b></td><td>画面を画像で保存（ピクチャ/Soramado）</td></tr>
<tr><td><b>Ctrl+R</b></td><td>録画の開始・停止（ビデオ/Soramado、ffmpeg が必要）</td></tr>
<tr><td><b>Ctrl+E</b></td><td>日食・月食の一覧</td></tr>
<tr><td><b>Ctrl+F</b></td><td>天体を名前で探す（星座・星雲・星団。小惑星・系外惑星はダウンロードしたとき）</td></tr>
<tr><td><b>星座名をダブルクリック</b></td><td>星座の解説（見ごろ・見つけ方・神話）</td></tr>
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
「見る天体」から銀河を選ぶと、その銀河まで飛んでいきます。銀河の形は模式図です。</p>""")


def _fmt_dist(au: float) -> str:
    if 0.1 <= au < 1000:
        return f"{au:,.3f} AU"
    return format_length(au)


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle(f"{tr('そらみ窓')} {__version__}")
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
        self.view.conSelected.connect(lambda _i: (self._update_panel(force=True), self._refresh_ui()))

        self._build_toolbar()
        self._build_panel()
        self._build_menu()
        self._tour = None
        self._tour_deadline = None
        self._rec = None
        self._rec_tour = False
        self._tour_timer = QTimer(self)        # 場面の切り替えは、ビューの時計で判定する
        self._tour_timer.timeout.connect(self._tour_check)
        self._tour_timer.start(50)

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
        self._restore_settings()
        QTimer.singleShot(400, self._check_gl)

    # ---------------------------------------------------------- 画面の部品

    def _build_toolbar(self):
        tb = QToolBar(tr("操作"))
        tb.setObjectName("toolbar")
        tb.setMovable(False)
        self.addToolBar(tb)

        tb.addWidget(QLabel(tr(" 見る天体 ")))
        self.cb_target = QComboBox()
        for key in TARGET_ORDER:
            par = BY_KEY[key].parent
            # 衛星は字下げして、どの惑星の衛星か分かるようにする
            self.cb_target.addItem(("　" + BY_KEY[key].name) if par not in ("sun", "") else BY_KEY[key].name, key)
        self.cb_target.setMaxVisibleItems(30)
        self.cb_target.insertSeparator(self.cb_target.count())
        for key in SMALL_ORDER:
            self.cb_target.addItem(BY_KEY[key].name, key)
        self.cb_target.insertSeparator(self.cb_target.count())
        for sc in crafts.SPACECRAFT:
            self.cb_target.addItem("🛰 " + sc.name, sc.key)
        self.cb_target.insertSeparator(self.cb_target.count())
        # 星雲・星団（解説のある有名なもの。ほかは画面でダブルクリック）
        for i, n in sorted(enumerate(neb.NEBULAE), key=lambda t: t[1].ly):
            if n.note:
                self.cb_target.addItem("✦ " + n.name, f"n:{i}")
        self.cb_target.insertSeparator(self.cb_target.count())
        for g in gx.GALAXIES:
            if g.in_menu:
                self.cb_target.addItem(g.name, g.key)
        self.cb_target.insertSeparator(self.cb_target.count())
        self.cb_target.addItem(tr("観測できる宇宙の果て"), "u:cmb")
        self.cb_target.setMaxVisibleItems(30)
        self.cb_target.activated.connect(lambda i: self.view.set_target(self.cb_target.itemData(i)))
        tb.addWidget(self.cb_target)

        self.btn_all = QPushButton(tr("全体を見る"))
        self.btn_all.clicked.connect(self.view.overview)
        tb.addWidget(self.btn_all)
        tb.addSeparator()

        self.btn_ground = QPushButton(tr("🔭 地上から見る"))
        self.btn_ground.setCheckable(True)
        self.btn_ground.toggled.connect(self._on_ground)
        tb.addWidget(self.btn_ground)
        self.cb_place = QComboBox()
        for name, lat, lon in PLACES:
            self.cb_place.addItem(name, (name, lat, lon))
        self.cb_place.addItem(tr("緯度・経度を入力…"), None)
        self.cb_place.activated.connect(self._on_place)
        tb.addWidget(self.cb_place)
        tb.addSeparator()

        self.btn_rec = QPushButton(tr("⏺ 録画"))
        self.btn_rec.setCheckable(True)
        self.btn_rec.setToolTip(tr("画面を動画（MP4）に録画します"))
        self.btn_rec.toggled.connect(self._on_record)
        tb.addWidget(self.btn_rec)
        tb.addSeparator()

        self.btn_play = QPushButton(tr("⏸ 停止"))
        self.btn_play.setMinimumWidth(80)
        self.btn_play.clicked.connect(self._toggle_pause)
        tb.addWidget(self.btn_play)

        self.chk_reverse = QCheckBox(tr("逆再生"))
        self.chk_reverse.toggled.connect(self._apply_speed)
        tb.addWidget(self.chk_reverse)

        self.cb_speed = QComboBox()
        for label, _ in SPEEDS:
            self.cb_speed.addItem(label)
        self.cb_speed.setCurrentIndex(DEFAULT_SPEED)
        self.cb_speed.currentIndexChanged.connect(self._apply_speed)
        tb.addWidget(self.cb_speed)

        btn_now = QPushButton(tr("現在時刻"))
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
        lay.addWidget(QLabel(tr("惑星の大きさ")))
        self.sl_mag = QSlider(Qt.Horizontal)
        self.sl_mag.setRange(0, 300)          # 10^(値/100) 倍
        self.sl_mag.setFixedWidth(140)
        self.sl_mag.valueChanged.connect(self._on_magnify)
        lay.addWidget(self.sl_mag)
        self.lb_mag = QLabel(tr("×1（実寸）"))
        self.lb_mag.setMinimumWidth(80)
        lay.addWidget(self.lb_mag)
        tb.addWidget(box)

        box2 = QWidget()
        lay2 = QHBoxLayout(box2)
        lay2.setContentsMargins(6, 0, 6, 0)
        lay2.addWidget(QLabel(tr("星の数")))
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
        m_file = mb.addMenu(tr("ファイル(&F)"))
        act_dl = QAction(tr("惑星の画像をダウンロード…"), self)
        act_dl.triggered.connect(lambda: self._start_download(force=True))
        m_file.addAction(act_dl)
        act_shot = QAction(tr("画面を画像で保存"), self)
        act_shot.setShortcut(QKeySequence("Ctrl+S"))
        act_shot.triggered.connect(self.save_picture)
        m_file.insertAction(m_file.actions()[0] if m_file.actions() else None, act_shot)
        act_rec = QAction(tr("録画の開始・停止"), self)
        act_rec.setShortcut(QKeySequence("Ctrl+R"))
        act_rec.triggered.connect(lambda: self.btn_rec.toggle())
        m_file.insertAction(m_file.actions()[1], act_rec)
        act_open = QAction(tr("保存したフォルダを開く"), self)
        act_open.triggered.connect(self._open_folders)
        m_file.insertAction(m_file.actions()[2], act_open)
        m_file.insertSeparator(m_file.actions()[3])
        act_q = QAction(tr("クエーサーのデータをダウンロード…"), self)
        act_q.triggered.connect(self._download_quasars)
        m_file.addAction(act_q)
        act_mp = QAction(tr("小惑星・彗星のデータをダウンロード…"), self)
        act_mp.triggered.connect(lambda: self._download_minor(None))
        m_file.addAction(act_mp)
        act_mpf = QAction(tr("小惑星・彗星のデータを手元のファイルから読み込む…"), self)
        act_mpf.triggered.connect(self._load_minor_files)
        m_file.addAction(act_mpf)
        act_tle = QAction(tr("人工衛星のデータ（ISS など）をダウンロード…"), self)
        act_tle.triggered.connect(self._download_tle)
        m_file.addAction(act_tle)
        act_exo = QAction(tr("系外惑星のデータをダウンロード…"), self)
        act_exo.triggered.connect(lambda: self._download_exo(None))
        m_file.addAction(act_exo)
        act_exof = QAction(tr("系外惑星のデータを手元のファイル（CSV）から読み込む…"), self)
        act_exof.triggered.connect(self._load_exo_file)
        m_file.addAction(act_exof)
        act_ph = QAction(tr("星雲・銀河の写真をダウンロード…"), self)
        act_ph.triggered.connect(self._download_photos)
        m_file.addAction(act_ph)
        act_mw = QAction(tr("天の川の写真（Gaia）をダウンロード…"), self)
        act_mw.triggered.connect(self._download_mwphoto)
        m_file.addAction(act_mw)
        m_file.addSeparator()
        act_quit = QAction(tr("終了"), self)
        act_quit.setShortcut(QKeySequence.Quit)
        act_quit.triggered.connect(self.close)
        m_file.addAction(act_quit)

        m_view = mb.addMenu(tr("表示(&V)"))
        self.act_orbits = QAction(tr("軌道"), self, checkable=True, checked=True)
        self.act_orbits.toggled.connect(self._on_toggle_orbits)
        m_view.addAction(self.act_orbits)
        self.act_labels = QAction(tr("名前"), self, checkable=True, checked=True)
        self.act_labels.toggled.connect(self._on_toggle_labels)
        m_view.addAction(self.act_labels)
        m_view.addSeparator()
        self.act_stars = self._toggle(m_view, tr("恒星"), "show_stars")
        self.act_conl = self._toggle(m_view, tr("星座線"), "show_con_lines")
        self.act_conn = self._toggle(m_view, tr("星座名"), "show_con_names")
        self.act_starn = self._toggle(m_view, tr("星の名前"), "show_star_names")
        self.act_neb = self._toggle(m_view, tr("星雲・星団"), "show_nebulae")
        self.act_gal = self._toggle(m_view, tr("銀河"), "show_galaxies")
        self.act_photo = self._toggle(m_view, tr("星雲・銀河を写真で表示（ダウンロードしたもの）"), "show_photos")
        self.act_mwphoto = self._toggle(m_view, tr("天の川を写真で表示（ダウンロードしたもの）"), "show_mwphoto")
        self.act_small = self._toggle(m_view, tr("準惑星・小惑星・彗星"), "show_small")
        self.act_minor = self._toggle(m_view, tr("たくさんの小惑星・彗星（ダウンロードしたもの）"), "show_minor")
        self.act_exo = self._toggle(m_view, tr("系外惑星を持つ恒星（ダウンロードしたもの）"), "show_exo")
        act_find = QAction(tr("天体を探す（星座・星雲・小惑星・系外惑星）…"), self)
        act_find.setShortcut(QKeySequence("Ctrl+F"))
        act_find.triggered.connect(self._find_minor)
        m_view.addAction(act_find)
        self.act_craft = self._toggle(m_view, tr("探査機の航路"), "show_craft")
        self.act_qso = self._toggle(m_view, tr("クエーサー"), "show_quasars")
        self.act_cmb = self._toggle(m_view, tr("宇宙マイクロ波背景放射"), "show_cmb")
        m_view.addSeparator()
        act_full = QAction(tr("全画面表示"), self, checkable=True)
        act_full.setShortcut(QKeySequence("F11"))
        act_full.toggled.connect(lambda on: self.showFullScreen() if on else self.showNormal())
        m_view.addAction(act_full)

        m_view.addSeparator()
        m_view.addAction(self.panel.toggleViewAction())
        m_lang = m_view.addMenu("言語 / Language")
        from PySide6.QtGui import QActionGroup
        grp = QActionGroup(self)
        cur = str(self.settings.value("ui/lang", "ja"))
        for code, label in (("ja", "日本語"), ("en", "English")):
            a = QAction(label, self, checkable=True)
            a.setChecked(cur == code)
            a.triggered.connect(lambda _=False, c=code: self._set_lang(c))
            grp.addAction(a)
            m_lang.addAction(a)

        m_ev = mb.addMenu(tr("天文現象(&E)"))
        act_ecl = QAction(tr("日食・月食…"), self)
        act_ecl.setShortcut(QKeySequence("Ctrl+E"))
        act_ecl.triggered.connect(self._show_eclipses)
        m_ev.addAction(act_ecl)
        act_met = QAction(tr("流星群…"), self)
        act_met.triggered.connect(self._show_showers)
        m_ev.addAction(act_met)
        act_iss = QAction(tr("人工衛星（ISS など）が見える時刻…"), self)
        act_iss.triggered.connect(self._show_passes)
        m_ev.addAction(act_iss)
        act_conj = QAction(tr("惑星・月の接近と見ごろ…"), self)
        act_conj.triggered.connect(self._show_events)
        m_ev.addAction(act_conj)
        m_ev.addSeparator()
        self.act_meteor = self._toggle(m_ev, tr("地上モードで流星を流す"), "show_meteors")
        self.act_artsat = self._toggle(m_ev, tr("人工衛星を表示する"), "show_artsat")

        m_tour = mb.addMenu(tr("ツアー(&T)"))
        for tid, title, _fn in tours.TOURS:
            act = QAction(tr(title), self)
            act.triggered.connect(lambda _=False, t=tid: self.start_tour(t))
            m_tour.addAction(act)
        m_tour.addSeparator()
        m_rec = m_tour.addMenu(tr("ツアーを動画にする"))
        for tid, title, _fn in tours.TOURS:
            act = QAction(tr(title), self)
            act.triggered.connect(lambda _=False, t=tid: self.record_tour(t))
            m_rec.addAction(act)
        m_tour.addSeparator()
        act_stop = QAction(tr("ツアーを終わる"), self)
        act_stop.setShortcut(QKeySequence("Esc"))
        act_stop.triggered.connect(self.stop_tour)
        m_tour.addAction(act_stop)

        m_help = mb.addMenu(tr("ヘルプ(&H)"))
        act_manual = QAction(tr("説明書"), self)
        act_manual.setShortcut(QKeySequence("F1"))
        act_manual.triggered.connect(self._show_manual)
        m_help.addAction(act_manual)
        act_howto = QAction(tr("操作方法（早見表）"), self)
        act_howto.triggered.connect(lambda: QMessageBox.information(self, tr("操作方法"), HELP_TEXT))
        m_help.addAction(act_howto)
        act_about = QAction(tr("そらみ窓について"), self)
        act_about.triggered.connect(self._about)
        m_help.addAction(act_about)

    # ---------------------------------------------------------- 動作

    # ---------------------------------------------------------- 設定の保存と復元

    _VIEW_FLAGS = ("show_orbits", "show_labels", "show_stars", "show_con_lines", "show_con_names",
                   "show_star_names", "show_galaxies", "show_small", "show_craft", "show_quasars", "show_cmb", "show_minor", "show_exo", "show_nebulae", "show_artsat", "show_photos", "show_mwphoto")

    def _restore_settings(self):
        st = self.settings
        geo = st.value("window/geometry")
        if geo is not None:
            self.restoreGeometry(geo)
        state = st.value("window/state")
        if state is not None:
            self.restoreState(state)
        acts = {"show_orbits": self.act_orbits, "show_labels": self.act_labels, "show_stars": self.act_stars,
                "show_con_lines": self.act_conl, "show_con_names": self.act_conn, "show_star_names": self.act_starn,
                "show_galaxies": self.act_gal, "show_small": self.act_small, "show_craft": self.act_craft,
                "show_quasars": self.act_qso, "show_cmb": self.act_cmb, "show_minor": self.act_minor, "show_exo": self.act_exo, "show_nebulae": self.act_neb, "show_artsat": self.act_artsat, "show_photos": self.act_photo, "show_mwphoto": self.act_mwphoto}
        for name, act in acts.items():
            val = st.value(f"view/{name}")
            if val is not None:
                act.setChecked(str(val).lower() in ("true", "1"))
        if st.value("view/limit") is not None:
            self.sl_stars.setValue(int(st.value("view/limit")))
        if st.value("view/magnify") is not None:
            self.sl_mag.setValue(int(st.value("view/magnify")))
        if st.value("time/speed") is not None:
            self.cb_speed.setCurrentIndex(int(st.value("time/speed")))
        target = st.value("view/target")
        if target and self.view.valid_key(str(target)):
            self.view.set_target(target, fly=False)

    def _save_settings(self):
        st = self.settings
        st.setValue("window/geometry", self.saveGeometry())
        st.setValue("window/state", self.saveState())
        for name in self._VIEW_FLAGS:
            st.setValue(f"view/{name}", bool(getattr(self.view, name)))
        st.setValue("view/limit", self.sl_stars.value())
        st.setValue("view/magnify", self.sl_mag.value())
        st.setValue("time/speed", self.cb_speed.currentIndex())
        if not self.view.ground:
            st.setValue("view/target", self.view.target)

    def _set_lang(self, code):
        self.settings.setValue("ui/lang", code)
        QMessageBox.information(self, "そらみ窓 / Soramado",
                                "言語は、次にそらみ窓を起動したときから切り替わります。\n"
                                "The language will change the next time you start Soramado.\n\n"
                                "（英語のときも、天体の解説・ツアーの字幕・説明書は今は日本語です。）\n"
                                "(Descriptions, tour captions and the manual are still in Japanese.)")

    def _check_gl(self):
        if self.view.gl_error:
            QMessageBox.critical(self, tr("そらみ窓"), self.view.gl_error)

    def _show_manual(self):
        from pathlib import Path
        dlg = QDialog(self)
        dlg.setWindowTitle(tr("そらみ窓 説明書"))
        dlg.resize(760, 640)
        lay = QVBoxLayout(dlg)
        tb = QTextBrowser()
        tb.setOpenExternalLinks(True)
        path = Path(__file__).parent / "manual.md"
        tb.setMarkdown(path.read_text(encoding="utf-8") if path.is_file() else tr("説明書が見つかりません。"))
        lay.addWidget(tb)
        bb = QDialogButtonBox(QDialogButtonBox.Close)
        bb.rejected.connect(dlg.reject)
        lay.addWidget(bb)
        dlg.exec()

    # ---------------------------------------------------------- 画像・動画

    def save_picture(self):
        path = recorder.picture_path()
        img = self.view.grabFramebuffer()
        if img.save(str(path)):
            self.statusBar().showMessage(f"画像を保存しました: {path}", 8000)
        else:
            QMessageBox.warning(self, tr("画像の保存"), f"保存できませんでした: {path}")

    def _open_folders(self):
        for p in (recorder.picture_path().parent, recorder.video_path().parent):
            QDesktopServices.openUrl(QUrl.fromLocalFile(str(p)))

    def _on_record(self, on):
        v = self.view
        if on:
            if not recorder.ffmpeg_available():
                QMessageBox.warning(self, tr("録画"), "録画には ffmpeg が必要です。端末で次のコマンドを実行してください。\n\n"
                                    "sudo apt install ffmpeg")
                self.btn_rec.blockSignals(True)
                self.btn_rec.setChecked(False)
                self.btn_rec.blockSignals(False)
                return
            img = v.grabFramebuffer()
            self._rec = recorder.VideoRecorder(recorder.video_path(), img.width(), img.height())
            v.start_recording(self._rec_frame)
            self.btn_rec.setText(tr("⏹ 停止 0:00"))
            self.btn_rec.setStyleSheet("QPushButton { color: #ff5050; font-weight: bold; }")
        else:
            v.stop_recording()
            self.btn_rec.setText(tr("⏺ 録画"))
            self.btn_rec.setStyleSheet("")
            rec, self._rec = self._rec, None
            if rec is None:
                return
            ok, err = rec.finish()
            if ok:
                box = QMessageBox(self)
                box.setWindowTitle(tr("録画"))
                box.setText(f"{rec.seconds:.1f} 秒の動画を保存しました。\n{rec.path}")
                b_open = box.addButton(tr("フォルダを開く"), QMessageBox.ActionRole)
                box.addButton(QMessageBox.Ok)
                box.exec()
                if box.clickedButton() is b_open:
                    QDesktopServices.openUrl(QUrl.fromLocalFile(str(rec.path.parent)))
            else:
                QMessageBox.warning(self, tr("録画"), tr("動画を保存できませんでした。\n\n") + err[-800:])

    def _rec_frame(self, img):
        rec = self._rec
        if rec is None:
            return
        if not rec.add(img):
            QTimer.singleShot(0, lambda: self.btn_rec.setChecked(False))
            return
        if rec.frames % 15 == 0:
            sec = int(rec.seconds)
            self.btn_rec.setText(f"⏹ 停止 {sec // 60}:{sec % 60:02d}")

    def record_tour(self, tid):
        if self.btn_rec.isChecked():
            self.btn_rec.setChecked(False)
        self.start_tour(tid)
        self._rec_tour = True
        self.btn_rec.setChecked(True)

    # ---------------------------------------------------------- クエーサーのダウンロード

    def _download_quasars(self):
        if getattr(self, "_qso_dl", None):
            return
        ans = QMessageBox.question(
            self, tr("クエーサーのデータ"),
            "SDSS の第16次クエーサーカタログ（DR16Q、約75万個）を、天文データセンター VizieR から"
            "ダウンロードします（通信量 約20〜40MB、数分かかることがあります）。よろしいですか？")
        if ans != QMessageBox.Yes:
            return
        dl = cosmos.QuasarDownloader()
        dlg = QProgressDialog(tr("クエーサーのデータをダウンロードしています…"), tr("キャンセル"), 0, 0, self)
        dlg.setWindowTitle(tr("クエーサーのデータ"))
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
                QMessageBox.information(self, tr("クエーサーのデータ"), f"{dl.count:,} 個のクエーサーを読み込みました。\n"
                                        "数億光年より遠くまで引くと見えます。")
            else:
                QMessageBox.warning(self, tr("クエーサーのデータ"), tr("ダウンロードできませんでした。\n\n") + dl.message)

        timer.timeout.connect(poll)
        self._qso_dl = (dl, timer, dlg)
        dl.start()
        timer.start(200)

    # ---------------------------------------------------------- 小惑星・彗星のダウンロードと検索

    def _load_minor_files(self):
        files, _ = QFileDialog.getOpenFileNames(
            self, tr("JPL の軌道要素の表を選ぶ（ELEMENTS.NUMBR(.gz) と ELEMENTS.COMET）"), str(Path.home() / tr("ダウンロード")),
            tr("軌道要素の表 (ELEMENTS.* *.gz *.txt);;すべてのファイル (*)"))
        if files:
            self._download_minor(files)

    def _download_minor(self, files):
        if getattr(self, "_mp_dl", None):
            return
        if files is None:
            ans = QMessageBox.question(
                self, tr("小惑星・彗星のデータ"),
                "NASA JPL から、番号の付いた小惑星（約80万個）と彗星（約4千個）の軌道要素の表を"
                "ダウンロードします。\n\n通信量は約60〜90MB、読み込みまで数分かかることがあります。よろしいですか？")
            if ans != QMessageBox.Yes:
                return
        dl = mpl.MinorPlanetDownloader(files)
        dlg = QProgressDialog(tr("準備しています…"), tr("キャンセル"), 0, 0, self)
        dlg.setWindowTitle(tr("小惑星・彗星のデータ"))
        dlg.setWindowModality(Qt.WindowModal)
        dlg.setMinimumDuration(0)
        dlg.canceled.connect(dl.cancel)
        timer = QTimer(self)

        def poll():
            dlg.setLabelText(f"{dl.stage}…\n{dl.bytes / 1e6:,.1f} MB" if dl.bytes else f"{dl.stage}…")
            if not dl.done:
                return
            timer.stop()
            dlg.close()
            self._mp_dl = None
            if dl.ok:
                self.view.reload_minor()
                mp = self.view.mp
                lines = [f"{len(mp):,} 個の小惑星・彗星を読み込みました。", ""]
                for k, (_key, name, _c) in enumerate(mpl.KINDS):
                    n = mp.count(k)
                    if n:
                        lines.append(f"　{name}: {n:,} 個")
                lines += ["", tr("点をダブルクリックすると、その天体の名前と軌道がわかります。"),
                          tr("「表示」→「小惑星・彗星を探す」（Ctrl+F）で名前から探せます。")]
                if dl.message:
                    lines += ["", dl.message]
                QMessageBox.information(self, tr("小惑星・彗星のデータ"), "\n".join(lines))
            else:
                QMessageBox.warning(
                    self, tr("小惑星・彗星のデータ"), tr("読み込めませんでした。\n\n") + dl.message +
                    "\n\nブラウザーで次のファイルをダウンロードして、「ファイル」→「小惑星・彗星のデータを"
                    f"手元のファイルから読み込む」で選ぶこともできます。\n{mpl.URL_NUMBERED}\n{mpl.URL_COMETS}")

        timer.timeout.connect(poll)
        self._mp_dl = (dl, timer, dlg)
        dl.start()
        timer.start(200)

    def _load_exo_file(self):
        f, _ = QFileDialog.getOpenFileName(self, tr("NASA Exoplanet Archive の表（CSV）を選ぶ"), str(Path.home() / tr("ダウンロード")),
                                           tr("CSV (*.csv);;すべてのファイル (*)"))
        if f:
            self._download_exo(f)

    def _download_exo(self, file):
        if getattr(self, "_exo_dl", None):
            return
        if file is None:
            ans = QMessageBox.question(
                self, tr("系外惑星のデータ"),
                "NASA Exoplanet Archive から、これまでに見つかった系外惑星（約6千個）の表をダウンロードします。"
                "\n\n通信量は約1〜2MBです。よろしいですか？")
            if ans != QMessageBox.Yes:
                return
        dl = exo.ExoplanetDownloader(file)
        dlg = QProgressDialog(tr("系外惑星のデータを読み込んでいます…"), tr("キャンセル"), 0, 0, self)
        dlg.setWindowTitle(tr("系外惑星のデータ"))
        dlg.setWindowModality(Qt.WindowModal)
        dlg.setMinimumDuration(0)
        dlg.canceled.connect(dl.cancel)
        timer = QTimer(self)

        def poll():
            if dl.bytes:
                dlg.setLabelText(f"系外惑星のデータをダウンロードしています…\n{dl.bytes / 1e6:,.2f} MB")
            if not dl.done:
                return
            timer.stop()
            dlg.close()
            self._exo_dl = None
            if dl.ok:
                self.view.reload_exo()
                QMessageBox.information(
                    self, tr("系外惑星のデータ"),
                    f"{dl.count:,} 個の恒星をまわる、{dl.planets:,} 個の系外惑星を読み込みました。\n\n"
                    "系外惑星を持つ恒星には緑の丸が付きます。ダブルクリックすると、その惑星系へ飛んでいけます。\n"
                    "Ctrl+F で、恒星や惑星の名前（例: TRAPPIST-1、Proxima Cen、51 Peg）から探せます。")
            else:
                QMessageBox.warning(
                    self, tr("系外惑星のデータ"), tr("読み込めませんでした。\n\n") + dl.message +
                    "\n\nブラウザーで次のアドレスを開いて CSV を保存し、「ファイル」→「系外惑星のデータを手元の"
                    f"ファイル（CSV）から読み込む」で選ぶこともできます。\n{exo.URL}")

        timer.timeout.connect(poll)
        self._exo_dl = (dl, timer, dlg)
        dl.start()
        timer.start(200)

    def _download_photos(self):
        if getattr(self, "_ph_dl", None):
            return
        dl = dsoimages.PhotoDownloader()
        if dl.total == 0:
            QMessageBox.information(self, tr("星雲・銀河の写真"), tr("写真はすべてダウンロード済みです。"))
            return
        ans = QMessageBox.question(
            self, tr("星雲・銀河の写真"),
            tr("星雲・星団・銀河の本物の写真（DSS2 color）をダウンロードします。\n"
               "ESA（ESASky）が配信している全天の写真から、天体ごとに切り出して保存します。\n\n"
               "通信量は約80MB、時間は回線によって数分〜十数分です。よろしいですか？"))
        if ans != QMessageBox.Yes:
            return
        dlg = QProgressDialog(tr("星雲・銀河の写真をダウンロードしています…"), tr("キャンセル"), 0, dl.total, self)
        dlg.setWindowTitle(tr("星雲・銀河の写真"))
        dlg.setWindowModality(Qt.WindowModal)
        dlg.setMinimumDuration(0)
        dlg.canceled.connect(dl.cancel)
        timer = QTimer(self)

        def poll():
            dlg.setValue(dl.finished)
            dlg.setLabelText(trx(f"星雲・銀河の写真をダウンロードしています…\n"
                                 f"{dl.finished} / {dl.total}　{dl.current}　（{dl.bytes / 1e6:,.1f} MB）"))
            if not dl.done:
                return
            timer.stop()
            dlg.close()
            self._ph_dl = None
            self.view.reload_photos()
            got = len(self.view._ph)
            if dl.ok:
                msg = trx(f"{got} 個の天体の写真を用意しました。") + "\n\n" + tr(
                    "星雲・銀河を地球の側から見ると、本物の写真で表示されます。横や裏に回ると、粒の模式図に切り替わります。\n"
                    "「表示」→「星雲・銀河を写真で表示」で、写真を出さないようにもできます。")
                if dl.failed:
                    msg += "\n\n" + trx(f"{dl.failed} 個はダウンロードできませんでした（もう一度実行すると、足りない分だけ取りに行きます）。")
                QMessageBox.information(self, tr("星雲・銀河の写真"), msg)
            else:
                QMessageBox.warning(self, tr("星雲・銀河の写真"), tr("ダウンロードできませんでした。\n\n") + dl.message)
            self._update_panel(force=True)

        timer.timeout.connect(poll)
        self._ph_dl = (dl, timer, dlg)
        dl.start()
        timer.start(200)

    def _download_mwphoto(self):
        if getattr(self, "_mw_dl", None):
            return
        again = skyphoto.path().is_file()
        ans = QMessageBox.question(
            self, tr("天の川の写真"),
            (tr("天の川の写真はダウンロード済みです。もう一度作り直しますか？\n\n") if again else "") +
            tr("ESA の Gaia 衛星が測った約17億個の星の光から作られた、全天の地図（CDS が配信）をダウンロードして、"
               "太陽系から見た空に天の川を表示します。\n\n通信量は約3MB です。よろしいですか？"))
        if ans != QMessageBox.Yes:
            return
        dl = skyphoto.SkyDownloader()
        dlg = QProgressDialog(tr("天の川の写真をダウンロードしています…"), tr("キャンセル"), 0, dl.total + 1, self)
        dlg.setWindowTitle(tr("天の川の写真"))
        dlg.setWindowModality(Qt.WindowModal)
        dlg.setMinimumDuration(0)
        dlg.canceled.connect(dl.cancel)
        timer = QTimer(self)

        def poll():
            dlg.setValue(min(dl.finished, dl.total))
            dlg.setLabelText(trx(f"天の川の写真をダウンロードしています…\n{dl.finished} / {dl.total}"
                                 f"　（{dl.bytes / 1e6:,.1f} MB）") +
                             (("\n" + tr("全天の画像に並べ直しています…")) if dl.finished >= dl.total else ""))
            if not dl.done:
                return
            timer.stop()
            dlg.close()
            self._mw_dl = None
            self.view.reload_mwphoto()
            if dl.ok:
                QMessageBox.information(self, tr("天の川の写真"), tr(
                    "天の川の写真を用意しました。\n\n太陽系の近くから見た空と、「地上から見る」の夜空に天の川が出ます。\n"
                    "「表示」→「天の川を写真で表示」で、出さないようにもできます。"))
            elif "キャンセル" not in dl.message:
                QMessageBox.warning(self, tr("天の川の写真"), tr("ダウンロードできませんでした。\n\n") + dl.message)

        timer.timeout.connect(poll)
        self._mw_dl = (dl, timer, dlg)
        dl.start()
        timer.start(200)

    def _find_minor(self):
        mp, ex = self.view.mp, self.view.exo
        dlg = QDialog(self)
        dlg.setWindowTitle(tr("天体を探す（星座・星雲・小惑星・系外惑星）"))
        dlg.resize(460, 440)
        lay = QVBoxLayout(dlg)
        lay.addWidget(QLabel(tr("名前か番号を入れてください。\n例: オリオン、すばる、M42、Itokawa、Ryugu、433、Halley、TRAPPIST-1\n"
                                "（小惑星・系外惑星はダウンロードしたときだけ、英語の名前で探せます）")))
        ed = QLineEdit()
        lay.addWidget(ed)
        lst = QListWidget()
        lay.addWidget(lst, 1)

        def search():
            lst.clear()
            t = ed.text().strip()
            if t:
                tl = t.lower()
                for i, c in enumerate(self.view.stars.constellations):
                    if t in c.name or tl == c.id.lower():
                        it = QListWidgetItem(trx(f"{c.name}　（星座）"))
                        it.setData(Qt.UserRole, f"con:{i}")
                        lst.addItem(it)
                for i, sa in enumerate(self.view.artsats):
                    if t in sa.ja or tl in sa.name.lower():
                        it = QListWidgetItem(trx(f"{sa.ja}　（人工衛星）"))
                        it.setData(Qt.UserRole, f"s:{i}")
                        lst.addItem(it)
                        if lst.count() > 40:
                            break
                for i, n in enumerate(neb.NEBULAE):
                    mname = f"m{n.m}" if n.m else ""
                    if t in n.name or tl == mname or tl.replace(" ", "") == n.id.lower():
                        it = QListWidgetItem(trx(f"{n.name}　（{neb.TYPE_JA[n.type]}）"))
                        it.setData(Qt.UserRole, f"n:{i}")
                        lst.addItem(it)
            if ex is not None:
                for i in ex.find(ed.text()):
                    n = len(ex.systems[i]["planets"])
                    it = QListWidgetItem(trx(f"{ex.name(i)}　（系外惑星 {n} 個を持つ恒星）"))
                    it.setData(Qt.UserRole, f"x:{i}")
                    lst.addItem(it)
            if mp is not None:
                for i in mp.find(ed.text()):
                    it = QListWidgetItem(trx(f"{mp.name(i)}　（{mp.kind_name(i)}）"))
                    it.setData(Qt.UserRole, f"mp:{i}")
                    lst.addItem(it)
            if lst.count():
                lst.setCurrentRow(0)

        def go(item=None):
            item = item or lst.currentItem()
            if item is None:
                return
            dlg.accept()
            key = item.data(Qt.UserRole)
            if key.startswith("con:"):
                ci = int(key[4:])
                v = self.view
                if v.ground:
                    v.look_dir(v.stars.constellations[ci].center)
                v.select_con(ci)
            else:
                self.view.set_target(key)

        ed.textChanged.connect(search)
        ed.returnPressed.connect(go)
        lst.itemActivated.connect(go)
        bb = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        bb.button(QDialogButtonBox.Ok).setText(tr("そこへ行く"))
        bb.accepted.connect(go)
        bb.rejected.connect(dlg.reject)
        lay.addWidget(bb)
        dlg.exec()

    # ---------------------------------------------------------- 日食・月食

    def _set_status(self, text):
        self.status_info.setText(trx(text))

    @staticmethod
    def _local_time(jd, with_date=True):  # noqa: D401
        dt = astro.datetime_from_jd(jd).astimezone()
        return dt.strftime(tr("%Y年%-m月%-d日 %H:%M")) if with_date else dt.strftime("%H:%M")

    def _eclipse_local_text(self, e) -> str:
        return trx(self._eclipse_local_text_ja(e))

    def _eclipse_local_text_ja(self, e) -> str:
        loc = e.local
        place = self.view.place
        if e.kind == "solar":
            if not loc.get("visible"):
                return f"{place}では見えない"
            kind = {"total": tr("皆既"), "annular": tr("金環")}.get(loc["type"], tr("部分日食"))
            t = self._local_time(loc["jd"], False)
            txt = f"{kind}（最大 {t}、太陽の{loc['frac'] * 100:.0f}%がかくれる）" if kind == tr("部分日食") else \
                f"{kind}が見える（最大 {t}）"
            if loc["alt"] < 0:
                txt += tr("・最大のときは地平線の下")
            return txt
        if not loc.get("visible"):
            return f"{place}では見えない（月が地平線の下）"
        if loc.get("all"):
            return f"全部見える（最大のとき月の高度 {loc['alt']:.0f}°）"
        if loc.get("alt_start", 0) > 0 >= loc.get("alt_end", 0):
            return tr("途中まで見える（食の途中で月が沈む）")
        if loc.get("alt_start", 0) <= 0 < loc.get("alt_end", 0):
            return tr("途中から見える（欠けたまま月が昇る）")
        return tr("一部が見える")

    def _show_eclipses(self):
        if not eclipses.available():
            QMessageBox.warning(self, tr("日食・月食"), tr("日食・月食を探すには PyEphem（python3-ephem）が必要です。"))
            return
        from PySide6.QtWidgets import QApplication
        QApplication.setOverrideCursor(Qt.WaitCursor)
        try:
            v = self.view
            jd0 = astro.jd_now() - 1
            found = eclipses.search(jd0, 15, v.lat, v.lon)
        finally:
            QApplication.restoreOverrideCursor()
        dlg = QDialog(self)
        dlg.setWindowTitle(trx(f"日食・月食（これから15年・観測地 {self.view.place}）"))
        dlg.resize(860, 560)
        lay = QVBoxLayout(dlg)
        only = QCheckBox(trx(f"{self.view.place}で見えるものだけ"))
        lay.addWidget(only)
        tbl = QTableWidget(0, 4)
        tbl.setHorizontalHeaderLabels([tr("日時（最大）"), tr("種類"), trx(f"{self.view.place}での見え方"), tr("食分")])
        tbl.setSelectionBehavior(QAbstractItemView.SelectRows)
        tbl.setSelectionMode(QAbstractItemView.SingleSelection)
        tbl.setEditTriggers(QAbstractItemView.NoEditTriggers)
        tbl.verticalHeader().setVisible(False)
        tbl.horizontalHeader().setSectionResizeMode(2, QHeaderView.Stretch)
        lay.addWidget(tbl, 1)
        note = QLabel(tr("日時は地球全体で食がいちばん大きくなるとき（このパソコンの時刻帯）。時刻は数分ずれることがあります。\n"
                         "「宇宙から見る」は影の様子を宇宙から、「地上から見る」は観測地から空を見上げます（▶ 再生で食が進みます）。\n"
                         "※ 太陽を直接見ると目を傷めます。本物の日食は、必ず日食グラスなどで観察してください。"))
        note.setWordWrap(True)
        lay.addWidget(note)
        rows = []

        def fill():
            tbl.setRowCount(0)
            rows.clear()
            for e in found:
                if only.isChecked() and not e.local.get("visible"):
                    continue
                r = tbl.rowCount()
                tbl.insertRow(r)
                items = [self._local_time(e.jd_max), e.type_ja, self._eclipse_local_text(e),
                         f"{e.magnitude:.3f}"]
                for c, t in enumerate(items):
                    it = QTableWidgetItem(t)
                    if e.local.get("visible"):
                        it.setForeground(QColor(120, 220, 140))
                    tbl.setItem(r, c, it)
                rows.append(e)
            tbl.resizeColumnsToContents()
            if rows:
                tbl.selectRow(0)

        only.toggled.connect(fill)
        fill()
        bb = QDialogButtonBox()
        b_space = bb.addButton(tr("宇宙から見る"), QDialogButtonBox.ActionRole)
        b_ground = bb.addButton(tr("地上から見る"), QDialogButtonBox.ActionRole)
        bb.addButton(tr("閉じる"), QDialogButtonBox.RejectRole)
        bb.rejected.connect(dlg.reject)
        lay.addWidget(bb)

        def current():
            r = tbl.currentRow()
            return rows[r] if 0 <= r < len(rows) else None

        def go(ground):
            e = current()
            if e is None:
                return
            dlg.accept()
            self._go_eclipse(e, ground)

        b_space.clicked.connect(lambda: go(False))
        b_ground.clicked.connect(lambda: go(True))
        tbl.cellDoubleClicked.connect(lambda *_: go(False))
        dlg.exec()

    def _event_table(self, title, headers, rows, note, on_go):
        """天文現象の一覧（表）を出す共通のダイアログ。rows: (セルの文字のリスト, 見えるか, データ)。"""
        dlg = QDialog(self)
        dlg.setWindowTitle(title)
        dlg.resize(900, 560)
        lay = QVBoxLayout(dlg)
        only = QCheckBox(trx(f"{self.view.place}で見えるものだけ"))
        lay.addWidget(only)
        tbl = QTableWidget(0, len(headers))
        tbl.setHorizontalHeaderLabels(headers)
        tbl.setSelectionBehavior(QAbstractItemView.SelectRows)
        tbl.setSelectionMode(QAbstractItemView.SingleSelection)
        tbl.setEditTriggers(QAbstractItemView.NoEditTriggers)
        tbl.verticalHeader().setVisible(False)
        tbl.horizontalHeader().setSectionResizeMode(len(headers) - 1, QHeaderView.Stretch)
        lay.addWidget(tbl, 1)
        lab = QLabel(tr(note))
        lab.setWordWrap(True)
        lay.addWidget(lab)
        shown = []

        def fill():
            tbl.setRowCount(0)
            shown.clear()
            for cells, vis, data in rows:
                if only.isChecked() and not vis:
                    continue
                r = tbl.rowCount()
                tbl.insertRow(r)
                for c, t in enumerate(cells):
                    it = QTableWidgetItem(trx(t))
                    if vis:
                        it.setForeground(QColor(120, 220, 140))
                    tbl.setItem(r, c, it)
                shown.append(data)
            tbl.resizeColumnsToContents()
            if shown:
                tbl.selectRow(0)

        only.toggled.connect(fill)
        fill()
        bb = QDialogButtonBox()
        b_go = bb.addButton(tr("地上から見る"), QDialogButtonBox.ActionRole)
        bb.addButton(tr("閉じる"), QDialogButtonBox.RejectRole)
        bb.rejected.connect(dlg.reject)
        lay.addWidget(bb)

        def go(*_):
            r = tbl.currentRow()
            if 0 <= r < len(shown):
                dlg.accept()
                on_go(shown[r])

        b_go.clicked.connect(go)
        tbl.cellDoubleClicked.connect(go)
        dlg.exec()

    def _ground_at(self, jd):
        v = self.view
        self.stop_tour()
        v.paused = True
        v.set_jd(jd)
        if not self.btn_ground.isChecked():
            self.btn_ground.setChecked(True)
        self.cb_speed.setCurrentIndex(1)       # 1分/秒
        self._apply_speed()
        v.paused = True
        self._refresh_ui()

    def _show_showers(self):
        if not evt.available():
            QMessageBox.warning(self, tr("流星群"), tr("PyEphem（python3-ephem）が必要です。"))
            return
        v = self.view
        nights = evt.shower_nights(astro.jd_now() - 2, 370, v.lat, v.lon)
        rows = []
        for n in nights:
            sh = n.shower
            best = self._local_time(n.jd_best, True) if n.jd_best else "―"
            cells = [self._local_time(n.jd_peak), sh.name, best,
                     f"約{n.rate:.0f} 個/時" if n.jd_best else "―", n.condition,
                     f"放射点の高さ {n.radiant_alt:.0f}°・月 {n.moon_illum * 100:.0f}%・{sh.parent}"]
            rows.append((cells, n.jd_best is not None and n.rate >= 3, n))

        def go(n):
            jd = n.jd_best or n.jd_peak
            self._ground_at(jd)
            ok = v.look_dir(evt.radiant_vector(n.shower), fov=100.0)
            self.act_meteor.setChecked(True)
            msg = (f"{n.shower.name} (meteors shown about {v.METEOR_BOOST:.0f}× more often than real)" if EN_MODE else
                   f"{n.shower.name}：{n.shower.note}（流れる数は実際の約{v.METEOR_BOOST:.0f}倍に増やしています）")
            if not ok:
                msg = tr("このとき放射点は地平線の下です。") + msg
            self.statusBar().showMessage(trx(msg), 20000)

        self._event_table(
            trx(f"流星群（これから1年・観測地 {v.place}）"),
            [tr("極大"), tr("流星群"), tr("見やすい時刻"), tr("見える数の目安"), tr("月明かり"), tr("くわしく")], rows,
            "見える数の目安は、空の暗い場所で放射点が高いときの1時間あたりの数です（町なかではもっと少なくなります）。"
            "流星は放射点から四方へ飛ぶので、放射点だけでなく空全体を広く見るのがこつです。\n"
            "「地上から見る」で、見やすい時刻の空に流星が流れます（流れる数は実際の約10倍に増やしています）。",
            go)

    def _download_tle(self, then=None):
        if getattr(self, "_tle_dl", None):
            return
        dl = artsat.TleDownloader()
        dlg = QProgressDialog(tr("人工衛星のデータをダウンロードしています…"), None, 0, 0, self)
        dlg.setWindowTitle(tr("人工衛星のデータ"))
        dlg.setWindowModality(Qt.WindowModal)
        dlg.setMinimumDuration(0)
        timer = QTimer(self)

        def poll():
            if not dl.done:
                return
            timer.stop()
            dlg.close()
            self._tle_dl = None
            if dl.ok:
                self.view.reload_artsats()
                QMessageBox.information(self, tr("人工衛星のデータ"),
                                        f"{dl.count} 個の人工衛星の軌道を読み込みました（CelesTrak）。\n\n"
                                        "地球に近づくと、国際宇宙ステーションなどが地球のまわりを回ります。"
                                        "地上モードでは、空を横切る衛星が見えます。\n"
                                        "軌道のデータは数日で古くなるので、ときどきダウンロードし直してください。")
                if then:
                    then()
            else:
                QMessageBox.warning(self, tr("人工衛星のデータ"), tr("ダウンロードできませんでした。\n\n") + dl.message)

        timer.timeout.connect(poll)
        self._tle_dl = (dl, timer, dlg)
        dl.start()
        timer.start(200)

    def _show_passes(self):
        v = self.view
        if not artsat.available():
            QMessageBox.warning(self, tr("人工衛星"), tr("PyEphem（python3-ephem）が必要です。"))
            return
        if not v.artsats:
            ans = QMessageBox.question(self, tr("人工衛星"), "人工衛星のデータ（CelesTrak の軌道要素、数十KB）を"
                                       "ダウンロードしますか？")
            if ans == QMessageBox.Yes:
                self._download_tle(then=self._show_passes)
            return
        jd = astro.jd_now()
        age = artsat.tle_age_days(v.artsats, jd)
        from PySide6.QtWidgets import QApplication
        QApplication.setOverrideCursor(Qt.WaitCursor)
        try:
            ps = []
            for s in v.artsats:
                if s.featured:
                    ps += artsat.passes(s, v.lat, v.lon, jd - 0.02, 10)
        finally:
            QApplication.restoreOverrideCursor()
        ps.sort(key=lambda p: p.rise_jd)
        dirs = [tr("北"), tr("北北東"), tr("北東"), tr("東北東"), tr("東"), tr("東南東"), tr("南東"), tr("南南東"),
                tr("南"), tr("南南西"), tr("南西"), tr("西南西"), tr("西"), tr("西北西"), tr("北西"), tr("北北西")]

        def d(az):
            return dirs[int((az + 11.25) // 22.5) % 16]

        rows = []
        for p in ps:
            cells = [self._local_time(p.rise_jd), p.sat.ja,
                     f"{d(p.rise_az)} → 最大 {p.max_alt:.0f}°（{d(p.max_az)}・{self._local_time(p.max_jd, False)}）"
                     f" → {d(p.set_az)}",
                     tr("見える（夜空で太陽の光を反射）") if p.visible else tr("見えない（昼間か、地球の影の中）")]
            rows.append((cells, p.visible, p))

        def go(p):
            self._ground_at(p.max_jd - 1.5 / 1440)
            a, z = math.radians(p.max_alt), math.radians(p.max_az)
            off, zen, north, east = astro.observer_frame(v.jd, v.lat, v.lon)
            v.look_dir(zen * math.sin(a) + (north * math.cos(z) + east * math.sin(z)) * math.cos(a), fov=110.0)
            self.cb_speed.setCurrentIndex(0)      # 実時間で動かす
            self._apply_speed()
            v.paused = False
            self._refresh_ui()

        note = ("高度10°より高く昇るときの一覧です（これから10日）。「見える」は、空が暗く、衛星に太陽の光が当たっているときで、"
                "明るい星のような光がゆっくり空を横切ります。「地上から見る」で、そのときの空を実時間で見られます。")
        if age > 7:
            note = (f"⚠ Orbit data is {age:.0f} days old. Download it again from the File menu.\n" if EN_MODE else
                    f"⚠ 軌道のデータが {age:.0f} 日前のもので古くなっています。「ファイル」からダウンロードし直してください。\n") + tr(note)
        self._event_table(trx(f"人工衛星が見える時刻（これから10日・観測地 {v.place}）"),
                          [tr("昇る時刻"), tr("衛星"), tr("動き（方角）"), tr("見え方")], rows, note, go)

    def _show_events(self):
        if not evt.available():
            QMessageBox.warning(self, tr("惑星・月の接近"), tr("PyEphem（python3-ephem）が必要です。"))
            return
        from PySide6.QtWidgets import QApplication
        QApplication.setOverrideCursor(Qt.WaitCursor)
        try:
            v = self.view
            events = evt.find_events(astro.jd_now() - 1, 400, v.lat, v.lon)
        finally:
            QApplication.restoreOverrideCursor()
        rows = []
        for e in events:
            loc = e.local
            if loc.get("jd"):
                when = self._local_time(loc["jd"], True)
                look = f"{when}ごろ 高さ {loc['alt']:.0f}°" if loc["visible"] else tr("見えにくい（低い・明るい空）")
            else:
                look = tr("見えない")
            det = e.detail
            if "sep" in loc:
                det += f"／{v.place}から {loc['sep']:.1f}°"
            if e.kind == "occult":
                det += tr("（地球のどこかで月が惑星をかくす惑星食）")
            rows.append(([self._local_time(e.jd), e.title, look, det], bool(loc.get("visible")), e))

        def go(e):
            jd = e.local.get("jd") or e.jd
            self._ground_at(jd)
            pos = [v.display_pos(k) for k in e.keys]
            off, _z, _n, _e = astro.observer_frame(v.jd, v.lat, v.lon)
            eye = v.positions["earth"] + off
            dirs = [(p - eye) / np.linalg.norm(p - eye) for p in pos]
            mid = sum(dirs) / len(dirs)
            sep = e.local.get("sep", e.sep)       # 観測地から見た離れ角（月は場所で変わる）
            fov = {"conj": max(6.0, sep * 2.5), "occult": max(4.0, sep * 2.5), "opposition": 40.0,
                   "elong": 50.0}[e.kind]
            ok = v.look_dir(mid / np.linalg.norm(mid), fov=fov)
            if not ok:
                self.statusBar().showMessage(tr("このとき、観測地では地平線の下です"), 8000)

        self._event_table(
            trx(f"惑星・月の接近と見ごろ（これから1年あまり・観測地 {v.place}）"),
            [tr("日時"), tr("できごと"), trx(f"{v.place}での見やすい時刻"), tr("くわしく")], rows,
            "日時は、いちばん近づくとき（地球の中心から見た計算）です。月は地球に近いので、見る場所によって近づき方が"
            "少し変わります。「地上から見る」は、観測地で日の入り後・日の出前の、いちばん高く見える時刻の空を出します。",
            go)

    def _go_eclipse(self, e, ground):
        v = self.view
        self.stop_tour()
        self.sl_mag.setValue(0)              # 実際の大きさでないと、影の位置関係が正しくならない
        v.paused = True
        if ground:
            jd = e.local.get("jd", e.jd_max) if e.kind == "solar" else e.jd_max
            v.set_jd(jd)
            if not self.btn_ground.isChecked():
                self.btn_ground.setChecked(True)
            self.cb_speed.setCurrentIndex(1)     # 1分/秒
            v.paused = True
            ok = v.look_at("sun" if e.kind == "solar" else "moon")
            v.g_fov = 3.0
            if not ok:
                self.statusBar().showMessage(tr("そのとき、観測地では地平線の下です（地面を消すと見えます）"), 8000)
        else:
            v.set_jd(e.jd_max)
            if self.btn_ground.isChecked():
                self.btn_ground.setChecked(False)
            self.cb_speed.setCurrentIndex(2)     # 10分/秒
            P = v.positions
            if e.kind == "solar":
                # 太陽の側から地球を見る（地球の昼の面に落ちた月の影が見える）
                d = P["sun"] - P["earth"]
                v.fly_to("earth", 0.00012, view_dir=d / np.linalg.norm(d))
            else:
                # 地球と月のあいだから、地球の影に入った月を見る
                d = P["earth"] - P["moon"]
                d = d / np.linalg.norm(d)
                side = np.cross(d, [0.0, 0.0, 1.0])
                side /= np.linalg.norm(side)
                v.fly_to("moon", 0.00006, view_dir=(d * 0.97 + side * 0.25))
        self._apply_speed()
        v.paused = True
        self._refresh_ui()
        v.update()

    # ---------------------------------------------------------- 解説パネル

    def _build_panel(self):
        self.panel = QDockWidget(tr("解説"), self)
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
        key = ("star", v.selected_star) if v.selected_star >= 0 else \
            ("con", v.selected_con) if v.selected_con >= 0 else ("body", v.target, v.ground)
        if key == self._panel_key and not force:
            return
        self._panel_key = key
        html = ["<div style='font-size:11pt; line-height:150%'>"]
        if v.selected_star >= 0:
            i = v.selected_star
            html.append(f"<h2>★ {v.stars.short_name(i)}</h2>")
            html.append("<p>" + v.stars.describe(i).replace("　｜　", "<br>") + "</p>")
            html.append(f"<p>{STAR_TEXT}</p>")
        elif v.selected_con >= 0:
            from . import constellation_info as ci
            c = v.stars.constellations[v.selected_con]
            season, txt = ci.text(c.id)
            html.append(f"<h2>{c.name}</h2>")
            if season:
                html.append(f"<p style='color:#9ab'>見ごろ：{season}</p>")
            html.append(f"<p>{txt}</p>")
            stars = sorted([i for i in range(min(v.stars.count, 3000)) if str(v.stars.con[i]) == c.id],
                           key=lambda i: v.stars.mag[i])[:5]
            if stars:
                html.append(tr("<h3>おもな星</h3><ul>"))
                for i in stars:
                    html.append(f"<li>{v.stars.short_name(i)}（{v.stars.mag[i]:.1f}等）</li>")
                html.append("</ul>")
            html.append(tr("<p style='color:#888'>星座の名前をダブルクリックすると選べます。ほかの場所をダブルクリックすると選択が外れます。</p>"))
        elif v.ground:
            html.append(tr("<h2>地上から見た空</h2>"))
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
            elif t in crafts.BY_KEY:
                sc = crafts.BY_KEY[t]
                html.append(f"<h2>🛰 {sc.name}</h2><p>{sc.note}</p><h3>おもなできごと</h3><ul>")
                for jd_e, txt in sc.events:
                    d = astro.datetime_from_jd(jd_e)
                    mark = "✔ " if jd_e <= v.jd else ""
                    html.append(f"<li>{mark}{d.year}年{d.month}月{d.day}日　{txt}</li>")
                html.append("</ul><p style='color:#888'>" + self.status_info.text().replace("　｜　", "<br>") + "</p>")
            elif v.is_artsat(t):
                sa = v.artsats[int(t[2:])]
                html.append(f"<h2>{sa.ja}</h2>")
                html.append(f"<p>高度 約{artsat.height_km(sa, v.jd):,.0f} km<br>地球を1周 約{1440 / sa.rev_per_day:.0f} 分"
                            f"<br>1日に {sa.rev_per_day:.1f} 周</p>")
                html.append(f"<p>{sa.note}</p>")
                age = v.jd - sa.epoch_jd
                html.append(f"<p style='color:#888'>位置は CelesTrak の軌道要素（{abs(age):.0f}日{tr('前') if age >= 0 else tr('後')}"
                            "のもの）から計算しています。データが古くなるほど、位置はずれていきます。</p>")
            elif v.is_neb(t):
                n = neb.NEBULAE[int(t[2:])]
                html.append(f"<h2>{n.name}</h2>")
                html.append("<p>" + "<br>".join(neb.describe(n)) + "</p>")
                if n.note:
                    html.append(f"<p>{n.note}</p>")
                html.append(f"<p><b>{neb.TYPE_JA[n.type]}</b>：{neb.TYPE_NOTE[n.type]}</p>")
                if v.has_photo(t) and v.show_photos:
                    html.append("<p style='color:#888'>位置・見かけの大きさは OpenNGC、距離は代表的な値の目安です。"
                                "地球の側から見ると本物の写真、横や裏から見ると粒を並べた模式図になります。<br>"
                                f"{dsoimages.CREDIT}</p>")
                else:
                    html.append("<p style='color:#888'>位置・見かけの大きさは OpenNGC、距離は代表的な値の目安です。"
                                "形は、見かけの大きさと向きに合わせて粒を並べた模式図です（本物の写真ではありません）。</p>")
            elif v.is_exo(t):
                i = int(t[2:])
                sy = v.exo.systems[i]
                html.append(f"<h2>{sy['host']}</h2>")
                html.append("<p>" + "<br>".join(v.exo.describe_system(i)) + "</p>")
                for pl in sy["planets"]:
                    hz = v.exo.in_hz(pl)
                    col = "#7deb96" if hz else "#ddd"
                    html.append(f"<p><b style='color:{col}'>{pl['name']}</b><br>{exo.describe_planet(pl)}"
                                + ("<br><span style='color:#7deb96'>ハビタブルゾーン（水が液体でいられるかもしれない"
                                   "範囲）の中にあります</span>" if hz else "") + "</p>")
                methods = {pl["method"] for pl in sy["planets"]}
                for m in methods:
                    if m in exo.METHOD_NOTE:
                        html.append(f"<p><b>{exo.METHOD_JA[m]}</b>：{exo.METHOD_NOTE[m]}</p>")
                html.append("<p style='color:#888'>データは NASA Exoplanet Archive によります。惑星の軌道の向きと、"
                            "軌道上の位置は模式です（地球から見て真横を向いているように描いています）。"
                            "緑の軌道はハビタブルゾーンの中の惑星です。</p>")
            elif v.is_minor(t):
                i = int(t[3:])
                html.append(f"<h2>{v.mp.name(i)}</h2>")
                html.append("<p>" + "<br>".join(v.mp.describe(i, v.jd)) + "</p>")
                html.append(f"<p>{v.mp.kind_note(i)}</p>")
                html.append("<p style='color:#888'>軌道の要素は NASA JPL の表によります。位置は惑星の引力を"
                            "入れていない、おおよそのものです。直径は明るさからの推定です。</p>")
            elif t == "u:cmb":
                html.append(tr("<h2>観測できる宇宙の果て</h2>"))
                html.append(f"<p>{text_for('u:cmb')}</p>")
                html.append("<p style='color:#888'>" + self.status_info.text().replace("　｜　", "<br>") + "</p>")
            else:
                name = gx.BY_KEY[t].name if t in gx.BY_KEY else BY_KEY[t].name
                html.append(f"<h2>{name}</h2>")
                txt = text_for(t)
                if txt:
                    html.append(f"<p>{txt}</p>")
                html.append("<p style='color:#888'>" + self.status_info.text().replace("　｜　", "<br>") + "</p>")
                if v.has_photo(t) and v.show_photos:
                    html.append("<p style='color:#888'>地球の側から見ると本物の写真、横や裏から見ると模式図になります。<br>"
                                f"{dsoimages.CREDIT}</p>")
        html.append("</div>")
        if EN_MODE:
            # 数字や単位の入った短い行だけ英語にする（解説の文章は、いまは日本語のまま）
            html = [trx(h) if (len(h) < 160 or "<br>" in h) and "。" not in h else h for h in html]
            html.append("<p style='color:#888'>(Detailed descriptions are currently available in Japanese only.)</p>")
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
        for text, step in ((tr("◀ 前"), -1), (tr("次 ▶"), +1)):
            b = QPushButton(text)
            b.clicked.connect(lambda _=False, d=step: self._tour_go(d))
            lay.addWidget(b)
        b = QPushButton(tr("終了"))
        b.clicked.connect(self.stop_tour)
        lay.addWidget(b)
        self.tour_bar.hide()

    def start_tour(self, tid):
        for t, title, fn in tours.TOURS:
            if t == tid:
                steps = fn(self.view) if tid in ("tonight", "asteroids", "exoplanets") else fn()
                self._tour = {"title": title, "steps": steps, "i": -1}
                self.tour_bar.show()
                self._tour_go(+1)
                return

    def stop_tour(self):
        if not self._tour:
            return
        self._tour = None
        self._tour_deadline = None
        self.tour_bar.hide()
        if self._rec_tour and self.btn_rec.isChecked():
            self._rec_tour = False
            self.btn_rec.setChecked(False)

    def _tour_check(self):
        if self._tour and self._tour_deadline is not None and self.view.now() >= self._tour_deadline:
            self._tour_deadline = None
            self._tour_go(+1)

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
            if "jd" in st.extra:
                v.set_jd(st.extra["jd"])
            if "speed_index" in st.extra:      # 惑星が回る様子を見せる場面では、時間を進める
                self.cb_speed.setCurrentIndex(st.extra["speed_index"])
                v.paused = False
            dist = st.dist
            if dist is None and st.dist_mult:
                dist = v._default_dist(st.target) * st.dist_mult
            v.fly_to(st.target, dist, st.pitch)
        self.tour_label.setText(st.text)
        self.tour_count.setText(f"{tr['title']}　{i + 1} / {len(tr['steps'])}")
        fly = v._fly["dur"] if v._fly else 0.0
        self._tour_deadline = v.now() + st.seconds + fly
        self._update_panel(force=True)
        v.update()

    # ---------------------------------------------------------- 地上モード

    def _on_ground(self, on):
        self.view.set_ground(on)
        self.btn_all.setEnabled(not on)
        self.sl_mag.setEnabled(not on)
        self.btn_ground.setText(tr("🚀 宇宙へ戻る") if on else tr("🔭 地上から見る"))
        # 1日/秒より速いと空がぐるぐる回って見づらいので、地上では少しゆっくりにする
        if on and self.cb_speed.currentIndex() > 3:
            self.cb_speed.setCurrentIndex(1)
        self.view.setFocus()

    def _restore_place(self):
        name = self.settings.value("place/name", tr("大阪"))
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
        dlg.setWindowTitle(tr("観測地"))
        form = QFormLayout(dlg)
        ed_name = QLineEdit(tr("観測地"))
        sp_lat = QDoubleSpinBox()
        sp_lat.setRange(-90, 90)
        sp_lat.setDecimals(3)
        sp_lat.setValue(self.view.lat)
        sp_lat.setSuffix(tr("°（北緯が＋）"))
        sp_lon = QDoubleSpinBox()
        sp_lon.setRange(-180, 180)
        sp_lon.setDecimals(3)
        sp_lon.setValue(self.view.lon)
        sp_lon.setSuffix(tr("°（東経が＋）"))
        form.addRow(tr("名前"), ed_name)
        form.addRow(tr("緯度"), sp_lat)
        form.addRow(tr("経度"), sp_lon)
        bb = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        bb.accepted.connect(dlg.accept)
        bb.rejected.connect(dlg.reject)
        form.addRow(bb)
        if dlg.exec() != QDialog.Accepted:
            return None
        return (ed_name.text().strip() or tr("観測地"), sp_lat.value(), sp_lon.value())

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
        self.lb_stars.setText(trx(f"{lim:.1f}等まで（{n:,}個）"))
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
        self.lb_mag.setText(tr("×1（実寸）") if m == 1.0 else f"×{m:,.0f}")

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
        self.btn_play.setText(tr("▶ 再生") if v.paused else tr("⏸ 停止"))
        if not self.dt_edit.hasFocus():
            unix = (v.jd - 2440587.5) * 86400.0
            self.dt_edit.blockSignals(True)
            self.dt_edit.setDateTime(QDateTime.fromSecsSinceEpoch(int(round(unix)), Qt.LocalTime))
            self.dt_edit.blockSignals(False)

        if v.selected_con >= 0 and v.selected_star < 0:
            from . import constellation_info as ci
            c = v.stars.constellations[v.selected_con]
            self._set_status(f"<b>{c.name}</b>　｜　見ごろ：{ci.text(c.id)[0]}")
            self._refresh_warn(v)
            return
        elif v.selected_star >= 0:
            self._set_status("★ " + v.stars.describe(v.selected_star))
            self._refresh_warn(v)
            return
        key = v.target
        if key in crafts.BY_KEY:
            sc = crafts.BY_KEY[key]
            p = crafts.position(sc, v.jd)
            parts = [f"<b>{sc.name}</b>", tr("探査機")]
            if p is None:
                t0, _t1 = crafts.span(sc)
                parts.append(tr("打ち上げ前") if v.jd < t0 else tr("この画面で表示する航路はここまで"))
            else:
                parts += [f"太陽から {_fmt_dist(np.linalg.norm(p))}",
                          f"地球から {_fmt_dist(np.linalg.norm(p - v.positions['earth']))}",
                          f"最近のできごと: {crafts.last_event(sc, v.jd)}"]
            parts.append(tr("※ 航路はおおよそ"))
            self._set_status("　｜　".join(parts))
            self._refresh_warn(v)
            return
        if v.is_artsat(key):
            sa = v.artsats[int(key[2:])]
            parts = [f"<b>{sa.ja}</b>", f"高度 約{artsat.height_km(sa, v.jd):,.0f} km",
                     f"1周 約{1440 / sa.rev_per_day:.0f} 分", f"視点の距離 {_fmt_dist(v.dist)}"]
            self._set_status("　｜　".join(parts))
            self._refresh_warn(v)
            return
        if v.is_neb(key):
            n = neb.NEBULAE[int(key[2:])]
            photo = v.has_photo(key) and v.show_photos
            parts = [f"<b>{n.name}</b>"] + neb.describe(n) + [tr("写真（DSS2）と模式図") if photo else tr("※ 形は模式図")]
            parts.append(f"視点の距離 {_fmt_dist(v.dist)}")
            self._set_status("　｜　".join(parts))
            self._refresh_warn(v)
            return
        if v.is_exo(key):
            i = int(key[2:])
            parts = [f"<b>{v.exo.name(i)}</b>"] + v.exo.describe_system(i)
            surface = v.dist - v.display_radius(key)
            parts.append(f"視点の距離 {_fmt_dist(max(surface, 0.0))}（恒星から）")
            self._set_status("　｜　".join(parts))
            self._refresh_warn(v)
            return
        if v.is_minor(key):
            i = int(key[3:])
            p = v.mp.position(i, v.jd)
            parts = [f"<b>{v.mp.name(i)}</b>"] + v.mp.describe(i, v.jd)[:2] + [
                f"太陽から {_fmt_dist(np.linalg.norm(p))}",
                f"地球から {_fmt_dist(np.linalg.norm(p - v.positions['earth']))}", tr("※ 位置はおおよそ")]
            self._set_status("　｜　".join(parts))
            self._refresh_warn(v)
            return
        if key == "u:cmb":
            q = f"クエーサー {v.qso_count:,} 個を表示中" if v.qso_count else tr("クエーサーのデータは未ダウンロード（ファイルメニュー）")
            self._set_status("<b>観測できる宇宙の果て</b>　｜　宇宙マイクロ波背景放射まで 約"
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
                parts.append(tr("夜"))
            if key in BY_KEY and key not in ("earth",):
                alt, az = v.ground_altaz(key)
                where = f"高度 {alt:.1f}°・方位 {az:.0f}°" if alt > 0 else tr("地平線の下")
                parts.append(f"{BY_KEY[key].name}: {where}")
            self._set_status("　｜　".join(parts))
            self._refresh_warn(v)
            return
        if key.startswith("c:"):
            self._set_status(v.gcat.describe(int(key[2:])) + tr("　｜　視点の距離 ")
                                     + format_length(v.dist))
            self._refresh_warn(v)
            return
        if key in gx.BY_KEY:
            desc = gx.describe(gx.BY_KEY[key])
            if v.has_photo(key) and v.show_photos:
                desc = desc.replace("※ 形は模式図", "写真（DSS2）と模式図")
            self._set_status(desc + tr("　｜　視点の距離 ")
                                     + format_length(v.dist))
            self._refresh_warn(v)
            return
        b = BY_KEY[key]
        if key in sbs.BY_KEY or key == "pluto":
            sb = sbs.BY_KEY.get(key)
            kind = sbs.KIND_JA[sb.kind] if sb else tr("準惑星")
            dia = b.radius_km * 2
            parts = [f"<b>{b.name}</b>", kind,
                     f"直径 約{dia:,.0f} km" if dia >= 10 else f"直径 約{dia * 1000:,.0f} m",
                     f"太陽から {_fmt_dist(np.linalg.norm(v.positions[key]))}",
                     f"地球から {_fmt_dist(np.linalg.norm(v.positions[key] - v.positions['earth']))}"]
            if sb and sb.note:
                parts.append(sb.note)
            parts.append(tr("※ 位置はおおよそ"))
            self._set_status("　｜　".join(parts))
            self._refresh_warn(v)
            return
        parts = [f"<b>{b.name}</b>",
                 f"半径 {b.radius_km:,.0f} km" if b.radius_km >= 10 else f"半径 約{b.radius_km:,.1f} km"]
        if b.parent not in ("sun", ""):
            par = BY_KEY[b.parent]
            d = np.linalg.norm(v.positions[key] - v.positions[b.parent]) * astro.AU_KM
            parts.append(f"{par.name}の衛星（{par.name}から {d / 1e4:,.1f} 万km）")
            st = sats.BY_KEY.get(key)
            if st is not None:
                per = f"公転周期 {st.period:,.1f} 日" if st.period >= 2 else f"公転周期 {st.period * 24:,.1f} 時間"
                if st.i > 90:
                    per += tr("（逆行）")
                parts.append(per)
        if key != "sun":
            parts.append(f"太陽から {_fmt_dist(np.linalg.norm(v.positions[key])):s}")
        if key not in ("earth", "sun"):
            parts.append(f"地球から {_fmt_dist(np.linalg.norm(v.positions[key] - v.positions['earth']))}")
        if key == "sun":
            parts.append(f"地球から {_fmt_dist(np.linalg.norm(v.positions['earth']))}")
        surface = v.dist - v.display_radius(key)
        parts.append(f"視点の距離 {_fmt_dist(max(surface, 0.0))}（表面から）")
        if key in sats.BY_KEY and not sats.uses_ephem(key):
            parts.append(tr("※ 位置はおおよそ"))
        self._set_status("　｜　".join(parts))
        self._refresh_warn(v)

    def _refresh_warn(self, v):
        if not astro.elements_valid(v.jd):
            self.status_warn.setText(trx(f"※ {astro.VALID_FROM_YEAR}〜{astro.VALID_TO_YEAR}年の範囲外のため、惑星の位置は概算です"))
        else:
            self.status_warn.setText("")

    # ---------------------------------------------------------- 画像のダウンロード

    def _maybe_offer_download(self):
        if not textures.missing_textures() or self.settings.value("asked_textures", False, type=bool):
            return
        self.settings.setValue("asked_textures", True)
        ans = QMessageBox.question(
            self, tr("惑星の画像"),
            "惑星の表面の画像（Solar System Scope 提供、約10MB）をダウンロードしますか？\n\n"
            "ダウンロードしない場合は、簡易的な模様で表示します。\n"
            "あとからでも「ファイル」メニューからダウンロードできます。")
        if ans == QMessageBox.Yes:
            self._start_download()

    def _start_download(self, force=False):
        files = textures.missing_textures()
        if not files and force:
            ans = QMessageBox.question(self, tr("惑星の画像"),
                                       tr("画像はすべてダウンロード済みです。もう一度ダウンロードしますか？"))
            if ans != QMessageBox.Yes:
                return
            from .bodies import all_texture_files
            files = all_texture_files()
        if not files or self._download:
            return
        dlg = QProgressDialog(tr("画像をダウンロードしています…"), tr("キャンセル"), 0, len(files), self)
        dlg.setWindowTitle(tr("惑星の画像"))
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
                QMessageBox.warning(self, tr("惑星の画像"),
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
            self, tr("そらみ窓について"),
            f"<h3>そらみ窓（Soramado） v{__version__}</h3>"
            "<p>太陽系から宇宙の果てまでを旅する、Ubuntu 用の宇宙シミュレーター。</p>"
            "<p>作者: 飯田顕治 ／ ライセンス: MIT</p>"
            "<p><b>使用しているデータ</b><br>"
            "・惑星の軌道: NASA JPL「Approximate Positions of the Planets」<br>"
            "・月の位置・日食・月食・流星群・惑星の接近: PyEphem<br>"
            "・衛星の位置: PyEphem（おもな衛星）、NASA JPL Horizons の軌道要素（小さな衛星・トリトン）<br>"
            "・小天体の軌道: 冥王星は NASA JPL、その他は Wikipedia 各記事の軌道要素（JPL などが出典）<br>"
            "・探査機の航路: 惑星・小惑星を通過した日付から計算したおおよその航路<br>"
            "・天体の大きさ・自転軸: IAU WGCCRE 報告（2015年）<br>"
            "・恒星: HYG データベース v4.1（CC BY-SA 4.0）<br>"
            "・星座線・星座名: d3-celestial（© Olaf Frohn, BSD 3-Clause）<br>"
            "・銀河: 位置・距離・大きさは文献のおおよその値。形は粒子で作った模式図<br>"
            "・銀河カタログ（約1万個）: OpenNGC（CC BY-SA 4.0）。距離は後退速度から推定<br>"
            "・星雲・星団: OpenNGC（CC BY-SA 4.0）の位置・大きさ。形は模式図<br>"
            "・星雲・銀河の写真（ダウンロードしたとき）: DSS2 color（STScI・CDS、ESA ESASky から）<br>"
            "・天の川の写真（ダウンロードしたとき）: ESA/Gaia/DPAC の Gaia DR2 から CDS が作った全天地図（CC BY-SA 3.0 IGO）<br>"
            "・流星群: 国際流星機構（IMO）の流星群カレンダーの代表値<br>"
            "・クエーサー（ダウンロードした場合）: SDSS DR16Q（Lyke et al. 2020）、VizieR VII/289<br>"
            "・小惑星・彗星（ダウンロードした場合）: NASA JPL Solar System Dynamics の軌道要素の表<br>"
            "・系外惑星（ダウンロードした場合）: NASA Exoplanet Archive<br>"
            "・人工衛星（ダウンロードした場合）: CelesTrak の軌道要素（TLE）<br>"
            "・宇宙マイクロ波背景放射: 計算で作った模式図（本物の観測地図ではありません）<br>"
            "・惑星の画像（ダウンロードした場合）: "
            "<a href='https://www.solarsystemscope.com/textures/'>Solar System Scope</a>"
            "（CC BY 4.0）</p>"
            "<p>このソフトは国立天文台の Mitaka とは関係のない独自のソフトです。</p>")

    def closeEvent(self, e):
        if self.btn_rec.isChecked():
            self.btn_rec.setChecked(False)
        self._save_settings()
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
