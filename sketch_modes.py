"""
sketch_modes.py
---------------
Turns an image into strokes for the turtle to draw: filled shapes and pen lines.

Modes:
  silhouette  solid shapes from one brightness cutoff. Works on light or dark backgrounds.
  lineart     the image's edges, drawn as pen lines, like a sketch.
  color       the image reduced to a few colors, each region filled in its color.
  comic       color regions with line art drawn on top. Best for anime and illustrations.
  sketch      a pencil-style scribble: the pen visits every dark pixel, hopping to the nearest
              one next, like shading by hand. Best for pencil drawings and photos.
  auto        silhouette for two-tone images, sketch for nearly colorless images,
              comic for everything else.

Palettes:
  original    the image's own colors
  grayscale   shades of gray
  bw          pure black and white

Detail: low, medium or high. Higher keeps more colors and smaller shapes, so it looks
closer to the original but takes longer to draw.
"""

from dataclasses import dataclass

import cv2
import numpy as np

MODES = ("auto", "sketch", "silhouette", "lineart", "color", "comic")
PALETTES = ("original", "grayscale", "bw")
DETAILS = {
    #          colors, smallest region kept (px), smoothing strength, outline simplification
    "low": dict(colors=8, min_area=40, smooth=60, epsilon=1.5),
    "medium": dict(colors=14, min_area=20, smooth=40, epsilon=1.0),
    "high": dict(colors=24, min_area=10, smooth=25, epsilon=0.7),
}
MIN_LINE_LENGTH = 25  # pixels; shorter edges are usually noise
# Sketch style per detail level: adaptive threshold block size and offset. A smaller offset keeps
# fainter pencil marks, so more shading is drawn.
SKETCH_DETAIL = {"low": (15, 5), "medium": (13, 3), "high": (11, 2)}
PENCIL = "#4d4d4d"  # turtle's "gray30"


@dataclass
class Stroke:
    kind: str           # "fill" (closed shape, filled) or "line" (open pen stroke)
    points: np.ndarray  # (N, 2) pixel coordinates
    color: str          # turtle color: a name like "black" or "#rrggbb"
    width: float = 1.0  # pen width in image pixels; it scales with the drawing


def _hex(bgr) -> str:
    b, g, r = (int(np.clip(v, 0, 255)) for v in bgr)
    return f"#{r:02x}{g:02x}{b:02x}"


def _gray(img):
    return cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)


def _area(points) -> float:
    return cv2.contourArea(points.reshape(-1, 1, 2).astype(np.int32))


def border_is_dark(gray) -> bool:
    """The image's edges are usually background, so their brightness tells us which side is the subject."""
    border = np.concatenate([gray[0], gray[-1], gray[:, 0], gray[:, -1]])
    return float(border.mean()) < 128


def is_two_tone(gray) -> bool:
    """True for silhouettes: almost every pixel is near black or near white, and the ink is mostly solid black.

    The second test matters for pencil drawings, whose light paper also looks "near white" but whose
    marks are mostly mid-gray shading rather than solid black.
    """
    black, white = float((gray < 60).mean()), float((gray > 195).mean())
    ink = 1.0 - white
    return black + white > 0.9 and ink > 0 and black / ink > 0.5


def is_colorless(img) -> bool:
    """True for pencil drawings and black-and-white photos: almost no color saturation."""
    return float(cv2.cvtColor(img, cv2.COLOR_BGR2HSV)[..., 1].mean()) < 20


def choose_mode(img) -> str:
    if is_two_tone(_gray(img)):
        return "silhouette"
    return "sketch" if is_colorless(img) else "comic"


def _recolor(bgr, palette, fallback="black"):
    """Convert a BGR color to the chosen palette."""
    if palette == "original":
        return _hex(bgr)
    if palette == "grayscale":
        level = int(0.114 * bgr[0] + 0.587 * bgr[1] + 0.299 * bgr[2])
        return _hex((level, level, level))
    return fallback


def silhouette(img, threshold=None, min_area=15, palette="original", pen_color="black"):
    """Solid shapes. threshold=None picks the cutoff automatically (Otsu's method)."""
    gray = _gray(img)
    keep = cv2.THRESH_BINARY if border_is_dark(gray) else cv2.THRESH_BINARY_INV
    if threshold is None:
        _, mask = cv2.threshold(gray, 0, 255, keep | cv2.THRESH_OTSU)
    else:
        _, mask = cv2.threshold(gray, threshold, 255, keep)
    contours, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_NONE)
    contours = sorted((c for c in contours if cv2.contourArea(c) > min_area), key=cv2.contourArea, reverse=True)
    subject = cv2.mean(img, mask=mask)[:3] if contours else (0, 0, 0)
    color = _recolor(subject, palette, pen_color)
    return [Stroke("fill", c.reshape(-1, 2), color) for c in contours]


