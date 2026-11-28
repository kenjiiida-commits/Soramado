from soramado import recorder as r


def test_music_filter_segments():
    files, g = r.music_filter([(0.0, "a.mp3"), (5.0, "b.ogg"), (8.0, None)], 10.0)
    assert files == ["a.mp3", "b.ogg"]
    assert "amix=inputs=2" in g and "adelay=5000" in g and "atrim=0:5.000" in g and "atrim=0:3.000" in g


def test_music_filter_none():
    assert r.music_filter([(0.0, None)], 5.0) == ([], "")
    files, g = r.music_filter([(0.0, "a.mp3")], 6.0)
    assert files == ["a.mp3"] and "afade=t=out:st=3.000:d=3.000" in g and "amix" not in g
