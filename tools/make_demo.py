"""
tools/make_demo.py
------------------
Renders a demo GIF: the original image next to the drawing as it is made, stroke by stroke.

It uses the same strokes as main.py (same MODE, COLORS and THRESHOLD settings), but replays
them with OpenCV instead of opening a turtle window, so it runs anywhere, including CI.

Usage (from the project root):
    pip install -r requirements-dev.txt
    python tools/make_demo.py [image] [output.gif] [mode]
"""

import os
import sys
import types

import cv2
import numpy as np
from PIL import Image, ImageColor

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
os.chdir(ROOT)
os.environ.setdefault("IMAGE_SOURCE", "spiderman.png")
if len(sys.argv) > 3:
    os.environ["MODE"] = sys.argv[3]
sys.modules.setdefault("turtle", types.ModuleType("turtle"))  # no window needed here

from image_loader import load_image  # noqa: E402
from main import preprocess_image  # noqa: E402

OUTPUT_HEIGHT = 434
FRAMES = 60           # frames while drawing
HOLD_FRAMES = 18      # frames holding the finished drawing
FRAME_MS = 60
GAP = 24


def bgr(color):
    r, g, b = ImageColor.getrgb(color)[:3]
    return (b, g, r)


def render(source: str, out_path: str) -> None:
    img = load_image(source)
    strokes, width, height, mode = preprocess_image(img)
    if not strokes:
        sys.exit("Nothing to draw. Try another MODE.")

    scale = OUTPUT_HEIGHT / height
    w, h = int(width * scale), OUTPUT_HEIGHT
    original = cv2.resize(img, (w, h), interpolation=cv2.INTER_AREA)
    total = sum(len(s.points) for s in strokes)
    every = max(1, total // FRAMES)

    def frame(drawing):
        canvas = np.full((h, w * 2 + GAP, 3), 255, np.uint8)
        canvas[:, :w] = original
        canvas[:, w + GAP:] = drawing
        return Image.fromarray(cv2.cvtColor(canvas, cv2.COLOR_BGR2RGB))

    frames, drawn = [], 0
    drawing = np.full((h, w, 3), 255, np.uint8)
    for stroke in strokes:
        pts = (stroke.points * scale).astype(np.int32)
        color = bgr(stroke.color)
        for i in range(1, len(pts), every):
            cv2.polylines(drawing, [pts[: i + 1]], stroke.kind == "fill" and i + 1 >= len(pts), color, 1, cv2.LINE_AA)
            frames.append(frame(drawing))
        if stroke.kind == "fill":
            cv2.fillPoly(drawing, [pts], color, cv2.LINE_AA)
        else:
            cv2.polylines(drawing, [pts], False, color, 1, cv2.LINE_AA)
        drawn += len(pts)
        if drawn // every > len(frames):
            frames.append(frame(drawing))
    frames.append(frame(drawing))
    frames += [frames[-1]] * HOLD_FRAMES

    os.makedirs(os.path.dirname(out_path) or ".", exist_ok=True)
    paletted = [f.convert("P", palette=Image.ADAPTIVE, colors=128) for f in frames]
    paletted[0].save(out_path, save_all=True, append_images=paletted[1:], duration=FRAME_MS, loop=0, optimize=True)
    print(f"Saved {out_path} ({mode} mode): {len(frames)} frames, {os.path.getsize(out_path) // 1024} KB")


if __name__ == "__main__":
    render(sys.argv[1] if len(sys.argv) > 1 else os.environ["IMAGE_SOURCE"],
           sys.argv[2] if len(sys.argv) > 2 else os.path.join("docs", "demo.gif"))
