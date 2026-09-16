"""
main.py
-------
Turtle Image Sketcher — turns any image (local file or URL, set via .env)
into a hand-drawn-style animation.

Setup:
  1. pip install -r requirements.txt
  2. cp .env.example .env
  3. Edit .env -> set IMAGE_SOURCE to a local path or an image URL
  4. python main.py
"""

import sys
import time

import cv2
import turtle

from config import settings
from image_loader import load_image, ImageLoadError


def preprocess_image(img):
    """Resize, grayscale, threshold, and extract sorted contours from the image."""
    ratio = settings.target_height / img.shape[0]
    width = int(img.shape[1] * ratio)
    img = cv2.resize(img, (width, settings.target_height))

    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    _, thresh = cv2.threshold(gray, settings.threshold, 255, cv2.THRESH_BINARY_INV)

    contours, _ = cv2.findContours(thresh, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_NONE)

    contours = [c for c in contours if cv2.contourArea(c) > settings.min_contour_area]
    contours = sorted(contours, key=cv2.contourArea, reverse=True)

    if not contours:
        print(
            "Warning: no contours found after thresholding. Try lowering THRESHOLD "
            "in .env, or check that the image has a clear subject against a light background."
        )

    return contours, width, settings.target_height


def build_point_mapper(img_width, img_height):
    def map_point(px, py):
        tx = (px - img_width / 2) * settings.draw_scale
        ty = (img_height / 2 - py) * settings.draw_scale
        return tx, ty

    return map_point


def draw_contours(contours, img_width, img_height):
    screen = turtle.Screen()
    screen.bgcolor(settings.background_color)
    screen.setup(width=settings.window_width, height=settings.window_height)
    screen.tracer(1, 5)

    pen = turtle.Turtle()
    pen.speed(settings.pen_speed)
    pen.hideturtle()
    pen.color(settings.pen_color)
    pen.pensize(settings.pen_size)

    map_point = build_point_mapper(img_width, img_height)

    point_counter = 0
    total_contours = len(contours)

    for idx, contour in enumerate(contours, start=1):
        points = contour.reshape(-1, 2)
        if len(points) < 2:
            continue

        x0, y0 = map_point(points[0][0], points[0][1])
        pen.penup()
        pen.goto(x0, y0)
        pen.pendown()
        pen.begin_fill()

        for px, py in points[1:]:
            x, y = map_point(px, py)
            pen.goto(x, y)
            point_counter += 1
            if point_counter % settings.update_every == 0:
                screen.update()

        pen.goto(x0, y0)
        pen.end_fill()
        screen.update()

        if idx % 10 == 0 or idx == total_contours:
            print(f"  Drawn {idx}/{total_contours} shapes...")

    screen.tracer(0)
    pen.speed(0)

    if settings.save_output_path:
        try:
            ts = screen.getcanvas()
            ts.postscript(file=settings.save_output_path)
            print(f"Saved drawing to: {settings.save_output_path}")
        except Exception as e:
            print(f"Warning: could not save output ({e})")

    if settings.auto_close_after_seconds > 0:
        print(f"Auto-closing in {settings.auto_close_after_seconds}s...")
        screen.ontimer(screen.bye, settings.auto_close_after_seconds * 1000)
        turtle.mainloop()
    else:
        turtle.done()


def main():
    print(f"Loading image: {settings.image_source}")
    try:
        img = load_image(settings.image_source)
    except ImageLoadError as e:
        print(f"\nERROR: {e}")
        sys.exit(1)

    print("Processing image (resize, threshold, contour extraction)...")
    contours, img_width, img_height = preprocess_image(img)
    print(f"Found {len(contours)} shape(s) to draw.")

    print("Opening turtle window and drawing...")
    draw_contours(contours, img_width, img_height)


if __name__ == "__main__":
    main()