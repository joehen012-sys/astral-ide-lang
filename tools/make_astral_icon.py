from PIL import Image, ImageDraw
from pathlib import Path

OUT = Path(__file__).resolve().parents[1] / "assets" / "icons" / "astral.ico"
OUT.parent.mkdir(parents=True, exist_ok=True)

size = 256
img = Image.new("RGBA", (size, size), (12, 18, 32, 255))
d = ImageDraw.Draw(img)

# Outer ring
margin = 24
d.ellipse((margin, margin, size - margin, size - margin), outline=(96, 165, 250, 255), width=16)

# Star center
cx, cy = size // 2, size // 2
r1, r2 = 58, 24
points = []
for i in range(10):
    r = r1 if i % 2 == 0 else r2
    a = -90 + i * 36
    from math import cos, sin, radians

    points.append((cx + r * cos(radians(a)), cy + r * sin(radians(a))))

d.polygon(points, fill=(252, 211, 77, 255))

# Export multi-size ICO
sizes = [(16, 16), (24, 24), (32, 32), (48, 48), (64, 64), (128, 128), (256, 256)]
img.save(OUT, format="ICO", sizes=sizes)
print(f"Wrote icon: {OUT}")
