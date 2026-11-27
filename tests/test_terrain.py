import math

import numpy as np

from soramado import terrain as T


def test_decode_picks_smooth_byte_order():
    a = (np.add.outer(np.arange(T.H), np.arange(T.W)) % 2000).astype(np.int16)
    for dt in (">i2", "<i2"):
        m = T.decode(a.astype(dt).tobytes(), 0.5)
        assert m.dtype == np.int16
        assert int(m[10, 20]) == round(0.5 * a[10, 20])


def test_height_interpolation_and_wrap():
    dem = np.zeros((T.H, T.W), np.int16)
    dem[:, 0] = 1000
    dem[:, -1] = 1000
    # 東経0度の線の上は1km、ずっと東は0km、経度は360度でつながる
    assert abs(float(T.height_km(dem, 0.0, 0.0)) - 1.0) < 0.01
    assert float(T.height_km(dem, 0.0, 90.0)) == 0.0
    assert abs(float(T.height_km(dem, 0.0, 359.99)) - 1.0) < 0.01


def test_horizon_sees_mountain_in_the_east():
    dem = np.zeros((T.H, T.W), np.int16)
    yy, xx = np.mgrid[0:T.H, 0:T.W]
    y0, x0 = 90 * 16, 10 * 16 + 30           # 赤道・東経10度の観測地から、東に約1.9度
    dem[:] = (3000 * np.exp(-((yy - y0) ** 2 + (xx - x0) ** 2) / 40)).astype(np.int16)
    T._cache["moon"] = dem
    try:
        tri, horizon, h0 = T.build("moon", 0.0, 10.0, 1737.4)
    finally:
        T.forget("moon")
    assert tri.shape[1] == 8 and len(tri) % 3 == 0
    assert np.isfinite(tri).all()
    east = horizon[180]                       # 方位90度
    west = horizon[540]
    assert east > 0.5 and east > west + 0.5
    assert abs(int(np.argmax(horizon)) * 0.5 - 90) < 10


def test_places_are_on_the_body():
    for body, places in T.PLACES.items():
        assert body in T.SOURCES
        for name, lat, lon in places:
            assert -90 <= lat <= 90 and -180 <= lon <= 180, name


def test_light_version_and_level(tmp_path, monkeypatch):
    monkeypatch.setattr(T, "data_dir", lambda: tmp_path)
    w, h = T.LEVELS[4]
    raw = (np.add.outer(np.arange(h), np.arange(w)) % 1000).astype(">i2").tobytes()
    dem = T.decode(raw, 1.0)
    assert dem.shape == (h, w)
    assert T.level("mars") == 0
    np.save(T.path("mars", 4), dem)
    T.forget("mars")
    assert T.level("mars") == 4 and T.available("mars") and not T.available("mars", 16)
    got = T.load("mars")
    assert got.shape == (h, w)
    # 1/4度ごとの図でも、高さの読み取りが合う（緯度 90-0.125*... の点の中心）
    assert abs(float(T.height_km(got, 90 - 0.125 - 10 * 0.25, 0.125 + 20 * 0.25)) - 0.030) < 1e-6
    T.forget("mars")
