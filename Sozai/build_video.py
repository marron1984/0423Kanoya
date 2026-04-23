"""Generate SNS MP4 for 奈良春日 鹿のや, using on-repo photos + Kagura clip.

Output: Sozai/post_kasuga_forest.mp4 (1080x1920 / 9:16, 30fps).
Typography: Shippori Mincho (bundled under Sozai/fonts).
"""

from __future__ import annotations

import math
import shutil
import subprocess
from dataclasses import dataclass
from pathlib import Path

from PIL import Image, ImageDraw, ImageFilter, ImageFont

ROOT = Path(__file__).resolve().parent
REPO = ROOT.parent
FRAMES = ROOT / "_frames"
OUT = ROOT / "post_kasuga_forest.mp4"

# Vertical (Reels / Stories) 9:16
W, H = 1080, 1920
FPS = 30
ASPECT = W / H  # 0.5625

FONT_SERIF = str(ROOT / "fonts" / "ShipporiMincho-Regular.ttf")
FONT_SERIF_BOLD = str(ROOT / "fonts" / "ShipporiMincho-Bold.ttf")

INK = (242, 239, 230)   # warm off-white (kinari)
MIST = (201, 207, 195)
SHADOW = (0, 0, 0)


@dataclass
class PhotoScene:
    path: Path
    lines: list[str]
    subtext: str
    duration: float
    zoom_from: float = 1.00
    zoom_to: float = 1.08
    pan_from: tuple[float, float] = (0.5, 0.5)
    pan_to: tuple[float, float] = (0.5, 0.5)
    caption_pos: str = "lower"  # "lower" | "center" | "upper"
    veil: float = 0.0             # full-frame darkening (0..1)


@dataclass
class VideoScene:
    path: Path
    start: float
    duration: float
    lines: list[str]
    subtext: str
    caption_pos: str = "lower"
    veil: float = 0.0
    zoom_from: float = 1.00
    zoom_to: float = 1.00
    pan_from: tuple[float, float] = (0.5, 0.5)
    pan_to: tuple[float, float] = (0.5, 0.5)


SCENES: list = [
    PhotoScene(
        path=REPO / "7C1A5078.JPG",
        lines=["世界遺産の森の、", "すぐ隣で目を覚ます。"],
        subtext="",
        duration=4.5,
        zoom_from=1.00, zoom_to=1.06,
        pan_from=(0.50, 0.55), pan_to=(0.50, 0.48),
    ),
    PhotoScene(
        path=REPO / "7C1A5093.JPG",
        lines=["千年以上、", "斧の音を知らない。"],
        subtext="― 春日山原始林 ―",
        duration=4.5,
        zoom_from=1.04, zoom_to=1.00,
        pan_from=(0.38, 0.55), pan_to=(0.45, 0.55),
    ),
    PhotoScene(
        path=REPO / "7C1A5102.JPG",
        lines=["その深い緑と、", "神域の静けさに守られて。"],
        subtext="",
        duration=4.5,
        zoom_from=1.00, zoom_to=1.08,
        pan_from=(0.55, 0.50), pan_to=(0.48, 0.52),
    ),
    VideoScene(
        path=REPO / "鹿のや_神楽狂言_動画.mp4",
        start=1.0,
        duration=4.5,
        lines=["森の気配とともに、", "祈りの音。"],
        subtext="",
        caption_pos="upper",
        zoom_from=1.00, zoom_to=1.00,
        pan_from=(0.42, 0.55), pan_to=(0.58, 0.55),
    ),
    PhotoScene(
        path=REPO / "7C1A5107.JPG",
        lines=["奈良春日　鹿のや"],
        subtext="全5室・隠れ家オーベルジュ",
        duration=5.0,
        zoom_from=1.04, zoom_to=1.00,
        pan_from=(0.50, 0.50), pan_to=(0.50, 0.52),
        caption_pos="center",
        veil=0.40,
    ),
]


def ease(t: float) -> float:
    return 3 * t * t - 2 * t * t * t


def scene_alpha(local_t: float, duration: float, fade_in=0.9, fade_out=0.9) -> float:
    if local_t < fade_in:
        return ease(local_t / fade_in)
    if local_t > duration - fade_out:
        return ease(max(0.0, (duration - local_t) / fade_out))
    return 1.0


