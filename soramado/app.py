"""メインウィンドウ。"""

from __future__ import annotations

import math
import time
from datetime import datetime, timedelta
from pathlib import Path

import numpy as np
from PySide6.QtCore import QCoreApplication, QDateTime, QSettings, Qt, QTimer, QUrl
from PySide6.QtGui import QAction, QColor, QDesktopServices, QIcon, QImage, QKeySequence
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
from . import tonight
from . import landscape
from .constellation_info import INFO as CON_INFO
from . import satellites as sats
from . import scope as scopes
from . import terrain
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
    (tr("1恒星日ずつ（星を止める）"), "sidereal"),
    (tr("1太陽日ずつ（太陽を止める）"), "solar"),
]
SIDEREAL_DAY = 0.99726956633       # 1恒星日 [日]（23時間56分4.1秒）
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
<tr><td><b>Ctrl+L</b></td><td>黄道（太陽の通り道）の線を出す・消す</td></tr>
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
        if str(self.settings.value("ui/tonight_on_start", "false")).lower() in ("true", "1"):
            QTimer.singleShot(1500, lambda: self._show_tonight())

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
        self._ground_instant = False
        tb.addWidget(self.btn_ground)
        self.btn_airless = QPushButton(tr("🌑 大気なし"))
        self.btn_airless.setCheckable(True)
        self.btn_airless.setEnabled(False)
        self.btn_airless.setToolTip(tr("地上から見るとき、空気も地面もないものとして見ます（昼でも星が見え、地平線の下も見える）"))
        self.btn_airless.toggled.connect(self._on_airless)
        tb.addWidget(self.btn_airless)
        self.btn_ecl = QPushButton(tr("〰 黄道"))
        self.btn_ecl.setCheckable(True)
        self.btn_ecl.setToolTip(tr("黄道（太陽の通り道）を表示します。惑星はこの線の近くを動きます"))
        tb.addWidget(self.btn_ecl)
        self.btn_scope = QPushButton(tr("◎ 望遠鏡"))
        self.btn_scope.setCheckable(True)
        self.btn_scope.setToolTip(tr("地上から、天体望遠鏡や双眼鏡でのぞいたように見ます"))
        tb.addWidget(self.btn_scope)
        self._build_scope_bar()
        self.cb_body = QComboBox()
        for key, label in (("earth", "🌏 地球"), ("moon", "🌕 月"), ("mars", "🔴 火星")):
            self.cb_body.addItem(tr(label), key)
        self.cb_body.setToolTip(tr("地上モードで立つ天体（月や火星にも降り立てます）"))
        fm = self.cb_body.fontMetrics()
        widest = max(fm.horizontalAdvance(self.cb_body.itemText(i)) for i in range(self.cb_body.count()))
        self.cb_body.setMinimumWidth(widest + fm.horizontalAdvance("M") * 2 + 40)   # 絵文字の幅は少なめに測られるので余白を足す
        self.cb_body.activated.connect(lambda i: self._set_body(self.cb_body.itemData(i)))
        tb.addWidget(self.cb_body)
        self.cb_place = QComboBox()
        self._fill_places("earth")
        self.cb_place.activated.connect(self._on_place)
        tb.addWidget(self.cb_place)
        self.view.landRequest.connect(self._land_request)
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
        from PySide6.QtWidgets import QSpinBox
        self.sp_step = QSpinBox()
        self.sp_step.setRange(1, 100)
        self.sp_step.setValue(10)
        self.sp_step.setPrefix(tr("1秒に "))
        self.sp_step.setSuffix(tr(" 日"))
        self.sp_step.setToolTip(tr("コマ送りで、1秒に何日分進めるか"))
        self.sp_step.valueChanged.connect(self._apply_speed)
        self.act_sp_step = tb.addWidget(self.sp_step)
        self.act_sp_step.setVisible(False)

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
        for body in ("moon", "mars"):
            nm = terrain.body_name(body)
            a = QAction(f"Download the {nm} terrain (elevation data)…" if EN_MODE else f"{nm}の地形（標高のデータ）をダウンロード…", self)
            a.triggered.connect(lambda _c=False, b=body: self._download_terrain_menu(b))
            m_file.addAction(a)
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
        self.act_atm = self._toggle(m_view, tr("大気の効果（地上モード：浮き上がり・減光・空の色）"), "show_atmosphere")
        self.act_lift = self._toggle(m_view, tr("地上と宇宙を行き来するとき、飛び立つ・着陸する様子を見せる"), "show_lift")
        m_lp = m_view.addMenu(tr("空の暗さ（光害）"))
        from PySide6.QtGui import QActionGroup
        self._lp_grp = QActionGroup(self)
        self._lp_acts = {}
        from .view import LIGHT_POLLUTION
        for b, ja, en in LIGHT_POLLUTION:
            a = QAction(en if EN_MODE else ja, self, checkable=True)
            a.setChecked(b == self.view.bortle)
            a.triggered.connect(lambda _=False, b=b: self._set_bortle(b))
            self._lp_grp.addAction(a)
            m_lp.addAction(a)
            self._lp_acts[b] = a
        self.act_trails = self._toggle(m_view, tr("惑星と月の通った跡（地上モード）"), "show_trails")
        m_lines = m_view.addMenu(tr("空の線"))
        self.act_ecl = self._toggle(m_lines, tr("黄道（太陽の通り道・各月の太陽の位置）"), "show_ecliptic")
        self.act_equ = self._toggle(m_lines, tr("天の赤道"), "show_equator")
        self.act_mer = self._toggle(m_lines, tr("子午線（地上モード）"), "show_meridian")
        self.act_altaz = self._toggle(m_lines, tr("方位・高度の目盛り（地上モード）"), "show_altaz")
        self.act_ecl.setShortcut("Ctrl+L")
        self.act_ecl.toggled.connect(self.btn_ecl.setChecked)
        self.btn_ecl.toggled.connect(self.act_ecl.setChecked)
        act_ct = QAction(tr("通った跡を消す"), self)
        act_ct.triggered.connect(self.view.clear_trails)
        m_view.addAction(act_ct)
        m_land = m_view.addMenu(tr("地上の風景"))
        from PySide6.QtGui import QActionGroup
        self._land_grp = QActionGroup(self)
        self._land_acts = {}
        for key, ja, en in landscape.PRESETS:
            a = QAction(en if EN_MODE else ja, self, checkable=True)
            a.triggered.connect(lambda _=False, k=key: self._set_landscape(k))
            self._land_grp.addAction(a)
            m_land.addAction(a)
            self._land_acts[key] = a
        m_land.addSeparator()
        a = QAction(tr("自分の360°写真を読み込む…"), self, checkable=True)
        a.triggered.connect(self._load_landscape_file)
        self._land_grp.addAction(a)
        m_land.addAction(a)
        self._land_acts["file"] = a
        self._land_acts["none"].setChecked(True)
        m_mwl = m_view.addMenu(tr("天の川の明るさ"))
        from PySide6.QtGui import QActionGroup
        self._mw_grp = QActionGroup(self)
        self._mw_acts = []
        for i, label in enumerate((tr("控えめ（暗い山の上の見え方）"), tr("ふつう"), tr("明るめ"), tr("とても明るい"))):
            a = QAction(label, self, checkable=True)
            a.setChecked(i == self.view.mw_level)
            a.triggered.connect(lambda _=False, i=i: self._set_mw_level(i))
            self._mw_grp.addAction(a)
            m_mwl.addAction(a)
            self._mw_acts.append(a)
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
        act_ep = QAction(tr("星座の形の変化（星の動き）…"), self)
        act_ep.setShortcut(QKeySequence("Ctrl+Y"))
        act_ep.triggered.connect(self._show_epoch_panel)
        m_view.addAction(act_ep)
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
        act_tn = QAction(tr("今夜の空ガイド…"), self)
        act_tn.setShortcut(QKeySequence("Ctrl+G"))
        act_tn.triggered.connect(lambda: self._show_tonight())
        m_ev.addAction(act_tn)
        m_ev.addSeparator()
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
                   "show_star_names", "show_galaxies", "show_small", "show_craft", "show_quasars", "show_cmb", "show_minor", "show_exo", "show_nebulae", "show_artsat", "show_photos", "show_mwphoto", "show_atmosphere", "show_trails", "show_lift", "show_ecliptic", "show_equator", "show_meridian", "show_altaz")

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
                "show_quasars": self.act_qso, "show_cmb": self.act_cmb, "show_minor": self.act_minor, "show_exo": self.act_exo, "show_nebulae": self.act_neb, "show_artsat": self.act_artsat, "show_photos": self.act_photo, "show_mwphoto": self.act_mwphoto, "show_atmosphere": self.act_atm, "show_trails": self.act_trails, "show_lift": self.act_lift, "show_ecliptic": self.act_ecl, "show_equator": self.act_equ, "show_meridian": self.act_mer, "show_altaz": self.act_altaz}
        for name, act in acts.items():
            val = st.value(f"view/{name}")
            if val is not None:
                act.setChecked(str(val).lower() in ("true", "1"))
        if st.value("view/limit") is not None:
            self.sl_stars.setValue(int(st.value("view/limit")))
        try:
            b = int(st.value("view/bortle", 3))
            if b in self._lp_acts:
                self._set_bortle(b)
        except (TypeError, ValueError):
            pass
        try:
            self.sp_step.setValue(int(st.value("time/step_rate", 10)))
        except (TypeError, ValueError):
            pass
        ls = str(st.value("view/landscape", "none"))
        try:
            if ls.startswith("file|"):
                _f, path, north = ls.split("|")
                if Path(path).is_file():
                    self._load_landscape_file(path, float(north), save=False)
            elif ls != "none" and ls in self._land_acts:
                self._set_landscape(ls, save=False)
        except (ValueError, OSError):
            pass
        try:
            lv = st.value("view/mw_level")
            if lv is not None and 0 <= int(lv) <= 3:
                self._set_mw_level(int(lv))
        except (TypeError, ValueError):
            pass
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
        st.setValue("view/mw_level", self.view.mw_level)
        st.setValue("time/step_rate", self.sp_step.value())
        st.setValue("view/magnify", self.sl_mag.value())
        st.setValue("time/speed", self.cb_speed.currentIndex())
        if not self.view.ground:
            st.setValue("view/target", self.view.target)

    def _set_landscape(self, key, save=True):
        from PySide6.QtWidgets import QApplication
        QApplication.setOverrideCursor(Qt.WaitCursor)
        try:
            self.view.set_landscape(landscape.make(key))
        finally:
            QApplication.restoreOverrideCursor()
        if key in self._land_acts:
            self._land_acts[key].setChecked(True)
        if save:
            self.settings.setValue("view/landscape", key)
        if key != "none" and not self.view.ground and save:
            self.statusBar().showMessage(tr("風景は「地上から見る」のときに出ます"), 6000)

    def _load_landscape_file(self, path=None, north=None, save=True):
        from PySide6.QtWidgets import QInputDialog
        if not path:
            path, _ = QFileDialog.getOpenFileName(
                self, tr("360°写真（正距円筒図）を選ぶ"), str(Path.home()),
                tr("画像 (*.png *.jpg *.jpeg *.webp)"))
            if not path:
                self._land_acts.get(str(self.settings.value("view/landscape", "none")).split("|")[0],
                                    self._land_acts["none"]).setChecked(True)
                return
        img = QImage(path)
        if img.isNull():
            QMessageBox.warning(self, tr("地上の風景"), tr("画像を読めませんでした。"))
            return
        if north is None:
            north, ok = QInputDialog.getInt(
                self, tr("地上の風景"),
                tr("写真の左はしは、どの方位ですか？（北 = 0、東 = 90、南 = 180、西 = 270）\n"
                   "空のところが透明な PNG にすると、星空が見えます。"), 0, 0, 359)
            if not ok:
                return
        img = img.convertToFormat(QImage.Format.Format_RGBA8888)
        if img.width() > 8192:
            img = img.scaledToWidth(8192, Qt.SmoothTransformation)
        w, h = img.width(), img.height()
        arr = np.frombuffer(img.constBits(), np.uint8, count=img.bytesPerLine() * h).reshape(h, img.bytesPerLine())
        arr = arr[:, :w * 4].reshape(h, w, 4).copy()
        self.view.set_landscape(landscape.from_image(arr, float(north), Path(path).name))
        self._land_acts["file"].setChecked(True)
        if save:
            self.settings.setValue("view/landscape", f"file|{path}|{north}")

    def _set_bortle(self, b):
        self.view.bortle = b
        if b in self._lp_acts:
            self._lp_acts[b].setChecked(True)
        self.settings.setValue("view/bortle", b)
        self.view.update()

    def _set_mw_level(self, i):
        self.view.mw_level = i
        self._mw_acts[i].setChecked(True)
        self.view.update()

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
            self._set_ground_checked(True)
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

        go = self._go_shower
        self._event_table(
            trx(f"流星群（これから1年・観測地 {v.place}）"),
            [tr("極大"), tr("流星群"), tr("見やすい時刻"), tr("見える数の目安"), tr("月明かり"), tr("くわしく")], rows,
            "見える数の目安は、空の暗い場所で放射点が高いときの1時間あたりの数です（町なかではもっと少なくなります）。"
            "流星は放射点から四方へ飛ぶので、放射点だけでなく空全体を広く見るのがこつです。\n"
            "「地上から見る」で、見やすい時刻の空に流星が流れます（流れる数は実際の約10倍に増やしています）。",
            go)

    # ---------------------------------------------------------- 星座の形の変化（星の動き）

    def _show_epoch_panel(self):
        if getattr(self, "_ep_dlg", None) is not None:
            self._ep_dlg.raise_()
            self._ep_dlg.activateWindow()
            return
        v = self.view
        dlg = QDialog(self)
        dlg.setWindowTitle(tr("星座の形の変化"))
        dlg.resize(560, 300)
        lay = QVBoxLayout(dlg)
        lab = QLabel(tr("星は1つ1つが、それぞれの向きと速さで宇宙を動いています。近くの星ほど、空の上で大きく動きます。\n"
                        "時代を変えると、星の位置だけが動いて、星座の形が変わっていくのを見られます（惑星や時計は変わりません）。"))
        lab.setWordWrap(True)
        lay.addWidget(lab)
        val = QLabel()
        f = val.font()
        f.setPointSizeF(f.pointSizeF() * 1.5)
        f.setBold(True)
        val.setFont(f)
        val.setAlignment(Qt.AlignCenter)
        lay.addWidget(val)
        sl = QSlider(Qt.Horizontal)
        sl.setRange(-200, 200)          # 1目もり = 1000年
        sl.setValue(int(round(v.stars.epoch / 1000)))
        sl.setTickPosition(QSlider.TicksBelow)
        sl.setTickInterval(50)
        lay.addWidget(sl)
        ends = QHBoxLayout()
        ends.addWidget(QLabel(tr("20万年前")))
        ends.addStretch(1)
        ends.addWidget(QLabel(tr("今")))
        ends.addStretch(1)
        ends.addWidget(QLabel(tr("20万年後")))
        lay.addLayout(ends)
        row = QHBoxLayout()
        b_back = QPushButton(tr("◀ 過去へ動かす"))
        b_stop = QPushButton(tr("止める"))
        b_fwd = QPushButton(tr("未来へ動かす ▶"))
        b_now = QPushButton(tr("今に戻す"))
        for b in (b_back, b_stop, b_fwd, b_now):
            row.addWidget(b)
        lay.addLayout(row)
        row2 = QHBoxLayout()
        row2.addWidget(QLabel(tr("見る星座:")))
        cb = QComboBox()
        names = sorted(((c.name, i) for i, c in enumerate(v.stars.constellations)
                        if "見えない" not in CON_INFO.get(c.id, ("",))[0]), key=lambda t: t[0])
        favs = ["UMa", "Ori", "Cas", "Sco", "Leo", "Cyg"]
        idx = {c.id: i for i, c in enumerate(v.stars.constellations)}
        for cid in favs:
            if cid in idx:
                cb.addItem(v.stars.constellations[idx[cid]].name, idx[cid])
        cb.insertSeparator(cb.count())
        for name, i in names:
            cb.addItem(name, i)
        row2.addWidget(cb, 1)
        b_look = QPushButton(tr("地上から見る"))
        row2.addWidget(b_look)
        lay.addLayout(row2)
        chk = QCheckBox(tr("明るい星の動いた跡を線で出す"))
        chk.setChecked(v.show_star_trails)
        chk.toggled.connect(lambda on: (setattr(v, "show_star_trails", on), v.update()))
        lay.addWidget(chk)
        timer = QTimer(dlg)
        step = [0]

        def show_val(k):
            y = k * 1000
            if y == 0:
                val.setText(tr("今の星の位置"))
            elif EN_MODE:
                val.setText(f"{abs(y):,} years {'from now' if y > 0 else 'ago'}")
            else:
                val.setText(f"{abs(y):,} 年{'後' if y > 0 else '前'}")

        def on_slider(k):
            show_val(k)
            v.set_star_epoch(k * 1000.0)

        def tick():
            k = sl.value() + step[0]
            if k > sl.maximum() or k < sl.minimum():
                timer.stop()
                return
            sl.setValue(k)

        def play(d):
            step[0] = d
            timer.start(80)

        sl.valueChanged.connect(on_slider)
        timer.timeout.connect(tick)
        b_back.clicked.connect(lambda: play(-1))
        b_fwd.clicked.connect(lambda: play(1))
        b_stop.clicked.connect(timer.stop)
        b_now.clicked.connect(lambda: (timer.stop(), sl.setValue(0)))
        b_look.clicked.connect(lambda: self._look_constellation(cb.currentData()))
        show_val(sl.value())
        dlg.finished.connect(lambda *_: (timer.stop(), setattr(self, "_ep_dlg", None)))
        self._ep_dlg = dlg
        dlg.setModal(False)
        dlg.show()

    def _look_constellation(self, ci):
        """その星座が夜10時ごろ高く見える日（これから1年のうち）の空を、地上から見る。"""
        if ci is None:
            return
        v = self.view
        c = v.stars.constellations[int(ci)]
        now = datetime.now().astimezone().replace(hour=22, minute=0, second=0, microsecond=0)
        best, best_alt = None, -90.0
        for d in range(0, 366, 3):
            jd = astro.jd_from_datetime(now + timedelta(days=d))
            _off, zen, north, east = astro.observer_frame(jd, v.lat, v.lon)
            alt, _az = astro.alt_az(np.asarray(c.center), zen, north, east)
            if alt > best_alt:
                best, best_alt = jd, alt
        self._ground_at(best)
        v.look_dir(c.center, fov=75.0)
        v.select_con(int(ci))

    # ---------------------------------------------------------- 今夜の空ガイド

    def _show_tonight(self, date=None):
        if not tonight.available():
            QMessageBox.warning(self, tr("今夜の空ガイド"), tr("PyEphem（python3-ephem）が必要です。"))
            return
        if getattr(self, "_tn_dlg", None) is not None:
            self._tn_dlg.raise_()
            self._tn_dlg.activateWindow()
            return
        from PySide6.QtWidgets import QApplication
        dlg = QDialog(self)
        dlg.setWindowTitle(tr("今夜の空ガイド"))
        dlg.resize(760, 820)
        lay = QVBoxLayout(dlg)
        nav = QHBoxLayout()
        b_prev = QPushButton(tr("◀ 前の夜"))
        b_today = QPushButton(tr("今夜"))
        b_next = QPushButton(tr("次の夜 ▶"))
        for b in (b_prev, b_today, b_next):
            nav.addWidget(b)
        nav.addStretch(1)
        lay.addLayout(nav)
        tb = QTextBrowser()
        tb.setOpenLinks(False)
        lay.addWidget(tb, 1)
        chk = QCheckBox(tr("そらみ窓を起動したときに、今夜の空ガイドを出す"))
        chk.setChecked(str(self.settings.value("ui/tonight_on_start", "false")).lower() in ("true", "1"))
        chk.toggled.connect(lambda on: self.settings.setValue("ui/tonight_on_start", bool(on)))
        lay.addWidget(chk)
        bb = QDialogButtonBox()
        bb.addButton(tr("閉じる"), QDialogButtonBox.RejectRole)
        bb.rejected.connect(dlg.reject)
        lay.addWidget(bb)
        state = {"date": date or datetime.now().astimezone(), "guide": None}

        def refresh():
            QApplication.setOverrideCursor(Qt.WaitCursor)
            try:
                v = self.view
                state["guide"] = tonight.build(state["date"], v.lat, v.lon, v.stars,
                                               {k: x[0] for k, x in CON_INFO.items()}, v.artsats)
                tb.setHtml(self._tonight_html(state["guide"]))
            finally:
                QApplication.restoreOverrideCursor()

        def shift(days):
            state["date"] = tonight.night_of(state["date"]) + timedelta(days=days)
            refresh()

        b_prev.clicked.connect(lambda: shift(-1))
        b_next.clicked.connect(lambda: shift(1))
        b_today.clicked.connect(lambda: (state.__setitem__("date", datetime.now().astimezone()), refresh()))
        tb.anchorClicked.connect(lambda url: self._tonight_go(url.toString(), state["guide"]))
        dlg.finished.connect(lambda *_: setattr(self, "_tn_dlg", None))
        self._tn_dlg = dlg
        refresh()
        dlg.setModal(False)
        dlg.show()

    def _tonight_html(self, g) -> str:
        v = self.view

        def L(ja, en):
            return en if EN_MODE else ja

        def hm(jd):
            return self._local_time(jd, False) if jd else "―"

        dirs = [tr("北"), tr("北北東"), tr("北東"), tr("東北東"), tr("東"), tr("東南東"), tr("南東"), tr("南南東"),
                tr("南"), tr("南南西"), tr("南西"), tr("西南西"), tr("西"), tr("西北西"), tr("北西"), tr("北北西")]

        def d(az):
            return dirs[int((az + 11.25) // 22.5) % 16]

        def go(href, label=None):
            return f" <a href='{href}'>{label or L('［空を見る］', '[view]')}</a>"

        con_by_id = {c.id: c.name for c in v.stars.constellations}
        n = g.night
        day = n.date
        nxt = day + timedelta(days=1)
        if EN_MODE:
            title = f"Tonight's sky — {v.place}, {day:%b %-d}–{nxt:%-d}, {day:%Y}"
        else:
            title = f"今夜の空 — {v.place}・{day.year}年{day.month}月{day.day}日〜{nxt.day}日"
        h = [f"<h2>{title}</h2>"]
        h.append("<p>" + L(f"日の入り {hm(n.sunset)} → 暗くなる {hm(n.dusk)} … 明るくなりはじめる {hm(n.dawn)} → 日の出 {hm(n.sunrise)}",
                           f"Sunset {hm(n.sunset)} → dark {hm(n.dusk)} … dawn {hm(n.dawn)} → sunrise {hm(n.sunrise)}") + "</p>")
        # 月
        m = g.moon
        if m:
            phase_en = {"新月": "New moon", "三日月": "Crescent", "上弦前の月": "Waxing crescent", "上弦の月": "First quarter",
                        "十日夜〜十三夜の月": "Waxing gibbous", "満月": "Full moon", "満月すぎの月": "Waning gibbous",
                        "下弦の月": "Last quarter", "有明の月": "Waning crescent"}
            h.append("<h3>" + L("月", "Moon") + "</h3><p>")
            h.append(L(f"<b>{m.phase}</b>（月齢 {m.age:.1f}・明るい部分 {m.illum * 100:.0f}%）",
                       f"<b>{phase_en.get(m.phase, m.phase)}</b> (age {m.age:.1f} d, {m.illum * 100:.0f}% lit)"))
            h.append("<br>" + L(f"月の出 {hm(m.rise)}・月の入り {hm(m.set)}", f"Moonrise {hm(m.rise)}, moonset {hm(m.set)}"))
            if m.best:
                h.append(go("go:moon"))
            if m.bright_night:
                h.append("<br><span style='color:#c96'>" + L("明るい月が夜の多くの時間に出ているので、暗い星や天の川は見えにくい夜です。",
                                                           "A bright Moon is up most of the night, so faint stars and the Milky Way are hard to see.") + "</span>")
            elif m.illum < 0.3:
                h.append("<br><span style='color:#7c9'>" + L("月明かりが少なく、星空を見るのによい夜です。",
                                                           "Little moonlight — a good night for stargazing.") + "</span>")
            h.append("</p>")
        # 惑星
        h.append("<h3>" + L("惑星", "Planets") + "</h3><ul>")
        when_ja = {"evening": "宵の空", "morning": "明け方の空", "night": "夜中から明け方", "all": "一晩中", "late": "夜中"}
        when_en = {"evening": "evening", "morning": "morning", "night": "late night to dawn", "all": "all night",
                   "late": "late night"}
        seen = sorted((p for p in g.planets if p.start), key=lambda p: p.start)
        for p in seen:
            name = BY_KEY[p.key].name
            con = con_by_id.get(p.con, p.con)
            h.append("<li>" + L(
                f"<b>{name}</b>（{p.mag:.1f}等・{con}）{when_ja[p.when]}　{hm(p.start)}〜{hm(p.end)}"
                f"<br>　いちばん高いのは {hm(p.best)}（{d(p.best_az)}・高さ {p.best_alt:.0f}°）",
                f"<b>{name}</b> (mag {p.mag:.1f}, {con}) {when_en[p.when]}, {hm(p.start)}–{hm(p.end)}"
                f"<br>　Highest at {hm(p.best)} ({d(p.best_az)}, alt {p.best_alt:.0f}°)") + go(f"go:planet:{p.key}") + "</li>")
        h.append("</ul>")
        hidden = [BY_KEY[p.key].name for p in g.planets if not p.start]
        if hidden:
            h.append("<p style='color:#888'>" + L("太陽に近いなどで見えない: ", "Not visible (too close to the Sun etc.): ")
                     + L("・", ", ").join(hidden) + "</p>")
        # 星座
        if g.cons:
            h.append("<h3>" + L(f"{hm(g.con_jd)}ごろ高く見える星座", f"Constellations high at {hm(g.con_jd)}") + "</h3><p>")
            h.append(L("　", ", ").join(
                f"<a href='go:con:{c.index}'>{v.stars.constellations[c.index].name}</a>"
                + L(f"（{d(c.az)}・{c.alt:.0f}°）", f" ({d(c.az)} {c.alt:.0f}°)") for c in g.cons) + "</p>")
        # 人工衛星
        h.append("<h3>" + L("人工衛星（ISS など）", "Satellites (ISS etc.)") + "</h3>")
        if not v.artsats:
            h.append("<p style='color:#888'>" + L("人工衛星のデータがありません。", "No satellite data.")
                     + go("dl:tle", L("［ダウンロードする］", "[download]")) + "</p>")
        elif g.passes:
            h.append("<ul>")
            for i, p in enumerate(g.passes):
                h.append("<li>" + L(f"<b>{p.sat.ja}</b> {hm(p.rise_jd)} {d(p.rise_az)}から → 最大 {p.max_alt:.0f}°"
                                    f"（{d(p.max_az)}・{hm(p.max_jd)}） → {d(p.set_az)}へ",
                                    f"<b>{p.sat.ja}</b> {hm(p.rise_jd)} from {d(p.rise_az)} → max {p.max_alt:.0f}°"
                                    f" ({d(p.max_az)}, {hm(p.max_jd)}) → {d(p.set_az)}") + go(f"go:pass:{i}") + "</li>")
            h.append("</ul>")
        else:
            h.append("<p style='color:#888'>" + L("今夜、見える通過はありません。", "No visible passes tonight.") + "</p>")
        # 流星群
        if g.showers:
            h.append("<h3>" + L("流星群", "Meteor showers") + "</h3><ul>")
            for i, sn in enumerate(g.showers):
                h.append("<li>" + L(f"<b>{sn.shower.name}</b>（極大 {self._local_time(sn.jd_peak)}）見やすいのは {hm(sn.jd_best)}・"
                                    f"1時間に約{sn.rate:.0f}個・{sn.condition}",
                                    f"<b>{sn.shower.name}</b> (peak {self._local_time(sn.jd_peak)}) best at {hm(sn.jd_best)}, "
                                    f"about {sn.rate:.0f}/h, {sn.condition}") + go(f"go:shower:{i}") + "</li>")
            h.append("</ul>")
        # これからの天文現象
        if g.events or g.eclipses:
            h.append("<h3>" + L("これからの天文現象", "Coming up") + "</h3><ul>")
            for i, e in enumerate(g.eclipses):
                h.append(f"<li>{self._local_time(e.jd_max)}　<b>{e.type_ja}</b>　{self._eclipse_local_text(e)}"
                         + (go(f"go:ecl:{i}") if e.local.get("visible") else "") + "</li>")
            for i, e in enumerate(g.events):
                vis = e.local.get("visible")
                h.append(f"<li>{self._local_time(e.jd)}　{e.title}"
                         + (L(f"（{v.place}で見やすいのは {self._local_time(e.local['jd'], False)}ごろ）",
                              f" (best from {v.place} around {self._local_time(e.local['jd'], False)})") + go(f"go:event:{i}")
                            if vis else "<span style='color:#888'>" + L("（見えにくい）", " (hard to see)") + "</span>") + "</li>")
            h.append("</ul>")
        h.append("<p style='color:#888'>" + L("「空を見る」を押すと、そのときの空を地上モードで見られます。時刻はこのパソコンの時刻帯です。",
                                              "Press [view] to see that sky in ground mode. Times are in this computer's time zone.")
                 + "</p>")
        return "".join(h)

    def _tonight_go(self, href: str, g):
        if g is None:
            return
        v = self.view
        parts = href.split(":")
        kind = parts[0] + (":" + parts[1] if len(parts) > 1 else "")
        if kind != "go:con" and v.selected_con >= 0:
            v.select_con(-1)
        if href == "dl:tle":
            self._download_tle(then=lambda: (self._tn_dlg and self._tn_dlg.close(), self._show_tonight()))
            return
        if kind == "go:moon" and g.moon and g.moon.best:
            self._ground_at(g.moon.best)
            self._look_at_keys(["moon"], 40.0)
        elif kind == "go:planet":
            p = next((x for x in g.planets if x.key == parts[2]), None)
            if p and p.best:
                self._ground_at(p.best)
                self._look_at_keys([p.key], 50.0)
        elif kind == "go:con":
            i = int(parts[2])
            self._ground_at(g.con_jd)
            v.look_dir(v.stars.constellations[i].center, fov=80.0)
            v.select_con(i)
        elif kind == "go:pass":
            self._go_pass(g.passes[int(parts[2])])
        elif kind == "go:shower":
            self._go_shower(g.showers[int(parts[2])])
        elif kind == "go:event":
            self._go_event(g.events[int(parts[2])])
        elif kind == "go:ecl":
            self._go_eclipse(g.eclipses[int(parts[2])], True)

    def _on_panel_link(self, url):
        href = url.toString()
        if href.startswith("http"):
            QDesktopServices.openUrl(url)
            return
        if href.startswith("jd:"):
            v = self.view
            v.paused = True
            v.set_jd(float(href[3:]))
            v.dist = max(v.dist, v._default_dist(v.target) * 0.5)
            self._refresh_ui()
            self._update_panel(force=True)

    def _go_shower(self, n):
        v = self.view
        jd = n.jd_best or n.jd_peak
        self._ground_at(jd)
        ok = v.look_dir(evt.radiant_vector(n.shower), fov=100.0)
        self.act_meteor.setChecked(True)
        msg = (f"{n.shower.name} (meteors shown about {v.METEOR_BOOST:.0f}× more often than real)" if EN_MODE else
               f"{n.shower.name}：{n.shower.note}（流れる数は実際の約{v.METEOR_BOOST:.0f}倍に増やしています）")
        if not ok:
            msg = tr("このとき放射点は地平線の下です。") + msg
        self.statusBar().showMessage(trx(msg), 20000)

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

        go = self._go_pass
        note = ("高度10°より高く昇るときの一覧です（これから10日）。「見える」は、空が暗く、衛星に太陽の光が当たっているときで、"
                "明るい星のような光がゆっくり空を横切ります。「地上から見る」で、そのときの空を実時間で見られます。")
        if age > 7:
            note = (f"⚠ Orbit data is {age:.0f} days old. Download it again from the File menu.\n" if EN_MODE else
                    f"⚠ 軌道のデータが {age:.0f} 日前のもので古くなっています。「ファイル」からダウンロードし直してください。\n") + tr(note)
        self._event_table(trx(f"人工衛星が見える時刻（これから10日・観測地 {v.place}）"),
                          [tr("昇る時刻"), tr("衛星"), tr("動き（方角）"), tr("見え方")], rows, note, go)

    def _go_pass(self, p):
        v = self.view
        self._ground_at(p.max_jd - 1.5 / 1440)
        a, z = math.radians(p.max_alt), math.radians(p.max_az)
        off, zen, north, east = astro.observer_frame(v.jd, v.lat, v.lon)
        v.look_dir(zen * math.sin(a) + (north * math.cos(z) + east * math.sin(z)) * math.cos(a), fov=110.0)
        self.cb_speed.setCurrentIndex(0)      # 実時間で動かす
        self._apply_speed()
        v.paused = False
        self._refresh_ui()

    def _look_at_keys(self, keys, fov):
        """地上モードで、その天体（いくつかなら、そのまん中）の方を向く。"""
        v = self.view
        pos = [v.display_pos(k) for k in keys]
        off, _z, _n, _e = astro.observer_frame(v.jd, v.lat, v.lon)
        eye = v.positions["earth"] + off
        dirs = [(p - eye) / np.linalg.norm(p - eye) for p in pos]
        mid = sum(dirs) / len(dirs)
        return v.look_dir(mid / np.linalg.norm(mid), fov=fov)

    def _go_event(self, e):
        self._ground_at(e.local.get("jd") or e.jd)
        sep = e.local.get("sep", e.sep)       # 観測地から見た離れ角（月は場所で変わる）
        fov = {"conj": max(6.0, sep * 2.5), "occult": max(4.0, sep * 2.5), "opposition": 40.0,
               "elong": 50.0}[e.kind]
        if not self._look_at_keys(e.keys, fov):
            self.statusBar().showMessage(tr("このとき、観測地では地平線の下です"), 8000)

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

        go = self._go_event
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
                self._set_ground_checked(True)
            self.cb_speed.setCurrentIndex(1)     # 1分/秒
            v.paused = True
            ok = v.look_at("sun" if e.kind == "solar" else "moon")
            v.g_fov = 3.0
            if not ok:
                self.statusBar().showMessage(tr("そのとき、観測地では地平線の下です（地面を消すと見えます）"), 8000)
        else:
            v.set_jd(e.jd_max)
            if self.btn_ground.isChecked():
                self._set_ground_checked(False)
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
        self.panel_text.setOpenLinks(False)
        self.panel_text.anchorClicked.connect(self._on_panel_link)
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
        elif v.ground and v.ground_body != "earth":
            html.append(self._body_sky_html(v))
            if v.target in BY_KEY and text_for(v.target):
                html.append(f"<h3>{BY_KEY[v.target].name}</h3><p>{text_for(v.target)}</p>")
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
                html.append(f"<h2>🛰 {sc.name}</h2><p>{sc.note}</p><h3>おもなできごと</h3>")
                t0, t1 = crafts.span(sc)
                if not (t0 <= v.jd <= t1):
                    html.append("<p style='color:#c96'>" + tr("いまの日付では、この探査機は飛んでいません。") + "</p>")
                html.append("<p style='color:#888'>" + tr("できごとを押すと、その日へ移ります。") + "</p><ul>")
                for jd_e, txt in sc.events:
                    d = astro.datetime_from_jd(jd_e)
                    mark = "✔ " if jd_e <= v.jd else ""
                    date = f"{d:%Y-%m-%d}" if EN_MODE else f"{d.year}年{d.month}月{d.day}日"
                    html.append(f"<li>{mark}<a href='jd:{jd_e + 0.5}'>{date}</a>　{txt}</li>")
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
        if self.view.ground_body != "earth":
            self._set_ground_checked(False)
            self.cb_body.setCurrentIndex(0)
            self._fill_places("earth")
            self.view.set_ground_body("earth")
            self._select_place(self.view.place, self.view.lat, self.view.lon)
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
                self._set_ground_checked(True)
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
                self._set_ground_checked(False)
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

    # ---- 天体望遠鏡モード

    def _build_scope_bar(self):
        bar = QToolBar(tr("望遠鏡"))
        bar.setObjectName("scopebar")
        self.addToolBarBreak()
        self.addToolBar(bar)
        self.scope_bar = bar
        bar.addWidget(QLabel(tr(" 望遠鏡 ")))
        self.cb_scope = QComboBox()
        for t in scopes.TELESCOPES:
            self.cb_scope.addItem(tr(t.name), t.key)
        bar.addWidget(self.cb_scope)
        bar.addWidget(QLabel(tr("  接眼レンズ ")))
        self.cb_eye = QComboBox()
        for e in scopes.EYEPIECES:
            self.cb_eye.addItem(scopes.eyepiece_name(e))
        self.cb_eye.setToolTip(tr("焦点距離の短い接眼レンズほど、倍率が上がります（マウスのホイールや＋−キーでも変えられます）"))
        bar.addWidget(self.cb_eye)
        bar.addWidget(QLabel(tr("  像の向き ")))
        self.cb_image = QComboBox()
        for key, name in scopes.IMAGE_ORIENTATIONS:
            self.cb_image.addItem(tr(name), key)
        bar.addWidget(self.cb_image)
        self.chk_track = QCheckBox(tr("自動追尾"))
        self.chk_track.setToolTip(tr("地球が回っても、天体が視野から逃げないように望遠鏡を動かします"))
        bar.addWidget(self.chk_track)
        st = self.settings
        i = self.cb_scope.findData(st.value("scope/telescope", "ref80"))
        self.cb_scope.setCurrentIndex(max(0, i))
        self.cb_eye.setCurrentIndex(min(len(scopes.EYEPIECES) - 1, max(0, int(st.value("scope/eyepiece", 2)))))
        self.chk_track.setChecked(st.value("scope/track", "false") in (True, "true"))
        self._sync_image_default()
        bar.setVisible(False)
        self.btn_scope.toggled.connect(self._on_scope)
        self.cb_scope.currentIndexChanged.connect(lambda _i: (self._sync_image_default(), self._apply_scope_ui()))
        self.cb_eye.currentIndexChanged.connect(lambda _i: self._apply_scope_ui())
        self.cb_image.currentIndexChanged.connect(lambda _i: self._apply_scope_ui())
        self.chk_track.toggled.connect(lambda _b: self._apply_scope_ui())
        self.view.scopeStep.connect(self._scope_step)

    def _sync_image_default(self):
        t = scopes.BY_KEY[self.cb_scope.currentData()]
        self.cb_image.blockSignals(True)
        self.cb_image.setCurrentIndex(max(0, self.cb_image.findData(t.image)))
        self.cb_image.blockSignals(False)
        self.cb_eye.setEnabled(not t.bino_mag)

    def _apply_scope_ui(self):
        st = self.settings
        st.setValue("scope/telescope", self.cb_scope.currentData())
        st.setValue("scope/eyepiece", self.cb_eye.currentIndex())
        st.setValue("scope/track", self.chk_track.isChecked())
        if not self.btn_scope.isChecked():
            return
        t = scopes.BY_KEY[self.cb_scope.currentData()]
        self.view.set_scope(t, scopes.EYEPIECES[self.cb_eye.currentIndex()], self.cb_image.currentData(),
                            self.chk_track.isChecked())

    def _on_scope(self, on):
        self.scope_bar.setVisible(on)
        if on:
            if not self.btn_ground.isChecked():
                self._set_ground_checked(True)
            # 速く時間が進むと、天体がすぐ視野から出てしまうので実時間にする（コマ送りはそのまま）
            sp = SPEEDS[self.cb_speed.currentIndex()][1]
            if not isinstance(sp, str) and sp > 60.0:
                self.cb_speed.setCurrentIndex(0)
            self._apply_scope_ui()
            self.statusBar().showMessage(tr("望遠鏡でのぞいています。ドラッグで向きを変え、ホイールで接眼レンズ（倍率）を変えます"), 8000)
        else:
            self.view.set_scope(None)
        self.view.setFocus()

    def _scope_step(self, d):
        if self.cb_eye.isEnabled():
            i = max(0, min(self.cb_eye.count() - 1, self.cb_eye.currentIndex() + d))
            self.cb_eye.setCurrentIndex(i)

    def _set_ground_checked(self, on):
        """プログラムから地上モードを切りかえる（ツアーや日食の場面では、飛ばずにすぐ切りかえる）。"""
        if on and self.view.ground_body != "earth" and not getattr(self, "_keep_body", False):
            self.cb_body.setCurrentIndex(0)          # ツアー・日食・今夜の空は、地球の地上で見る
            self._fill_places("earth")
            self.view.set_ground_body("earth")
            self._select_place(self.view.place, self.view.lat, self.view.lon)
        self._ground_instant = True
        try:
            self.btn_ground.setChecked(on)
        finally:
            self._ground_instant = False

    def _on_ground(self, on):
        self.view.set_ground(on, animate=not self._ground_instant and self.view.show_lift)
        self.btn_all.setEnabled(not on)
        self.sl_mag.setEnabled(not on)
        self.btn_ground.setText(tr("🚀 宇宙へ戻る") if on else tr("🔭 地上から見る"))
        self.btn_airless.setEnabled(on)
        if not on and self.btn_scope.isChecked():
            self.btn_scope.setChecked(False)
        # 1日/秒より速いと空がぐるぐる回って見づらいので、地上では少しゆっくりにする（コマ送りはそのまま）
        if on and self.cb_speed.currentIndex() > 3 and not isinstance(SPEEDS[self.cb_speed.currentIndex()][1], str):
            self.cb_speed.setCurrentIndex(1)
        self.view.setFocus()

    def _on_airless(self, on):
        self.view.airless = on
        self.view.update()
        if on:
            self.statusBar().showMessage(tr("大気なし：空気も地面もないものとして見ています（昼でも星が見え、地平線の下も見えます）"), 8000)

    def _restore_place(self):
        name = self.settings.value("place/name", tr("大阪"))
        lat = float(self.settings.value("place/lat", 34.69))
        lon = float(self.settings.value("place/lon", 135.50))
        self.view.set_place(name, lat, lon)
        self._select_place(name, lat, lon)

    def _fill_places(self, body):
        self.cb_place.clear()
        items = PLACES if body == "earth" else [(tr(n), la, lo) for n, la, lo in terrain.PLACES[body]]
        for name, lat, lon in items:
            self.cb_place.addItem(name, (name, lat, lon))
        self.cb_place.addItem(tr("緯度・経度を入力…"), None)

    def _select_place(self, name, lat, lon):
        i = self.cb_place.findText(name)
        if i < 0:
            self.cb_place.insertItem(self.cb_place.count() - 1, name, (name, lat, lon))
            i = self.cb_place.findText(name)
        else:
            self.cb_place.setItemData(i, (name, lat, lon))
        self.cb_place.setCurrentIndex(i)

    def _on_place(self, i):
        data = self.cb_place.itemData(i)
        body = self.view.ground_body
        if data is None:
            data = self._ask_place()
            if data is None:
                cur = self.view.place if body == "earth" else tr(self.view.gb_place)
                self.cb_place.setCurrentIndex(max(0, self.cb_place.findText(cur)))
                return
            self._select_place(*data)
        name, lat, lon = data
        if body != "earth":
            self.view.set_ground_body(body, name, lat, lon)
            if not self.btn_ground.isChecked():
                self.btn_ground.setChecked(True)
            return
        self.view.set_place(name, lat, lon)
        self.settings.setValue("place/name", name)
        self.settings.setValue("place/lat", lat)
        self.settings.setValue("place/lon", lon)

    def _body_sky_html(self, v):
        real = terrain.available(v.ground_body)
        lv = terrain.level(v.ground_body)
        src = tr(terrain.SOURCES[v.ground_body].credit)
        if EN_MODE:
            pl = v.ground_place_name()
            if v.ground_body == "moon":
                t = ("<h2>The sky from the Moon</h2>"
                     f"<p>{pl} (lat {v.gb_lat:+.2f}°, lon {v.gb_lon:+.2f}°).</p>"
                     "<p>The Moon has no air, so the sky is black even in daytime and the stars are always visible. "
                     "Seen from the near side, the Earth stays at almost the same place in the sky and goes through phases "
                     "over about 29.5 days — one lunar day. From the far side, the Earth is never seen.</p>")
            else:
                t = ("<h2>The sky from Mars</h2>"
                     f"<p>{pl} (lat {v.gb_lat:+.2f}°, lon {v.gb_lon:+.2f}°).</p>"
                     "<p>Fine dust makes the daytime sky butterscotch, while sunsets turn blue around the Sun. "
                     "A day on Mars (a sol) lasts about 24 h 40 min. The two small moons Phobos and Deimos cross the sky, "
                     "and the Earth shines as a bright morning or evening star.</p>")
            t += f"<p style='color:#888'>Terrain: {src} (1/{lv}°)" if real else \
                "<p style='color:#888'>Terrain: smooth ground (download the real terrain from the File menu)"
            return t + "</p>"
        pl = v.ground_place_name()
        if v.ground_body == "moon":
            t = ("<h2>月面から見た空</h2>"
                 f"<p>{pl}（緯度 {v.gb_lat:+.2f}°・経度 {v.gb_lon:+.2f}°）</p>"
                 "<p>月には空気がないので、昼でも空は真っ黒で、いつでも星が見えます。"
                 "表側からは、地球が空のほぼ同じ場所にとどまり、約29.5日（月の1日）かけて満ち欠けします。"
                 "裏側からは、地球は見えません。</p>")
        else:
            t = ("<h2>火星から見た空</h2>"
                 f"<p>{pl}（緯度 {v.gb_lat:+.2f}°・経度 {v.gb_lon:+.2f}°）</p>"
                 "<p>昼の空は、細かいちりで黄土色（バタースコッチ色）に見えます。夕焼けは逆に、太陽のまわりが青くなります。"
                 "火星の1日は約24時間40分。小さな2つの月フォボスとダイモスが空を動き、地球は明るい明けの明星・宵の明星として見えます。</p>")
        t += f"<p style='color:#888'>地形: {src}（1/{lv}度ごと）" if real else \
            "<p style='color:#888'>地形: なだらかな地面（「ファイル」メニューから本物の地形をダウンロードできます）"
        return t + "</p>"

    def _set_body(self, body, place=None, animate=True):
        """地上モードで立つ天体を変える（月・火星なら、地形のデータを用意する）。"""
        v = self.view
        if body != "earth":
            if not terrain.available(body):
                self._ask_terrain(body)          # ダウンロードしなくても、なだらかな地面で降りられる
            elif self.settings.value(f"terrain/want_{body}", False) in (True, "true"):
                self._start_terrain_bg(body)     # 詳しい版がまだなら、裏で続きを受け取る
        self.cb_body.setCurrentIndex(max(0, self.cb_body.findData(body)))
        self._fill_places(body)
        if body == "earth":
            v.set_ground_body("earth")
            self._select_place(v.place, v.lat, v.lon)
        else:
            name, lat, lon = place or (tr(terrain.PLACES[body][0][0]),) + terrain.PLACES[body][0][1:]
            self._select_place(name, lat, lon)
            # 宇宙からなら、その天体へ着陸する。地上（地球など）にいるなら、すぐに移る
            v.set_ground_body(body, name, lat, lon)
        if not self.btn_ground.isChecked():
            self._keep_body = True
            try:
                if animate:
                    self.btn_ground.setChecked(True)
                else:
                    self._set_ground_checked(True)
            finally:
                self._keep_body = False
        self._update_panel(force=True)
        self.view.setFocus()

    def _ask_terrain(self, body):
        """地形のデータをダウンロードするか聞いて、するなら軽い版をすぐに、詳しい版を裏でダウンロードする。"""
        src = terrain.SOURCES[body]
        nm = terrain.body_name(body)
        if EN_MODE:
            title = f"{nm} terrain"
            msg = (f"Download the real terrain (elevation data) of the {nm}?\n\n{tr(src.credit)}\n\n"
                   f"First a light version (about {src.size_mb[4]:.0f} MB) so you can land right away, then the detailed "
                   f"version (about {src.size_mb[16]:.0f} MB) in the background while you use the app.\n\n"
                   "If you skip this, you will land on smooth ground (you can download it later from the File menu).")
        else:
            title = f"{nm}の地形"
            msg = (f"{nm}の本物の地形（標高のデータ）をダウンロードしますか？\n\n{src.credit}\n\n"
                   f"まず軽い版（約{src.size_mb[4]:.0f}MB）を受け取って、すぐに降り立ちます。"
                   f"詳しい版（約{src.size_mb[16]:.0f}MB）は、ソフトを使っているあいだに裏で受け取り、終わったら地形が細かくなります。\n\n"
                   "ダウンロードしないときは、なだらかな地面に降ります（あとで「ファイル」メニューからダウンロードできます）。")
        if QMessageBox.question(self, title, msg) != QMessageBox.Yes:
            return False
        return self._get_terrain(body)

    def _get_terrain(self, body):
        """軽い版が無ければ待って受け取り、詳しい版は裏で受け取る。"""
        self.settings.setValue(f"terrain/want_{body}", True)
        ok = terrain.available(body, 4) or self._download_terrain(body, 4)
        if ok:
            self.view.reload_terrain()
        self._start_terrain_bg(body)
        return ok or terrain.available(body)

    def _download_terrain(self, body, ppd):
        """待ちながら受け取る（軽い版用）。"""
        dl = terrain.Downloader(body, ppd)
        nm = terrain.body_name(body)
        title = f"{nm} terrain" if EN_MODE else f"{nm}の地形"
        label = f"Downloading the {nm} terrain…" if EN_MODE else f"{nm}の地形をダウンロードしています…"
        dlg = QProgressDialog(label, tr("キャンセル"), 0, 1000, self)
        dlg.setWindowTitle(title)
        dlg.setWindowModality(Qt.WindowModal)
        dlg.setMinimumDuration(0)
        dlg.canceled.connect(dl.cancel)
        dl.start()
        while not dl.done:
            QCoreApplication.processEvents()
            dlg.setValue(int(1000 * min(1.0, dl.bytes / max(dl.total, 1))))
            dlg.setLabelText(f"{label}\n{dl.bytes / 1e6:,.1f} / {dl.total / 1e6:,.1f} MB")
            time.sleep(0.05)
        dlg.close()
        if dl.ok:
            return True
        if "キャンセル" not in dl.message:
            QMessageBox.warning(self, title, tr("ダウンロードできませんでした。\n\n") + dl.message)
        return False

    def _start_terrain_bg(self, body):
        """詳しい版を裏で受け取る（前に切れていたら続きから）。"""
        if terrain.available(body, 16):
            return
        bg = getattr(self, "_terrain_bg", None)
        if bg is None:
            self._terrain_bg = bg = {}
            self._terrain_timer = QTimer(self)
            self._terrain_timer.timeout.connect(self._poll_terrain_bg)
            self._terrain_label = QLabel()
            self.statusBar().addPermanentWidget(self._terrain_label)
        if body in bg and not bg[body].done:
            return
        dl = terrain.Downloader(body, 16)
        bg[body] = dl
        dl.start()
        self._terrain_timer.start(500)
        self._poll_terrain_bg()

    def _poll_terrain_bg(self):
        bg = self._terrain_bg
        texts = []
        for body, dl in list(bg.items()):
            nm = terrain.body_name(body)
            if not dl.done:
                if EN_MODE:
                    texts.append(f"Detailed {nm} terrain {dl.bytes / 1e6:,.1f} / {dl.total / 1e6:,.1f} MB")
                else:
                    texts.append(f"{nm}の詳しい地形 {dl.bytes / 1e6:,.1f} / {dl.total / 1e6:,.1f} MB")
                continue
            del bg[body]
            if dl.ok:
                if self.view.ground_body == body:
                    self.view.reload_terrain()
                    self._update_panel(force=True)
                msg = f"The detailed {nm} terrain is ready." if EN_MODE else f"{nm}の詳しい地形を受け取りました。"
            else:
                msg = (f"Could not get the detailed {nm} terrain ({dl.message}). It resumes next time."
                       if EN_MODE else f"{nm}の詳しい地形を受け取れませんでした（{dl.message}）。次は続きから受け取ります。")
            self.statusBar().showMessage(msg, 15000)
        self._terrain_label.setText("　".join(texts))
        self._terrain_label.setVisible(bool(texts))
        if not bg:
            self._terrain_timer.stop()

    def _download_terrain_menu(self, body):
        if self._get_terrain(body):
            nm = terrain.body_name(body)
            QMessageBox.information(self, tr("地形"), (
                f"The light version of the {nm} terrain is ready. The detailed version continues in the background "
                "(see the status bar)." if EN_MODE else
                f"{nm}の地形（軽い版）を用意しました。詳しい版は裏で受け取っています（下のステータスバーに進み具合が出ます）。"))

    @staticmethod
    def _latlon_text(lat, lon):
        lon = lon % 360.0
        if EN_MODE:
            return f"{abs(lat):.1f}°{'N' if lat >= 0 else 'S'}, {lon:.1f}°E"
        return (f"北緯 {lat:.1f}°" if lat >= 0 else f"南緯 {-lat:.1f}°") + f"・東経 {lon:.1f}°"

    def _land_request(self, body, lat, lon):
        """宇宙から月・火星をダブルクリックした場所に降り立つ。"""
        nm = terrain.body_name(body)
        where = self._latlon_text(lat, lon)
        msg = f"Land on the {nm} at {where}?" if EN_MODE else f"{nm}の {where} に降り立ちますか？"
        if QMessageBox.question(self, tr("降り立つ"), msg) != QMessageBox.Yes:
            return
        self._set_body(body, (where, lat, ((lon + 180) % 360) - 180))

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
        v = self.view
        if isinstance(s, str):
            # コマ送り: 恒星日ずつなら星座が止まって見え、惑星の動き（逆行など）が分かる
            v.step_unit = SIDEREAL_DAY if s == "sidereal" else 1.0
            v.step_rate = float(self.sp_step.value())
            v.speed = -1.0 if self.chk_reverse.isChecked() else 1.0
            self.act_sp_step.setVisible(True)
        else:
            v.step_unit = None
            v.speed = -s if self.chk_reverse.isChecked() else s
            self.act_sp_step.setVisible(False)

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
            if v.ground_body != "earth":
                parts = [f"<b>{v.ground_place_name()}</b>（{v.gb_lat:+.2f}°・{v.gb_lon:+.2f}°）"]
            else:
                parts = [f"<b>地上から見た空</b>（{v.place}　北緯 {v.lat:.2f}°・東経 {v.lon:.2f}°）"]
            sun_alt, _ = v.ground_altaz("sun")
            if sun_alt > 0:
                parts.append(f"太陽の高度 {sun_alt:.0f}°（昼）")
            elif sun_alt > -18:
                parts.append(f"太陽の高度 {sun_alt:.0f}°（薄明）")
            else:
                parts.append(tr("夜"))
            if key in BY_KEY and key != v.ground_body:
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
