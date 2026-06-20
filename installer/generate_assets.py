#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
ExamGuard Installer Asset Generator
====================================
Converts the premium source PNG into production-ready installer assets:

  - installer/assets/examguard.ico       -- Multi-size Windows icon (16-256px)
  - installer/assets/examguard_256.png   -- Reference PNG
  - installer/assets/wizard_banner.bmp  -- Inno Setup left panel (164x314)
  - installer/assets/wizard_header.bmp  -- Inno Setup corner icon  (55x55)

Source image: installer/assets/icon_source.png
Replace that file to change the icon across all assets in one rebuild.
"""

import os
import sys

sys.stdout.reconfigure(encoding="utf-8")

try:
    from PIL import Image, ImageDraw, ImageFont, ImageFilter, ImageEnhance
except ImportError:
    import subprocess
    subprocess.check_call([sys.executable, "-m", "pip", "install", "Pillow", "--quiet"])
    from PIL import Image, ImageDraw, ImageFont, ImageFilter, ImageEnhance

# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------
SCRIPT_DIR  = os.path.dirname(os.path.abspath(__file__))
ASSETS_DIR  = os.path.join(SCRIPT_DIR, "assets")
SOURCE_PNG  = os.path.join(ASSETS_DIR, "icon_source.png")
ICO_PATH    = os.path.join(ASSETS_DIR, "examguard.ico")
PNG256_PATH = os.path.join(ASSETS_DIR, "examguard_256.png")
BANNER_PATH = os.path.join(ASSETS_DIR, "wizard_banner.bmp")
HEADER_PATH = os.path.join(ASSETS_DIR, "wizard_header.bmp")

os.makedirs(ASSETS_DIR, exist_ok=True)

# ---------------------------------------------------------------------------
# Color palette (matches the premium icon)
# ---------------------------------------------------------------------------
COL_BG_TOP    = (5,   10,  26)   # Deep space navy
COL_BG_BOT    = (13,  27,  62)   # Dark cobalt
COL_ACCENT    = (0,   180, 240)  # Electric cyan
COL_BORDER    = (30,  100, 200)  # Blue border
COL_TEXT      = (255, 255, 255)  # Pure white
COL_SUBTEXT   = (100, 160, 220)  # Soft blue-white
COL_MUTED     = (55,  100, 160)  # Muted blue
COL_DIVIDER   = (25,  60,  120)  # Divider line


# ---------------------------------------------------------------------------
# Helper: load source PNG at a given size (always sharp)
# ---------------------------------------------------------------------------
def get_source(size: int) -> Image.Image:
    """Load the premium source PNG and resize to `size` x `size`.
    Applies extra sharpening for small sizes so they read clearly
    in Windows Explorer, taskbar, and desktop shortcuts.
    """
    if not os.path.exists(SOURCE_PNG):
        raise FileNotFoundError(
            f"Source icon PNG not found: {SOURCE_PNG}\n"
            "Run build.ps1 which copies it from the project root."
        )
    src = Image.open(SOURCE_PNG).convert("RGBA")

    # Resize with LANCZOS (best quality downscaling)
    img = src.resize((size, size), Image.LANCZOS)

    # For small sizes, sharpen so details don't blur out
    if size <= 32:
        img = img.filter(ImageFilter.UnsharpMask(radius=0.6, percent=160, threshold=2))
        enhancer = ImageEnhance.Contrast(img)
        img = enhancer.enhance(1.3)
        enhancer = ImageEnhance.Sharpness(img)
        img = enhancer.enhance(2.0)
    elif size <= 48:
        img = img.filter(ImageFilter.UnsharpMask(radius=0.8, percent=120, threshold=2))
        enhancer = ImageEnhance.Sharpness(img)
        img = enhancer.enhance(1.5)

    return img


# ---------------------------------------------------------------------------
# Helper: gradient fill on a draw object
# ---------------------------------------------------------------------------
def draw_gradient(draw, w, h, top_col, bot_col):
    for y in range(h):
        t = y / max(h - 1, 1)
        r = int(top_col[0] + (bot_col[0] - top_col[0]) * t)
        g = int(top_col[1] + (bot_col[1] - top_col[1]) * t)
        b = int(top_col[2] + (bot_col[2] - top_col[2]) * t)
        draw.line([(0, y), (w - 1, y)], fill=(r, g, b))


# ---------------------------------------------------------------------------
# Helper: font loader
# ---------------------------------------------------------------------------
def load_font(size: int, bold: bool = False) -> ImageFont.FreeTypeFont:
    candidates = [
        "C:/Windows/Fonts/segoeuib.ttf" if bold else "C:/Windows/Fonts/segoeui.ttf",
        "C:/Windows/Fonts/segoeuil.ttf",
        "C:/Windows/Fonts/calibrib.ttf" if bold else "C:/Windows/Fonts/calibri.ttf",
        "C:/Windows/Fonts/arialbd.ttf"  if bold else "C:/Windows/Fonts/arial.ttf",
    ]
    for path in candidates:
        if os.path.exists(path):
            try:
                return ImageFont.truetype(path, size)
            except Exception:
                continue
    return ImageFont.load_default()


# ---------------------------------------------------------------------------
# Helper: centered text
# ---------------------------------------------------------------------------
def draw_centered(draw, text, font, canvas_w, y, color):
    try:
        bbox = font.getbbox(text)
        tw   = bbox[2] - bbox[0]
    except Exception:
        tw = len(text) * 6
    x = max((canvas_w - tw) // 2, 0)
    draw.text((x, y), text, font=font, fill=color)


# ---------------------------------------------------------------------------
# 1. Generate .ICO  (16 through 256 px)
# ---------------------------------------------------------------------------
def generate_ico():
    print("[1/3] Generating application icon (ICO)...")
    sizes  = [16, 24, 32, 48, 64, 128, 256]
    frames = []

    for s in sizes:
        frame = get_source(s)
        frames.append(frame)
        print(f"  Rendered {s}x{s} icon frame")

    # Save ICO with all sizes embedded
    frames[0].save(
        ICO_PATH,
        format="ICO",
        sizes=[(s, s) for s in sizes],
        append_images=frames[1:]
    )

    # Save 256px PNG reference
    frames[-1].save(PNG256_PATH)

    print(f"  [OK] Saved: {ICO_PATH}")
    print(f"  [OK] Saved: {PNG256_PATH}")


# ---------------------------------------------------------------------------
# 2. Generate wizard banner  (164 x 314 BMP -- Inno Setup left panel)
# ---------------------------------------------------------------------------
def generate_banner():
    print("[2/3] Generating wizard banner (164x314 BMP)...")
    W, H = 164, 314

    banner = Image.new("RGB", (W, H))
    draw   = ImageDraw.Draw(banner)

    # Dark gradient background
    draw_gradient(draw, W, H, COL_BG_TOP, COL_BG_BOT)

    # Subtle left accent bar (electric cyan fade)
    for y in range(H):
        t      = y / H
        # Brightest in the middle
        fade   = 1.0 - abs(t - 0.4) * 2.2
        fade   = max(0.0, min(1.0, fade))
        cy_r   = int(0   * fade)
        cy_g   = int(180 * fade)
        cy_b   = int(240 * fade)
        draw.line([(0, y), (2, y)], fill=(cy_r, cy_g, cy_b))

    # Subtle right accent bar
    for y in range(H):
        t      = y / H
        fade   = 1.0 - abs(t - 0.6) * 3.0
        fade   = max(0.0, min(1.0, fade)) * 0.4
        cy_r   = int(0   * fade)
        cy_g   = int(120 * fade)
        cy_b   = int(200 * fade)
        draw.line([(W - 1, y), (W - 3, y)], fill=(cy_r, cy_g, cy_b))

    # --- App icon (centered, upper section) ---
    icon_sz = 96
    icon    = get_source(icon_sz)
    ix      = (W - icon_sz) // 2
    iy      = 38
    banner.paste(icon, (ix, iy), icon)

    # Subtle glow ring under icon
    for r in range(icon_sz // 2 + 18, icon_sz // 2 + 2, -1):
        alpha = int(30 * (1 - (r - icon_sz // 2 - 2) / 16))
        cx    = ix + icon_sz // 2
        cy    = iy + icon_sz // 2
        draw.ellipse(
            [(cx - r, cy - r), (cx + r, cy + r)],
            outline=(0, 120, 200, alpha)
        )

    # --- Typography ---
    font_title = load_font(13, bold=True)
    font_sub   = load_font(8,  bold=False)
    font_feat  = load_font(8,  bold=False)
    font_ver   = load_font(8,  bold=False)

    ty = iy + icon_sz + 12
    draw_centered(draw, "ExamGuard", font_title, W, ty, COL_TEXT)

    ty += 17
    draw_centered(draw, "Integrity Monitor", font_sub, W, ty, COL_SUBTEXT)

    # Divider
    ty += 15
    draw.line([(16, ty), (W - 16, ty)], fill=COL_DIVIDER, width=1)

    # Feature list
    ty += 10
    features = [
        "Exam integrity",
        "Live monitoring",
        "Risk scoring",
        "Local data only",
    ]
    for feat in features:
        # Dot bullet
        draw.ellipse([(16, ty + 3), (19, ty + 6)], fill=COL_ACCENT)
        draw.text((23, ty), feat, font=font_feat, fill=COL_SUBTEXT)
        ty += 13

    # Version tag
    draw_centered(draw, "v4.0.0", font_ver, W, H - 18, COL_MUTED)

    banner.save(BANNER_PATH, format="BMP")
    print(f"  [OK] Saved: {BANNER_PATH}")


# ---------------------------------------------------------------------------
# 3. Generate wizard header  (55 x 55 BMP -- corner thumbnail on inner pages)
# ---------------------------------------------------------------------------
def generate_header():
    print("[3/3] Generating wizard header (55x55 BMP)...")

    # White background (matches wizard page background)
    header = Image.new("RGB", (55, 55), (255, 255, 255))
    icon   = get_source(48)
    offset = (55 - 48) // 2
    header.paste(icon, (offset, offset), icon)

    header.save(HEADER_PATH, format="BMP")
    print(f"  [OK] Saved: {HEADER_PATH}")


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------
if __name__ == "__main__":
    print("[ExamGuard] Generating installer assets...")
    print()

    generate_ico()
    print()

    generate_banner()
    print()

    generate_header()
    print()

    print("[DONE] All assets generated successfully.")
    print()
    print(f"    ICO    : {ICO_PATH}")
    print(f"    Banner : {BANNER_PATH}")
    print(f"    Header : {HEADER_PATH}")