def crop_zoom(img: Image.Image, zoom: float, cx: float, cy: float) -> Image.Image:
    """Crop a 4:5 region at (cx, cy) with zoom, then resize to WxH."""
    iw, ih = img.size
    # The crop region has aspect ASPECT (W/H = 4/5 = 0.8). Fit by whichever
    # side of the source is the binding constraint.
    if iw / ih >= ASPECT:
        crop_h = ih / zoom
        crop_w = crop_h * ASPECT
    else:
        crop_w = iw / zoom
        crop_h = crop_w / ASPECT
    x = cx * iw - crop_w / 2
    y = cy * ih - crop_h / 2
    x = max(0, min(iw - crop_w, x))
    y = max(0, min(ih - crop_h, y))
    box = (int(x), int(y), int(x + crop_w), int(y + crop_h))
    return img.crop(box).resize((W, H), Image.LANCZOS)


def add_vignette(img: Image.Image, strength: float = 0.35) -> Image.Image:
    mask = Image.new("L", (W, H), 0)
    md = ImageDraw.Draw(mask)
    md.ellipse([-W * 0.1, -H * 0.1, W * 1.1, H * 1.1], fill=255)
    mask = mask.filter(ImageFilter.GaussianBlur(180))
    dark = Image.new("RGB", (W, H), (0, 0, 0))
    inv = Image.eval(mask, lambda v: int(255 - v))
    out = img.copy()
    out.paste(dark, (0, 0), Image.eval(inv, lambda v: int(v * strength)))
    return out


def add_bottom_scrim(img: Image.Image) -> Image.Image:
    """Gradient scrim at bottom for text legibility."""
    scrim = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    d = ImageDraw.Draw(scrim)
    for y in range(int(H * 0.55), H):
        t = (y - H * 0.55) / (H * 0.45)
        a = int(150 * ease(t))
        d.line([(0, y), (W, y)], fill=(0, 0, 0, a))
    return Image.alpha_composite(img.convert("RGBA"), scrim).convert("RGB")


def add_top_scrim(img: Image.Image) -> Image.Image:
    """Gradient scrim at top (for captions positioned high)."""
    scrim = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    d = ImageDraw.Draw(scrim)
    top_h = int(H * 0.40)
    for y in range(top_h):
        t = 1.0 - (y / top_h)
        a = int(140 * ease(t))
        d.line([(0, y), (W, y)], fill=(0, 0, 0, a))
    return Image.alpha_composite(img.convert("RGBA"), scrim).convert("RGB")


def apply_veil(img: Image.Image, strength: float) -> Image.Image:
    if strength <= 0:
        return img
    overlay = Image.new("RGB", (W, H), (10, 16, 14))
    return Image.blend(img, overlay, strength)


def load_font(size: int, bold: bool = False) -> ImageFont.FreeTypeFont:
    return ImageFont.truetype(FONT_SERIF_BOLD if bold else FONT_SERIF, size=size)


def draw_caption(
    base: Image.Image,
    lines: list[str],
    subtext: str,
    alpha: float,
    position: str = "lower",
) -> Image.Image:
    layer = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    draw = ImageDraw.Draw(layer)

    longest = max((len(s) for s in lines), default=0)
    # Scale typography with frame height so landscape frames stay readable.
    h_scale = min(1.0, H / 900)
    main_base = 74 if longest > 10 else 86
    main_size = max(34, int(main_base * h_scale))
    sub_size = max(18, int(30 * max(0.75, h_scale)))
    sub_gap = int(40 * max(0.6, h_scale))
    edge_margin = max(24, int(60 * h_scale))

    main_font = load_font(main_size)
    sub_font = load_font(sub_size)

    line_gap = int(main_size * 0.55)
    widths, heights = [], []
    for s in lines:
        bbox = draw.textbbox((0, 0), s, font=main_font)
        widths.append(bbox[2] - bbox[0])
        heights.append(bbox[3] - bbox[1])
    main_h = sum(heights) + line_gap * max(0, len(lines) - 1)

    sub_h = sub_w = 0
    if subtext:
        sb = draw.textbbox((0, 0), subtext, font=sub_font)
        sub_w = sb[2] - sb[0]
        sub_h = sb[3] - sb[1]

    total_h = main_h + (sub_gap + sub_h if subtext else 0)

    if position == "center":
        y = (H - total_h) // 2
    elif position == "upper":
        y = edge_margin
    else:  # "lower" — bottom-align so short frames still fit.
        y = H - total_h - edge_margin

    a = int(255 * alpha)
    sa = int(170 * alpha)

    for i, s in enumerate(lines):
        x = (W - widths[i]) // 2
        draw.text((x + 2, y + 2), s, font=main_font, fill=(*SHADOW, sa))
        draw.text((x, y), s, font=main_font, fill=(*INK, a))
        y += heights[i] + line_gap

    if subtext:
        y_sub = y + sub_gap - line_gap
        divider_w = max(60, int(90 * h_scale))
        dx = (W - divider_w) // 2
        draw.line(
            [(dx, y_sub - int(18 * h_scale)), (dx + divider_w, y_sub - int(18 * h_scale))],
            fill=(*MIST, int(180 * alpha)),
            width=1,
        )
        x = (W - sub_w) // 2
        draw.text((x, y_sub), subtext, font=sub_font, fill=(*MIST, a))

    return Image.alpha_composite(base.convert("RGBA"), layer).convert("RGB")


