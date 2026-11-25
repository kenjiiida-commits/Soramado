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
    v_col = a_rgb * min(a_w * u_k * r * r * u_fade, 1.2);
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
