# そらみ窓（Soramado）

Ubuntu で動く、Mitaka のような宇宙シミュレーターです。
太陽系を 3D で自由に飛び回り、惑星が実際の日付どおりに公転するようすを眺められます。

> このソフトは国立天文台の Mitaka とは関係のない、独自に作ったソフトです。

## できること

- 太陽・8つの惑星・月を、**指定した日時の実際の位置**に表示
- 時間の早送り（実時間〜1年/秒）・逆再生・一時停止、日時の直接指定
- マウスで視点を回す・近づく。天体をダブルクリックするとその天体へ飛んでいく
- 惑星の自転軸の傾き・自転、土星の環（環と本体の影つき）
- 「惑星の大きさ」スライダーで、惑星を実寸の最大1000倍まで拡大表示
- 惑星の表面画像をダウンロードして本物らしく表示（任意。しない場合は簡易的な模様）
- 約12万個の恒星を、本当の明るさと色で表示（v0.2）。「星の数」で何等星まで出すかを調整
- 星座線・日本語の星座名・おもな星の名前（シリウス、ベテルギウスなど）
- 恒星をダブルクリックすると、名前・明るさ・距離（光年）・スペクトル型を表示
- ホイールでどこまでも引いていける（v0.3）：太陽系 → 近くの恒星 → 天の川銀河 → 近くの銀河（約24億光年まで）。左下に画面の横幅（km・AU・光年）を表示
- 天の川銀河と近くの銀河12個（アンドロメダ銀河、大・小マゼラン雲、M81、ソンブレロ銀河、M87 など）。「見る天体」から選ぶと飛んでいける
- 「🔭 地上から見る」で、観測地（大阪・東京・札幌など、または緯度・経度を入力）から見上げた星空を表示（v0.4、プラネタリウム）。昼の青空・夕焼け・薄明・夜の変化、地平線と方角、月の満ち欠け。ホイールで視野を1度まで拡大できる
- 実在の銀河 約1万個（OpenNGC）を、本当の方向・距離・大きさ・向きで配置。数億光年まで引くと、おとめ座銀河団などの銀河の集まりが見える。ダブルクリックで飛んでいける

## 動作環境

- Ubuntu 25.04 以降（26.04 LTS で開発）
- OpenGL 3.3 以上に対応したグラフィック（最近の内蔵 GPU なら十分です）

## インストール

### DEB パッケージで入れる（おすすめ）

[Releases](https://github.com/kenjiiida-commits/Soramado/releases) から `soramado_x.x.x_all.deb` をダウンロードして、

```bash
sudo apt install ./soramado_0.1.0_all.deb
```

アプリ一覧に「そらみ窓」が出てきます。

### ソースから動かす

```bash
sudo apt install python3-numpy python3-pyside6.qtwidgets python3-pyside6.qtopengl python3-pyside6.qtopenglwidgets
git clone https://github.com/kenjiiida-commits/Soramado.git
cd Soramado
python3 -m soramado
```

DEB を自分で作るときは `bash packaging/build_deb.sh`（`dist/` にできます）。

## 操作方法

| 操作 | 動き |
|---|---|
| 左ドラッグ | 視点を回す |
| ホイール / 右ドラッグ | 近づく・離れる |
| ダブルクリック | 惑星・銀河へ移動／恒星の情報を見る |
| スペース | 時間を止める・動かす |
| + / − | 近づく・離れる |
| F11 | 全画面表示 |

地上から見るとき（プラネタリウム）

| 操作 | 動き |
|---|---|
| 左ドラッグ | 見る方向を変える |
| ホイール / 右ドラッグ | 視野を広く・狭く |
| 見る天体 / ダブルクリック | その天体の方を向く／恒星の情報を見る |

## 計算の精度

- 惑星の位置は NASA JPL の近似軌道要素で計算しています。1800〜2050年の範囲で、地球から見た方向の誤差は水星〜火星で 0.01度程度、木星・土星で 0.2度以内です（`tests/test_astro.py` で astropy と比較）。範囲外の年は概算になります。
- 月の位置は簡易式で、誤差は 0.05度程度です。
- 地上から見た高度・方位は、恒星時と歳差を計算しています（`tests/test_ground.py` で astropy と比較し、恒星で0.01度、月で0.1度程度）。大気による浮き上がり（大気差、地平線近くで約0.5度）は計算していません。
- 恒星の方向は HYG データベースの J2000 の位置で、固有運動は計算していません（`tests/test_stars.py`）。
- 銀河の位置（赤経・赤緯）・距離・大きさ・傾きは文献のおおよその値です。銀河の形は写真ではなく、粒子で作った模式図です。天の川銀河は、太陽から中心まで 8.2 kpc（約2.7万光年）、4本の渦巻き腕と棒状構造をもつ形にしています。
- 約1万個の銀河の距離は、後退速度からハッブルの法則（H0 = 70 km/s/Mpc）で求めた推定値です（おとめ座銀河団の方向の近い銀河は 16.5 Mpc に置いています）。

## 今後の予定

- 惑星の衛星・小惑星・彗星
- 天体の解説、宇宙を巡るツアー

## 使用しているデータとライセンス

- プログラム: MIT ライセンス（`LICENSE`）
- 惑星の軌道: [NASA JPL, Approximate Positions of the Planets](https://ssd.jpl.nasa.gov/planets/approx_pos.html)
- 月の位置: Paul Schlyter, *How to compute planetary positions*
- 天体の大きさ・自転軸: IAU WGCCRE 報告（2015年）
- 恒星: [HYG データベース v4.1](https://github.com/astronexus/HYG-Database)（CC BY-SA 4.0）。変換したデータ `soramado/data/stars.npz` も CC BY-SA 4.0 です
- 銀河カタログ: [OpenNGC](https://github.com/mattiaverga/OpenNGC)（CC BY-SA 4.0）。変換したデータ `soramado/data/galaxies.npz` も CC BY-SA 4.0 です
- 星座線・星座名: [d3-celestial](https://github.com/ofrohn/d3-celestial)（© 2015 Olaf Frohn、BSD 3-Clause）
- データのライセンスの詳細は `soramado/data/LICENSE-DATA.md` を見てください
- 惑星の画像（ダウンロードした場合）: [Solar System Scope](https://www.solarsystemscope.com/textures/)（CC BY 4.0）。画像はソフトに同梱しておらず、`~/.local/share/soramado/textures/` に保存されます。

作者: 飯田顕治
