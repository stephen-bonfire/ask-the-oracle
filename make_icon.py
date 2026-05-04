from PIL import Image, ImageDraw, ImageFilter
import math
import os
import shutil

def draw_icon(size):
    img = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)

    cx = cy = size / 2
    r = size * 0.42

    # --- Sphere: deep purple gradient, lighter at upper-left ---
    steps = int(r) + 1
    for i in range(steps, 0, -1):
        t = i / steps  # 1 at edge, 0 at center
        red   = int(18 + (1 - t) * 22)
        green = int(10 + (1 - t) * 12)
        blue  = int(38 + (1 - t) * 42)
        draw.ellipse([cx-i, cy-i, cx+i, cy+i], fill=(red, green, blue, 255))

    # --- Thin gold outer ring ---
    rw = max(1, int(size * 0.022))
    draw.ellipse([cx-r, cy-r, cx+r, cy+r], outline=(212, 168, 67, 200), width=rw)

    # --- Soft inner nebula glow (upper-left) ---
    glow_x = cx - r * 0.18
    glow_y = cy - r * 0.18
    glow_r = r * 0.55
    glow = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    gd = ImageDraw.Draw(glow)
    for i in range(int(glow_r), 0, -3):
        t = 1 - (i / glow_r)
        alpha = int(t * t * 55)
        gd.ellipse(
            [glow_x - i, glow_y - i, glow_x + i, glow_y + i],
            fill=(120, 80, 200, alpha),
        )
    glow = glow.filter(ImageFilter.GaussianBlur(radius=size * 0.04))
    img = Image.alpha_composite(img, glow)

    # --- Gold crescent highlight ---
    draw = ImageDraw.Draw(img)
    hl_x = cx - r * 0.22
    hl_y = cy - r * 0.28
    hl_r = r * 0.28
    for i in range(int(hl_r), 0, -1):
        t = 1 - (i / hl_r)
        alpha = int(t ** 1.5 * 200)
        col = (255, 220, 120, alpha)
        draw.ellipse([hl_x-i, hl_y-i, hl_x+i, hl_y+i], fill=col)

    # Bright specular point
    sp = max(1, int(hl_r * 0.28))
    draw.ellipse([hl_x-sp, hl_y-sp, hl_x+sp, hl_y+sp], fill=(255, 252, 220, 240))

    # --- Clip everything to the sphere circle ---
    mask = Image.new("L", (size, size), 0)
    ImageDraw.Draw(mask).ellipse([cx-r, cy-r, cx+r, cy+r], fill=255)
    img.putalpha(mask)

    # Re-draw gold ring on top of the mask
    draw = ImageDraw.Draw(img)
    draw.ellipse([cx-r+rw//2, cy-r+rw//2, cx+r-rw//2, cy+r-rw//2],
                 outline=(212, 168, 67, 200), width=rw)

    return img


# Build iconset
iconset = "/tmp/OracleApp.iconset"
os.makedirs(iconset, exist_ok=True)

sizes = [
    ("icon_16x16.png",       16),
    ("icon_16x16@2x.png",    32),
    ("icon_32x32.png",       32),
    ("icon_32x32@2x.png",    64),
    ("icon_128x128.png",    128),
    ("icon_128x128@2x.png", 256),
    ("icon_256x256.png",    256),
    ("icon_256x256@2x.png", 512),
    ("icon_512x512.png",    512),
    ("icon_512x512@2x.png",1024),
]

for filename, sz in sizes:
    icon = draw_icon(sz)
    icon.save(os.path.join(iconset, filename))
    print(f"  {filename}")

# Convert to .icns
icns_path = "/tmp/OracleApp.icns"
os.system(f"iconutil -c icns {iconset} -o {icns_path}")
print(f"\nSaved: {icns_path}")
