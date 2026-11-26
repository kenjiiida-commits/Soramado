"""衛星の位置の確認。

1. 木星のガリレオ衛星を、Meeus『天文計算』の簡易式（東西の離角）と比べる。
2. 衛星の軌道面が、惑星の赤道面（自転軸）とほぼ一致していることを確かめる。
"""

import math
import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from soramado import astro, satellites as S  # noqa: E402
from soramado.bodies import BY_KEY  # noqa: E402


def _meeus_x(jd):
    """Meeus の簡易式による、ガリレオ衛星の西向きの離角 [木星半径]。"""
    r = math.radians
    s, c = (lambda x: math.sin(r(x))), (lambda x: math.cos(r(x)))
    d = jd - 2451545.0
    V = 172.74 + 0.00111588 * d
    M = 357.529 + 0.9856003 * d
    N = 20.020 + 0.0830853 * d + 0.329 * s(V)
    J = 66.115 + 0.9025179 * d - 0.329 * s(V)
    A = 1.915 * s(M) + 0.020 * s(2 * M)
    B = 5.555 * s(N) + 0.168 * s(2 * N)
    K = J + A - B
    R = 1.00014 - 0.01671 * c(M) - 0.00014 * c(2 * M)
    rr = 5.20872 - 0.25208 * c(N) - 0.00611 * c(2 * N)
    D = math.sqrt(rr * rr + R * R - 2 * rr * R * c(K))
    psi = math.degrees(math.asin(R / D * s(K)))
    t = d - D / 173
    u = [163.8069 + 203.4058646 * t, 358.4140 + 101.2916335 * t,
         5.7176 + 50.2345180 * t, 224.8092 + 21.4879800 * t]
    u = [x + psi - B for x in u]
    G, H = 331.18 + 50.310482 * t, 87.45 + 21.569231 * t
    u[0] += 0.473 * s(2 * (u[0] - u[1]))
    u[1] += 1.065 * s(2 * (u[1] - u[2]))
    u[2] += 0.165 * s(G)
    u[3] += 0.843 * s(H)
    rad = [5.9057 - 0.0244 * c(2 * (u[0] - u[1])), 9.3966 - 0.0882 * c(2 * (u[1] - u[2])),
           14.9883 - 0.0216 * c(G), 26.3627 - 0.1939 * c(H)]
    return [ri * s(ui) for ri, ui in zip(rad, u)]


def test_galilean():
    if not S.available():
        return
    worst = {}
    radii = {"io": 5.9, "europa": 9.4, "ganymede": 15.0, "callisto": 26.4}
    for jd in np.linspace(2460000.5, 2462000.5, 25):
        pos = S.add_positions(astro.all_positions(jd), jd)
        los = pos["jupiter"] - pos["earth"]
        los /= np.linalg.norm(los)
        # Meeus の X は「木星の赤道に沿った」西向きの離角なので、木星の自転軸を空に投影して使う
        pole = astro.pole_vector(268.056595, 64.495303)
        pole_sky = pole - los * np.dot(pole, los)
        west = -np.cross(pole_sky, los)
        west /= np.linalg.norm(west)
        for k, xm in zip(("io", "europa", "ganymede", "callisto"), _meeus_x(jd)):
            x = float(np.dot(pos[k] - pos["jupiter"], west)) * astro.AU_KM / 71492.0
            # 軌道半径に対する角度のずれ [度] に直して評価する
            worst[k] = max(worst.get(k, 0.0), math.degrees(abs(x - xm) / radii[k]))
    for k, v in worst.items():
        assert v < 6.0, (k, v)     # 比べる相手（Meeus の簡易式）自体の誤差もあるので、公転位置で 6 度以内
    return {k: round(v, 2) for k, v in worst.items()}


def test_planes():
    if not S.available():
        return
    jd = 2461005.5
    worst = 0.0
    for key, pts in S.orbit_paths(jd, 60).items():
        parent = BY_KEY[S.BY_KEY[key].parent]
        n = np.linalg.svd(pts - pts.mean(0))[2][-1]
        pole = astro.pole_vector(parent.pole_ra, parent.pole_dec)
        ang = math.degrees(math.acos(min(1.0, abs(float(np.dot(n, pole))))))
        if key != "iapetus":        # イアペトゥスは軌道が約15度傾いている
            worst = max(worst, ang)
            # もともとの軌道傾斜（ミランダは約4度）＋計算のずれ 4度まで
            assert ang < 4.0 + S.BY_KEY[key].i, (key, ang)
    return worst


if __name__ == "__main__":
    print("ガリレオ衛星（Meeus の簡易式との公転位置のずれ、最大）[度]:", test_galilean())
    print("軌道面と惑星の赤道面のずれ（最大）[度]:", test_planes())
    print("OK")
