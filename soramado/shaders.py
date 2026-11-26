"""GLSL シェーダー（OpenGL 3.3 core）。

宇宙は「近く」と「遠く」の差が極端に大きいので、すべてのシェーダーで
対数デプス（logarithmic depth）を使い、奥行きの精度不足によるちらつきを防ぐ。
座標は「カメラの位置を原点にした黄道座標（AU）」で渡す。
"""

LOGDEPTH_VS = """
uniform float u_logc;      // 距離のスケール（AU→km）
out float v_logz;
"""

LOGDEPTH_FS = """
uniform float u_fcoef;     // 1 / log2(far*u_logc + 1)
in float v_logz;
void writeDepth() { gl_FragDepth = log2(v_logz) * u_fcoef; }
"""


# ---------------------------------------------------------------- 大気（地上モード）
# 大気差: 空気で光が曲がり、地平線近くの天体は少し浮き上がって見える（地平線で約0.6°）。
# 大気による減光: 地平線に近いほど空気の層を長く通るので、暗く赤くなる。
ATM_VS = """
uniform vec3 u_atm_zen;    // 天頂（地上モードのとき）
uniform float u_atm;       // 1 = 大気の効果をつける
vec3 atmRefract(vec3 rel) {
    if (u_atm < 0.5) return rel;
    float L = length(rel);
    if (L <= 0.0) return rel;
    vec3 d = rel / L;
    float s = clamp(dot(d, u_atm_zen), -1.0, 1.0);
    float h = degrees(asin(s));
    if (h < -3.0) return rel;
    float hc = max(h, -1.5);
    float R = 1.02 / tan(radians(hc + 10.3 / (hc + 5.11))) / 60.0;   // Saemundsson の式 [度]
    R = clamp(R, 0.0, 0.75);
    vec3 perp = u_atm_zen - d * s;
    float pl = length(perp);
    if (pl < 1e-6) return rel;
    float r = radians(R);
    return (d * cos(r) + perp / pl * sin(r)) * L;
}
float atmAirmass(vec3 dir) {
    float s = max(dot(normalize(dir), u_atm_zen), -0.02);
    return 1.0 / (max(s, 0.0) + 0.025 * exp(-11.0 * max(s, 0.0)));        // 地平線で約40
}
// 赤・緑・青それぞれが通りぬける割合（青ほど弱まる）。太陽や月は、本当は地平線で千分の一ほどに
// なるが、画面では目が慣れるので、色は赤くしつつ明るさはゆるやかに落とす
vec3 atmTransmit(vec3 dir) {
    if (u_atm < 0.5) return vec3(1.0);
    float X = min(atmAirmass(dir), 30.0);
    vec3 t = exp(-(X - 1.0) * vec3(0.08, 0.12, 0.22));
    float m = max(t.r, 1e-4);
    return t / m * pow(m, 0.2);
}
"""

# ---------------------------------------------------------------- 球（惑星）
SPHERE_VS = """#version 330 core
layout(location=0) in vec3 a_pos;
layout(location=1) in vec2 a_uv;
uniform mat4 u_model;      // 天体の向き・大きさ・カメラからの位置
uniform mat4 u_viewproj;
""" + LOGDEPTH_VS + ATM_VS + """
out vec3 v_world;
out vec3 v_normal;
out vec2 v_uv;
out vec3 v_ext;
void main() {
    vec4 w = u_model * vec4(a_pos, 1.0);
    v_world = w.xyz;
    v_normal = normalize(mat3(u_model) * a_pos);
    v_uv = a_uv;
    v_ext = atmTransmit(w.xyz);
    gl_Position = u_viewproj * vec4(atmRefract(w.xyz), 1.0);
    v_logz = 1.0 + u_logc * gl_Position.w;
}
"""

