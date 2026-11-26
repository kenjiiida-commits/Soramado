from datetime import datetime, timezone

from soramado import astro, events as E


def test_shower_peaks():
    if not E.available():
        return
    jd = astro.jd_from_datetime(datetime(2027, 1, 1, tzinfo=timezone.utc))
    nights = E.shower_nights(jd, 365, 34.69, 135.50)
    peaks = {n.shower.key: astro.datetime_from_jd(n.jd_peak) for n in nights}
    assert (peaks["per"].month, peaks["per"].day) in ((8, 12), (8, 13))      # ペルセウス座流星群
    assert (peaks["gem"].month, peaks["gem"].day) in ((12, 14), (12, 15))    # ふたご座流星群
    assert peaks["qua"].month == 1 and 3 <= peaks["qua"].day <= 4            # しぶんぎ座流星群


def test_oppositions():
    if not E.available():
        return
    jd = astro.jd_from_datetime(datetime(2027, 1, 1, tzinfo=timezone.utc))
    ev = E.find_events(jd, 300, 34.69, 135.50)
    opp = {e.keys[0]: astro.datetime_from_jd(e.jd) for e in ev if e.kind == "opposition"}
    assert opp["mars"].month == 2 and 18 <= opp["mars"].day <= 20          # 2027年2月19日ごろ
    assert opp["jupiter"].month == 2 and 9 <= opp["jupiter"].day <= 12
