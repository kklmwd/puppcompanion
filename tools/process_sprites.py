"""Turn the green-screen renders in art/raw into pixel-art sprites in assets/.

art/raw/*.png         one pose per image
art/raw/sheets/*.png  several animation frames per image (read row by row)
"""
import sys
from pathlib import Path
import numpy as np
from PIL import Image
from scipy import ndimage

ROOT = Path(__file__).resolve().parent.parent
RAW, OUT = ROOT / "art" / "raw", ROOT / "assets"
CELL = 24      # raw pixels per pixel-art pixel for single poses (the app shows each one 3x)
COLORS = 32    # shared palette size
OUTLINE = (74, 40, 24, 255)
# sheets: frame count, and how tall (in sprite pixels) a reference frame should end up
SHEETS = {
    "walk": {"frames": 8, "height": 62, "ref": None, "align": "body"},   # ref None = average frame
    "fall": {"frames": 4, "height": 74, "ref": 3, "names": ["fall1", "fall2", "splat", "dazed"]},
}

# Ears are drawn smaller than in the renders. Each entry is (centre x, centre y, radius)
# of an ear: full-image coordinates for single poses, frame coordinates for sheet frames.
EAR_SCALE = 0.7
EARS = {
    "sit": [(1140, 360, 140), (385, 365, 95)],
    "blink": [(1140, 360, 140), (385, 365, 95)],
    "happy": [(1140, 360, 140), (385, 365, 95)],
    "held": [(1215, 280, 110), (700, 285, 100)],
    "sleep": [(1135, 1040, 130), (305, 1010, 95)],
    "walk": [[(238, 60, 58)]] * 8,
    "fall": [
        [(55, 85, 95), (360, 45, 65)],
        [(70, 140, 110), (340, 75, 85)],
        [(340, 305, 75), (610, 255, 60)],
        [(222, 118, 80), (505, 43, 50)],
    ],
}


def shrink_ears(rgba, ears, scale=EAR_SCALE):
    """Pinch each ear toward its centre so it ends up `scale` times its size.

    Inside the ear the picture is scaled down; a ring around it stretches to fill
    the gap, so the head and background stay continuous.
    """
    out = rgba.astype(np.float32)
    out[..., :3] *= out[..., 3:] / 255          # premultiply so edges don't fringe
    src = out.copy()
    h, w = rgba.shape[:2]
    for cx, cy, ear_r in ears:
        outer = ear_r * 1.6
        y0, y1 = max(0, int(cy - outer)), min(h, int(cy + outer) + 1)
        x0, x1 = max(0, int(cx - outer)), min(w, int(cx + outer) + 1)
        yy, xx = np.mgrid[y0:y1, x0:x1].astype(np.float32)
        dx, dy = xx - cx, yy - cy
        r = np.hypot(dx, dy)
        inner = scale * ear_r
        ring = ear_r + (r - inner) * (outer - ear_r) / (outer - inner)
        from_r = np.where(r <= inner, r / scale, np.where(r < outer, ring, r))
        k = np.where(r > 0, from_r / np.maximum(r, 1e-6), 1)
        coords = [cy + dy * k, cx + dx * k]
        for c in range(4):
            out[y0:y1, x0:x1, c] = ndimage.map_coordinates(src[..., c], coords, order=1, mode="constant")
        src = out.copy()
    a = out[..., 3:]
    out[..., :3] = np.where(a > 0, out[..., :3] * 255 / np.maximum(a, 1e-3), 0)
    return np.clip(out, 0, 255).astype(np.uint8)


def key(path):
    """Green screen -> RGBA with soft alpha and green spill removed."""
    rgb = np.asarray(Image.open(path).convert("RGB")).astype(np.float32)
    r, g, b = rgb[..., 0], rgb[..., 1], rgb[..., 2]
    spill = g - np.maximum(r, b)              # how much greener than anything else
    alpha = np.clip(1.0 - (spill - 20) / 60, 0, 1)
    alpha = np.minimum(alpha, ndimage.minimum_filter(alpha, 3))  # shave 1px halo
    g2 = np.where(spill > 0, np.maximum(r, b), g)                # despill
    return np.dstack([r, g2, b, alpha * 255]).astype(np.uint8)