SPHERE_FS = """#version 330 core
in vec3 v_world;
in vec3 v_normal;
in vec2 v_uv;
in vec3 v_ext;
""" + LOGDEPTH_FS + """
uniform sampler2D u_tex;
uniform sampler2D u_night;
uniform sampler2D u_clouds;
uniform int u_mode;          // 0=惑星, 1=太陽（自ら光る）, 2=地球（夜景・雲つき）
uniform int u_has_night;
uniform int u_has_clouds;
uniform vec3 u_sun;          // 太陽の位置（カメラ原点）
uniform vec3 u_shadow_c;     // 環の影を落とす天体（土星）の中心
uniform vec3 u_ring_n;       // 環の面の法線
uniform vec2 u_ring_r;       // 環の内径・外径（表示上の大きさ）
uniform int u_has_ring;
uniform vec4 u_occ;          // 日食・月食で太陽をかくす天体（xyz: 中心, w: 半径。w=0 なら無し）
uniform float u_sun_r;       // 太陽の半径
uniform int u_occ_red;       // 1 なら、かげの中を赤銅色にする（月食の月）
out vec4 frag;

// 太陽（半径 rs）が半径 ro の円にかくされる面積の割合（中心の間の角 d）
float overlapFrac(float rs, float ro, float d) {
    if (d >= rs + ro) return 0.0;
    if (d <= abs(ro - rs)) return ro >= rs ? 1.0 : (ro * ro) / (rs * rs);
    float a = rs * rs * acos(clamp((d * d + rs * rs - ro * ro) / (2.0 * d * rs), -1.0, 1.0));
    float b = ro * ro * acos(clamp((d * d + ro * ro - rs * rs) / (2.0 * d * ro), -1.0, 1.0));
    float c = 0.5 * sqrt(max(0.0, (-d + rs + ro) * (d + rs - ro) * (d - rs + ro) * (d + rs + ro)));
    return clamp((a + b - c) / (3.14159265 * rs * rs), 0.0, 1.0);
}

// この点から見て、太陽がどれだけ見えているか（1=全部、0=皆既）
float sunVisible(vec3 p) {
    if (u_occ.w <= 0.0) return 1.0;
    vec3 ds = u_sun - p;
    vec3 dobj = u_occ.xyz - p;
    float ls = length(ds);
    float lo = length(dobj);
    if (lo >= ls || lo <= u_occ.w) return 1.0;
    float rs = asin(min(1.0, u_sun_r / ls));
    float ro = asin(min(1.0, u_occ.w / lo));
    float d = atan(length(cross(ds, dobj)), dot(ds, dobj));
    return 1.0 - overlapFrac(rs, ro, d);
}

void main() {
    writeDepth();
    vec3 n = normalize(v_normal);
    vec3 base = texture(u_tex, v_uv).rgb;
    if (u_mode == 1) {
        vec3 toEye = normalize(-v_world);
        float limb = 0.55 + 0.45 * pow(max(dot(n, toEye), 0.0), 0.6);
        frag = vec4(base * 1.25 * limb * v_ext, 1.0);
        return;
    }
    vec3 l = normalize(u_sun - v_world);
    float ndl = dot(n, l);
    float diff = max(ndl, 0.0);
    // 土星の環が本体に落とす影
    if (u_has_ring == 1 && diff > 0.0) {
        float denom = dot(l, u_ring_n);
        if (abs(denom) > 1e-6) {
            float t = dot(u_shadow_c - v_world, u_ring_n) / denom;
            if (t > 0.0) {
                float r = length(v_world + l * t - u_shadow_c);
                if (r > u_ring_r.x && r < u_ring_r.y) diff *= 0.45;
            }
        }
    }
    vec3 col = base;
    if (u_mode == 2 && u_has_clouds == 1) {
        float c = texture(u_clouds, v_uv).r;
        col = mix(col, vec3(1.0), c * 0.85);
    }
    float vis = diff > 0.0 ? sunVisible(v_world) : 1.0;
    vec3 lit = col * (0.025 + 1.05 * diff * vis);
    if (u_occ_red == 1) {
        // 皆既月食の月が赤く見えるのは、地球の大気で曲げられた赤い光が影の中に届くから
        lit += col * vec3(0.30, 0.09, 0.03) * diff * (1.0 - vis) * (1.0 - vis);
    }
    col = lit;
    if (u_mode == 2 && u_has_night == 1) {
        float dark = 1.0 - smoothstep(-0.15, 0.05, ndl);
        col += texture(u_night, v_uv).rgb * dark * 0.9;
    }
    frag = vec4(col * v_ext, 1.0);
}
"""

# ---------------------------------------------------------------- 環
RING_VS = """#version 330 core
layout(location=0) in vec3 a_pos;     // xy: 単位円上の位置, z: 0=内側 1=外側
uniform mat4 u_model;
uniform mat4 u_viewproj;
uniform vec2 u_radii;                 // 内径・外径（モデル単位=天体半径）
""" + LOGDEPTH_VS + """
out vec3 v_world;
out float v_t;
void main() {
    float r = mix(u_radii.x, u_radii.y, a_pos.z);
    vec4 w = u_model * vec4(a_pos.xy * r, 0.0, 1.0);
    v_world = w.xyz;
    v_t = a_pos.z;
    gl_Position = u_viewproj * w;
    v_logz = 1.0 + u_logc * gl_Position.w;
}
"""

RING_FS = """#version 330 core
in vec3 v_world;
in float v_t;
""" + LOGDEPTH_FS + """
uniform sampler2D u_tex;
uniform vec3 u_sun;
uniform vec3 u_center;      // 土星の中心（カメラ原点）
uniform float u_planet_r;   // 土星の表示半径
out vec4 frag;
void main() {
    writeDepth();
    vec4 c = texture(u_tex, vec2(v_t, 0.5));
    // 土星本体の影
    vec3 l = normalize(u_sun - v_world);
    vec3 oc = v_world - u_center;
    float b = dot(oc, l);
    float cc = dot(oc, oc) - u_planet_r * u_planet_r;
    float shade = 1.0;
    if (b < 0.0 && b * b - cc > 0.0) shade = 0.08;
    frag = vec4(c.rgb * (0.15 + 0.85 * shade), c.a);
}
"""

