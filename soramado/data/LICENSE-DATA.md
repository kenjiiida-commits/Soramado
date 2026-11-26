# データのライセンス

このフォルダのデータは、プログラム本体（MIT ライセンス）とは別のライセンスです。

## stars.npz — 恒星データ

HYG データベース v4.1（David Nash / Astronexus）を、そらみ窓で使いやすい形に変換したものです。
<https://github.com/astronexus/HYG-Database>

ライセンス: Creative Commons Attribution-ShareAlike 4.0 International（CC BY-SA 4.0）
<https://creativecommons.org/licenses/by-sa/4.0/>

変換の内容: 太陽を除き、位置（赤経・赤緯・距離）を直交座標に直し、空間速度（vx, vy, vz）を加えて、明るい順に並べ替えた。
変換に使ったプログラムは `tools/make_star_data.py` です。
この変換後のデータも CC BY-SA 4.0 で提供します。

## galaxies.npz — 銀河カタログ

OpenNGC（Mattia Verga）の NGC/IC カタログから、後退速度のある銀河 約1万個を取り出したものです。
<https://github.com/mattiaverga/OpenNGC>

ライセンス: Creative Commons Attribution-ShareAlike 4.0 International（CC BY-SA 4.0）

変換の内容: 銀河だけを取り出し、後退速度からハッブルの法則（H0 = 70 km/s/Mpc）で距離を求めた
（おとめ座銀河団の方向の近い銀河は 16.5 Mpc に置いた）。変換に使ったプログラムは
`tools/make_galaxy_data.py` です。この変換後のデータも CC BY-SA 4.0 で提供します。

## constellations.json — 星座線・星座名

d3-celestial（Olaf Frohn）の星座データ（constellations.json, constellations.lines.json）から作りました。
<https://github.com/ofrohn/d3-celestial>

Copyright (c) 2015, Olaf Frohn
All rights reserved.

Redistribution and use in source and binary forms, with or without modification, are permitted provided that the following conditions are met:

1. Redistributions of source code must retain the above copyright notice, this list of conditions and the following disclaimer.

2. Redistributions in binary form must reproduce the above copyright notice, this list of conditions and the following disclaimer in the documentation and/or other materials provided with the distribution.

3. Neither the name of the copyright holder nor the names of its contributors may be used to endorse or promote products derived from this software without specific prior written permission.

THIS SOFTWARE IS PROVIDED BY THE COPYRIGHT HOLDERS AND CONTRIBUTORS "AS IS" AND ANY EXPRESS OR IMPLIED WARRANTIES, INCLUDING, BUT NOT LIMITED TO, THE IMPLIED WARRANTIES OF MERCHANTABILITY AND FITNESS FOR A PARTICULAR PURPOSE ARE DISCLAIMED. IN NO EVENT SHALL THE COPYRIGHT HOLDER OR CONTRIBUTORS BE LIABLE FOR ANY DIRECT, INDIRECT, INCIDENTAL, SPECIAL, EXEMPLARY, OR CONSEQUENTIAL DAMAGES (INCLUDING, BUT NOT LIMITED TO, PROCUREMENT OF SUBSTITUTE GOODS OR SERVICES; LOSS OF USE, DATA, OR PROFITS; OR BUSINESS INTERRUPTION) HOWEVER CAUSED AND ON ANY THEORY OF LIABILITY, WHETHER IN CONTRACT, STRICT LIABILITY, OR TORT (INCLUDING NEGLIGENCE OR OTHERWISE) ARISING IN ANY WAY OUT OF THE USE OF THIS SOFTWARE, EVEN IF ADVISED OF THE POSSIBILITY OF SUCH DAMAGE.
## 星雲・星団（nebulae.json）

位置・見かけの大きさ・種類・明るさは OpenNGC (https://github.com/mattiaverga/OpenNGC) による（CC BY-SA 4.0）。
距離と日本語の名前・解説はそらみ窓で付けたもの（tools/make_nebula_data.py）。このファイルも CC BY-SA 4.0 で配布する。

## ダウンロードする星雲・銀河の写真（DSS2 color）

「ファイル」→「星雲・銀河の写真をダウンロード…」で取得する写真は、ソフトには含まれていません。
利用者のパソコンが、ESA の ESASky（<https://cdn.skies.esac.esa.int/DSSColor>）または
CDS（<https://alasky.cds.unistra.fr/DSS/DSSColor>）が配信している HiPS「DSS2 color」のタイルを
ダウンロードし、天体ごとに切り出して `~/.local/share/soramado/dso_photos/` に保存します。

- DSS2 color: CDS（ストラスブール天文データセンター）が DSS2 の赤と青の画像から作ったカラー合成
- The Digitized Sky Surveys were produced at the Space Telescope Science Institute under U.S. Government
  grant NAG W-2166. The images of these surveys are based on photographic data obtained using the
  Oschin Schmidt Telescope on Palomar Mountain and the UK Schmidt Telescope.
  The plates were processed into the present compressed digital form with the permission of these institutions.

## ダウンロードする天の川の写真（Gaia DR2 color flux map）

「ファイル」→「天の川の写真（Gaia）をダウンロード…」で取得する画像は、ソフトには含まれていません。
利用者のパソコンが CDS の HiPS「Gaia DR2 color flux map」の全天画像（Norder3/Allsky.jpg）を
ダウンロードし、正距円筒図に並べ直して `~/.local/share/soramado/milkyway_gaia.jpg` に保存します。

- データ: ESA/Gaia/DPAC（Gaia Data Release 2）。ライセンス: CC BY-SA 3.0 IGO
- HiPS: CDS（ストラスブール天文データセンター）, T. Boch
- This work has made use of data from the European Space Agency (ESA) mission Gaia
  (https://www.cosmos.esa.int/gaia), processed by the Gaia Data Processing and Analysis Consortium (DPAC).

## spacecraft_paths.npz — 探査機の航路

NASA/JPL の Horizons（<https://ssd.jpl.nasa.gov/horizons/>）の探査機の位置（太陽中心・黄道座標 J2000）を、
1〜5日おきに取り出したもの。将来の部分は、各ミッションが公表している予定の軌道です。
Horizons の出力は米国政府（NASA/JPL）の公開データです。

変換の内容: そらみ窓の惑星・小惑星・彗星の位置は簡単な式で計算しているので、JPL の正確な位置と少しずれる。
探査機が天体の近くにいるあいだは、そのずれのぶんだけ探査機をずらして、画面の天体に合わせた。
変換に使ったプログラムは `tools/make_spacecraft_data.py` です。
はやぶさ（初代）は Horizons に2009年より前の位置がないため、通過点から計算したおおよその航路です。
