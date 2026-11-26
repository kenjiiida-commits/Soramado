"""共動距離を astropy の宇宙モデルと比べ、VizieR の表の読み取りを確かめる。"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from soramado import cosmos  # noqa: E402

try:
    from astropy.cosmology import FlatLambdaCDM
    HAVE = True
except ImportError:  # pragma: no cover
    HAVE = False


def test_comoving():
    if not HAVE:
        return
    cosmo = FlatLambdaCDM(H0=70, Om0=0.3, Tcmb0=2.725)
    worst = 0.0
    for z in (0.1, 0.5, 1, 2, 4, 7, 1090):
        ref = cosmo.comoving_distance(z).value
        worst = max(worst, abs(float(cosmos.comoving_mpc(z)) - ref) / ref)
    assert worst < 0.01, worst
    return worst


def test_parse():
    tsv = "#\n# VizieR\n\nRAJ2000\tDEJ2000\tz\ndeg\tdeg\t\n---\t---\t---\n10.5\t+20.1\t1.5\n11.0\t-3.0\t2.0\n"
    h, rows = cosmos.parse_tsv(tsv)
    assert h == ["RAJ2000", "DEJ2000", "z"] and len(rows) == 2
    assert cosmos._pick(h, ["Z", "z"]) == "z"
    assert abs(cosmos._sexa_to_deg("12 30 49.4", True) - 187.7058) < 1e-3


if __name__ == "__main__":
    print("共動距離（astropy との差、最大）:", test_comoving())
    test_parse()
    print("OK")
