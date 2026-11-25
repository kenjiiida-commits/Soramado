# データのライセンス

このフォルダのデータは、プログラム本体（MIT ライセンス）とは別のライセンスです。

## stars.npz — 恒星データ

HYG データベース v4.1（David Nash / Astronexus）を、そらみ窓で使いやすい形に変換したものです。
<https://github.com/astronexus/HYG-Database>

ライセンス: Creative Commons Attribution-ShareAlike 4.0 International（CC BY-SA 4.0）
<https://creativecommons.org/licenses/by-sa/4.0/>

変換の内容: 太陽を除き、位置（赤経・赤緯・距離）を直交座標に直し、明るい順に並べ替えた。
変換に使ったプログラムは `tools/make_star_data.py` です。
この変換後のデータも CC BY-SA 4.0 で提供します。

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