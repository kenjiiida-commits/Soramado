"""画面の操作をひととおり自動で試す（開発者用）。

使い方: xvfb-run -a python3 tools/smoke.py [データのフォルダ]
ツアー・天文現象・今夜の空ガイド・星座の形の変化・風景・光害・大気なし・コマ送り・探査機などを順に動かし、
最後に「steps 〇 errors 0」と出れば成功。設定は一時フォルダ（環境変数 SMOKE_CFG）に書く。
"""
import sys, os, traceback, math
sys.path.insert(0, str(__import__('pathlib').Path(__file__).resolve().parents[1]))
data = sys.argv[1] if len(sys.argv) > 1 else __import__("tempfile").mkdtemp()
os.environ["XDG_DATA_HOME"] = data; os.environ["XDG_CONFIG_HOME"] = os.environ.get("SMOKE_CFG", "/tmp/smokecfg")
from PySide6.QtCore import QTimer
from PySide6.QtGui import QSurfaceFormat
from PySide6.QtWidgets import QApplication, QDialog, QMessageBox
fmt = QSurfaceFormat(); fmt.setVersion(3,3); fmt.setProfile(QSurfaceFormat.CoreProfile); fmt.setDepthBufferSize(24); QSurfaceFormat.setDefaultFormat(fmt)
app = QApplication(sys.argv)
errs = []
def hook(t, v, tb): errs.append("".join(traceback.format_exception(t, v, tb)))
sys.excepthook = hook
QDialog.exec = lambda self: 0
QMessageBox.question = staticmethod(lambda *a, **k: QMessageBox.No)
QMessageBox.information = staticmethod(lambda *a, **k: 0)
QMessageBox.warning = staticmethod(lambda *a, **k: 0)
QMessageBox.about = staticmethod(lambda *a, **k: 0)
from soramado.app import make_window
from soramado import tours
w = make_window(); w.settings.setValue("asked_textures", True); w.resize(1200,800); w.show(); v = w.view
steps = []
for tid, _t, _f in tours.TOURS:
    steps.append(lambda tid=tid: w.start_tour(tid))
    steps.append(lambda: w._tour_go(+1))
    steps.append(lambda: w._tour_go(+1))
    steps.append(lambda: w.stop_tour())
steps += [lambda: w._show_eclipses(), lambda: w._show_showers(), lambda: w._show_events(), lambda: w._show_passes(),
          lambda: w._find_minor(), lambda: w._show_manual(), lambda: w._about() if hasattr(w, "_about") else None,
          lambda: w.btn_ground.setChecked(True), lambda: v.set_jd(2461389.0), lambda: w.btn_ground.setChecked(False),
          lambda: v.set_target("saturn"), lambda: w.sl_mag.setValue(200), lambda: w.sl_mag.setValue(0)]
# v2.6〜2.13 で増えた機能
from PySide6.QtCore import QUrl
from soramado.app import SPEEDS
from soramado import landscape
def close(attr):
    d = getattr(w, attr, None)
    if d is not None:
        d.close()
steps += [lambda: w._show_tonight(), lambda: close("_tn_dlg"),
          lambda: w._show_epoch_panel(), lambda: v.set_star_epoch(50000.0), lambda: v.set_star_epoch(-150000.0),
          lambda: w._look_constellation(0), lambda: v.set_star_epoch(0.0), lambda: close("_ep_dlg"),
          lambda: w.btn_ground.setChecked(True)]
for key, _ja, _en in landscape.PRESETS:
    steps.append(lambda k=key: w._set_landscape(k, save=False))
for b in (1, 5, 9, 3):
    steps.append(lambda b=b: w._set_bortle(b))
steps += [lambda: w._set_mw_level(3), lambda: w._set_mw_level(2),
          lambda: setattr(v, "show_atmosphere", False), lambda: setattr(v, "show_atmosphere", True),
          lambda: w.btn_airless.setChecked(True),
          lambda: w.cb_speed.setCurrentIndex(len(SPEEDS) - 2), lambda: setattr(v, "paused", False),
          lambda: v.set_jd(v.jd + 20), lambda: w.cb_speed.setCurrentIndex(len(SPEEDS) - 1),
          lambda: w.chk_reverse.setChecked(True), lambda: w.chk_reverse.setChecked(False),
          lambda: v.set_jd(2378496.5), lambda: v.set_jd(2525000.5),          # 1800年・2200年
          lambda: v.clear_trails(), lambda: w.btn_airless.setChecked(False),
          lambda: w._set_landscape("none", save=False), lambda: w.cb_speed.setCurrentIndex(5),
          lambda: setattr(v, "paused", True), lambda: w.btn_ground.setChecked(False),
          lambda: v.set_target("sc:hayabusa", fly=False), lambda: w._update_panel(force=True),
          lambda: w._on_panel_link(QUrl("jd:2453625.0")), lambda: v.set_jd(2461371.0),
          lambda: v.reload_photos(), lambda: v.reload_mwphoto()]