def biggest_blob(rgba):
    """Keep only the main figure; erode first so thin bridges to stray artifacts break."""
    alpha = rgba[..., 3]
    core = ndimage.binary_erosion(alpha > 127, iterations=10)
    labels, n = ndimage.label(core)
    if n > 1:
        sizes = ndimage.sum(np.ones_like(labels), labels, range(1, n + 1))
        keep = labels == (1 + int(np.argmax(sizes)))
        rgba = rgba.copy()
        rgba[..., 3] = alpha * ndimage.binary_dilation(keep, iterations=13)
    return rgba


def bbox(rgba):
    ys, xs = np.where(rgba[..., 3] > 8)
    return xs.min(), ys.min(), xs.max() + 1, ys.max() + 1


def crop(rgba, box):
    x0, y0, x1, y1 = box
    return rgba[y0:y1, x0:x1]


def split_sheet(rgba, count):
    """Cut a sheet into its figures, ordered row by row then left to right."""
    labels, n = ndimage.label(rgba[..., 3] > 127)
    sizes = ndimage.sum(np.ones_like(labels), labels, range(1, n + 1))
    top = np.argsort(sizes)[::-1][:count] + 1
    if len(top) < count:
        raise SystemExit(f"expected {count} figures, found {len(top)}")
    slices = ndimage.find_objects(labels)
    figs = []
    for lab in top:
        sl = slices[lab - 1]
        part = rgba[sl].copy()
        part[..., 3] = np.where(labels[sl] == lab, part[..., 3], 0)
        figs.append((sl[0].start, sl[0].stop, sl[1].start, part))
    row_h = max(b - a for a, b, _, _ in figs)
    first = min((a + b) / 2 for a, b, _, _ in figs)
    figs.sort(key=lambda f: (round(((f[0] + f[1]) / 2 - first) / row_h), f[2]))
    return [f[3] for f in figs]


def pixelate(rgba, cell):
    """Shrink to chunky pixels with hard edges. Returns (rgb float, mask)."""
    h, w = rgba.shape[:2]
    w2, h2 = max(1, round(w / cell)), max(1, round(h / cell))
    arr = rgba.astype(np.float32)
    a = arr[..., 3:4] / 255
    pre = Image.fromarray(np.dstack([arr[..., :3] * a, arr[..., 3:]]).astype(np.uint8), "RGBA")
    small = np.asarray(pre.resize((w2, h2), Image.BOX)).astype(np.float32)
    sa = small[..., 3:4] / 255
    rgb = np.where(sa > 0, small[..., :3] / np.maximum(sa, 1e-3), 0)
    return np.clip(rgb, 0, 255), sa[..., 0] >= 0.5


