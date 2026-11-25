"""銀河カタログのデータファイルを作る（開発者用。普段は使わない）。

入力: OpenNGC (https://github.com/mattiaverga/OpenNGC, CC BY-SA 4.0)
      database_files/NGC.csv, database_files/addendum.csv
出力: soramado/data/galaxies.npz

距離は後退速度からハッブルの法則（H0 = 70 km/s/Mpc）で求める。
おとめ座銀河団の方向にある近い銀河は、固有運動で速度がばらつくので、
銀河団までの距離（16.5 Mpc）に置く。後退速度が 400 km/s 未満の銀河は、
速度から距離を出せないので除く（近い有名な銀河は soramado/galaxies.py で別に扱う）。

使い方: python3 tools/make_galaxy_data.py NGC.csv addendum.csv
"""

import csv
import math
import sys
import zlib
from pathlib import Path

import numpy as np

OUT = Path(__file__).resolve().parents[1] / "soramado" / "data" / "galaxies.npz"
H0 = 70.0
VIRGO_RA, VIRGO_DEC, VIRGO_MPC = 187.7059, 12.3911, 16.5
# soramado/galaxies.py で詳しく描いている銀河（重複させない）
SKIP = {"NGC0224", "NGC0221", "NGC0205", "NGC0598", "NGC3031", "NGC3034", "NGC5128",
        "NGC5457", "NGC5194", "NGC4594", "NGC4486"}


def hms(s):
    h, m, x = (float(v) for v in s.split(":"))
    return (h + m / 60 + x / 3600) * 15


def dms(s):
    sign = -1 if s.startswith("-") else 1
    d, m, x = (float(v) for v in s.lstrip("+-").split(":"))
    return sign * (d + m / 60 + x / 3600)


def sep_deg(ra1, de1, ra2, de2):
    r1, d1, r2, d2 = map(math.radians, (ra1, de1, ra2, de2))
    c = math.sin(d1) * math.sin(d2) + math.cos(d1) * math.cos(d2) * math.cos(r1 - r2)
    return math.degrees(math.acos(max(-1, min(1, c))))


def kind_of(hubble):
    h = hubble.strip()
    if h.startswith(("E", "cD")):
        return 3          # 楕円
    if h.startswith(("S0", "SB0", "SAB0", "SA0")):
        return 1          # レンズ状
    if h.startswith(("I", "Sm", "SBm", "SABm")):
        return 4          # 不規則
    return 0              # 渦巻


def main(*files):
    rows = []
    for fn in files:
        rows += list(csv.DictReader(open(fn, newline=""), delimiter=";"))
    out = {k: [] for k in ("ra", "dec", "mpc", "maj", "minr", "pa", "kind", "name", "messier", "common")}
    for r in rows:
        if r["Type"] not in ("G", "GPair", "GTrpl", "GGroup") or r["Name"] in SKIP:
            continue
        if not r["MajAx"] or not (r["RadVel"] or r["Redshift"]):
            continue
        v = float(r["RadVel"]) if r["RadVel"] else float(r["Redshift"]) * 299792.458
        ra, dec = hms(r["RA"]), dms(r["Dec"])
        if sep_deg(ra, dec, VIRGO_RA, VIRGO_DEC) < 8 and v < 2600:
            mpc = VIRGO_MPC * (1 + 0.04 * (zlib.crc32(r["Name"].encode()) % 21 - 10) / 10)   # 少し奥行きを散らす
        elif v < 400:
            continue
        else:
            mpc = v / H0
        maj = float(r["MajAx"])
        mn = float(r["MinAx"]) if r["MinAx"] else maj
        out["ra"].append(ra)
        out["dec"].append(dec)
        out["mpc"].append(mpc)
        out["maj"].append(maj)
        out["minr"].append(max(0.05, min(1.0, mn / maj)))
        out["pa"].append(float(r["PosAng"]) if r["PosAng"] else 0.0)
        out["kind"].append(kind_of(r["Hubble"]))
        out["name"].append(r["Name"])
        out["messier"].append(r["M"].lstrip("0"))
        out["common"].append(r["Common names"].split(",")[0])
    np.savez_compressed(
        OUT, ra=np.array(out["ra"], np.float64), dec=np.array(out["dec"], np.float64),
        mpc=np.array(out["mpc"], np.float32), maj=np.array(out["maj"], np.float32),
        minr=np.array(out["minr"], np.float32), pa=np.array(out["pa"], np.float32),
        kind=np.array(out["kind"], np.int8), name=np.array(out["name"], "U12"),
        messier=np.array(out["messier"], "U4"), common=np.array(out["common"], "U32"))
    print("銀河", len(out["ra"]), "個 →", OUT)


if __name__ == "__main__":
    main(*sys.argv[1:])
