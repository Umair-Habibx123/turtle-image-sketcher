# Turtle Image Sketcher

Turns any image into a hand-drawn-style animation using Python's `turtle` module. The script extracts the silhouette/outline of an image with OpenCV, then "draws" it live on screen stroke by stroke — filling in each shape with solid black (or your chosen color) as it goes.

Now fully config-driven: point it at **any local image or image URL**, and tweak every setting through a `.env` file — no code editing required.

## Credits

This project is based on the original idea and implementation by [nourhan11atef](https://github.com/nourhan11atef) — [Spiderman_Recreate_image](https://github.com/nourhan11atef/Spiderman_Recreate_image). Big thanks for the original concept of using OpenCV contours + turtle graphics to recreate images as hand-drawn animations. This version builds on that idea with a config-driven setup (`.env`-based settings, URL support, and other tweaks).

## Setup

```bash
pip install -r requirements.txt
cp .env.example .env
```

Then open `.env` and set `IMAGE_SOURCE` to either:

```bash
# a local file (relative to this folder, or an absolute path)
IMAGE_SOURCE=spiderman.png

# OR a full image URL
IMAGE_SOURCE=https://example.com/images/spiderman.png
```

Run it:

```bash
python main.py
```

A turtle graphics window opens and animates the drawing.

## How it works

1. **Load** — `image_loader.py` reads `IMAGE_SOURCE` from config. If it starts with `http://`/`https://`, the image is downloaded to a temp file first; otherwise it's treated as a local path.
2. **Resize** — Resized to `TARGET_HEIGHT` pixels tall, aspect ratio preserved.
3. **Threshold** — Grayscale + binary threshold (`THRESHOLD`) to separate the subject from the background.
4. **Find contours** — OpenCV traces each shape's outline, drops tiny noise (`MIN_CONTOUR_AREA`), and sorts largest-first.
5. **Animate** — A turtle pen walks each contour, refreshing the screen every `UPDATE_EVERY` points, filling each shape as it's traced.

## Configuration (`.env`)

| Variable | Effect |
|---|---|
| `IMAGE_SOURCE` | Local file path **or** image URL — this is the only required setting |
| `TARGET_HEIGHT` | Resize height in pixels (width scales to match) |
| `THRESHOLD` | 0–255 cutoff; lower catches more detail, higher keeps only darkest areas |
| `MIN_CONTOUR_AREA` | Minimum contour size kept; raise to ignore more small artifacts |
| `DRAW_SCALE` | Scales the drawing size on the turtle canvas |
| `WINDOW_WIDTH` / `WINDOW_HEIGHT` | Turtle window size |
| `PEN_SPEED` | Turtle drawing speed (0 fastest, 1 slowest, 10 fast) |
| `UPDATE_EVERY` | Points between screen refreshes; lower = smoother/slower, higher = faster/jumpier |
| `PEN_SIZE` | Pen line thickness |
| `BACKGROUND_COLOR` / `PEN_COLOR` | Any turtle color name or hex code |
| `SAVE_OUTPUT_PATH` | Optional path to save the finished drawing as PostScript/EPS |
| `AUTO_CLOSE_AFTER_SECONDS` | Auto-close the window N seconds after finishing (0 = stay open) |

See `.env.example` for full comments on each setting.

## Project structure

```
main.py           # entry point — orchestrates load → process → draw
config.py         # loads and validates .env settings
image_loader.py   # resolves IMAGE_SOURCE (local path or URL) into a cv2 image
requirements.txt
.env.example       # copy to .env and edit
```

## Notes

- Works best with high-contrast images (clear subject against a light background) since it relies on brightness thresholding rather than edge detection.
- Contours from OpenCV aren't always perfectly ordered closed loops, so fills on complex/self-intersecting shapes may occasionally look slightly imperfect — this is a limitation of pixel-contour tracing, not a bug.
- If `IMAGE_SOURCE` is a URL, make sure the link points directly to an image file (not an HTML page); the loader checks the response's Content-Type and will error clearly if it doesn't look like an image.

## License

MIT (or your license of choice)