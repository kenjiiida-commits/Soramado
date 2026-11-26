import numpy as np

from soramado import hips


def test_ang2pix_known_values():
    # healpy.ang2pix(nside, ra, dec, nest=True, lonlat=True) で求めた値
    assert int(hips.ang2pix_nest(0, 0.0, 0.0)) == 4
    assert int(hips.ang2pix_nest(0, 45.0, 60.0)) == 0
    assert int(hips.ang2pix_nest(0, 45.0, -60.0)) == 8


def test_plan_center_tile_and_consistency():
    # 環状星雲のまわり（order 9）: 実際に ESA のタイル 950641/950643 で並びを確かめた
    k, tiles, row, col = hips.plan(283.3959, 33.0286, 0.04, 512)
    assert k == 9
    assert set(np.unique(tiles).tolist()) == {950641, 950643}
    assert row.min() >= 0 and row.max() < 512 and col.min() >= 0 and col.max() < 512


def test_tile_url():
    assert hips.tile_url("B", 6, 21435) == "B/Norder6/Dir20000/Npix21435.jpg"


def test_assemble_picks_pixels():
    tiles = np.array([[1, 2]])
    row = np.array([[3, 4]])
    col = np.array([[5, 6]])
    a = np.zeros((512, 512, 3), np.uint8)
    b = np.zeros((512, 512, 3), np.uint8)
    a[3, 5] = 10
    b[4, 6] = 20
    out = hips.assemble({1: a, 2: b}, tiles, row, col)
    assert out[0, 0, 0] == 10 and out[0, 1, 0] == 20