def render_photo_scene(scene: PhotoScene, start_frame: int) -> int:
    print(f"  photo: {scene.path.name}")
    src = Image.open(scene.path).convert("RGB")
    # pre-downsize to speed up repeated crops
    max_side = 2400
    if max(src.size) > max_side:
        ratio = max_side / max(src.size)
        src = src.resize((int(src.size[0] * ratio), int(src.size[1] * ratio)), Image.LANCZOS)

    n = int(scene.duration * FPS)
    for k in range(n):
        t = k / max(1, n - 1)
        te = ease(t)
        zoom = scene.zoom_from + (scene.zoom_to - scene.zoom_from) * te
        cx = scene.pan_from[0] + (scene.pan_to[0] - scene.pan_from[0]) * te
        cy = scene.pan_from[1] + (scene.pan_to[1] - scene.pan_from[1]) * te
        frame = crop_zoom(src, zoom, cx, cy)
        frame = add_vignette(frame, 0.30)
        frame = apply_veil(frame, scene.veil)
        if scene.caption_pos == "upper":
            frame = add_top_scrim(frame)
        elif scene.caption_pos == "lower":
            frame = add_bottom_scrim(frame)
        alpha = scene_alpha(k / FPS, scene.duration)
        frame = draw_caption(frame, scene.lines, scene.subtext, alpha, scene.caption_pos)
        frame.save(FRAMES / f"f_{start_frame + k:05d}.png", "PNG")
    return n


def render_video_scene(scene: VideoScene, start_frame: int) -> int:
    print(f"  video: {scene.path.name}")
    tmp = ROOT / "_vidtmp"
    if tmp.exists():
        shutil.rmtree(tmp)
    tmp.mkdir()
    # Extract at source resolution; crop/zoom/pan happens per-frame in Python
    # so the Kagura clip can share the same Ken Burns treatment as the stills.
    cmd = [
        "ffmpeg", "-y",
        "-ss", str(scene.start),
        "-t", str(scene.duration),
        "-i", str(scene.path),
        "-vf", f"fps={FPS}",
        "-q:v", "2",
        str(tmp / "v_%05d.jpg"),
    ]
    subprocess.run(cmd, check=True, capture_output=True)

    files = sorted(tmp.glob("v_*.jpg"))
    n = len(files)
    for k, p in enumerate(files):
        t = k / max(1, n - 1)
        te = ease(t)
        zoom = scene.zoom_from + (scene.zoom_to - scene.zoom_from) * te
        cx = scene.pan_from[0] + (scene.pan_to[0] - scene.pan_from[0]) * te
        cy = scene.pan_from[1] + (scene.pan_to[1] - scene.pan_from[1]) * te
        src = Image.open(p).convert("RGB")
        frame = crop_zoom(src, zoom, cx, cy)
        frame = add_vignette(frame, 0.25)
        frame = apply_veil(frame, scene.veil)
        if scene.caption_pos == "upper":
            frame = add_top_scrim(frame)
        elif scene.caption_pos == "lower":
            frame = add_bottom_scrim(frame)
        alpha = scene_alpha(k / FPS, scene.duration)
        frame = draw_caption(frame, scene.lines, scene.subtext, alpha, scene.caption_pos)
        frame.save(FRAMES / f"f_{start_frame + k:05d}.png", "PNG")
    shutil.rmtree(tmp)
    return n


def render() -> int:
    if FRAMES.exists():
        shutil.rmtree(FRAMES)
    FRAMES.mkdir(parents=True)

    idx = 0
    for scene in SCENES:
        if isinstance(scene, PhotoScene):
            idx += render_photo_scene(scene, idx)
        else:
            idx += render_video_scene(scene, idx)
    print(f"rendered {idx} frames ({idx / FPS:.1f}s)")
    return idx


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
    print(f"wrote {OUT.relative_to(REPO)}")


if __name__ == "__main__":
    render()
    encode()
