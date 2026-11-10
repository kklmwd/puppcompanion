"""Turn the green-screen renders in art/raw into pixel-art sprites in assets/."""
import sys
from pathlib import Path
import numpy as np
from PIL import Image
from scipy import ndimage

ROOT = Path(__file__).resolve().parent.parent
RAW, OUT = ROOT / "art" / "raw", ROOT / "assets"
CELL = 24      # raw pixels per pixel-art pixel (the app shows each one 3x)
COLORS = 24    # shared palette size
OUTLINE = (74, 40, 24, 255)


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


def pixelate(im):
    """Shrink to chunky pixels with hard edges."""
    w, h = max(1, round(im.width / CELL)), max(1, round(im.height / CELL))
    arr = np.asarray(im).astype(np.float32)
    a = arr[..., 3:4] / 255
    pre = Image.fromarray(np.dstack([arr[..., :3] * a, arr[..., 3:]]).astype(np.uint8), "RGBA")
    small = np.asarray(pre.resize((w, h), Image.BOX)).astype(np.float32)
    sa = small[..., 3:4] / 255
    rgb = np.where(sa > 0, small[..., :3] / np.maximum(sa, 1e-3), 0)
    return np.clip(rgb, 0, 255), sa[..., 0] >= 0.5


def outline(rgba):
    """Add a 1px dark outline around the silhouette."""
    padded = np.pad(rgba, ((1, 1), (1, 1), (0, 0)))
    solid = padded[..., 3] > 0
    edge = ndimage.binary_dilation(solid) & ~solid
    padded[edge] = OUTLINE
    return padded


def main():
    OUT.mkdir(exist_ok=True)
    keyed, boxes = {}, {}
    for src in sorted(RAW.glob("*.png"), key=lambda p: p.stem != "sit"):  # sit first
        im = key(src)
        boxes[src.stem] = im.getchannel("A").point(lambda a: 255 if a > 8 else 0).getbbox()
        # blink is the sit frame with closed eyes: share its box so it doesn't jitter
        keyed[src.stem] = im.crop(boxes["sit"] if src.stem == "blink" else boxes[src.stem])

    small = {name: pixelate(im) for name, im in keyed.items()}

    # one palette for every pose so colours never flicker between frames
    pool = np.concatenate([rgb[mask] for rgb, mask in small.values()])
    pool = np.clip((pool - 128) * 1.12 + 128, 0, 255).astype(np.uint8)   # a touch more contrast
    pal_img = Image.fromarray(pool[None], "RGB").quantize(COLORS, method=Image.MEDIANCUT, kmeans=4)

    for name, (rgb, mask) in small.items():
        rgb = np.clip((rgb - 128) * 1.12 + 128, 0, 255).astype(np.uint8)
        q = Image.fromarray(rgb, "RGB").quantize(palette=pal_img, dither=Image.NONE).convert("RGB")
        rgba = np.dstack([np.asarray(q), mask.astype(np.uint8) * 255])
        rgba[~mask] = 0
        out = Image.fromarray(outline(rgba), "RGBA")
        out.save(OUT / f"{name}.png")
        print(name, out.size)
        if name == "sit":
            side = int(out.width * 0.64)
            face = out.crop((0, 0, side, side))
            face.resize((256, 256), Image.NEAREST).save(OUT / "icon.png")
            face.resize((32, 32), Image.BOX).save(OUT / "tray.png")


if __name__ == "__main__":
    sys.exit(main())