def edge_thresholds(gray):
    """Canny cutoffs from how strong this image's edges actually are.

    Basing them on brightness instead (a common rule of thumb) sets them far too high on light
    images such as pencil drawings, so their soft lines are lost.
    """
    gx = cv2.Sobel(gray, cv2.CV_32F, 1, 0)
    gy = cv2.Sobel(gray, cv2.CV_32F, 0, 1)
    magnitude = cv2.magnitude(gx, gy)
    strong = magnitude[magnitude > 4]
    if strong.size == 0:
        return 20, 60
    high = float(np.clip(np.percentile(strong, 75), 30, 255))
    return int(high * 0.4), int(high)


def is_light_page(img) -> bool:
    """A drawing on light paper: bright, nearly colorless edges."""
    gray = _gray(img)
    border = np.concatenate([gray[0], gray[-1], gray[:, 0], gray[:, -1]])
    return float(border.mean()) > 150 and is_colorless(img)


def lineart(img, palette="original", pen_color="black", darken=0.55):
    """Edges as pen lines. In the original palette, each line takes a darker shade of the colors under it."""
    gray = cv2.bilateralFilter(_gray(img), 9, 60, 60)
    low, high = edge_thresholds(gray)
    edges = cv2.dilate(cv2.Canny(gray, low, high), np.ones((2, 2), np.uint8))
    contours, _ = cv2.findContours(edges, cv2.RETR_LIST, cv2.CHAIN_APPROX_NONE)
    lines = [cv2.approxPolyDP(c, 1.0, False) for c in contours if cv2.arcLength(c, False) > MIN_LINE_LENGTH]
    lines.sort(key=lambda c: cv2.arcLength(c, False), reverse=True)

    strokes = []
    h, w = img.shape[:2]
    for c in lines:
        pts = c.reshape(-1, 2)
        if palette == "original":
            xs, ys = np.clip(pts[:, 0], 0, w - 1), np.clip(pts[:, 1], 0, h - 1)
            color = _hex(img[ys, xs].mean(axis=0) * darken)
        else:
            color = pen_color
        strokes.append(Stroke("line", pts, color))
    return strokes


def dark_pixels(gray, detail="high"):
    """Pixels darker than their neighbourhood (adaptive threshold), as (x, y) points."""
    block, offset = SKETCH_DETAIL[detail]
    blurred = cv2.GaussianBlur(gray, (7, 7), 0)
    mask = cv2.adaptiveThreshold(blurred, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C, cv2.THRESH_BINARY, block, offset)
    ys, xs = np.where(mask == 0)
    return np.stack([xs, ys], axis=1)


