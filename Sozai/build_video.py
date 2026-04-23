"""Generate an SNS teaser MP4 for 奈良春日 鹿のや.

Outputs: Sozai/post_kasuga_forest.mp4 (1080x1080, ~22s, 30fps).
Requires: Pillow, ffmpeg, Noto Serif CJK JP.
"""

from __future__ import annotations

import math
import shutil
import subprocess
from pathlib import Path

from PIL import Image, ImageDraw, ImageFilter, ImageFont

ROOT = Path(__file__).resolve().parent
FRAMES = ROOT / "_frames"
OUT = ROOT / "post_kasuga_forest.mp4"

W, H = 1080, 1080
FPS = 30

FONT_SERIF = "/usr/share/fonts/opentype/noto/NotoSerifCJK-Regular.ttc"
FONT_SERIF_BOLD = "/usr/share/fonts/opentype/noto/NotoSerifCJK-Bold.ttc"


# (text_lines, subtext, seconds)
SCENES: list[tuple[list[str], str, float]] = [
    (["世界遺産の森の、", "すぐ隣で目を覚ます。"], "", 4.0),
    (["千年以上、", "斧の音を知らない。"], "― 春日山原始林 ―", 4.0),
    (["その深い緑と、", "神域の静けさに守られて。"], "", 4.0),
    (["奈良春日の森に泊まる。"], "ここだけの贅沢を。", 4.0),
    (["奈良春日　鹿のや"], "全5室・隠れ家オーベルジュ", 4.5),
]


def hex_rgb(c: str) -> tuple[int, int, int]:
    c = c.lstrip("#")
    return (int(c[0:2], 16), int(c[2:4], 16), int(c[4:6], 16))


# Deep sumi-midori (ink green) to mist grey gradient — sacred forest at dawn.
TOP = hex_rgb("#0f1a14")
BOTTOM = hex_rgb("#2a3a31")
MIST = hex_rgb("#c9cfc3")
INK = hex_rgb("#f2efe6")  # warm off-white (kinari)


def make_background(seed: float) -> Image.Image:
    """Vertical gradient + soft radial glow that drifts with time."""
    bg = Image.new("RGB", (W, H), TOP)
    px = bg.load()
    for y in range(H):
        t = y / (H - 1)
        r = int(TOP[0] * (1 - t) + BOTTOM[0] * t)
        g = int(TOP[1] * (1 - t) + BOTTOM[1] * t)
        b = int(TOP[2] * (1 - t) + BOTTOM[2] * t)
        for x in range(W):
            px[x, y] = (r, g, b)

    # Drifting warm glow (like filtered morning light through leaves).
    glow = Image.new("RGB", (W, H), (0, 0, 0))
    gd = ImageDraw.Draw(glow)
    cx = W * (0.35 + 0.15 * math.sin(seed * 0.6))
    cy = H * (0.30 + 0.08 * math.cos(seed * 0.4))
    radius = int(W * 0.55)
    gd.ellipse([cx - radius, cy - radius, cx + radius, cy + radius], fill=(90, 105, 80))
    glow = glow.filter(ImageFilter.GaussianBlur(220))
    bg = Image.blend(bg, glow, 0.35)

    # Subtle mist band near the horizon.
    mist = Image.new("RGB", (W, H), (0, 0, 0))
    md = ImageDraw.Draw(mist)
    band_y = int(H * (0.55 + 0.03 * math.sin(seed * 0.8)))
    md.rectangle([0, band_y - 120, W, band_y + 120], fill=MIST)
    mist = mist.filter(ImageFilter.GaussianBlur(160))
    bg = Image.blend(bg, mist, 0.12)

    return bg


def fit_font(path: str, size: int) -> ImageFont.FreeTypeFont:
    return ImageFont.truetype(path, size=size, index=0)


def draw_text_block(
    base: Image.Image,
    lines: list[str],
    subtext: str,
    alpha: float,
) -> Image.Image:
    """Draw main lines + subtext centered, with a faint hairline divider."""
    layer = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    draw = ImageDraw.Draw(layer)

    main_size = 74 if max((len(s) for s in lines), default=0) > 10 else 88
    sub_size = 30
    main_font = fit_font(FONT_SERIF, main_size)
    sub_font = fit_font(FONT_SERIF, sub_size)

    # Measure main block.
    line_gap = int(main_size * 0.55)
    heights = []
    widths = []
    for s in lines:
        bbox = draw.textbbox((0, 0), s, font=main_font)
        widths.append(bbox[2] - bbox[0])
        heights.append(bbox[3] - bbox[1])
    main_h = sum(heights) + line_gap * max(0, len(lines) - 1)

    sub_h = 0
    sub_w = 0
    if subtext:
        sb = draw.textbbox((0, 0), subtext, font=sub_font)
        sub_w = sb[2] - sb[0]
        sub_h = sb[3] - sb[1]

    total_h = main_h + (60 + sub_h if subtext else 0)
    y = (H - total_h) // 2

    a = int(255 * alpha)
    shadow_a = int(140 * alpha)

    for i, s in enumerate(lines):
        x = (W - widths[i]) // 2
        # soft shadow for legibility on the forest gradient
        draw.text((x + 2, y + 2), s, font=main_font, fill=(0, 0, 0, shadow_a))
        draw.text((x, y), s, font=main_font, fill=(*INK, a))
        y += heights[i] + line_gap

    if subtext:
        y_sub = (H + main_h) // 2 + 40
        # hairline divider
        divider_w = 90
        dx = (W - divider_w) // 2
        draw.line(
            [(dx, y_sub - 20), (dx + divider_w, y_sub - 20)],
            fill=(*MIST, int(180 * alpha)),
            width=1,
        )
        x = (W - sub_w) // 2
        draw.text((x, y_sub), subtext, font=sub_font, fill=(*MIST, a))

    return Image.alpha_composite(base.convert("RGBA"), layer).convert("RGB")


def ease(t: float) -> float:
    """Ease in-out cubic."""
    return 3 * t * t - 2 * t * t * t


def scene_alpha(local_t: float, duration: float) -> float:
    """Fade-in 0.8s, hold, fade-out 0.8s."""
    fade = 0.8
    if local_t < fade:
        return ease(local_t / fade)
    if local_t > duration - fade:
        return ease(max(0.0, (duration - local_t) / fade))
    return 1.0


def render() -> None:
    if FRAMES.exists():
        shutil.rmtree(FRAMES)
    FRAMES.mkdir(parents=True)

    frame_idx = 0
    elapsed = 0.0
    for lines, subtext, dur in SCENES:
        n = int(dur * FPS)
        for k in range(n):
            local_t = k / FPS
            alpha = scene_alpha(local_t, dur)
            bg = make_background(elapsed + local_t)
            img = draw_text_block(bg, lines, subtext, alpha)
            img.save(FRAMES / f"f_{frame_idx:05d}.png", "PNG")
            frame_idx += 1
        elapsed += dur

    print(f"rendered {frame_idx} frames ({frame_idx / FPS:.1f}s)")


def encode() -> None:
    cmd = [
        "ffmpeg", "-y",
        "-framerate", str(FPS),
        "-i", str(FRAMES / "f_%05d.png"),
        "-c:v", "libx264",
        "-pix_fmt", "yuv420p",
        "-profile:v", "high",
        "-crf", "20",
        "-movflags", "+faststart",
        str(OUT),
    ]
    subprocess.run(cmd, check=True)
    shutil.rmtree(FRAMES)
    print(f"wrote {OUT.relative_to(ROOT.parent)}")


if __name__ == "__main__":
    render()
    encode()