# ---------------------------------------------------------------- 線（軌道）
LINE_VS = """#version 330 core
layout(location=0) in vec3 a_pos;
uniform vec3 u_offset;     // 軌道の中心（カメラ原点）
uniform float u_scale;
uniform mat4 u_viewproj;
""" + LOGDEPTH_VS + ATM_VS + """
void main() {
    gl_Position = u_viewproj * vec4(atmRefract(u_offset + a_pos * u_scale), 1.0);
    v_logz = 1.0 + u_logc * gl_Position.w;
}
"""

LINE_FS = """#version 330 core
""" + LOGDEPTH_FS + """
uniform vec4 u_color;
out vec4 frag;
void main() {
    writeDepth();
    frag = u_color;
}
"""

# ---------------------------------------------------------------- 太陽の光芒
GLOW_VS = """#version 330 core
layout(location=0) in vec2 a_corner;
uniform vec2 u_center;     // 画面上の中心（NDC）
uniform vec2 u_size;       // 半径（NDC）
out vec2 v_p;
void main() {
    v_p = a_corner;
    gl_Position = vec4(u_center + a_corner * u_size, 0.0, 1.0);
}
"""

GLOW_FS = """#version 330 core
in vec2 v_p;
uniform float u_depth;
uniform vec3 u_color;
uniform float u_core;      // 光芒全体に対する太陽本体の大きさ
out vec4 frag;
void main() {
    gl_FragDepth = u_depth;
    float r = length(v_p);
    if (r > 1.0) discard;
    float g = exp(-6.0 * max(r - u_core, 0.0) / max(1.0 - u_core, 1e-3)) * (1.0 - r);
    frag = vec4(u_color * g, 1.0);
}
"""

# ---------------------------------------------------------------- 恒星
STAR_VS = """#version 330 core
layout(location=0) in vec3 a_pos;     // 太陽中心の位置 [AU]
layout(location=1) in float a_mag;    // 地球（太陽）から見た等級
layout(location=2) in float a_dist;   // 太陽からの距離 [AU]
layout(location=3) in vec3 a_rgb;
uniform vec3 u_eye;                   // カメラの位置（太陽中心）[AU]
uniform mat4 u_viewproj;
uniform float u_limit;                // 見える限界の等級
uniform float u_px;                   // 画面の拡大率（高解像度画面用）
uniform float u_gain;                 // 星の明るさの調整
uniform int u_hide_unknown;           // 距離不明の星を隠す（太陽系から遠く離れたとき）
uniform float u_near;                 // これより近い星は描かない（よその惑星系を見ているとき。位置の誤差が大きいので）
""" + ATM_VS + """
out vec3 v_col;
void main() {
    vec3 rel = a_pos - u_eye;
    float d = max(length(rel), 1e-6);
    if ((u_hide_unknown == 1 && a_dist > 1.5e10) || d < u_near) {
        gl_Position = vec4(2.0, 2.0, 2.0, 1.0);
        gl_PointSize = 0.0;
        v_col = vec3(0.0);
        return;
    }
    // カメラの位置から見た等級（遠ざかれば暗く、近づけば明るく）
    float m = a_mag + 5.0 * log(d / a_dist) / log(10.0);
    vec3 ext = vec3(1.0);
    if (u_atm > 0.5) {                        // 地平線に近いほど暗く、赤く
        float X = atmAirmass(rel);
        m += 0.22 * (X - 1.0);
        ext = exp(-(X - 1.0) * vec3(0.0, 0.06, 0.16));
    }
    float li = -0.4 * (m - u_limit);          // log10(明るさ / 限界の明るさ)
    if (li < 0.0) {
        gl_Position = vec4(2.0, 2.0, 2.0, 1.0);   // 画面の外へ（描かない）
        gl_PointSize = 0.0;
        v_col = vec3(0.0);
        return;
    }
    // 星は方向だけが大事なので、一定の距離に置いて描く
    gl_Position = u_viewproj * vec4(atmRefract(rel / d * 1000.0), 1.0);
    gl_PointSize = clamp(2.0 + 2.2 * li, 2.0, 16.0) * u_px;
    float a = clamp(0.30 + 0.35 * li, 0.25, 1.4) * u_gain;
    v_col = a_rgb * a * ext;
}
"""

