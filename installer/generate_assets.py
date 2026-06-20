"""
ExamGuard Installer Asset Generator
====================================
Generates all bitmap/icon assets required by Inno Setup from a source PNG.

Outputs
-------
  installer/assets/examguard.ico        -- Multi-size Windows icon (16->256)
  installer/assets/examguard_256.png    -- 256px PNG (for reference)
  installer/assets/wizard_banner.bmp    -- 164x314 sidebar banner
  installer/assets/wizard_header.bmp    -- 55x55 header badge

Source
------
  installer/assets/source_icon.png      -- High-res source icon (1024x1024)
  If the source PNG is missing, a geometric fallback is drawn with Pillow.
"""

import os
import sys
import math

# ---------------------------------------------------------------------------
# Force UTF-8 output so no UnicodeEncodeError on Windows cp1252 consoles
# ---------------------------------------------------------------------------
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

from PIL import Image, ImageDraw, ImageFilter

# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------
SCRIPT_DIR  = os.path.dirname(os.path.abspath(__file__))
ASSETS_DIR  = os.path.join(SCRIPT_DIR, "assets")
SOURCE_PNG  = os.path.join(ASSETS_DIR, "source_icon.png")
ICO_PATH    = os.path.join(ASSETS_DIR, "examguard.ico")
PNG256_PATH = os.path.join(ASSETS_DIR, "examguard_256.png")
BANNER_PATH = os.path.join(ASSETS_DIR, "wizard_banner.bmp")
HEADER_PATH = os.path.join(ASSETS_DIR, "wizard_header.bmp")

os.makedirs(ASSETS_DIR, exist_ok=True)

# ---------------------------------------------------------------------------
# Brand colors
# ---------------------------------------------------------------------------
C_BG_DARK   = (6,  11,  28)     # #060B1C  deep navy
C_BG_MID    = (13, 27,  62)     # #0D1B3E  navy
C_BLUE      = (21, 101, 192)    # #1565C0  cobalt
C_CYAN      = (0,  229, 255)    # #00E5FF  electric cyan
C_WHITE     = (255, 255, 255)
C_DIVIDER   = (30, 60, 120)     # subtle blue line


# ===========================================================================
# SOURCE ICON LOADER
# ===========================================================================

def load_source_icon(size: int) -> Image.Image:
    """
    Load the high-res source PNG and resize to `size`x`size` with LANCZOS
    anti-aliasing for perfect sharpness at any size.
    Falls back to the programmatic shield if source_icon.png is missing.
    """
    if os.path.exists(SOURCE_PNG):
        img = Image.open(SOURCE_PNG).convert("RGBA")
        return img.resize((size, size), Image.LANCZOS)
    else:
        print("  [WARN] source_icon.png not found -- using fallback drawing")
        return _draw_fallback_shield(size)


