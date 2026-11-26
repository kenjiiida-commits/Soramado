"""探査機の航路の確認。

1. はやぶさ（計算で作った航路）の区間のつなぎ目で位置が飛ばないこと。
2. JPL Horizons の表を使う探査機が、訪れた天体のそばにいること（画面の天体に合わせてずらしたあと）。
3. 2026年11月の太陽からの距離が、公表値（ボイジャー1号 約173AU、2号 約144AU、ニュー・ホライズンズ 約66AU）に合うこと。
"""

import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from soramado import astro  # noqa: E402
from soramado import smallbodies as sb  # noqa: E402
from soramado import spacecraft as S  # noqa: E402


def test_legs():
    for sc in S.SPACECRAFT:
        for leg in sc.legs:
            if leg.kind == "lambert":
                r1, v1 = S._lambert_state(leg)
                r2 = S._body_pos(leg.b, leg.t1)
                assert np.linalg.norm(S.propagate(r1, v1, leg.t1 - leg.t0) - r2) < 1e-6, (sc.key, leg.b)
        for a, b in zip(sc.legs, sc.legs[1:]):
            assert np.linalg.norm(S.leg_position(a, a.t1) - S.leg_position(b, b.t0)) < 0.05, (sc.key, a.b)


def test_voyager_and_far_probes():
    now = {k: float(np.linalg.norm(S.position(S.BY_KEY[k], S.ANCHOR_JD)))
           for k in ("sc:voyager1", "sc:voyager2", "sc:newhorizons")}
    assert abs(now["sc:voyager1"] - 173) < 2 and abs(now["sc:voyager2"] - 144.5) < 2
    assert abs(now["sc:newhorizons"] - 66) < 2
    # 表の終わりのあとも、まっすぐ進み続ける
    assert np.linalg.norm(S.position(S.BY_KEY["sc:voyager1"], S._jd(2040, 1, 1))) > 210
    # 木星に最接近した日には木星のすぐそば
    t = S._jd(1979, 3, 5)
    assert np.linalg.norm(S.position(S.BY_KEY["sc:voyager1"], t) - astro.planet_position("jupiter", t)) < 0.05


def test_table_spacecraft_near_targets():
    cases = [("sc:cassini", "saturn", (2010, 1, 1), 0.05), ("sc:juno", "jupiter", (2020, 1, 1), 0.06),
             ("sc:dawn", "vesta", (2012, 1, 1), 0.01), ("sc:rosetta", "67p", (2015, 6, 1), 0.01),
             ("sc:osirisrex", "bennu", (2019, 6, 1), 0.01)]
    for key, body, date, lim in cases:
        t = S._jd(*date)
        q = sb.position(sb.BY_KEY[body], t) if body in sb.BY_KEY else astro.planet_position(body, t)
        assert np.linalg.norm(S.position(S.BY_KEY[key], t) - q) < lim, key


def test_span_and_after_end():
    sc = S.BY_KEY["sc:cassini"]
    t0, t1 = S.span(sc)
    assert S.position(sc, t0 - 10) is None and S.position(sc, t1 + 10) is None
    assert S.position(sc, (t0 + t1) / 2) is not None


if __name__ == "__main__":
    test_legs()
    test_voyager_and_far_probes()
    test_table_spacecraft_near_targets()
    print("OK")
