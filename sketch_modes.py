"""
sketch_modes.py
---------------
Turns an image into strokes for the turtle to draw: filled shapes and pen lines.

Modes:
  silhouette  solid shapes from one brightness cutoff. Best for dark shapes on a light
              background, or light shapes on a dark one.
  lineart     the image's edges, drawn as pen lines, like a sketch.
  color       the image reduced to a few colors, each region filled in its color.
  comic       color regions with line art drawn on top. Best for anime and illustrations.
  auto        silhouette for two-tone images, comic for everything else.
"""

from dataclasses import dataclass

import cv2
import numpy as np

MODES = ("auto", "silhouette", "lineart", "color", "comic")
MIN_LINE_LENGTH = 25  # pixels; shorter edges are usually noise


@dataclass
class Stroke:
    kind: str          # "fill" (closed shape, filled) or "line" (open pen stroke)
    points: np.ndarray  # (N, 2) pixel coordinates
    color: str         # turtle color: a name like "black" or "#rrggbb"


def _hex(bgr) -> str:
    b, g, r = (int(v) for v in bgr)
    return f"#{r:02x}{g:02x}{b:02x}"


def _gray(img):
    return cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)


def border_is_dark(gray) -> bool:
    """The image's edges are usually background, so their brightness tells us which side is the subject."""
    border = np.concatenate([gray[0], gray[-1], gray[:, 0], gray[:, -1]])
    return float(border.mean()) < 128


def is_two_tone(gray) -> bool:
    """True when almost every pixel is near black or near white, as in a silhouette."""
    return float(((gray < 60) | (gray > 195)).mean()) > 0.9


def choose_mode(img) -> str:
    return "silhouette" if is_two_tone(_gray(img)) else "comic"


def silhouette(img, threshold=None, min_area=15, color="black"):
    """Solid shapes. threshold=None picks the cutoff automatically (Otsu's method)."""
    gray = _gray(img)
    keep = cv2.THRESH_BINARY if border_is_dark(gray) else cv2.THRESH_BINARY_INV
    if threshold is None:
        _, mask = cv2.threshold(gray, 0, 255, keep | cv2.THRESH_OTSU)
    else:
        _, mask = cv2.threshold(gray, threshold, 255, keep)
    contours, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_NONE)
    contours = sorted((c for c in contours if cv2.contourArea(c) > min_area), key=cv2.contourArea, reverse=True)
    return [Stroke("fill", c.reshape(-1, 2), color) for c in contours]


def lineart(img, color="black"):
    """Edges as pen lines. Smoothing first keeps the lines clean while preserving outlines."""
    gray = cv2.bilateralFilter(_gray(img), 9, 60, 60)
    median = float(np.median(gray))
    low, high = max(20, int(0.66 * median)), max(60, int(min(255, 1.33 * median)))
    edges = cv2.dilate(cv2.Canny(gray, low, high), np.ones((2, 2), np.uint8))
    contours, _ = cv2.findContours(edges, cv2.RETR_LIST, cv2.CHAIN_APPROX_NONE)
    lines = [cv2.approxPolyDP(c, 1.0, False) for c in contours if cv2.arcLength(c, False) > MIN_LINE_LENGTH]
    lines.sort(key=lambda c: cv2.arcLength(c, False), reverse=True)
    return [Stroke("line", c.reshape(-1, 2), color) for c in lines]


def color_regions(img, colors=12, min_area=25):
    """Reduce the image to a few colors (k-means in Lab color space) and fill each region in its color."""
    smooth = cv2.medianBlur(cv2.bilateralFilter(img, 7, 40, 40), 3)
    lab = cv2.cvtColor(smooth, cv2.COLOR_BGR2LAB).reshape(-1, 3).astype(np.float32)
    cv2.setRNGSeed(0)  # same image, same result
    criteria = (cv2.TERM_CRITERIA_EPS + cv2.TERM_CRITERIA_MAX_ITER, 20, 1.0)
    _, labels, centers = cv2.kmeans(lab, colors, None, criteria, 3, cv2.KMEANS_PP_CENTERS)
    labels = labels.reshape(img.shape[:2])
    palette = cv2.cvtColor(centers.reshape(1, -1, 3).astype(np.uint8), cv2.COLOR_LAB2BGR)[0]

    strokes = []
    kernel = np.ones((3, 3), np.uint8)
    for i in range(colors):
        mask = cv2.morphologyEx((labels == i).astype(np.uint8) * 255, cv2.MORPH_OPEN, kernel)
        contours, _ = cv2.findContours(mask, cv2.RETR_CCOMP, cv2.CHAIN_APPROX_NONE)
        for c in contours:
            if cv2.contourArea(c) > min_area:
                strokes.append(Stroke("fill", cv2.approxPolyDP(c, 1.0, True).reshape(-1, 2), _hex(palette[i])))
    # Big regions first, so smaller details are painted on top of them.
    strokes.sort(key=lambda s: cv2.contourArea(s.points.reshape(-1, 1, 2)), reverse=True)
    return strokes


def build_strokes(img, mode="auto", threshold=None, colors=12, min_area=15, pen_color="black"):
    """Return (strokes, mode actually used)."""
    if mode not in MODES:
        raise ValueError(f"Unknown mode '{mode}'. Choose one of: {', '.join(MODES)}")
    if mode == "auto":
        mode = choose_mode(img)
    if mode == "silhouette":
        return silhouette(img, threshold, min_area, pen_color), mode
    if mode == "lineart":
        return lineart(img, pen_color), mode
    if mode == "color":
        return color_regions(img, colors, max(min_area, 25)), mode
    return color_regions(img, max(2, colors - 2), max(min_area, 25)) + lineart(img, "#141414"), mode