def on_canvas(frames, align):
    """Pad frames to one size, feet on the bottom edge, so swapping them never jitters."""
    def anchor(mask):
        if align == "body":   # centre of the upper body: legs can swing without moving it
            return np.where(mask[: mask.shape[0] // 2])[1].mean()
        return mask.shape[1] / 2
    anchors = [anchor(m) for _, m in frames]
    left = int(np.ceil(max(anchors)))
    right = int(np.ceil(max(m.shape[1] - a for (_, m), a in zip(frames, anchors))))
    height = max(m.shape[0] for _, m in frames)
    out = []
    for (rgb, mask), a in zip(frames, anchors):
        h, w = mask.shape
        x, y = left - int(round(a)), height - h
        big_rgb = np.zeros((height, left + right, 3), np.float32)
        big_mask = np.zeros((height, left + right), bool)
        big_rgb[y:y + h, x:x + w], big_mask[y:y + h, x:x + w] = rgb, mask
        out.append((big_rgb, big_mask))
    return out


def breathe(rgb, mask, rise):
    """Sleeping breath: lift the top of the back by `rise` pixels."""
    r = max(1, round(mask.shape[0] * 0.15))
    rows = list(range(r)) + [r] * rise + list(range(r, mask.shape[0]))
    return rgb[rows], mask[rows]


def outline(rgba):
    padded = np.pad(rgba, ((1, 1), (1, 1), (0, 0)))
    solid = padded[..., 3] > 0
    padded[ndimage.binary_dilation(solid) & ~solid] = OUTLINE
    return padded


def main():
    OUT.mkdir(exist_ok=True)
    for old in OUT.glob("*.png"):
        old.unlink()
    sprites = {}

    # single poses
    sit_box = None
    for src in sorted(RAW.glob("*.png"), key=lambda p: p.stem != "sit"):  # sit first
        rgba = biggest_blob(key(src))
        if src.stem in EARS:
            rgba = shrink_ears(rgba, EARS[src.stem])
        if src.stem == "sit":
            sit_box = bbox(rgba)
        # blink is the sit frame with closed eyes: share its box so it doesn't jitter
        sprites[src.stem] = pixelate(crop(rgba, sit_box if src.stem == "blink" else bbox(rgba)), CELL)

    # animation sheets
    for name, cfg in SHEETS.items():
        figs = split_sheet(key(RAW / "sheets" / f"{name}.png"), cfg["frames"])
        figs = [shrink_ears(f, ears) for f, ears in zip(figs, EARS[name])]
        ref = np.mean([f.shape[0] for f in figs]) if cfg["ref"] is None else figs[cfg["ref"]].shape[0]
        frames = [pixelate(f, ref / cfg["height"]) for f in figs]
        names = cfg.get("names") or [f"{name}{i + 1}" for i in range(len(frames))]
        if cfg.get("align"):
            frames = on_canvas(frames, cfg["align"])
        sprites.update(zip(names, frames))
    for name in ("splat", "dazed"):   # drawn facing right; everything else faces left
        rgb, mask = sprites[name]
        sprites[name] = rgb[:, ::-1], mask[:, ::-1]
    sprites["fall1"], sprites["fall2"] = on_canvas([sprites["fall1"], sprites["fall2"]], "centre")

    # sleeping: three breath heights made from the one sleep pose
    base = sprites.pop("sleep")
    for i in range(3):
        sprites[f"sleep{i + 1}"] = breathe(*base, i)

    # one palette for every frame so colours never flicker
    contrast = lambda rgb: np.clip((rgb - 128) * 1.12 + 128, 0, 255).astype(np.uint8)
    pool = contrast(np.concatenate([rgb[mask] for rgb, mask in sprites.values()]))
    pal_img = Image.fromarray(pool[None], "RGB").quantize(COLORS, method=Image.MEDIANCUT, kmeans=4)

    for name, (rgb, mask) in sorted(sprites.items()):
        q = Image.fromarray(contrast(rgb), "RGB").quantize(palette=pal_img, dither=Image.NONE).convert("RGB")
        rgba = np.dstack([np.asarray(q), mask.astype(np.uint8) * 255])
        rgba[~mask] = 0
        out = Image.fromarray(outline(rgba), "RGBA")
        out.save(OUT / f"{name}.png")
        print(name, out.size)
        if name == "sit":
            side = int(out.width * 0.64)
            face = out.crop((0, 0, side, side))
            face.resize((512, 512), Image.NEAREST).save(OUT / "icon.png")
            face.resize((32, 32), Image.BOX).save(OUT / "tray.png")
            face.resize((18, 18), Image.BOX).save(OUT / "tray-mac.png")
            face.resize((36, 36), Image.BOX).save(OUT / "tray-mac@2x.png")


if __name__ == "__main__":
    sys.exit(main())