STAR_FS = """#version 330 core
in vec3 v_col;
out vec4 frag;
void main() {
    vec2 p = gl_PointCoord * 2.0 - 1.0;
    float r2 = dot(p, p);
    if (r2 > 1.0) discard;
    float k = exp(-r2 * 4.0) + 0.3 * exp(-r2 * 1.2);
    frag = vec4(v_col * k, 1.0);
}
"""

# ---------------------------------------------------------------- 銀河（粒子）
GALAXY_VS = """#version 330 core
layout(location=0) in vec3 a_pos;     // 銀河の局所座標 [kpc]
layout(location=1) in float a_size;   // 粒子の大きさ [kpc]
layout(location=2) in float a_w;      // 明るさの重み
layout(location=3) in vec3 a_rgb;
uniform vec3 u_center;                // 銀河中心（カメラ原点）[AU]
uniform mat3 u_rot;                   // 銀河の向き × (AU/kpc)
uniform float u_kpc;                  // 1 kpc [AU]
uniform mat4 u_viewproj;
uniform float u_focal;                // 距離1で1単位の物が何ピクセルか
uniform float u_k;                    // 銀河ごとの明るさの係数（表面輝度が一定になるように決めたもの）
uniform float u_fade;
uniform float u_boost;               // 小さく見える銀河を見やすくするための増光
uniform float u_floor;               // 銀河全体が数ピクセルしかないときの最低限の明るさ
uniform float u_px;
uniform float u_near;                 // これより近い粒は薄くする [kpc]（天の川銀河の中にいるとき）
out vec3 v_col;
void main() {
    vec3 w = u_center + u_rot * a_pos;
    float d = max(length(w), 1.0);
    gl_Position = u_viewproj * vec4(w / d * 1000.0, 1.0);
    // 本来の見かけの大きさ tp。1ピクセルより小さい粒子は、光の量を保ったまま暗くする
    float tp = a_size * u_kpc / d * u_focal;
    float px = clamp(tp, 1.0, 40.0);
    float r = min(tp, 40.0) / px;
    gl_PointSize = px * u_px;
    float s = a_w * u_k * r * r * u_fade * u_boost;
    s = a_w > 0.0 ? max(min(s, 3.0), a_w * u_floor * u_fade) : max(s, -1.5);   // 負の重みは光をさえぎるちり
    if (u_near > 0.0) s *= smoothstep(0.35 * u_near, u_near, d / u_kpc);
    v_col = a_rgb * s;
}
"""

GALAXY_FS = """#version 330 core
in vec3 v_col;
out vec4 frag;
void main() {
    vec2 p = gl_PointCoord * 2.0 - 1.0;
    float r2 = dot(p, p);
    if (r2 > 1.0) discard;
    frag = vec4(v_col * exp(-r2 * 3.0), 1.0);
}
"""

# ---------------------------------------------------------------- 銀河カタログ（四角形で描く）
GCAT_VS = """#version 330 core
layout(location=0) in vec2 a_corner;
layout(location=1) in vec3 a_center;  // 太陽中心 [AU]
layout(location=2) in vec3 a_ax1;     // 長軸方向 × 半径 [AU]
layout(location=3) in vec3 a_ax2;     // 円盤内のもう一つの軸 × 半径 [AU]
layout(location=4) in float a_mode;   // 0渦巻 1レンズ状 2中心のふくらみ 3楕円 4不規則
layout(location=5) in vec3 a_rgb;
layout(location=6) in float a_seed;
layout(location=7) in float a_flat;
uniform vec3 u_eye;
uniform mat4 u_viewproj;
uniform vec3 u_right;
uniform vec3 u_up;
uniform float u_focal;
uniform float u_gain;
out vec2 v_uv;
out vec3 v_col;
flat out int v_mode;
out float v_seed;
void main() {
    vec3 c = a_center - u_eye;
    float d = max(length(c), 1.0);
    float R = length(a_ax1);
    float rpx = R / d * u_focal;
    // 小さすぎて見えない銀河は、少し大きく描いて暗くする（光の点として見えるように）
    float s = max(1.0, 2.5 / max(rpx, 1e-6));
    vec3 off;
    int mode = int(a_mode + 0.5);
    if (mode == 2 || mode == 3) {
        off = (a_corner.x * u_right + a_corner.y * u_up * a_flat) * R;
    } else {
        off = a_corner.x * a_ax1 + a_corner.y * a_ax2;
    }
    gl_Position = u_viewproj * vec4(c + off * s, 1.0);
    v_uv = a_corner;
    v_mode = mode;
    v_seed = a_seed;
    v_col = a_rgb * u_gain * max(pow(s, -0.9), 0.8);
}
"""

