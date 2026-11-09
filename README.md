# Turtle Image Sketcher

**Turn any image into a live, hand-drawn animation: silhouettes, line art, flat color or comic style. OpenCV finds the shapes, and Python's turtle draws them.**

[![CI](https://github.com/Umair-Habibx123/turtle-image-sketcher/actions/workflows/ci.yml/badge.svg)](https://github.com/Umair-Habibx123/turtle-image-sketcher/actions/workflows/ci.yml)
![Python 3.10+](https://img.shields.io/badge/python-3.10%2B-3776AB)

**Status:** a small learning project, actively maintained (last updated November 2026). Tested on Windows 11 with Python 3.11. CI tests Python 3.10 and 3.12 on Windows and Ubuntu.
**License:** none yet. This project builds on [nourhan11atef/Spiderman_Recreate_image](https://github.com/nourhan11atef/Spiderman_Recreate_image), which has no license, so I've asked the original author to add one. Until then, ask before reusing this code.

![The original silhouette on the left, and the same shape being traced and filled stroke by stroke on the right](docs/demo.gif)

<sub>The GIF is rendered by `tools/make_demo.py` from the same shapes the turtle draws. The real program draws in a turtle window.</sub>

## Quick start

```bash
pip install -r requirements.txt
cp .env.example .env        # Windows Command Prompt: copy .env.example .env
python main.py
```

A small window asks how fast to draw (**Slow, Normal, Fast or Instant**), then a turtle window draws the bundled `spiderman.png`. While it draws, press **1 to 4** to change the speed and **Space** to pause. To use your own picture, set `IMAGE_SOURCE` in `.env` to a file path or an image URL:

```bash
IMAGE_SOURCE=my-photo.png
# or
IMAGE_SOURCE=https://example.com/images/silhouette.png
```

**Requirements:** Python 3.10 or newer. The turtle window needs Tk, which the python.org installers for Windows and macOS include. On Linux, install it with `sudo apt install python3-tk`. With Homebrew on macOS, use `brew install python-tk`.

<img src="docs/turtle-window.png" width="520" alt="The turtle window after drawing the sample image, with a status line reading Done">

## Drawing modes

Set `MODE` in `.env`. The default, `auto`, picks for you: **silhouette** for two-tone images and **comic** for everything else.

| Mode | What it draws | Best for |
|---|---|---|
| `silhouette` | Solid filled shapes from one brightness cutoff, picked automatically | Silhouettes and logos, on light or dark backgrounds |
| `lineart` | The image's edges as pen lines, like a sketch | Outlines and drawings |
| `color` | The image reduced to `COLORS` flat colors, each region filled in its color | Posters, landscapes and photos |
| `comic` | Flat colors with line art drawn on top | Anime, cartoons and illustrations |

## How it works

1. **Load:** `image_loader.py` opens the file, or downloads the URL to a temporary file first. It checks the download really is an image.
2. **Resize:** the image is scaled to `TARGET_HEIGHT` pixels tall, keeping its proportions.
3. **Find strokes:** `sketch_modes.py` turns the image into strokes for the chosen mode:
   - **silhouette:** an [Otsu](https://en.wikipedia.org/wiki/Otsu%27s_method) threshold, with the image's border used to tell background from subject
   - **lineart:** a [Canny](https://en.wikipedia.org/wiki/Canny_edge_detector) edge detector after edge-preserving smoothing
   - **color:** [k-means](https://en.wikipedia.org/wiki/K-means_clustering) color reduction in Lab color space, with big regions painted first and details on top
4. **Draw:** the turtle walks each stroke point by point, filling shapes and tracing lines, scaled to fit the window. The bundled image becomes 1 shape with about 2,300 points.

## What it's good at, and what it isn't

- **Good for:** the "watch it being drawn" effect on silhouettes, logos, illustrations and anime art. Comic mode on a detailed illustration produces about 700 strokes; pick **Fast** or **Instant** for those.
- **Not for:** photo-realistic results. Color mode flattens soft gradients into a few colors, and line art only finds strong edges. For a pencil-style still image, try OpenCV's `cv2.pencilSketch` instead.
- **Imperfect fills:** traced outlines aren't always clean closed loops, so complex or overlapping shapes can fill slightly wrong.

## Configuration

Every setting lives in `.env`. Only `IMAGE_SOURCE` is required, and `.env.example` explains each one.

| Variable | Default | Effect |
|---|---|---|
| `IMAGE_SOURCE` | none, required | Local file path or image URL |
| `TARGET_HEIGHT` | `700` | Height in pixels the image is resized to |
| `MODE` | `auto` | `auto`, `silhouette`, `lineart`, `color` or `comic`. See [Drawing modes](#drawing-modes) |
| `COLORS` | `12` | Number of colors for the color and comic modes, 2–32 |
| `THRESHOLD` | `auto` | Silhouette mode: brightness cutoff 0–255, or `auto` to pick it from the image |
| `MIN_CONTOUR_AREA` | `15` | Smallest shape kept. Raise it to ignore specks |
| `DRAW_SCALE` | `0.8` | Size of the drawing on the canvas. It shrinks automatically to fit the window |
| `WINDOW_WIDTH` / `WINDOW_HEIGHT` | `800` / `575` | Turtle window size |
| `SPEED` | `ask` | `ask` shows the speed picker. `slow`, `normal`, `fast` or `instant` skips it. `custom` uses the two settings below |
| `PEN_SPEED` | `3` | With `SPEED=custom`: turtle speed, where 1 is slowest, 10 is fast and 0 is fastest |
| `UPDATE_EVERY` | `3` | With `SPEED=custom`: points drawn between screen refreshes. Lower is smoother but slower |
| `PEN_SIZE` | `1` | Line thickness |
| `BACKGROUND_COLOR` / `PEN_COLOR` | `white` / `black` | Any turtle color name or hex code |
| `SAVE_OUTPUT_PATH` | empty | Save the finished drawing as a PostScript (`.eps`) file |
| `AUTO_CLOSE_AFTER_SECONDS` | `0` | Close the window this many seconds after finishing. `0` keeps it open. Above `0`, the speed picker is skipped so unattended runs don't wait |

## Project structure

```
main.py             Entry point: load, then find shapes, then draw
config.py           Reads and checks the .env settings
image_loader.py     Turns a file path or URL into an OpenCV image
sketch_modes.py     Turns the image into strokes: silhouette, lineart, color or comic
original/           The original single-file script by nourhan11atef, kept unchanged
tools/make_demo.py  Renders docs/demo.gif without opening a window
tests/              Tests for the pipeline (python -m pytest)
```

## Development

```bash
pip install -r requirements-dev.txt
python -m ruff check .
python -m pytest
python tools/make_demo.py      # regenerate docs/demo.gif
```

## Credits

The idea and the original script come from [nourhan11atef](https://github.com/nourhan11atef) in [Spiderman_Recreate_image](https://github.com/nourhan11atef/Spiderman_Recreate_image). This version adds:
- settings in `.env`
- image URLs
- clear error messages
- saving the output
- a speed picker and live speed and pause controls
- line art, color and comic drawing modes, chosen automatically
- support for dark backgrounds, and automatic fit to the window
- tests, CI and a reproducible demo

Maintained by [Umair Habib](https://github.com/Umair-Habibx123).
