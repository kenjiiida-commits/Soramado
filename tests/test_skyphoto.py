import numpy as np

from soramado import hips, skyphoto


def test_build_places_tiles_by_direction():
    # 各タイルを、そのタイル番号の色で塗った Allsky を作り、正距円筒図の各点が正しいタイルから来るか確かめる
    tile_px = 8
    allsky = np.zeros((29 * tile_px, 27 * tile_px, 3), np.uint8)
    for t in range(768):
        y, x = (t // 27) * tile_px, (t % 27) * tile_px
        allsky[y:y + tile_px, x:x + tile_px, 0] = t % 256
        allsky[y:y + tile_px, x:x + tile_px, 1] = t // 256
    old_w, old_h = skyphoto.W, skyphoto.H
    skyphoto.W, skyphoto.H = 64, 32
    try:
        img = skyphoto.build(skyphoto.allsky_getter(allsky, tile_px), 3, tile_px)
    finally:
        skyphoto.W, skyphoto.H = old_w, old_h
    ra = (np.arange(64) + 0.5) / 64 * 360.0
    dec = 90.0 - (np.arange(32) + 0.5) / 32 * 180.0
    RA, DEC = np.meshgrid(ra, dec)
    want = hips.ang2pix_nest(3, RA, DEC)
    got = img[..., 0].astype(int) + img[..., 1].astype(int) * 256
    assert (got == want).mean() > 0.99


def test_process_keeps_shape_and_darkens_background():
    img = np.full((40, 60, 3), 40, np.uint8)
    img[15:25, :] = 230
    out = skyphoto.process(img)
    assert out.shape == img.shape
    assert out[0, 0].max() == 0
    assert out[20, 30].mean() > 100
