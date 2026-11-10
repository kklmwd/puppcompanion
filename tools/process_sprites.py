"""Turn the green-screen renders in art/raw into trimmed transparent sprites in assets/."""
import sys
from pathlib import Path
import numpy as np
from PIL import Image
from scipy import ndimage

ROOT = Path(__file__).resolve().parent.parent
RAW, OUT = ROOT / "art" / "raw", ROOT / "assets"
SCALE = 0.25  # 2048px renders -> ~2x of on-screen size


def key(path):
    rgb = np.asarray(Image.open(path).convert("RGB")).astype(np.float32)
    r, g, b = rgb[..., 0], rgb[..., 1], rgb[..., 2]
    spill = g - np.maximum(r, b)              # how much greener than anything else
    alpha = np.clip(1.0 - (spill - 20) / 60, 0, 1)
    # keep only the biggest blob; erode first so thin bridges to stray artifacts break
    core = ndimage.binary_erosion(alpha > 0.5, iterations=10)
    labels, n = ndimage.label(core)
    if n > 1:
        sizes = ndimage.sum(np.ones_like(labels), labels, range(1, n + 1))
        keep = labels == (1 + int(np.argmax(sizes)))
        alpha = alpha * ndimage.binary_dilation(keep, iterations=13)
    alpha = np.minimum(alpha, ndimage.minimum_filter(alpha, 3))  # shave 1px halo
    g2 = np.where(spill > 0, np.maximum(r, b), g)                # despill
    out = np.dstack([r, g2, b, alpha * 255]).astype(np.uint8)
    return Image.fromarray(out, "RGBA")


def main():
    OUT.mkdir(exist_ok=True)
    boxes = {}
    for src in sorted(RAW.glob("*.png"), key=lambda p: p.stem != "sit"):  # sit first
        im = key(src)
        boxes[src.stem] = im.getchannel("A").point(lambda a: 255 if a > 8 else 0).getbbox()
        # blink is the sit frame with closed eyes: share its box so it doesn't jitter
        im = im.crop(boxes["sit"] if src.stem == "blink" else boxes[src.stem])
        if src.stem == "sit":
            w, h = im.size
            face = im.crop((0, 0, int(w * 0.62), int(w * 0.62)))
            face.resize((256, 256), Image.LANCZOS).save(OUT / "icon.png")
            face.resize((32, 32), Image.LANCZOS).save(OUT / "tray.png")
        im = im.resize((round(im.width * SCALE), round(im.height * SCALE)), Image.LANCZOS)
        im.save(OUT / src.name)
        print(src.name, im.size)


if __name__ == "__main__":
    sys.exit(main())
