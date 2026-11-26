"""探査機の航路データを作る（開発者用。普段は使わない）。

入力: NASA JPL Horizons の位置ベクトル（太陽中心・黄道座標 J2000・AU）の CSV 出力を、探査機ごとに
      <名前>.txt として1つのフォルダに入れたもの。取り方は README の「探査機の航路データ」を参照。
      訪れた天体（惑星・小惑星・彗星）の位置も、同じ形で別のフォルダに入れる（body/<天体のキー>.txt）。
出力: soramado/data/spacecraft_paths.npz（<名前>_jd と <名前>_xyz）

そらみ窓の惑星や小惑星の位置は簡単な式で計算しているので、JPL の正確な位置と少しずれる
（土星で 0.02 AU、67P 彗星では 1 AU 以上）。探査機が天体の近くにいるあいだは、
「そらみ窓の天体の位置 − JPL の天体の位置」だけ探査機をずらして、画面の天体に合わせる。
Horizons の出力は米国政府（NASA/JPL）の公開データ。
"""

import sys
from pathlib import Path

import numpy as np

OUT = Path(__file__).resolve().parents[1] / "soramado" / "data" / "spacecraft_paths.npz"


def parse(path):
    s = path.read_text()
    if "$$SOE" not in s:
        raise ValueError(f"{path.name}: データがありません")
    rows = s.split("$$SOE")[1].split("$$EOE")[0].strip().splitlines()
    jd, xyz = [], []
    for r in rows:
        c = [x.strip() for x in r.split(",")]
        jd.append(float(c[0]))
        xyz.append([float(c[2]), float(c[3]), float(c[4])])
    return np.array(jd), np.array(xyz, np.float32)


# 天体ごとに、ずれを全部直す距離 R1 と、まったく直さない距離 R2 [AU]
RANGES = {"jupiter": (0.08, 0.5), "saturn": (0.08, 0.5), "uranus": (0.03, 0.3), "neptune": (0.03, 0.3)}
SMALL = ("vesta", "ceres", "ryugu", "bennu", "67p", "pluto")


def _model(key, jd):
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
    from soramado import astro, smallbodies as sb
    from soramado.spacecraft import _body_pos
    if key == "earth":
        return _body_pos("earth", jd)
    if key in sb.BY_KEY:
        return sb.position(sb.BY_KEY[key], jd)
    return astro.planet_position(key, jd)


def correct(jd, xyz, bodies):
    """天体の近くでは、そらみ窓の天体の位置に合うように探査機をずらす。"""
    out = xyz.astype(np.float64).copy()
    best_w = np.zeros(len(jd))
    shift = np.zeros_like(out)
    for key, (bjd, bxyz) in bodies.items():
        m = (jd >= bjd[0]) & (jd <= bjd[-1])
        if not m.any():
            continue
        hb = np.stack([np.interp(jd[m], bjd, bxyz[:, k]) for k in range(3)], axis=1)
        d = np.linalg.norm(xyz[m] - hb, axis=1)
        r1, r2 = RANGES.get(key, (0.02, 0.15) if key in SMALL else (0.03, 0.2))
        t = np.clip((d - r1) / (r2 - r1), 0, 1)
        w = 1 - t * t * (3 - 2 * t)
        idx = np.where(m)[0]
        sel = w > best_w[idx]
        if not sel.any():
            continue
        ii = idx[sel]
        model = np.array([_model(key, t_) for t_ in jd[ii]])
        shift[ii] = (model - hb[sel]) * w[sel][:, None]
        best_w[ii] = w[sel]
    return (out + shift).astype(np.float32)


def main(folder, body_folder=None):
    bodies = {}
    if body_folder:
        for p in sorted(Path(body_folder).glob("*.txt")):
            bodies[p.stem] = parse(p)
            print(f"天体 {p.stem:10s} {len(bodies[p.stem][0]):5d}")
    out = {}
    for p in sorted(Path(folder).glob("*.txt")):
        try:
            jd, xyz = parse(p)
        except ValueError as e:
            print(e)
            continue
        if bodies:
            xyz = correct(jd, xyz, bodies)
        out[f"{p.stem}_jd"] = jd
        out[f"{p.stem}_xyz"] = xyz
        print(f"{p.stem:15s} {len(jd):5d}")
    np.savez_compressed(OUT, **out)
    print(OUT, OUT.stat().st_size)


if __name__ == "__main__":
    main(sys.argv[1], sys.argv[2] if len(sys.argv) > 2 else None)