GCAT_FS = """#version 330 core
in vec2 v_uv;
in vec3 v_col;
flat in int v_mode;
in float v_seed;
out vec4 frag;
void main() {
    float r = length(v_uv);
    if (r > 1.4) discard;
    float edge = smoothstep(1.4, 0.9, r);
    float val;
    if (v_mode == 0) {
        float th = atan(v_uv.y, v_uv.x);
        float arms = pow(0.5 + 0.5 * cos(2.0 * th - log(r + 0.03) * 4.5 + v_seed), 2.0);
        val = exp(-r * 3.0) * (0.25 + 1.1 * arms);
    } else if (v_mode == 1) {
        val = exp(-r * 3.5);
    } else if (v_mode == 4) {
        val = exp(-r * 2.2) * (0.7 + 0.3 * sin(v_uv.x * 7.0 + v_seed) * sin(v_uv.y * 5.0 + v_seed * 1.3));
    } else if (v_mode == 2) {
        val = exp(-r * r * 10.0) * 0.9;
    } else {
        val = exp(-r * r * 4.0);
    }
    frag = vec4(v_col * val * edge, 1.0);
}
"""

# ---------------------------------------------------------------- 地上モードの空と地面（画面全体に描く）
SKY_VS = """#version 330 core
layout(location=0) in vec2 a_corner;
out vec2 v_ndc;
void main() {
    v_ndc = a_corner;
    gl_Position = vec4(a_corner, 0.0, 1.0);
}
"""

SKY_FS = """#version 330 core
in vec2 v_ndc;
uniform vec3 u_fwd;
uniform vec3 u_right;
uniform vec3 u_up;
uniform float u_tx;        // tan(視野/2) × 縦横比
uniform float u_ty;        // tan(視野/2)
uniform vec3 u_zen;        // 天頂
uniform vec3 u_sun;        // 太陽の方向
uniform float u_sunalt;    // 太陽の高度 [度]
uniform float u_sunlight;  // 日食のとき、太陽が見えている割合で空を暗くする（0〜1）
uniform int u_mode;        // 0=空, 1=地面
out vec4 frag;
void main() {
    vec3 ray = normalize(u_fwd + v_ndc.x * u_tx * u_right + v_ndc.y * u_ty * u_up);
    float alt = dot(ray, u_zen);
    float day = smoothstep(-6.0, 8.0, u_sunalt) * u_sunlight;
    float twi = smoothstep(-18.0, -3.0, u_sunalt);
    if (u_mode == 1) {
        if (alt >= 0.0) discard;
        vec3 g = mix(vec3(0.012, 0.016, 0.012), vec3(0.16, 0.20, 0.12), day);
        g += vec3(0.05, 0.03, 0.02) * twi * (1.0 - day);
        // 地平線のすぐ下を少し明るく（地平線が分かるように）
        g += vec3(0.06, 0.07, 0.06) * exp(alt * 60.0) * (0.3 + 0.7 * twi);
        frag = vec4(g, 1.0);
        return;
    }
    if (alt < -0.02) discard;
    float a = max(alt, 0.0);
    // 見る向きの空気の厚さ（大気路程）。地平線に近いほど厚い
    float X = 1.0 / (a + 0.025 * exp(-11.0 * a));
    // 太陽の光が空気を通りぬけてくる色（太陽が低いほど赤い）
    float ss = max(sin(radians(u_sunalt)), 0.0);
    float Xs = 1.0 / (ss + 0.025 * exp(-11.0 * ss));
    vec3 sunTint = exp(-Xs * vec3(0.12, 0.20, 0.36));
    sunTint /= max(max(sunTint.r, sunTint.g), max(sunTint.b, 1e-3));      // 色だけ（明るさは別に）
    vec3 sunh = normalize(u_sun - u_zen * dot(u_sun, u_zen) + vec3(1e-6));
    vec3 rayh = normalize(ray - u_zen * alt + vec3(1e-6));
    float toward = max(dot(rayh, sunh), 0.0);       // 太陽の方位に近いほど 1
    float away = max(-dot(rayh, sunh), 0.0);        // 太陽と反対の方位に近いほど 1
    float near = max(dot(ray, u_sun), 0.0);

    // 昼の青空: 天頂は濃い青、地平線に近いほど白っぽく明るい
    vec3 zenithBlue = vec3(0.16, 0.36, 0.80);
    vec3 horizonWhite = vec3(0.70, 0.80, 0.92);
    vec3 dayCol = mix(zenithBlue, horizonWhite, 1.0 - exp(-0.35 * (X - 1.0)));
    dayCol *= mix(sunTint, vec3(1.0), 0.55);
    // 太陽のまわりの明るいところ（光が細かいちりで前に散る）
    dayCol += vec3(1.0, 0.92, 0.8) * sunTint * (pow(near, 400.0) * 1.2 + pow(near, 12.0) * 0.25);
    float dayk = smoothstep(-3.0, 8.0, u_sunalt) * u_sunlight;

    // 薄明（太陽が地平線の下 0〜18°）: 天頂は深い青、太陽の側の地平線は橙〜黄
    float tw = smoothstep(-18.0, -2.0, u_sunalt);
    vec3 twiCol = mix(vec3(0.012, 0.02, 0.06), vec3(0.06, 0.10, 0.24), tw) * (0.4 + 0.6 * exp(-a * 2.0));
    // 市民薄明（太陽 0〜-6°）のころは、まだ空が明るい青
    twiCol = mix(twiCol, vec3(0.16, 0.26, 0.50) * (0.7 + 0.3 * exp(-a * 2.0)), smoothstep(-7.0, 0.0, u_sunalt));
    float glowH = exp(-a * 7.0) * pow(toward, 2.0);
    twiCol += vec3(1.0, 0.42, 0.12) * glowH * smoothstep(-14.0, -3.0, u_sunalt) * 0.75;
    twiCol += vec3(1.0, 0.75, 0.35) * exp(-a * 14.0) * pow(toward, 6.0) * smoothstep(-8.0, -1.0, u_sunalt) * 0.6;
    // 太陽と反対側: 地平線のすぐ上に地球の影（暗い青）、その上にピンクの帯（ビーナスの帯）
    float belt = smoothstep(-7.0, -1.0, u_sunalt) * (1.0 - smoothstep(1.0, 6.0, u_sunalt));
    float shadow = (1.0 - smoothstep(0.0, 0.07, a)) * away;
    float pink = exp(-pow((a - 0.13) / 0.07, 2.0)) * away;

    vec3 col = mix(twiCol, dayCol, dayk);
    col += vec3(0.32, 0.14, 0.20) * pink * belt;
    col = mix(col, col * vec3(0.55, 0.62, 0.85), shadow * belt);
    // 日の出・日の入りのころ、太陽の側の地平線を赤く
    float low = 1.0 - smoothstep(-2.0, 10.0, u_sunalt);
    col += vec3(1.0, 0.38, 0.10) * exp(-a * 9.0) * pow(toward, 3.0) * low * smoothstep(-6.0, 0.0, u_sunalt) * 0.7 * u_sunlight;
    // 夜空のかすかな明るさ（大気光）
    col += vec3(0.004, 0.006, 0.009) * exp(-a * 4.0);
    frag = vec4(col, 1.0);
}
"""

