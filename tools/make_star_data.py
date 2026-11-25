"""恒星・星座のデータファイルを作る（開発者用。普段は使わない）。

入力:
  HYG データベース v4.1  (https://github.com/astronexus/HYG-Database, CC BY-SA 4.0)
      hyg/CURRENT/hygdata_v41.csv
  d3-celestial          (https://github.com/ofrohn/d3-celestial, BSD 3-Clause)
      data/constellations.json, data/constellations.lines.json
出力:
  soramado/data/stars.npz
  soramado/data/constellations.json

使い方:
  python3 tools/make_star_data.py HYG.csv constellations.json constellations.lines.json
"""

import csv
import json
import math
import sys
from pathlib import Path

import numpy as np

OUT = Path(__file__).resolve().parents[1] / "soramado" / "data"


def main(hyg_csv, cons_json, lines_json):
    OUT.mkdir(parents=True, exist_ok=True)
    xs, ys, zs, mags, cis = [], [], [], [], []
    hips, dists, propers, bayers, flams, cons, spects = [], [], [], [], [], [], []
    with open(hyg_csv, newline="") as fp:
        for r in csv.DictReader(fp):
            if r["proper"] == "Sol":
                continue
            ra = math.radians(float(r["ra"]) * 15.0)
            dec = math.radians(float(r["dec"]))
            d = float(r["dist"])          # パーセク（100000 は距離不明）
            # 位置は赤道座標（J2000）の単位ベクトル × 距離
            xs.append(math.cos(dec) * math.cos(ra) * d)
            ys.append(math.cos(dec) * math.sin(ra) * d)
            zs.append(math.sin(dec) * d)
            mags.append(float(r["mag"]))
            cis.append(float(r["ci"]) if r["ci"] else 0.65)
            hips.append(int(r["hip"]) if r["hip"] else 0)
            dists.append(d)
            propers.append(r["proper"])
            bayers.append(r["bayer"])
            flams.append(r["flam"])
            cons.append(r["con"])
            spects.append(r["spect"][:12])
    order = np.argsort(mags)   # 明るい順に並べておく
    pick = lambda a, dt: np.asarray(a, dtype=dt)[order]  # noqa: E731
    np.savez_compressed(
        OUT / "stars.npz",
        xyz=np.stack([pick(xs, np.float32), pick(ys, np.float32), pick(zs, np.float32)], axis=1),
        mag=pick(mags, np.float32), ci=pick(cis, np.float32), dist=pick(dists, np.float32),
        hip=pick(hips, np.int32), proper=pick(propers, "U24"), bayer=pick(bayers, "U6"),
        flam=pick(flams, "U4"), con=pick(cons, "U4"), spect=pick(spects, "U12"),
    )

    names = {}
    for f in json.load(open(cons_json))["features"]:
        p = f["properties"]
        ra, dec = f["geometry"]["coordinates"]
        names[f["id"]] = {"ja": p.get("ja") or p["name"], "en": p["name"], "ra": ra, "dec": dec}
    lines = {}
    for f in json.load(open(lines_json))["features"]:
        lines.setdefault(f["id"], []).extend(f["geometry"]["coordinates"])
    out = {"note": "d3-celestial (c) 2015 Olaf Frohn, BSD 3-Clause License",
           "constellations": [{"id": k, **v, "lines": lines.get(k, [])} for k, v in names.items()]}
    with open(OUT / "constellations.json", "w") as fp:
        json.dump(out, fp, ensure_ascii=False, separators=(",", ":"))
    print("恒星", len(order), "個 / 星座", len(names), "個")


if __name__ == "__main__":
    main(*sys.argv[1:4])
