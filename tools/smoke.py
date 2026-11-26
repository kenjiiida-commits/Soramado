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
for i in range(w.cb_target.count()):
    k = w.cb_target.itemData(i)
    if k: steps.append(lambda k=k: v.set_target(k, fly=False))
i = {"n": 0}
def step():
    if i["n"] >= len(steps):
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