# ---------------------------------------------------------------- クエーサー（点）
QSO_VS = """#version 330 core
layout(location=0) in vec3 a_pos;     // 太陽中心 [AU]
layout(location=1) in vec3 a_rgb;
uniform vec3 u_eye;
uniform mat4 u_viewproj;
uniform float u_gain;
uniform float u_px;
out vec3 v_col;
void main() {
    vec3 rel = a_pos - u_eye;
    float d = max(length(rel), 1.0);
    gl_Position = u_viewproj * vec4(rel / d * 1000.0, 1.0);
    gl_PointSize = 2.0 * u_px;
    v_col = a_rgb * u_gain;
}
"""

QSO_FS = """#version 330 core
in vec3 v_col;
out vec4 frag;
void main() {
    vec2 p = gl_PointCoord * 2.0 - 1.0;
    float r2 = dot(p, p);
    if (r2 > 1.0) discard;
    frag = vec4(v_col * exp(-r2 * 2.0), 1.0);
}
"""

# ---------------------------------------------------------------- 宇宙マイクロ波背景放射の球
CMB_VS = """#version 330 core
layout(location=0) in vec3 a_pos;
layout(location=1) in vec2 a_uv;
uniform mat4 u_model;
uniform mat4 u_viewproj;
out vec2 v_uv;
out vec3 v_dir;
void main() {
    vec4 w = u_model * vec4(a_pos, 1.0);
    v_uv = a_uv;
    v_dir = w.xyz;
    gl_Position = u_viewproj * w;
}
"""

CMB_FS = """#version 330 core
in vec2 v_uv;
in vec3 v_dir;
uniform sampler2D u_tex;
uniform float u_alpha;
out vec4 frag;
void main() {
    frag = vec4(texture(u_tex, v_uv).rgb * u_alpha, 1.0);
}
"""

