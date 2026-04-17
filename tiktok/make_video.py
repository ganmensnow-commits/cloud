# TikTok縦型動画生成スクリプト
# 熟年恋愛×癒し / 焚き火風アニメ背景 + テロップアニメ + 音声

import os
import wave
import subprocess
import numpy as np
from moviepy import (
    VideoClip, TextClip, CompositeVideoClip,
    AudioFileClip, CompositeAudioClip, vfx,
)

# ==== 設定 ====
W, H = 1080, 1920
FPS = 24
DURATION = 22.0
FONT = "/System/Library/Fonts/ヒラギノ角ゴシック W6.ttc"
OUTPUT = "output.mp4"
TTS_VOICE = "Kyoko"
SR = 44100

SCRIPT = [
    (0.0,  "もう恋なんてしないと思ってた",            "もう恋なんてしないと思ってた"),
    (2.0,  "60歳で離婚して",                          "60歳で離婚して"),
    (4.0,  "一人の方が楽だって、\n自分に言い聞かせてた", "一人の方が楽だって、自分に言い聞かせてた"),
    (7.0,  "でも",                                    "でも"),
    (8.5,  "この人に出会って",                        "この人に出会って"),
    (10.5, "また笑えるようになった",                  "また笑えるようになった"),
    (13.0, "誰かを好きになるって",                    "誰かを好きになるって"),
    (15.0, "こんなに温かかったんだ",                  "こんなに温かかったんだ"),
    (17.5, "恋に遅すぎるなんてない",                  "恋に遅すぎるなんてない"),
    (20.0, "あなたはどう思いますか？",                "あなたはどう思いますか？"),
]

os.makedirs("tts", exist_ok=True)

# ==== 1) 焚き火BGM生成 ====
def generate_bonfire_wav(path, duration, sr=SR):
    n = int(duration * sr)
    rng = np.random.default_rng(7)
    white = rng.standard_normal(n)
    brown = np.cumsum(white)
    brown -= brown.mean()
    brown /= np.max(np.abs(brown)) + 1e-9
    brown *= 0.35
    crackle = np.zeros(n)
    for _ in range(int(duration * 8)):
        start = rng.integers(0, n - 1000)
        length = rng.integers(200, 1200)
        amp = rng.uniform(0.2, 0.9)
        env = np.exp(-np.linspace(0, 6, length))
        crackle[start:start + length] += rng.standard_normal(length) * env * amp
    mix = np.clip(brown + crackle * 0.5, -1.0, 1.0)
    delay = int(sr * 0.012)
    right = np.concatenate([np.zeros(delay), mix[:-delay]])
    stereo = np.stack([mix, right], axis=-1)
    pcm = (stereo * 32767).astype(np.int16)
    with wave.open(path, "wb") as wf:
        wf.setnchannels(2); wf.setsampwidth(2); wf.setframerate(sr)
        wf.writeframes(pcm.tobytes())

BGM_PATH = "tts/bonfire.wav"
print("焚き火BGM生成中...")
generate_bonfire_wav(BGM_PATH, DURATION)

# ==== 2) 音声読み上げ生成 ====
def tts(text, idx):
    path = f"tts/line_{idx:02d}.aiff"
    subprocess.run(["say", "-v", TTS_VOICE, "-o", path, text], check=True)
    return path

print("音声読み上げ生成中...")
tts_files = [(s, tts(sp, i)) for i, (s, _, sp) in enumerate(SCRIPT)]

# ==== 3) 背景: 焚き火グロー + 火の粉パーティクル ====
# パーティクルを事前生成（決定的に）
rng = np.random.default_rng(123)
NUM_PARTICLES = 220
particles = []  # (birth, x0, vx, vy, lifetime, size, brightness)
for _ in range(NUM_PARTICLES):
    birth = rng.uniform(-2.0, DURATION)       # 一部は開始前から
    x0 = W / 2 + rng.normal(0, 110)           # 中央付近から発生
    vx = rng.normal(0, 18)                    # 横方向の揺らぎ
    vy = rng.uniform(140, 260)                # 上昇速度(px/s)
    lifetime = rng.uniform(1.8, 3.5)
    size = rng.uniform(4.0, 9.0)
    brightness = rng.uniform(0.6, 1.0)
    particles.append((birth, x0, vx, vy, lifetime, size, brightness))

