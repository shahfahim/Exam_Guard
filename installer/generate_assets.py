# installer/generate_assets.py — ExamGuard Installer Asset Generator
#
# Generates all installer graphics programmatically using Pillow.
# Run this BEFORE building with PyInstaller + Inno Setup.
#
# Outputs:
#   installer/assets/examguard.ico       — Multi-size Windows icon
#   installer/assets/wizard_banner.bmp   — Inno Setup left-panel image (164×314)
#   installer/assets/wizard_header.bmp   — Inno Setup inner-page header (55×55)
#
# Usage:
#   python installer/generate_assets.py

import os
import sys
import math

# ── Ensure Pillow is available ────────────────────────────────────────────────
try:
    from PIL import Image, ImageDraw, ImageFont, ImageFilter
except ImportError:
    print("Installing Pillow...")
    import subprocess
    subprocess.check_call([sys.executable, "-m", "pip", "install", "pillow", "-q"])
    from PIL import Image, ImageDraw, ImageFont, ImageFilter

# ── Paths ─────────────────────────────────────────────────────────────────────
SCRIPT_DIR  = os.path.dirname(os.path.abspath(__file__))
ASSETS_DIR  = os.path.join(SCRIPT_DIR, "assets")
os.makedirs(ASSETS_DIR, exist_ok=True)

ICO_PATH     = os.path.join(ASSETS_DIR, "examguard.ico")
BANNER_PATH  = os.path.join(ASSETS_DIR, "wizard_banner.bmp")
HEADER_PATH  = os.path.join(ASSETS_DIR, "wizard_header.bmp")

# ── Brand Colors ──────────────────────────────────────────────────────────────
BG_DARK     = (11,  13,  20)      # #0B0D14
BG_MID      = (13,  15,  24)      # #0D0F18
INDIGO      = (91,  94,  232)     # #5B5EE8  (accent)
INDIGO_DEEP = (61,  63,  170)     # #3D3FAA
INDIGO_GLOW = (139, 143, 255)     # #8B8FFF
WHITE       = (241, 245, 249)     # #F1F5F9
MUTED       = (100, 116, 139)     # #64748B


# ─────────────────────────────────────────────────────────────────────────────
#  Shield drawing helper
# ─────────────────────────────────────────────────────────────────────────────
def draw_shield(draw: ImageDraw.ImageDraw, cx: float, cy: float,
                size: float, fill, outline, outline_width: int = 2):
    """
    Draw a classic security-shield polygon centered at (cx, cy).
    `size` is the half-height of the shield.
    """
    w  = size * 0.72    # half-width
    h  = size           # half-height (top to bottom tip)
    bh = h * 0.55       # where the straight sides start curving inward

    # Shield points: top-left → top-right → right-straight → bottom-tip → left-straight
    pts = [
        (cx - w,  cy - h),          # top-left
        (cx + w,  cy - h),          # top-right
        (cx + w,  cy - h + bh),     # right kink
        (cx,      cy + h),          # bottom tip
        (cx - w,  cy - h + bh),     # left kink
    ]

    draw.polygon(pts, fill=fill)
    if outline_width > 0:
        draw.polygon(pts, outline=outline)


# ─────────────────────────────────────────────────────────────────────────────
#  Eye / lens symbol inside the shield
# ─────────────────────────────────────────────────────────────────────────────
def draw_eye(draw: ImageDraw.ImageDraw, cx: float, cy: float,
             rx: float, ry: float, fill, outline, lw: int = 2):
    """Draw an almond-shaped eye at (cx, cy)."""
    # Outer eye shape (two arcs)
    box = [cx - rx, cy - ry, cx + rx, cy + ry]
    draw.ellipse(box, fill=fill, outline=outline, width=lw)
    # Pupil
    pr = ry * 0.42
    pbox = [cx - pr, cy - pr, cx + pr, cy + pr]
    draw.ellipse(pbox, fill=outline)
    # Highlight dot
    hr = pr * 0.30
    hbox = [cx - hr * 0.5 - pr * 0.3, cy - pr * 0.4 - hr,
            cx - hr * 0.5 - pr * 0.3 + hr * 2, cy - pr * 0.4 + hr]
    draw.ellipse(hbox, fill=(255, 255, 255, 200))