def _draw_fallback_shield(size: int) -> Image.Image:
    """Minimal programmatic fallback shield if no source PNG exists."""
    img  = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)
    m    = size // 8

    # Shield body
    pts = [
        (m, m), (size - m, m),
        (size - m, size // 2),
        (size // 2, size - m),
        (m, size // 2),
    ]
    draw.polygon(pts, fill=(*C_BG_MID, 255))
    draw.polygon(pts, outline=(*C_CYAN, 220), width=max(1, size // 32))

    # Eye
    cx, cy = size // 2, int(size * 0.42)
    ew, eh = size // 3, size // 6
    draw.ellipse([cx - ew, cy - eh, cx + ew, cy + eh],
                 fill=(*C_CYAN, 200))
    r = size // 10
    draw.ellipse([cx - r, cy - r, cx + r, cy + r],
                 fill=(5, 10, 25, 255))
    return img


# ===========================================================================
# 1. ICO -- multi-size Windows icon
# ===========================================================================

def generate_ico():
    print("[1/3] Generating application icon (ICO)...")
    sizes  = [16, 24, 32, 48, 64, 128, 256]
    frames = []

    for s in sizes:
        frame = load_source_icon(s)
        # For very small sizes apply a very mild sharpening pass
        if s <= 32:
            frame = frame.filter(ImageFilter.SHARPEN)
        frames.append(frame)
        print(f"  [OK] Rendered {s}x{s}")

    # Save ICO (all sizes packed)
    frames[0].save(
        ICO_PATH,
        format="ICO",
        sizes=[(s, s) for s in sizes],
        append_images=frames[1:],
    )
    print(f"  [OK] Saved: {ICO_PATH}")

    # Save reference PNG at 256px
    frames[-1].save(PNG256_PATH, format="PNG")
    print(f"  [OK] Saved: {PNG256_PATH}")


# ===========================================================================
# 2. WIZARD BANNER -- 164x314 sidebar (left panel of the setup wizard)
# ===========================================================================

def generate_banner():
    """
    Produces a sharp, premium 164x314 sidebar banner:
      - Dark navy gradient background
      - Centred icon (110x110)
      - 'ExamGuard' title and subtitle
      - Bullet feature list
      - Version string at bottom
    """
    print("[2/3] Generating wizard banner (164x314 BMP)...")
    W, H = 164, 314
    img  = Image.new("RGB", (W, H), C_BG_DARK)
    draw = ImageDraw.Draw(img)

    # --- Background gradient (top navy -> slightly lighter mid) -----------
    for y in range(H):
        t   = y / H
        r   = int(C_BG_DARK[0] + (C_BG_MID[0] - C_BG_DARK[0]) * t)
        g   = int(C_BG_DARK[1] + (C_BG_MID[1] - C_BG_DARK[1]) * t)
        b   = int(C_BG_DARK[2] + (C_BG_MID[2] - C_BG_DARK[2]) * t * 0.6)
        draw.line([(0, y), (W, y)], fill=(r, g, b))

    # --- Subtle left/right edge cyan accent lines -------------------------
    draw.line([(0, 0), (0, H)],     fill=(*C_CYAN, 180), width=2)
    draw.line([(W-1, 0), (W-1, H)], fill=(*C_BLUE, 80),  width=1)

    # --- Icon (110x110, centered horizontally, top area) -----------------
    icon_size = 110
    icon_img  = load_source_icon(icon_size).convert("RGBA")

    # Paste with alpha mask so transparent corners stay clean
    icon_x = (W - icon_size) // 2
    icon_y = 18
    img.paste(icon_img, (icon_x, icon_y), icon_img)

    # --- Thin cyan divider below icon ------------------------------------
    div_y = icon_y + icon_size + 10
    draw.line([(14, div_y), (W - 14, div_y)], fill=(*C_CYAN, 160), width=1)

    # --- Title text (drawn pixel-by-pixel without font file dependency) --
    # We use Pillow's default bitmap font for guaranteed rendering
    try:
        from PIL import ImageFont
        # Try to load a system font for crisp text
        font_paths = [
            "C:/Windows/Fonts/segoeuib.ttf",   # Segoe UI Bold
            "C:/Windows/Fonts/calibrib.ttf",    # Calibri Bold
            "C:/Windows/Fonts/arialbd.ttf",     # Arial Bold
            "C:/Windows/Fonts/arial.ttf",       # Arial
        ]
        font_title = None
        font_sub   = None
        font_body  = None
        for fp in font_paths:
            if os.path.exists(fp):
                font_title = ImageFont.truetype(fp, 15)
                font_sub   = ImageFont.truetype(fp, 9)
                font_body  = ImageFont.truetype(fp, 9)
                break
        if font_title is None:
            font_title = ImageFont.load_default()
            font_sub   = font_title
            font_body  = font_title
    except Exception:
        from PIL import ImageFont
        font_title = ImageFont.load_default()
        font_sub   = font_title
        font_body  = font_title

    ty = div_y + 10

    # App name
    draw.text((W // 2, ty), "ExamGuard",
              font=font_title, fill=C_WHITE, anchor="mt")
    ty += 18

    # Subtitle
    draw.text((W // 2, ty), "Integrity Monitor",
              font=font_sub, fill=(*C_CYAN, 200), anchor="mt")
    ty += 16

    # Second divider
    draw.line([(14, ty), (W - 14, ty)], fill=C_DIVIDER, width=1)
    ty += 10

    # Feature bullets
    features = [
        "Exam integrity",
        "Live monitoring",
        "Risk scoring",
        "Local data only",
    ]
    for feat in features:
        draw.text((16, ty), "-  " + feat,
                  font=font_body, fill=(180, 200, 240), anchor="lt")
        ty += 13

    # Version at bottom
    draw.text((W // 2, H - 12), "v4.0.0",
              font=font_body, fill=(*C_CYAN, 180), anchor="mb")

    img.save(BANNER_PATH, format="BMP")
    print(f"  [OK] Saved: {BANNER_PATH}")


# ===========================================================================
# 3. WIZARD HEADER -- 55x55 badge (top-right on interior wizard pages)
# ===========================================================================

def generate_header():
    """
    55x55 icon badge — just the icon on a dark background, sharp at small size.
    """
    print("[3/3] Generating wizard header (55x55 BMP)...")
    W, H = 55, 55
    img  = Image.new("RGB", (W, H), C_BG_DARK)
    draw = ImageDraw.Draw(img)

    # Background gradient
    for y in range(H):
        t = y / H
        r = int(C_BG_DARK[0] + (C_BG_MID[0] - C_BG_DARK[0]) * t)
        g = int(C_BG_DARK[1] + (C_BG_MID[1] - C_BG_DARK[1]) * t)
        b = int(C_BG_DARK[2] + (C_BG_MID[2] - C_BG_DARK[2]) * t)
        draw.line([(0, y), (W, y)], fill=(r, g, b))

    # Icon centred, padded by 4px
    pad       = 4
    icon_size = W - pad * 2
    icon_img  = load_source_icon(icon_size).convert("RGBA")
    icon_img  = icon_img.filter(ImageFilter.SHARPEN)
    img.paste(icon_img, (pad, pad), icon_img)

    # Thin cyan border
    draw.rectangle([0, 0, W - 1, H - 1], outline=(*C_CYAN, 120), width=1)

    img.save(HEADER_PATH, format="BMP")
    print(f"  [OK] Saved: {HEADER_PATH}")


# ===========================================================================
# Entry point
# ===========================================================================

if __name__ == "__main__":
    print()
    print("[ExamGuard] Generating installer assets...")
    if os.path.exists(SOURCE_PNG):
        print(f"  Using source icon: {SOURCE_PNG}")
    else:
        print("  [WARN] No source_icon.png found -- using programmatic fallback")
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
