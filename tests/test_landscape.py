import numpy as np

from soramado import landscape


def test_presets_have_profile_and_sky_is_transparent():
    for key, _ja, _en in landscape.PRESETS:
        ls = landscape.make(key)
        if key == "none":
            assert ls is None
            continue
        assert ls.rgba.shape == (landscape.H, landscape.W, 4)
        assert ls.rgba[0, :, 3].max() == 0                 # 天頂は透明
        assert -5.0 < ls.profile.max() < 25.0
        assert ls.height_at(0) == ls.height_at(360)


def test_from_image_north_offset():
    img = np.zeros((50, 100, 4), np.uint8)
    img[30:, 0:10, 3] = 255                                 # 左はし（10%ぶん）だけ高い所がある
    img[45:, :, 3] = 255
    ls = landscape.from_image(img, north_deg=90.0)          # 左はしが東 → 高い所は東
    assert ls.height_at(95.0) > ls.height_at(200.0)