# ---------------------------------------------------------------- たくさんの小惑星（位置はここで計算する）
MP_VS = """#version 330 core
layout(location=0) in vec3 a_p;      // 軌道面の向き（近日点の方向）
layout(location=1) in vec3 a_q;
layout(location=2) in vec4 a_el;     // a [AU], e, 基準日の平均近点角 [rad], 平均運動 [rad/日]
layout(location=3) in vec3 a_col;
layout(location=4) in float a_kind;
uniform float u_far_gain;            // 遠くから見たときの、外側の天体（ケンタウルス族・外縁天体）の明るさ
uniform float u_dt;                  // 基準日からの日数
uniform vec3 u_sun;                  // カメラから見た太陽の位置
uniform mat4 u_viewproj;
uniform float u_gain;
uniform float u_px;
""" + LOGDEPTH_VS + """
out vec3 v_col;
out float v_size;
void main() {
    float e = a_el.y;
    float M = mod(a_el.z + a_el.w * u_dt, 6.28318531);
    float E = e > 0.8 ? 3.14159265 : M + e * sin(M);
    for (int k = 0; k < 10; k++) {
        E -= (E - e * sin(E) - M) / (1.0 - e * cos(E));
    }
    float xp = a_el.x * (cos(E) - e);
    float yp = a_el.x * sqrt(max(0.0, 1.0 - e * e)) * sin(E);
    vec3 rel = u_sun + a_p * xp + a_q * yp;
    gl_Position = u_viewproj * vec4(rel, 1.0);
    v_logz = 1.0 + u_logc * gl_Position.w;
    // 明るすぎる点は、色を保ったまま点を大きくする（白飛びさせずに目立たせる）
    float g = u_gain;
    if (a_kind > 3.5 && a_kind < 5.5) g = max(g, u_far_gain);
    vec3 c = a_col * g;
    float m = max(c.r, max(c.g, c.b));
    float size = 1.6;
    if (m > 1.0) {
        size *= min(3.0, sqrt(m));
        c /= m;
    }
    gl_PointSize = size * u_px;
    v_size = size;
    v_col = c;
}
"""

MP_FS = """#version 330 core
""" + LOGDEPTH_FS + """
in vec3 v_col;
in float v_size;
out vec4 frag;
void main() {
    writeDepth();
    if (v_size > 2.0) {
        vec2 q = gl_PointCoord * 2.0 - 1.0;
        float r2 = dot(q, q);
        if (r2 > 1.0) discard;
        frag = vec4(v_col * (1.0 - r2 * 0.6), 1.0);
    } else {
        frag = vec4(v_col, 1.0);
    }
}
"""

# ---------------------------------------------------------------- 星雲・星団（模式図の粒）
NEB_VS = """#version 330 core
layout(location=0) in vec3 a_pos;    // 天体の中心からの位置 [AU]
layout(location=1) in vec3 a_col;
layout(location=2) in float a_size;  // 粒の大きさ（半径）[AU]。0 は星
uniform vec3 u_center;               // カメラから見た天体の中心
uniform mat4 u_viewproj;
uniform float u_focal;               // 距離 1 で 1 AU が何ピクセルか
uniform float u_px;
uniform float u_star_gain;
uniform float u_haze_gain;
""" + LOGDEPTH_VS + """
out vec3 v_col;
out float v_haze;
void main() {
    vec3 rel = u_center + a_pos;
    gl_Position = u_viewproj * vec4(rel, 1.0);
    v_logz = 1.0 + u_logc * gl_Position.w;
    float w = max(gl_Position.w, 1e-9);
    if (a_size > 0.0) {
        float px = a_size / w * u_focal;
        float s = clamp(px, 1.5, 300.0);
        float k = (px < 1.5) ? (px * px) / (s * s) : 1.0;     // 小さすぎるときは、明るさの合計を保って暗くする
        if (px > 300.0) k = 300.0 / px;                       // 近づきすぎたら薄くする
        gl_PointSize = s * u_px;
        v_col = a_col * u_haze_gain * k;
        v_haze = 1.0;
    } else {
        gl_PointSize = 2.2 * u_px;
        v_col = a_col * u_star_gain * 2.5;
        v_haze = 0.0;
    }
}
"""

NEB_FS = """#version 330 core
""" + LOGDEPTH_FS + """
in vec3 v_col;
in float v_haze;
out vec4 frag;
void main() {
    writeDepth();
    vec2 q = gl_PointCoord * 2.0 - 1.0;
    float r2 = dot(q, q);
    if (r2 > 1.0) discard;
    float g = v_haze > 0.5 ? exp(-4.0 * r2) * (1.0 - r2) : exp(-3.0 * r2);
    frag = vec4(v_col * g, 1.0);
}
"""


# ---------------------------------------------------------------- 明るさの圧縮（星雲・銀河）
# 星雲や銀河の粒は、浮動小数点の画面に光をそのまま足し合わせてから、明るいところほどゆるやかに
# 明るくなるように圧縮して元の画面に重ねる。こうすると、粒が重なる中心部が真っ白につぶれない。
TONE_VS = """#version 330 core
layout(location=0) in vec2 a_pos;
out vec2 v_uv;
void main() {
    v_uv = a_pos * 0.5 + 0.5;
    gl_Position = vec4(a_pos, 0.0, 1.0);
}
"""

