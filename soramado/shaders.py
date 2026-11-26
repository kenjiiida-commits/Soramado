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

# ---------------------------------------------------------------- 球（惑星）
SPHERE_VS = """#version 330 core
layout(location=0) in vec3 a_pos;
layout(location=1) in vec2 a_uv;
uniform mat4 u_model;      // 天体の向き・大きさ・カメラからの位置
uniform mat4 u_viewproj;
""" + LOGDEPTH_VS + """
out vec3 v_world;
out vec3 v_normal;
out vec2 v_uv;
void main() {
    vec4 w = u_model * vec4(a_pos, 1.0);
    v_world = w.xyz;
    v_normal = normalize(mat3(u_model) * a_pos);
    v_uv = a_uv;
    gl_Position = u_viewproj * w;
    v_logz = 1.0 + u_logc * gl_Position.w;
}
"""

SPHERE_FS = """#version 330 core
in vec3 v_world;
in vec3 v_normal;
in vec2 v_uv;
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
out vec4 frag;
void main() {
    writeDepth();
    vec3 n = normalize(v_normal);
    vec3 base = texture(u_tex, v_uv).rgb;
    if (u_mode == 1) {
        vec3 toEye = normalize(-v_world);
        float limb = 0.55 + 0.45 * pow(max(dot(n, toEye), 0.0), 0.6);
        frag = vec4(base * 1.25 * limb, 1.0);
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
    col = col * (0.025 + 1.05 * diff);
    if (u_mode == 2 && u_has_night == 1) {
        float dark = 1.0 - smoothstep(-0.15, 0.05, ndl);
        col += texture(u_night, v_uv).rgb * dark * 0.9;
    }
    frag = vec4(col, 1.0);
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
""" + LOGDEPTH_VS + """
void main() {
    gl_Position = u_viewproj * vec4(u_offset + a_pos * u_scale, 1.0);
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
out vec3 v_col;
void main() {
    vec3 rel = a_pos - u_eye;
    float d = max(length(rel), 1e-6);
    if (u_hide_unknown == 1 && a_dist > 1.5e10) {
        gl_Position = vec4(2.0, 2.0, 2.0, 1.0);
        gl_PointSize = 0.0;
        v_col = vec3(0.0);
        return;
    }
    // カメラの位置から見た等級（遠ざかれば暗く、近づけば明るく）
    float m = a_mag + 5.0 * log(d / a_dist) / log(10.0);
    float li = -0.4 * (m - u_limit);          // log10(明るさ / 限界の明るさ)
    if (li < 0.0) {
        gl_Position = vec4(2.0, 2.0, 2.0, 1.0);   // 画面の外へ（描かない）
        gl_PointSize = 0.0;
        v_col = vec3(0.0);
        return;
    }
    // 星は方向だけが大事なので、一定の距離に置いて描く
    gl_Position = u_viewproj * vec4(rel / d * 1000.0, 1.0);
    gl_PointSize = clamp(2.0 + 2.2 * li, 2.0, 16.0) * u_px;
    float a = clamp(0.30 + 0.35 * li, 0.25, 1.4) * u_gain;
    v_col = a_rgb * a;
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
    v_col = a_rgb * max(min(a_w * u_k * r * r * u_fade * u_boost, 1.2), a_w * u_floor * u_fade);
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
uniform int u_mode;        // 0=空, 1=地面
out vec4 frag;
void main() {
    vec3 ray = normalize(u_fwd + v_ndc.x * u_tx * u_right + v_ndc.y * u_ty * u_up);
    float alt = dot(ray, u_zen);
    float day = smoothstep(-6.0, 8.0, u_sunalt);
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
    vec3 night = vec3(0.0);
    vec3 dusk = vec3(0.04, 0.06, 0.14);
    vec3 noon = mix(vec3(0.55, 0.72, 0.95), vec3(0.18, 0.40, 0.85), pow(a, 0.5));
    vec3 col = mix(night, dusk, twi);
    col = mix(col, noon, day);
    // 太陽のまわりの明るさ（昼）と、夕焼け・朝焼け（太陽が低いとき）
    vec3 sunh = normalize(u_sun - u_zen * dot(u_sun, u_zen) + vec3(1e-6));
    vec3 rayh = normalize(ray - u_zen * alt + vec3(1e-6));
    float toward = max(dot(rayh, sunh), 0.0);
    float near = max(dot(ray, u_sun), 0.0);
    col += vec3(1.0, 0.9, 0.7) * pow(near, 60.0) * 0.6 * day;
    float low = 1.0 - smoothstep(-12.0, 10.0, abs(u_sunalt - 1.0));
    col += vec3(1.0, 0.45, 0.15) * exp(-a * 9.0) * pow(toward, 3.0) * low * 0.8;
    col += vec3(0.25, 0.12, 0.20) * exp(-a * 4.0) * low * 0.3;
    frag = vec4(col, 1.0);
}
"""