def nearest_path(points, max_jump):
    """Visit every point, always moving to the nearest unvisited one.

    Returns a list of point runs; a move longer than max_jump lifts the pen and starts a new run.
    Points are bucketed into a grid, so each step only checks nearby cells instead of every point,
    which keeps tens of thousands of points to a second or two.
    """
    if len(points) == 0:
        return []
    cell = max(2, int(max_jump))
    grid = {}
    for i, (x, y) in enumerate(points.tolist()):
        grid.setdefault((x // cell, y // cell), set()).add(i)
    pts = points.tolist()
    remaining = len(pts)
    runs, run = [], []
    current = 0
    limit = max_jump * max_jump
    while True:
        x, y = pts[current]
        grid[(x // cell, y // cell)].discard(current)
        remaining -= 1
        run.append((x, y))
        if not remaining:
            break
        cx, cy = x // cell, y // cell
        best, best_d, ring = -1, 0, 0
        # Grow the search ring until it is wider than the best distance found so far.
        while best < 0 or ring <= 1 + int(best_d ** 0.5) // cell:
            for gx in range(cx - ring, cx + ring + 1):
                edge = gx in (cx - ring, cx + ring)
                for gy in range(cy - ring, cy + ring + 1) if edge else (cy - ring, cy + ring):
                    for j in grid.get((gx, gy), ()):
                        px, py = pts[j]
                        d = (px - x) * (px - x) + (py - y) * (py - y)
                        if best < 0 or d < best_d:
                            best, best_d = j, d
            ring += 1
        if best_d > limit:
            if len(run) > 1:
                runs.append(np.array(run))
            run = []
        current = best
    if len(run) > 1:
        runs.append(np.array(run))
    return runs


def sketch(img, detail="high", palette="original", pen_color="black"):
    """Pencil-style strokes. Inspired by Akashsshinde07/Image-Sketch-Drawing-in-Turtle."""
    h, w = img.shape[:2]
    runs = nearest_path(dark_pixels(_gray(img), detail), max_jump=((w + h) / 2) / 60)
    pencil_only = palette == "grayscale" or is_colorless(img)
    strokes = []
    for pts in runs:
        if palette == "bw":
            color = "#000000"
        elif pencil_only:
            color = PENCIL
        else:  # a darker shade of the colors under the stroke, like a colored pencil
            color = _hex(img[pts[:, 1], pts[:, 0]].mean(axis=0) * 0.6)
        strokes.append(Stroke("line", pts, color, width=1.8))  # thick enough that neighbouring pixels read as one pencil line
    return strokes


def color_regions(img, detail="high", palette="original", colors=None):
    """Reduce the image to a few colors (k-means in Lab color space) and fill each region in its color."""
    preset = DETAILS[detail]
    k = 2 if palette == "bw" else (colors or preset["colors"])
    source = cv2.cvtColor(_gray(img), cv2.COLOR_GRAY2BGR) if palette in ("grayscale", "bw") else img
    light_page = is_light_page(img)
    strength = 10 if light_page else preset["smooth"]   # pencil lines are thin; heavy smoothing erases them
    smooth = cv2.bilateralFilter(source, 7, strength, strength)
    lab = cv2.cvtColor(smooth, cv2.COLOR_BGR2LAB).reshape(-1, 3).astype(np.float32)
    h, w = img.shape[:2]

    # On a light page, the paper is left blank (the canvas shows through) and every color is
    # spent on the drawing itself, instead of on shades of paper.
    paper = None
    if light_page:
        gray = _gray(smooth)
        paper = (gray >= np.median(gray) - 25).reshape(-1)
        if paper.all():
            return []

    cv2.setRNGSeed(0)  # same image, same result
    criteria = (cv2.TERM_CRITERIA_EPS + cv2.TERM_CRITERIA_MAX_ITER, 20, 1.0)
    samples = lab if paper is None else lab[~paper]
    k = max(1, min(k, len(samples)))
    _, sample_labels, centers = cv2.kmeans(samples, k, None, criteria, 3, cv2.KMEANS_PP_CENTERS)
    if paper is None:
        labels = sample_labels.reshape(h, w)
    else:
        labels = np.full(h * w, -1, np.int32)
        labels[~paper] = sample_labels.ravel()
        labels = labels.reshape(h, w)
    centers_bgr = cv2.cvtColor(centers.reshape(1, -1, 3).astype(np.uint8), cv2.COLOR_LAB2BGR)[0]

    if palette == "bw":
        darkest = int(np.argmin(centers_bgr.sum(axis=1)))
        names = ["#000000" if i == darkest else "#ffffff" for i in range(k)]
    else:
        names = [_hex(c) for c in centers_bgr]

    # A base layer in the most common color, so tiny gaps between regions never show as white.
    # Not on a light page, where the blank canvas is the paper.
    common, base = -1, []
    if paper is None:
        common = int(np.bincount(labels.ravel(), minlength=k).argmax())
        base = [Stroke("fill", np.array([[0, 0], [w - 1, 0], [w - 1, h - 1], [0, h - 1]]), names[common])]

    strokes = []
    kernel = np.ones((2, 2), np.uint8)
    # On a light page the marks are thin pencil lines, so keep small shapes instead of cleaning them away.
    min_area = 3 if paper is not None else preset["min_area"]
    for i in range(k):
        if i == common:
            continue
        mask = (labels == i).astype(np.uint8) * 255
        if paper is None:
            mask = cv2.morphologyEx(mask, cv2.MORPH_OPEN, kernel)
        contours, _ = cv2.findContours(mask, cv2.RETR_CCOMP, cv2.CHAIN_APPROX_NONE)
        for c in contours:
            if cv2.contourArea(c) > min_area:
                strokes.append(Stroke("fill", cv2.approxPolyDP(c, preset["epsilon"], True).reshape(-1, 2), names[i]))
    # Big regions first, so smaller details are painted on top of them.
    strokes.sort(key=lambda s: _area(s.points), reverse=True)
    return base + strokes


def build_strokes(img, mode="auto", palette="original", detail="high", threshold=None, colors=None,
                  min_area=15, pen_color="black"):
    """Return (strokes, mode actually used)."""
    if mode not in MODES:
        raise ValueError(f"Unknown mode '{mode}'. Choose one of: {', '.join(MODES)}")
    if palette not in PALETTES:
        raise ValueError(f"Unknown palette '{palette}'. Choose one of: {', '.join(PALETTES)}")
    if detail not in DETAILS:
        raise ValueError(f"Unknown detail '{detail}'. Choose one of: {', '.join(DETAILS)}")
    if mode == "auto":
        mode = choose_mode(img)
    if mode == "silhouette":
        return silhouette(img, threshold, min_area, palette, pen_color), mode
    if mode == "lineart":
        return lineart(img, palette, pen_color), mode
    if mode == "sketch":
        return sketch(img, detail, palette, pen_color), mode
    fills = color_regions(img, detail, palette, colors)
    if mode == "color":
        return fills, mode
    ink = "#000000" if palette != "original" else pen_color
    return fills + lineart(img, palette, ink), mode