TONE_FS = """#version 330 core
in vec2 v_uv;
uniform sampler2D u_tex;
uniform float u_exp;
out vec4 frag;
void main() {
    vec3 c = max(texture(u_tex, v_uv).rgb, 0.0) * u_exp;    // ちりの粒で負になったところは 0 に
    float L = max(max(c.r, c.g), c.b);
    if (L < 1e-5) discard;
    float m = 1.0 - exp(-L);
    vec3 o = c * (m / L);                                  // 色合いを保ったまま明るさだけ圧縮
    o = mix(o, vec3(m), 0.45 * smoothstep(1.5, 8.0, L));   // とても明るいところは白っぽく
    frag = vec4(o, 1.0);
}
"""


# ---------------------------------------------------------------- 星雲・銀河の写真（地球から見た向きの板）
PHOTO_VS = """#version 330 core
layout(location=0) in vec2 a_c;       // 板の角 [-1, 1]
uniform vec3 u_center;                // 天体の中心（カメラ原点、縮めた座標）
uniform vec3 u_ax1;                   // 写真の右向き（西）× 半分の幅
uniform vec3 u_ax2;                   // 写真の上向き（北）× 半分の高さ
uniform mat4 u_viewproj;
out vec2 v_c;
void main() {
    v_c = a_c;
    gl_Position = u_viewproj * vec4(u_center + a_c.x * u_ax1 + a_c.y * u_ax2, 1.0);
}
"""

PHOTO_FS = """#version 330 core
in vec2 v_c;
uniform sampler2D u_tex;
uniform float u_gain;
uniform float u_flip;
out vec4 frag;
void main() {
    float r = length(v_c);
    float m = 1.0 - smoothstep(0.62, 0.98, r);            // まわりはなめらかに消す
    if (m <= 0.0) discard;
    vec2 uv = vec2(v_c.x * 0.5 + 0.5, u_flip > 0.5 ? 0.5 - v_c.y * 0.5 : v_c.y * 0.5 + 0.5);
    frag = vec4(texture(u_tex, uv).rgb * (u_gain * m), 1.0);
}
"""


# ---------------------------------------------------------------- 天の川の全天写真（太陽系の近くから見た空）
MWSKY_VS = """#version 330 core
layout(location=0) in vec2 a_pos;
out vec2 v_ndc;
void main() {
    v_ndc = a_pos;
    gl_Position = vec4(a_pos, 0.0, 1.0);
}
"""

MWSKY_FS = """#version 330 core
in vec2 v_ndc;
uniform mat4 u_inv;          // 画面 → 方向（カメラ原点の座標）
uniform mat3 u_ecl2eq;       // 黄道座標 → 赤道座標
uniform sampler2D u_tex;     // 正距円筒図（横 = 赤経、縦 = 赤緯 +90 → -90）
uniform float u_gain;
uniform vec3 u_atm_zen;      // 天頂（黄道座標）
uniform float u_atm;
out vec4 frag;
const float PI = 3.14159265358979;
void main() {
    vec4 p = u_inv * vec4(v_ndc, 0.0, 1.0);
    vec3 de = normalize(p.xyz / p.w);
    vec3 ext = vec3(1.0);
    if (u_atm > 0.5) {
        // 見えている向き → 本当の向き（大気差のぶん下げる。Bennett の式）
        float s = clamp(dot(de, u_atm_zen), -1.0, 1.0);
        float h = degrees(asin(s));
        float hc = max(h, -1.0);
        float R = clamp(1.0 / tan(radians(hc + 7.31 / (hc + 4.4))) / 60.0, 0.0, 0.75);
        vec3 perp = u_atm_zen - de * s;
        float pl = length(perp);
        if (pl > 1e-6) de = normalize(de * cos(radians(R)) - perp / pl * sin(radians(R)));
        float sh = max(s, 0.0);
        float X = 1.0 / (sh + 0.025 * exp(-11.0 * sh));
        ext = exp(-(X - 1.0) * vec3(0.18, 0.24, 0.40));
    }
    vec3 d = normalize(u_ecl2eq * de);
    float ra = atan(d.y, d.x);                       // -π〜π
    float u1 = ra / (2.0 * PI);
    float u0 = fract(u1);                            // 0〜1（赤経 0h で切れ目）
    float v = acos(clamp(d.z, -1.0, 1.0)) / PI;      // 0 = 北極
    // 赤経 0h の切れ目で、ミップマップがおかしくならないように微分を選ぶ
    vec2 dx0 = vec2(dFdx(u0), dFdx(v)), dy0 = vec2(dFdy(u0), dFdy(v));
    vec2 dx1 = vec2(dFdx(u1), dFdx(v)), dy1 = vec2(dFdy(u1), dFdy(v));
    bool use1 = abs(dx1.x) + abs(dy1.x) < abs(dx0.x) + abs(dy0.x);
    vec3 c = textureGrad(u_tex, vec2(u0, v), use1 ? dx1 : dx0, use1 ? dy1 : dy0).rgb;
    frag = vec4(c * u_gain * ext, 1.0);
}
"""
