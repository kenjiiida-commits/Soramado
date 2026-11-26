import math

import numpy as np

from soramado import astro, minorplanets as mp, smallbodies as sbs

AST = """ Num   Name              Epoch      a          e        i         w        Node        M         H    G   Ref
------ ----------------- ----- ---------- ---------- --------- --------- --------- ----------- ----- ----- ----------
     1 Ceres             55400  2.7653485 0.07913825  10.58682  72.58981  80.39320 113.4104434  3.34  0.12 JPL 30
     2 Pallas            55400  2.7721795 0.23085769  34.84136 309.98823 173.12968  96.1483050  4.13  0.11 JPL 25
   433 Eros              55400  1.4581110 0.22265200  10.82830 178.66420 304.37060 320.2160000 10.43  0.46 JPL 600
"""

COM = """Num  Name                                     Epoch      q           e        i         w        Node          Tp       Ref
------------------------------------------- ------- ----------- ---------- --------- --------- --------- -------------- ------------
  1P/Halley                                   49400  0.58597811 0.96714291 162.26269 111.33249  58.42008 19860209.43867 JPL J863/77
"""


def _cat():
    return mp.MinorPlanets(mp.build_catalog(mp.parse_asteroids(AST), mp.parse_comets(COM)))


def test_parse():
    a = mp.parse_asteroids(AST)
    assert list(a["num"]) == [1, 2, 433]
    assert a["name"][2] == "Eros"
    assert abs(a["a"][0] - 2.7653485) < 1e-9
    c = mp.parse_comets(COM)
    assert c["name"][0] == "1P/Halley"
    assert abs(c["tp"][0] - astro.jd_from_datetime(__import__("datetime").datetime(1986, 2, 9, 10, 31, 41,
                                                     tzinfo=__import__("datetime").timezone.utc))) < 0.01


def test_kinds_and_names():
    cat = _cat()
    assert [int(k) for k in cat.kind] == [1, 1, 0, 7]
    assert cat.name(0) == "(1) Ceres"
    assert cat.name(3) == "1P/Halley"
    assert cat.find("eros") == [2]
    assert cat.find("433") == [2]
    assert 600 < cat.diameter_km(0) < 1100


def test_ceres_matches_small_body_module():
    cat = _cat()
    jd = 2461000.5
    p = cat.position(0, jd)
    q = sbs.position(sbs.BY_KEY["ceres"], jd)
    assert np.linalg.norm(p - q) < 0.05


def test_halley_perihelion():
    cat = _cat()
    jd = 2446470.94
    r = np.linalg.norm(cat.position(3, jd))
    assert abs(r - 0.586) < 0.01


def test_vertex_layout():
    v = _cat().vertex_data()
    assert v.shape == (4, 13) and v.dtype == np.float32
