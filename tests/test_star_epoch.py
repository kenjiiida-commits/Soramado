import numpy as np

from soramado.stars import StarCatalog


def test_epoch_moves_stars_and_lines():
    c = StarCatalog()
    i = list(c.proper).index("Arcturus")
    d0 = c.dir[i].copy()
    uma = [k for k, x in enumerate(c.constellations) if x.id == "UMa"][0]
    s0 = c.segments_at_epoch(uma).copy()
    c.set_epoch(1000.0)
    # アークトゥルスの固有運動は約2.3″/年 → 1000年で約0.64°
    moved = np.degrees(np.arccos(np.clip(np.dot(d0, c.dir[i]), -1, 1)))
    assert 0.5 < moved < 0.8
    s1 = c.segments_at_epoch(uma)
    assert s1.shape == s0.shape and not np.allclose(s0, s1)
    c.set_epoch(0.0)
    assert np.allclose(c.dir[i], d0) and np.allclose(c.segments_at_epoch(uma), s0)


def test_line_vertices_count_unchanged():
    c = StarCatalog()
    n = len(c.line_vertices())
    c.set_epoch(-50000.0)
    assert len(c.line_vertices()) == n
