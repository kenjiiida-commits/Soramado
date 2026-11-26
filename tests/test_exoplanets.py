import math

import numpy as np

from soramado import exoplanets as ex

CSV = """hostname,pl_name,pl_letter,ra,dec,sy_dist,sy_vmag,sy_pnum,st_teff,st_rad,st_mass,st_spectype,pl_rade,pl_bmasse,pl_orbper,pl_orbsmax,pl_orbeccen,pl_eqt,pl_insol,discoverymethod,disc_year
Proxima Cen,Proxima Cen b,b,217.39232,-62.67607,1.30119,11.13,2,3050,0.141,0.12,M5.5 V,,1.07,11.1868,0.04856,0.02,234,0.65,Radial Velocity,2016
51 Peg,51 Peg b,b,344.36658,20.76883,15.4614,5.46,1,5768,1.15,1.09,G2 IV,,146,4.2308,0.0527,0.013,,,Radial Velocity,1995
TRAPPIST-1,TRAPPIST-1 c,c,346.6264,-5.0435,12.4299,18.8,7,2566,0.119,0.0898,M8,1.097,,2.4218,0.0158,0,,,Transit,2016
TRAPPIST-1,TRAPPIST-1 b,b,346.6264,-5.0435,12.4299,18.8,7,2566,0.119,0.0898,M8,1.116,,1.5108,0.01154,0,,,Transit,2016
NoDist,NoDist b,b,10,10,,,1,,,,,,,,,,,,Transit,2020
"""


def test_parse_and_group():
    s = ex.parse_csv(CSV)
    assert [x["host"] for x in s] == ["Proxima Cen", "TRAPPIST-1", "51 Peg"]     # 近い順、距離不明は省く
    assert [p["letter"] for p in s[1]["planets"]] == ["b", "c"]                   # 恒星に近い順


def test_types_and_hz():
    e = ex.Exoplanets(ex.parse_csv(CSV))
    peg = e.systems[2]["planets"][0]
    assert peg["type"] == "hotjupiter"
    prox = e.systems[0]["planets"][0]
    assert prox["type"] == "rocky" and e.in_hz(prox)
    assert e.find("trappist-1 c") == [1]


def test_position():
    e = ex.Exoplanets(ex.parse_csv(CSV))
    d = np.linalg.norm(e.pos[0]) / ex.LY_AU
    assert abs(d - 4.24) < 0.02            # プロキシマ・ケンタウリまで 4.24 光年
    # 恒星の方向が、赤経・赤緯と合っている
    from soramado import astro
    ra, dec = math.radians(217.39232), math.radians(-62.67607)
    v = astro.equatorial_to_ecliptic(np.array([math.cos(dec) * math.cos(ra), math.cos(dec) * math.sin(ra),
                                               math.sin(dec)]))
    assert np.dot(v, e.pos[0] / np.linalg.norm(e.pos[0])) > 0.99999


def test_planet_offsets():
    e = ex.Exoplanets(ex.parse_csv(CSV))
    offs = e.planet_offsets(1, 2461370.5)
    assert len(offs) == 2
    assert abs(np.linalg.norm(offs[0]) - 0.01154) < 0.001
