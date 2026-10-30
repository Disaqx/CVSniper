"""Draws installer/cvsniper.ico (the app and installer icon) with Pillow.

Run it again only if the design changes; the .ico is committed so building the
installer does not depend on it. Colours are the dashboard palette.
"""
from pathlib import Path
from PIL import Image, ImageDraw

S = 1024  # drawn large, scaled down per size so the lines stay crisp
img = Image.new("RGBA", (S, S), (0, 0, 0, 0))
d = ImageDraw.Draw(img)
d.rounded_rectangle((40, 40, S - 40, S - 40), radius=210, fill="#0a0a0c")

c, r = S // 2, 300
d.ellipse((c - r, c - r, c + r, c + r), outline="#7F5AF0", width=70)
for x0, y0, x1, y1 in ((c, 150, c, 380), (c, S - 380, c, S - 150),
                       (150, c, 380, c), (S - 380, c, S - 150, c)):
    d.line((x0, y0, x1, y1), fill="#7F5AF0", width=70)
d.ellipse((c - 75, c - 75, c + 75, c + 75), fill="#00E8C6")

out = Path(__file__).with_name("cvsniper.ico")
img.save(out, sizes=[(16, 16), (24, 24), (32, 32), (48, 48), (64, 64), (128, 128), (256, 256)])
print("wrote", out)