# グローのベース距離マップ
Y_idx, X_idx = np.mgrid[0:H, 0:W].astype(np.float32)
cx_base, cy_base = W / 2, H * 0.80
dist = np.sqrt((X_idx - cx_base) ** 2 + (Y_idx - cy_base) ** 2)
glow_base = np.exp(-dist / 420.0)
y_norm = Y_idx / H
grad_r = y_norm * 50
grad_g = y_norm * 14
grad_b = y_norm * 5

def add_particle(frame, px, py, size, alpha):
    """火の粉を小さなガウスブロブで描画（オレンジ系）"""
    if py < -20 or py > H + 20 or px < -20 or px > W + 20:
        return
    r_int = int(size * 3)
    x0 = max(0, int(px) - r_int)
    x1 = min(W, int(px) + r_int + 1)
    y0 = max(0, int(py) - r_int)
    y1 = min(H, int(py) + r_int + 1)
    if x1 <= x0 or y1 <= y0:
        return
    yy, xx = np.mgrid[y0:y1, x0:x1]
    d2 = (xx - px) ** 2 + (yy - py) ** 2
    blob = np.exp(-d2 / (2 * size * size)) * alpha * 255.0
    frame[y0:y1, x0:x1, 0] = np.clip(frame[y0:y1, x0:x1, 0] + blob,        0, 255)
    frame[y0:y1, x0:x1, 1] = np.clip(frame[y0:y1, x0:x1, 1] + blob * 0.55, 0, 255)
    frame[y0:y1, x0:x1, 2] = np.clip(frame[y0:y1, x0:x1, 2] + blob * 0.15, 0, 255)

def make_frame(t):
    # 焚き火グローの揺らぎ
    flicker = (
        0.78
        + 0.16 * np.sin(t * 7.3)
        + 0.09 * np.sin(t * 17.1 + 1.2)
        + 0.06 * np.sin(t * 31.7 + 0.5)
    )
    glow = glow_base * 255.0 * flicker
    r = np.clip(grad_r + glow * 1.00, 0, 255)
    g = np.clip(grad_g + glow * 0.45, 0, 255)
    b = np.clip(grad_b + glow * 0.12, 0, 255)
    frame = np.stack([r, g, b], axis=-1).astype(np.float32)

    # 火の粉パーティクル（上昇＆フェード）
    for birth, x0, vx, vy, life, size, bright in particles:
        age = t - birth
        if age < 0 or age > life:
            continue
        # 上昇しながら少し横に揺れる
        px = x0 + vx * age + np.sin(age * 3.0 + x0 * 0.01) * 12
        py = (H * 0.82) - vy * age
        # 寿命に応じたフェード（出現0.2s、消滅後半でフェードアウト）
        fade_in = min(1.0, age / 0.2)
        fade_out = min(1.0, (life - age) / (life * 0.6))
        alpha = bright * fade_in * fade_out
        add_particle(frame, px, py, size, alpha)

    return np.clip(frame, 0, 255).astype(np.uint8)

background = VideoClip(make_frame, duration=DURATION)

# ==== 4) テロップ（フェード + スライドアップ） ====
def make_text_clip(text, start, end):
    dur = end - start
    base = TextClip(
        font=FONT, text=text, font_size=72, color="white",
        stroke_color="black", stroke_width=3,
        method="caption", size=(W - 160, None), text_align="center",
    ).with_start(start).with_duration(dur)

    # スライドアップ: 最初の0.4秒で +30px → 0px
    def pos(ct):
        slide = max(0.0, 1.0 - ct / 0.4)  # 1→0
        offset = int(slide * 30)
        return ("center", H // 2 - base.h // 2 + offset)

    return base.with_position(pos).with_effects([
        vfx.CrossFadeIn(0.35),
        vfx.CrossFadeOut(0.25),
    ])

text_clips = []
starts = [s for s, _, _ in SCRIPT] + [DURATION]
for i, (start, text, _) in enumerate(SCRIPT):
    text_clips.append(make_text_clip(text, start, starts[i + 1]))

# ==== 5) 音声合成 ====
bgm = AudioFileClip(BGM_PATH).with_volume_scaled(0.25)
voice_clips = [
    AudioFileClip(p).with_start(s).with_volume_scaled(1.3)
    for s, p in tts_files
]
final_audio = CompositeAudioClip([bgm, *voice_clips])

# ==== 6) 書き出し ====
final = (
    CompositeVideoClip([background, *text_clips], size=(W, H))
    .with_duration(DURATION)
    .with_audio(final_audio)
)
final.write_videofile(
    OUTPUT, fps=FPS, codec="libx264", audio_codec="aac",
    preset="medium", threads=4,
)
print(f"完了: {OUTPUT}")