# 飛び立つ・着陸する（途中でボタン・天体の選択・クリックをしても壊れないか）
wait = lambda: [__import__("time").sleep(0.2), app.processEvents()]
steps += [lambda: w.btn_ground.click(), wait, wait, wait, lambda: w.btn_ground.click(), wait, wait,
          lambda: v.set_target("mars"), lambda: w.btn_ground.click(), wait, wait, wait, wait,
          lambda: v._finish_lift(), lambda: w.btn_ground.click(), wait, lambda: v.look_at("moon"),
          lambda: w.btn_ground.click(), wait, wait, wait, wait, wait, wait, wait, wait, wait, wait,
          wait, wait, wait, wait, wait, wait, wait, wait, wait, wait, wait, wait, wait, wait, wait, wait,
          lambda: w.btn_ground.click(), wait, lambda: w.start_tour(__import__("soramado.tours", fromlist=["x"]).TOURS[0][0]),
          lambda: w.stop_tour(), lambda: setattr(v, "show_lift", False), lambda: w.btn_ground.click(),
          lambda: w.btn_ground.click(), lambda: setattr(v, "show_lift", True),
          lambda: w._set_ground_checked(False)]
# 空の線（宇宙・地上・大気なし・英語の月名）
steps += [lambda: w.btn_ecl.setChecked(True), lambda: w.act_equ.setChecked(True), lambda: v.set_target("earth", fly=False),
          lambda: v.set_target("saturn", fly=False), lambda: w._set_ground_checked(True),
          lambda: w.act_mer.setChecked(True), lambda: w.act_altaz.setChecked(True),
          lambda: setattr(v, "g_alt", 1.55), lambda: setattr(v, "g_alt", -0.3), lambda: w.btn_airless.setChecked(True),
          lambda: setattr(v, "g_fov", 2.0), lambda: setattr(v, "g_fov", 90.0), lambda: w.btn_airless.setChecked(False),
          lambda: v.set_jd(2378496.5), lambda: v.set_jd(2461371.0), lambda: w._set_ground_checked(False),
          lambda: setattr(v, "dist", 5e6), lambda: v.set_target("earth", fly=False),
          lambda: [a.setChecked(False) for a in (w.act_ecl, w.act_equ, w.act_mer, w.act_altaz)]]
# 天体望遠鏡モード（宇宙から入る・望遠鏡と接眼レンズを全部・像の向き・追尾・ホイール・宇宙へ戻る）
steps += [lambda: w._set_ground_checked(False), lambda: w.btn_scope.setChecked(True), lambda: v.look_at("jupiter"),
          lambda: w.chk_track.setChecked(True), lambda: v.set_jd(v.jd + 0.05), lambda: v.set_jd(v.jd + 0.05),
          lambda: v.scopeStep.emit(1), lambda: v.scopeStep.emit(1), lambda: v.scopeStep.emit(-1)]
steps += [(lambda i=i: w.cb_scope.setCurrentIndex(i)) for i in range(w.cb_scope.count())]
steps += [(lambda i=i: w.cb_eye.setCurrentIndex(i)) for i in range(w.cb_eye.count())]
steps += [(lambda i=i: w.cb_image.setCurrentIndex(i)) for i in range(w.cb_image.count())]
steps += [lambda: v.look_at("moon"), lambda: v.look_at("saturn"), lambda: w.btn_airless.setChecked(True),
          lambda: w.btn_airless.setChecked(False), lambda: w.chk_track.setChecked(False), lambda: v.set_jd(v.jd + 0.01),
          lambda: w.btn_ground.click(), lambda: v._finish_lift(), lambda: w.btn_scope.setChecked(True),
          lambda: w.btn_scope.setChecked(False), lambda: w._set_ground_checked(False)]
