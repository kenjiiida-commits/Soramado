"""探査機の航路の確認。

1. 弾道区間（ランベルト問題）が、出発点から到着点にきちんと届いていること。
2. ボイジャーの打ち上げ直後の軌道の遠日点が、実際の値（1号 約8.9AU、2号 約6.2AU）に近いこと。
3. 2026年11月の太陽からの距離が、公表値（1号 約173AU、2号 約144AU、ニュー・ホライズンズ 約66AU）に合うこと。
"""

import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from soramado import spacecraft as S  # noqa: E402


def _aphelion(r, v):
    rn = np.linalg.norm(r)
    a = -S.MU / (2 * (np.dot(v, v) / 2 - S.MU / rn))
    h = np.cross(r, v)
    e = np.linalg.norm(np.cross(v, h) / S.MU - r / rn)
    return a * (1 + e)


def test_legs():
    for sc in S.SPACECRAFT:
        for leg in sc.legs:
            if leg.kind == "lambert":
                r1, v1 = S._lambert_state(leg)
                r2 = S._body_pos(leg.b, leg.t1)
                assert np.linalg.norm(S.propagate(r1, v1, leg.t1 - leg.t0) - r2) < 1e-6, (sc.key, leg.b)
        # 区間のつなぎ目で位置が飛ばない
        for a, b in zip(sc.legs, sc.legs[1:]):
            assert np.linalg.norm(S.leg_position(a, a.t1) - S.leg_position(b, b.t0)) < 0.05, (sc.key, a.b)


def test_voyager():
    q1 = _aphelion(*S._lambert_state(S.BY_KEY["sc:voyager1"].legs[0]))
    q2 = _aphelion(*S._lambert_state(S.BY_KEY["sc:voyager2"].legs[0]))
    assert abs(q1 - 8.9) < 0.6 and abs(q2 - 6.2) < 0.6, (q1, q2)
    now = {k: float(np.linalg.norm(S.position(S.BY_KEY[k], S.ANCHOR_JD)))
           for k in ("sc:voyager1", "sc:voyager2", "sc:newhorizons")}
    assert abs(now["sc:voyager1"] - 173) < 2 and abs(now["sc:voyager2"] - 144.5) < 2
    assert abs(now["sc:newhorizons"] - 66) < 2
    return round(q1, 2), round(q2, 2), {k: round(v, 1) for k, v in now.items()}


if __name__ == "__main__":
    test_legs()
    print("ボイジャーの最初の軌道の遠日点 [AU] と 2026年11月の距離:", test_voyager())
    print("OK")