# ─────────────────────────────────────────────────────────────────────────────
#  Render one icon frame at `size` × `size`
# ─────────────────────────────────────────────────────────────────────────────
def render_icon_frame(size: int) -> Image.Image:
    img  = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)

    cx, cy  = size / 2, size / 2
    margin  = size * 0.06
    shield_h = (size / 2) - margin

    # ── Glow layers (soft outer glow) ────────────────────────────────────────
    for i in range(4, 0, -1):
        glow_alpha = 30 + i * 12
        glow_color = (*INDIGO_GLOW, glow_alpha)
        draw_shield(draw, cx, cy, shield_h + i * (size * 0.015),
                    fill=(0, 0, 0, 0), outline=glow_color,
                    outline_width=max(1, int(size * 0.018)))

    # ── Shield gradient body (simulate with layered polys) ───────────────────
    steps = 20
    for step in range(steps):
        t     = step / steps
        r     = int(INDIGO_DEEP[0] + (INDIGO[0] - INDIGO_DEEP[0]) * t)
        g_col = int(INDIGO_DEEP[1] + (INDIGO[1] - INDIGO_DEEP[1]) * t)
        b     = int(INDIGO_DEEP[2] + (INDIGO[2] - INDIGO_DEEP[2]) * t)
        alpha = 255
        scale = 1.0 - (step / steps) * 0.0   # full size for body
        w     = size * 0.36 - step * 0.5
        h     = shield_h    - step * 0.7
        bh    = h * 0.55
        if w <= 0 or h <= 0:
            break
        pts = [
            (cx - w,  cy - h),
            (cx + w,  cy - h),
            (cx + w,  cy - h + bh),
            (cx,      cy + h),
            (cx - w,  cy - h + bh),
        ]
        draw.polygon(pts, fill=(r, g_col, b, alpha))

    # ── Shield bright border ─────────────────────────────────────────────────
    draw_shield(draw, cx, cy, shield_h,
                fill=(0, 0, 0, 0), outline=(*INDIGO_GLOW, 210),
                outline_width=max(1, int(size * 0.025)))

    # ── Eye symbol centred inside shield ─────────────────────────────────────
    eye_cx = cx
    eye_cy = cy - shield_h * 0.05
    eye_rx = shield_h * 0.34
    eye_ry = shield_h * 0.22

    # Subtle eye glow
    for i in range(3, 0, -1):
        draw.ellipse([eye_cx - eye_rx - i*2, eye_cy - eye_ry - i*2,
                      eye_cx + eye_rx + i*2, eye_cy + eye_ry + i*2],
                     fill=(*INDIGO_GLOW, 18 * i))

    # Eye body (white)
    draw.ellipse([eye_cx - eye_rx, eye_cy - eye_ry,
                  eye_cx + eye_rx, eye_cy + eye_ry],
                 fill=(*WHITE, 240))
    # Iris
    ir = eye_ry * 0.70
    draw.ellipse([eye_cx - ir, eye_cy - ir, eye_cx + ir, eye_cy + ir],
                 fill=(*INDIGO, 255))
    # Pupil
    pr = ir * 0.45
    draw.ellipse([eye_cx - pr, eye_cy - pr, eye_cx + pr, eye_cy + pr],
                 fill=(5, 7, 14, 255))
    # Specular highlight
    hr = pr * 0.38
    draw.ellipse([eye_cx - pr * 0.5 - hr, eye_cy - pr * 0.5 - hr,
                  eye_cx - pr * 0.5 + hr, eye_cy - pr * 0.5 + hr],
                 fill=(255, 255, 255, 220))

    # ── Subtle scan-line across the shield (monitoring motif) ────────────────
    if size >= 48:
        line_y = eye_cy
        line_w = max(1, int(size * 0.012))
        for offset in range(-int(shield_h * 0.55), int(shield_h * 0.55), max(1, int(size*0.04))):
            alpha = max(0, 30 - abs(offset) // 3)
            draw.line([(cx - size*0.35, line_y + offset),
                       (cx + size*0.35, line_y + offset)],
                      fill=(*INDIGO_GLOW, alpha), width=line_w)

    # Apply subtle blur for smooth anti-aliasing on larger sizes
    if size >= 64:
        img = img.filter(ImageFilter.SMOOTH)

    return img


# ─────────────────────────────────────────────────────────────────────────────
#  Generate multi-size Windows ICO
# ─────────────────────────────────────────────────────────────────────────────
def generate_ico():
    sizes = [16, 24, 32, 48, 64, 128, 256]
    frames = []
    for s in sizes:
        frame = render_icon_frame(s)
        frames.append(frame)
        print(f"  Rendered {s}×{s} icon frame")

    # Save .ico with all sizes
    frames[0].save(
        ICO_PATH,
        format="ICO",
        sizes=[(s, s) for s in sizes],
        append_images=frames[1:],
    )
    print(f"  ✓  Saved: {ICO_PATH}")

    # Also save a 256px PNG for reference / taskbar
    png_path = os.path.join(ASSETS_DIR, "examguard_256.png")
    frames[-1].save(png_path, format="PNG")
    print(f"  ✓  Saved: {png_path}")


# ─────────────────────────────────────────────────────────────────────────────
#  Generate Inno Setup Wizard Banner  (164 × 314 px BMP — left panel)
# ─────────────────────────────────────────────────────────────────────────────
def generate_banner():
    W, H = 164, 314
    img  = Image.new("RGB", (W, H), BG_DARK)
    draw = ImageDraw.Draw(img)

    # Vertical gradient background
    for y in range(H):
        t = y / H
        r = int(BG_DARK[0] + (BG_MID[0] - BG_DARK[0]) * t)
        g = int(BG_DARK[1] + (BG_MID[1] - BG_DARK[1]) * t)
        b = int(BG_DARK[2] + (BG_MID[2] - BG_DARK[2]) * t)
        draw.line([(0, y), (W, y)], fill=(r, g, b))

    # Decorative indigo line on right edge
    for y in range(H):
        draw.line([(W-2, y), (W-1, y)], fill=INDIGO)

    # Shield icon (centered, upper portion)
    shield_frame = render_icon_frame(80)
    shield_rgb   = Image.new("RGB", (80, 80), BG_DARK)
    shield_rgb.paste(shield_frame, mask=shield_frame.split()[3])
    img.paste(shield_rgb, ((W - 80) // 2, 48))

    # "ExamGuard" text
    try:
        font_title = ImageFont.truetype("C:/Windows/Fonts/segoeuib.ttf", 13)
        font_sub   = ImageFont.truetype("C:/Windows/Fonts/segoeui.ttf",   8)
    except Exception:
        font_title = ImageFont.load_default()
        font_sub   = font_title

    title = "ExamGuard"
    bbox  = draw.textbbox((0, 0), title, font=font_title)
    tw    = bbox[2] - bbox[0]
    draw.text(((W - tw) // 2, 140), title, font=font_title, fill=WHITE)

    sub = "Integrity Monitor"
    bbox2 = draw.textbbox((0, 0), sub, font=font_sub)
    sw    = bbox2[2] - bbox2[0]
    draw.text(((W - sw) // 2, 158), sub, font=font_sub, fill=MUTED)

    # Horizontal divider
    draw.line([(16, 178), (W-16, 178)], fill=INDIGO_DEEP, width=1)

    # Feature bullets
    try:
        font_feat = ImageFont.truetype("C:/Windows/Fonts/segoeui.ttf", 7)
    except Exception:
        font_feat = ImageFont.load_default()

    features = [
        "✓  Exam integrity",
        "✓  Live monitoring",
        "✓  Risk scoring",
        "✓  Local data only",
    ]
    for i, feat in enumerate(features):
        draw.text((18, 192 + i * 16), feat, font=font_feat, fill=MUTED)

    # Version at bottom
    try:
        font_ver = ImageFont.truetype("C:/Windows/Fonts/segoeui.ttf", 7)
    except Exception:
        font_ver = ImageFont.load_default()

    ver_text = "v4.0.0"
    bbox3    = draw.textbbox((0, 0), ver_text, font=font_ver)
    vw       = bbox3[2] - bbox3[0]
    draw.text(((W - vw) // 2, H - 20), ver_text, font=font_ver, fill=INDIGO)

    img.save(BANNER_PATH, format="BMP")
    print(f"  ✓  Saved: {BANNER_PATH}")


# ─────────────────────────────────────────────────────────────────────────────
#  Generate Inno Setup Wizard Header  (55 × 55 px BMP — inner pages top-right)
# ─────────────────────────────────────────────────────────────────────────────
def generate_header():
    W, H = 55, 55
    img  = Image.new("RGB", (W, H), BG_DARK)
    draw = ImageDraw.Draw(img)

    # Small shield centred
    shield_frame = render_icon_frame(44)
    shield_rgb   = Image.new("RGB", (44, 44), BG_DARK)
    shield_rgb.paste(shield_frame, mask=shield_frame.split()[3])
    img.paste(shield_rgb, ((W - 44) // 2, (H - 44) // 2))

    img.save(HEADER_PATH, format="BMP")
    print(f"  ✓  Saved: {HEADER_PATH}")


# ─────────────────────────────────────────────────────────────────────────────
#  Entry point
# ─────────────────────────────────────────────────────────────────────────────
if __name__ == "__main__":
    print("\n[ExamGuard] Generating installer assets...\n")

    print("[1/3] Generating application icon (ICO)...")
    generate_ico()

    print("\n[2/3] Generating wizard banner (164×314 BMP)...")
    generate_banner()

    print("\n[3/3] Generating wizard header (55×55 BMP)...")
    generate_header()

    print("\n✓  All assets generated successfully.\n")
    print(f"    ICO:    {ICO_PATH}")
    print(f"    Banner: {BANNER_PATH}")
    print(f"    Header: {HEADER_PATH}")