# 月・火星に降り立つ（地形データなし → 試験用の地形あり、場所をすべて、宇宙から着陸、ダブルクリックで着陸、望遠鏡、ツアーで地球へ）
import numpy as _np
from soramado import terrain as _T
def _fake_dem():
    for b in ("moon", "mars"):
        _T._cache[b] = (_np.random.default_rng(1).normal(0, 800, (_T.H // 16, _T.W // 16)).astype(_np.int16)
                        .repeat(16, 0).repeat(16, 1))
    v.reload_terrain = lambda: None
    if v.ground_body != "earth":
        v._build_terrain()
steps += [lambda: w._set_body("moon"), wait, wait, lambda: v._finish_lift(), lambda: w._set_body("mars"),
          lambda: setattr(v, "g_alt", -0.5), lambda: setattr(v, "g_alt", 1.5), lambda: v.set_jd(v.jd + 0.3),
          lambda: w._set_body("earth"), lambda: w._set_ground_checked(False), _fake_dem]
for _b in ("moon", "mars"):
    steps += [(lambda b=_b: w._set_body(b, animate=False))]
    steps += [(lambda i=i: (w.cb_place.setCurrentIndex(i), w._on_place(i))) for i in range(len(_T.PLACES[_b]))]
    steps += [lambda: v.look_at("earth"), lambda: v.look_at("sun"), lambda: w.btn_airless.setChecked(True),
              lambda: w.btn_airless.setChecked(False), lambda: w.btn_scope.setChecked(True), lambda: v.look_at("jupiter"),
              lambda: w.btn_scope.setChecked(False), lambda: w.btn_ground.click(), wait, lambda: v._finish_lift()]
# 台本（見本を流して途中で止める・間違いのある台本・英語の命令）
from soramado import script as _scr
def _chk(cond, msg):
    if not cond: errs.append(msg)
# 火星にいるときに台本を始めても、地球から始まる。行き先のない「着陸」は、見ている天体へ
steps += [lambda: w._set_body("mars", animate=False), lambda: w.play_script("待つ 0.1", "reset"),
          lambda: _chk(v.ground_body == "earth", "script did not reset to earth"), lambda: w.stop_tour(),
          lambda: w._set_ground_checked(False), lambda: v.set_target("moon", fly=False),
          lambda: w.play_script("着陸", "land-moon"), wait, lambda: v._finish_lift(),
          lambda: _chk(v.ground_body == "moon", "plain land did not go to moon: " + v.ground_body),
          lambda: w.stop_tour(), lambda: w._reset_to_earth()]
steps += [lambda: w.play_script(_scr.SAMPLE, "見本"), wait, wait, wait, wait, wait, lambda: w._tour_go(1),
          wait, wait, lambda: w.stop_tour(), lambda: w.play_script("とぶ 月\n待つ x", "bad"),
          lambda: w.play_script("fly jupiter\norbit 30 1\nzoom 10au\ncaption hi\nwait 0.5\nland moon\n"
                                "look earth\nfov 10\nscope dob200 9\nscope なし\nlines 黄道 on\nairless on\n"
                                "airless off\ntime sunset\nfly ないもの\nland earth 大阪\nplace 35.36 138.73\n", "en"),
          wait, wait, wait, wait, wait, wait, wait, wait, wait, wait, lambda: w.stop_tour(),
          lambda: w._set_ground_checked(False)]
steps += [lambda: v.set_target("mars", fly=False), lambda: w._land_request("mars", 10.0, 200.0), wait, wait,
          lambda: v._finish_lift(), lambda: w.btn_ground.click(), lambda: v._finish_lift(),
          lambda: v.set_target("moon", fly=False), lambda: v._surface_at("moon", 500, 350),
          lambda: w.start_tour(tours.TOURS[0][0]), lambda: w.stop_tour(), lambda: w._set_ground_checked(False)]
for i in range(w.cb_target.count()):
    k = w.cb_target.itemData(i)
    if k: steps.append(lambda k=k: v.set_target(k, fly=False))
i = {"n": 0}
def step():
    if i["n"] >= len(steps):
        if v.lifting():
            errs.append("lift did not finish")
        if v.ground_body != "earth":
            errs.append("still on " + v.ground_body)
        if v.scope is not None or w.btn_scope.isChecked():
            errs.append("scope still on")
        print("steps", len(steps), "errors", len(errs))
        for e in errs[:5]: print(e)
        app.quit(); return
    print("step", i["n"], flush=True)
    try:
        steps[i["n"]]()
    except Exception:
        errs.append(traceback.format_exc())
    i["n"] += 1
    v._fly = None
    QTimer.singleShot(60, step)
QTimer.singleShot(1500, step); app.exec()
