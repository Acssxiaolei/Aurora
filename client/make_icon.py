# -*- coding: utf-8 -*-
"""生成 Aurora 客户端图标（圆角方形 + 极光光带）。"""
import math
import os
from PIL import Image, ImageDraw

OUT_DIR = os.path.dirname(os.path.abspath(__file__))


def lerp_color(c1, c2, t):
    return tuple(int(c1[i] + (c2[i] - c1[i]) * t) for i in range(3))


def make_icon(size=256):
    img = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)
    for y in range(size):
        t = y / size
        c = lerp_color((30, 27, 75), (88, 28, 135), t)
        draw.line([(0, y), (size, y)], fill=c + (255,))

    mask = Image.new("L", (size, size), 0)
    md = ImageDraw.Draw(mask)
    radius = size // 5
    md.rounded_rectangle([0, 0, size - 1, size - 1], radius=radius, fill=255)
    img.putalpha(mask)

    for band, color in enumerate([(56, 189, 248), (168, 85, 247)]):
        pts = []
        for x in range(0, size, 4):
            y = size // 2 + math.sin(x / size * 4 + band * 1.5) * size // 6 + band * size // 12
            pts.append((x, y))
        for i in range(len(pts) - 1):
            draw.line([pts[i], pts[i + 1]], fill=color + (220,), width=max(4, size // 20))

    return img


if __name__ == "__main__":
    icon = make_icon(256)
    png_path = os.path.join(OUT_DIR, "aurora.png")
    ico_path = os.path.join(OUT_DIR, "aurora.ico")
    icon.save(png_path)
    icon.save(ico_path, sizes=[(256, 256), (128, 128), (64, 64), (48, 48), (32, 32), (16, 16)])
    print("icon saved:", png_path, ico_path)
