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

While it draws: press 1-4 to change the speed, and Space to pause or resume.
"""

import sys
import time
import turtle

import cv2

from config import settings
from image_loader import ImageLoadError, load_image
from sketch_modes import build_strokes

# name: (label, turtle pen speed, points drawn between screen refreshes)
SPEED_PRESETS = {
    "slow": ("Slow", 1, 1),
    "normal": ("Normal", 3, 3),
    "fast": ("Fast", 10, 40),
    "instant": ("Instant", 0, 2000),
}
SPEED_KEYS = {"1": "slow", "2": "normal", "3": "fast", "4": "instant"}


def preprocess_image(img):
    """Resize the image and turn it into strokes. Returns (strokes, width, height, mode used)."""
    ratio = settings.target_height / img.shape[0]
    width = int(img.shape[1] * ratio)
    img = cv2.resize(img, (width, settings.target_height), interpolation=cv2.INTER_AREA)

    strokes, mode = build_strokes(
        img,
        mode=settings.mode,
        threshold=settings.threshold,
        colors=settings.colors,
        min_area=settings.min_contour_area,
        pen_color=settings.pen_color,
    )
    if not strokes:
        print("Warning: nothing to draw. Try another MODE, or set THRESHOLD in .env for the silhouette mode.")
    return strokes, width, settings.target_height, mode


def fit_scale(img_width, img_height):
    """DRAW_SCALE, shrunk if needed so the whole drawing fits inside the window."""
    fit = min((settings.window_width - 40) / img_width, (settings.window_height - 50) / img_height)
    return min(settings.draw_scale, fit)


def build_point_mapper(img_width, img_height, scale=None):
    scale = settings.draw_scale if scale is None else scale

    def map_point(px, py):
        tx = (px - img_width / 2) * scale
        ty = (img_height / 2 - py) * scale
        return tx, ty

    return map_point


def speed_values(name):
    """Return (label, pen speed, refresh interval) for a speed name. 'custom' uses PEN_SPEED and UPDATE_EVERY."""
    if name == "custom":
        return "Custom", settings.pen_speed, settings.update_every
    return SPEED_PRESETS.get(name, SPEED_PRESETS["normal"])


def ask_speed(screen):
    """Show a small window to pick the animation speed. Enter or closing the window picks Normal."""
    import tkinter as tk

    root = screen.getcanvas().winfo_toplevel()
    choice = {"name": "normal"}

    win = tk.Toplevel(root)
    win.title("Animation speed")
    win.resizable(False, False)
    win.transient(root)

    def pick(name):
        choice["name"] = name
        win.destroy()

    tk.Label(win, text="How fast should it draw?", font=("Segoe UI", 11, "bold")).pack(padx=24, pady=(16, 10))
    row = tk.Frame(win)
    row.pack(padx=20)
    for key, name in SPEED_KEYS.items():
        label = SPEED_PRESETS[name][0]
        button = tk.Button(row, text=f"{label}\n({key})", width=9, command=lambda n=name: pick(n))
        button.pack(side="left", padx=4)
        win.bind(key, lambda _e, n=name: pick(n))
        if name == "normal":
            button.configure(default="active")
    tk.Label(win, text="While drawing: press 1-4 to change speed, Space to pause.", fg="#555").pack(pady=(10, 16))
    win.bind("<Return>", lambda _e: pick("normal"))
    win.protocol("WM_DELETE_WINDOW", lambda: pick("normal"))

    win.update_idletasks()
    x = root.winfo_rootx() + (root.winfo_width() - win.winfo_width()) // 2
    y = root.winfo_rooty() + (root.winfo_height() - win.winfo_height()) // 3
    win.geometry(f"+{max(x, 0)}+{max(y, 0)}")
    win.grab_set()
    win.focus_force()
    root.wait_window(win)
    return choice["name"]


def draw_strokes(strokes, img_width, img_height):
    screen = turtle.Screen()
    screen.bgcolor(settings.background_color)
    screen.setup(width=settings.window_width, height=settings.window_height)
    screen.title("Turtle Image Sketcher")

    pen = turtle.Turtle()
    pen.hideturtle()
    pen.color(settings.pen_color)
    pen.pensize(settings.pen_size)

    hint = turtle.Turtle()
    hint.hideturtle()
    hint.penup()
    hint.color("#777777")
    hint.goto(-settings.window_width / 2 + 12, -settings.window_height / 2 + 10)

    state = {"name": settings.speed, "paused": False, "update_every": 1}

    def show_hint():
        hint.clear()
        label = speed_values(state["name"])[0]
        status = "Paused, press Space to resume" if state["paused"] else "1-4 change speed · Space pause"
        hint.write(f"Speed: {label}   {status}", font=("Segoe UI", 9, "normal"))
        screen.update()

    def apply_speed(name):
        state["name"] = name
        _, pen_speed, update_every = speed_values(name)
        pen.speed(pen_speed)
        state["update_every"] = max(1, update_every)
        if pen_speed == 0:
            screen.tracer(0)              # draw off-screen and refresh in large batches
        else:
            screen.tracer(1, 5)
        show_hint()

    def toggle_pause():
        state["paused"] = not state["paused"]
        show_hint()

    if state["name"] == "ask":
        state["name"] = ask_speed(screen)
    apply_speed(state["name"])

    for key, name in SPEED_KEYS.items():
        screen.onkey(lambda n=name: apply_speed(n), key)
    screen.onkey(toggle_pause, "space")
    screen.listen()

    map_point = build_point_mapper(img_width, img_height, fit_scale(img_width, img_height))

    point_counter = 0
    total = len(strokes)

    for idx, stroke in enumerate(strokes, start=1):
        points = stroke.points
        if len(points) < 2:
            continue

        pen.color(stroke.color)
        x0, y0 = map_point(points[0][0], points[0][1])
        pen.penup()
        pen.goto(x0, y0)
        pen.pendown()
        if stroke.kind == "fill":
            pen.begin_fill()

        for px, py in points[1:]:
            while state["paused"]:
                screen.update()
                time.sleep(0.05)
            x, y = map_point(px, py)
            pen.goto(x, y)
            point_counter += 1
            if point_counter % state["update_every"] == 0:
                screen.update()

        if stroke.kind == "fill":
            pen.goto(x0, y0)
            pen.end_fill()
        if pen.speed() != 0:
            screen.update()

        if idx % 50 == 0 or idx == total:
            print(f"  Drawn {idx}/{total} strokes...")

    hint.clear()
    hint.write("Done", font=("Segoe UI", 9, "normal"))
    screen.update()

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

    print("Processing image...")
    strokes, img_width, img_height, mode = preprocess_image(img)
    points = sum(len(s.points) for s in strokes)
    print(f"Mode: {mode}. Found {len(strokes)} strokes ({points} points) to draw.")

    print("Opening turtle window and drawing...")
    draw_strokes(strokes, img_width, img_height)


if __name__ == "__main__":
    main()
