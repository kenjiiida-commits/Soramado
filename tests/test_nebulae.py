import math

import numpy as np

from soramado import nebulae as N


def test_catalog():
    assert len(N.NEBULAE) >= 80
    ids = {n.id: n for n in N.NEBULAE}
    m42 = ids["NGC1976"]
    assert m42.type == "emn" and m42.m == 42
    # オリオン大星雲は赤経 5h35m、赤緯 -5.4°
    assert abs(m42.ra - 83.82) < 0.05 and abs(m42.dec + 5.39) < 0.05
    assert abs(np.linalg.norm(m42.pos) / N.LY_AU - 1344) < 1
    # すばるの見かけの大きさ（約2.5度）から、実際の大きさは約19光年
    assert 15 < ids["Mel022"].radius_ly * 2 < 25


def test_shapes():
    for n in N.NEBULAE:
        v = N.vertex_data(n)
        assert v.shape[1] == 7 and len(v) > 10
        assert np.isfinite(v).all()
        # 粒は天体の大きさの範囲にだいたい収まっている
        assert np.abs(v[:, :3]).max() < n.radius_au * 3
