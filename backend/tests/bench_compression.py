"""Payload-size benchmark: PNG screenshot vs. extension's downscaled JPEG. Run: python tests/bench_compression.py"""
import base64
import io
import random

from PIL import Image, ImageChops, ImageDraw, ImageFilter


def chart(w=1920, h=1080):
    random.seed(1)
    img = Image.new("RGB", (w, h), (19, 23, 34))
    d = ImageDraw.Draw(img)
    for x in range(0, w, 120):
        d.line([(x, 0), (x, h)], fill=(40, 46, 60))
    for y in range(0, h, 90):
        d.line([(0, y), (w, y)], fill=(40, 46, 60))
    p = h / 2
    for x in range(20, w - 20, 14):
        o = p
        p += random.uniform(-25, 25)
        c = (38, 166, 154) if p >= o else (239, 83, 80)
        d.line([(x, min(o, p) - 12), (x, max(o, p) + 12)], fill=c)
        d.rectangle([x - 4, min(o, p), x + 4, max(o, p)], fill=c)
    return img


img = chart().filter(ImageFilter.GaussianBlur(0.6))
noise = Image.effect_noise(img.size, 12).convert("RGB")
img = ImageChops.add(img, noise, scale=2.0, offset=-64)
png = io.BytesIO(); img.save(png, "PNG")
small = img.resize((1280, round(1080 * 1280 / 1920)), Image.LANCZOS)
jpg = io.BytesIO(); small.save(jpg, "JPEG", quality=72)
for name, b in (("png_1920x1080", png), ("jpeg_1280_q72", jpg)):
    raw = len(b.getvalue())
    print(f"{name}: {raw/1024:.0f} KiB raw, {len(base64.b64encode(b.getvalue()))/1024:.0f} KiB base64")
