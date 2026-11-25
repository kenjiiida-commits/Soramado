"""恒星の日本語名とバイエル符号。"""

# 固有名（IAU 名）→ 日本語でよく使われる呼び名
JA_NAMES = {
    "Sirius": "シリウス", "Canopus": "カノープス", "Arcturus": "アークトゥルス",
    "Rigil Kentaurus": "リギル・ケンタウルス", "Toliman": "トリマン", "Vega": "ベガ（織姫星）",
    "Capella": "カペラ", "Rigel": "リゲル", "Procyon": "プロキオン", "Achernar": "アケルナル",
    "Betelgeuse": "ベテルギウス", "Hadar": "ハダル", "Altair": "アルタイル（彦星）",
    "Acrux": "アクルックス", "Aldebaran": "アルデバラン", "Spica": "スピカ", "Antares": "アンタレス",
    "Pollux": "ポルックス", "Fomalhaut": "フォーマルハウト", "Deneb": "デネブ", "Mimosa": "ミモザ",
    "Regulus": "レグルス", "Adhara": "アダーラ", "Castor": "カストル", "Gacrux": "ガクルックス",
    "Shaula": "シャウラ", "Bellatrix": "ベラトリックス", "Elnath": "エルナト",
    "Miaplacidus": "ミアプラキドゥス", "Alnilam": "アルニラム", "Alnair": "アルナイル",
    "Alnitak": "アルニタク", "Alioth": "アリオト", "Kaus Australis": "カウス・アウストラリス",
    "Mirfak": "ミルファク", "Dubhe": "ドゥーベ", "Wezen": "ウェズン", "Alkaid": "アルカイド",
    "Avior": "アヴィオール", "Sargas": "サルガス", "Menkalinan": "メンカリナン", "Atria": "アトリア",
    "Alhena": "アルヘナ", "Peacock": "ピーコック", "Polaris": "ポラリス（北極星）", "Mirzam": "ミルザム",
    "Alphard": "アルファルド", "Algieba": "アルギエバ", "Hamal": "ハマル", "Diphda": "ディフダ",
    "Nunki": "ヌンキ", "Menkent": "メンケント", "Alpheratz": "アルフェラッツ", "Kochab": "コカブ",
    "Mirach": "ミラク", "Saiph": "サイフ", "Rasalhague": "ラスアルハゲ", "Algol": "アルゴル",
    "Almach": "アルマク", "Denebola": "デネボラ", "Alphecca": "アルフェッカ", "Mizar": "ミザール",
    "Alcor": "アルコル", "Sadr": "サドル", "Eltanin": "エルタニン", "Schedar": "シェダル",
    "Mintaka": "ミンタカ", "Caph": "カフ", "Merak": "メラク", "Izar": "イザール", "Enif": "エニフ",
    "Phecda": "フェクダ", "Megrez": "メグレズ", "Scheat": "シェアト", "Alderamin": "アルデラミン",
    "Markab": "マルカブ", "Algenib": "アルゲニブ", "Menkar": "メンカル", "Zosma": "ゾスマ",
    "Arneb": "アルネブ", "Unukalhai": "ウヌカルハイ", "Sheratan": "シェラタン",
    "Zubeneschamali": "ズベンエスカマリ", "Zubenelgenubi": "ズベンエルゲヌビ",
    "Vindemiatrix": "ビンデミアトリックス", "Albireo": "アルビレオ", "Mira": "ミラ",
    "Thuban": "トゥバン", "Alcyone": "アルキオネ（すばる）", "Rasalgethi": "ラスアルゲティ",
    "Cor Caroli": "コル・カロリ", "Sadalmelik": "サダルメリク", "Sadalsuud": "サダルスウド",
    "Deneb Algedi": "デネブ・アルゲディ", "Alshain": "アルシャイン", "Tarazed": "タラゼド",
    "Ruchbah": "ルクバー", "Muphrid": "ムフリッド", "Nekkar": "ネッカル",
    "Proxima Centauri": "プロキシマ・ケンタウリ", "Barnard's Star": "バーナード星",
    "Atlas": "アトラス", "Electra": "エレクトラ", "Maia": "マイア", "Merope": "メローペ",
    "Taygeta": "タイゲタ", "Pleione": "プレイオネ", "Sualocin": "スアロキン", "Rotanev": "ロタネブ",
    "Acamar": "アカマル", "Ankaa": "アンカー", "Suhail": "スハイル", "Naos": "ナオス",
    "Gomeisa": "ゴメイサ", "Cursa": "クルサ", "Zaurak": "ザウラク", "Nihal": "ニハル",
    "Sabik": "サビク", "Alsephina": "アルセフィナ", "Aspidiske": "アスピディスケ",
    "Dschubba": "ジュバ", "Aludra": "アルドラ", "Markeb": "マルケブ", "Aljanah": "アルジャナー",
    "Acrab": "アクラブ", "Gienah": "ギェナー", "Ascella": "アスケラ", "Kraz": "クラズ",
    "Phact": "ファクト", "Mebsuta": "メブスタ", "Tejat": "テジャト", "Wasat": "ワサト",
    "Alterf": "アルテルフ", "Chertan": "シェルタン", "Porrima": "ポリマ", "Seginus": "セギヌス",
    "Lesath": "レサト", "Kaus Media": "カウス・メディア", "Kaus Borealis": "カウス・ボレアリス",
    "Albaldah": "アルバルダー", "Hassaleh": "ハッサレー", "Errai": "エライ",
    "Alfirk": "アルフィルク", "Homam": "ホマム", "Matar": "マタル", "Sadachbia": "サダクビア",
    "Skat": "スカト", "Ancha": "アンカ", "Azha": "アザー", "Zaniah": "ザニア",
    "Furud": "フルド", "Muliphein": "ムリフェイン", "Hatysa": "ハチサ", "Meissa": "メイサ",
    "Tabit": "タビト", "Rasalas": "ラスアラス", "Subra": "スブラ", "Heze": "ヘゼ",
    "Syrma": "シルマ", "Algorab": "アルゴラブ", "Kornephoros": "コルネフォロス",
    "Sarin": "サリン", "Marfik": "マルフィク", "Yed Prior": "イェド・プリオル",
    "Yed Posterior": "イェド・ポステリオル", "Cebalrai": "ケバルライ", "Grumium": "グルミウム",
    "Rastaban": "ラスタバン", "Edasich": "エダシク", "Pherkad": "フェルカド",
    "Talitha": "タリタ", "Tania Borealis": "タニア・ボレアリス", "Tania Australis": "タニア・アウストラリス",
    "Alula Borealis": "アルラ・ボレアリス", "Muscida": "ムシダ", "Alrescha": "アルリシャ",
    "Mesarthim": "メサルティム", "Botein": "ボテイン", "Menkib": "メンキブ",
    "Hyadum I": "ヒアデス第1星", "Ain": "アイン", "Chamukuy": "チャムクイ", "Tianguan": "天関（ティエンクアン）",
}

GREEK = {
    "Alp": "α", "Bet": "β", "Gam": "γ", "Del": "δ", "Eps": "ε", "Zet": "ζ", "Eta": "η",
    "The": "θ", "Iot": "ι", "Kap": "κ", "Lam": "λ", "Mu": "μ", "Nu": "ν", "Xi": "ξ",
    "Omi": "ο", "Pi": "π", "Rho": "ρ", "Sig": "σ", "Tau": "τ", "Ups": "υ", "Phi": "φ",
    "Chi": "χ", "Psi": "ψ", "Ome": "ω",
}


def greek(bayer: str) -> str:
    """HYG の bayer 欄（例 "Alp", "Pi-1"）をギリシャ文字にする。"""
    if not bayer:
        return ""
    base, _, num = bayer.partition("-")
    g = GREEK.get(base, base)
    if num:
        g += "¹²³⁴⁵⁶⁷⁸⁹"[int(num) - 1] if num.isdigit() and 0 < int(num) < 10 else num
    return g
