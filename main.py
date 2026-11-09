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

A setup window lets you pick the style, colors, detail and speed.
While it draws: press 1-4 to change the speed, and Space to pause or resume.
Resize or maximize the window at any time and the drawing redraws to fit.
"""

import sys
import time
import turtle

import cv2
import numpy as np

from config import settings
from image_loader import ImageLoadError, load_image
from sketch_modes import build_strokes

# name: (label, points drawn per frame, pause after each frame in milliseconds)
SPEED_PRESETS = {
    "slow": ("Slow", 2, 15),
    "normal": ("Normal", 6, 10),
    "fast": ("Fast", 25, 6),
    "instant": ("Instant", 3000, 0),
}
RESIZE_CHECK_EVERY = 150  # points; how often a long stroke checks whether the window was resized
SPEED_KEYS = {"1": "slow", "2": "normal", "3": "fast", "4": "instant"}

# Labels for the setup window: setting value -> what the user sees
MODE_LABELS = {"auto": "Auto", "sketch": "Sketch", "silhouette": "Silhouette", "lineart": "Line art",
               "color": "Color", "comic": "Comic"}
PALETTE_LABELS = {"original": "Original colors", "grayscale": "Grayscale", "bw": "Black & white"}
DETAIL_LABELS = {"low": "Low", "medium": "Medium", "high": "High"}

# Styles drawn on a blank page; color styles keep the whole frame because the background is part of the picture.
CROP_TO_DRAWING = ("sketch", "lineart", "silhouette")
STATUS_BAR = 44  # pixels kept free at the top of the window for the status text
UI_FONT = ("Segoe UI", 10, "normal")


def preprocess_image(img, mode=None, palette=None, detail=None):
    """Resize the image and turn it into strokes. Returns (strokes, width, height, mode used)."""
    img = crop_to_subject(img)                           # first, at full resolution, so no detail is lost
    ratio = settings.target_height / img.shape[0]
    width = int(img.shape[1] * ratio)
    img = cv2.resize(img, (width, settings.target_height), interpolation=cv2.INTER_AREA)

    strokes, mode_used = build_strokes(
        img,
        mode=mode or settings.mode,
        palette=palette or settings.palette,
        detail=detail or settings.detail,
        threshold=settings.threshold,
        colors=settings.colors,
        min_area=settings.min_contour_area,
        pen_color=settings.pen_color,
    )
    if not strokes:
        print("Warning: nothing to draw. Try another style, or set THRESHOLD in .env for the silhouette style.")
        return strokes, width, settings.target_height, mode_used
    if mode_used in CROP_TO_DRAWING:
        strokes, width, height = crop_to_strokes(strokes)
        return strokes, width, height, mode_used
    return strokes, width, settings.target_height, mode_used


def crop_to_subject(img, margin=16):
    """If the subject sits on a plain page with lots of empty space, crop to it before processing.

    Every style then spends its detail on the subject instead of the paper. Images that fill the
    frame (photos, full illustrations) are left alone.
    """
    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    border = np.concatenate([gray[0], gray[-1], gray[:, 0], gray[:, -1]])
    if border.mean() < 150:                              # dark or busy backgrounds are part of the picture
        return img
    ys, xs = np.where(gray < np.median(gray) - 35)      # clearly darker than the paper
    if len(xs) < 50:
        return img
    points = np.stack([xs, ys], axis=1)
    h, w = img.shape[:2]
    x0, y0 = np.percentile(points, 0.5, axis=0)       # percentiles ignore a few stray specks
    x1, y1 = np.percentile(points, 99.5, axis=0)
    box_area = (x1 - x0) * (y1 - y0)
    if box_area > 0.6 * w * h:
        return img
    x0, y0 = max(0, int(x0) - margin), max(0, int(y0) - margin)
    x1, y1 = min(w, int(x1) + margin), min(h, int(y1) + margin)
    return img[y0:y1, x0:x1]


def crop_to_strokes(strokes, margin=12):
    """Trim empty space around the drawing, so a small subject on a big page fills the window."""
    points = np.vstack([s.points for s in strokes])
    low = points.min(axis=0) - margin
    high = points.max(axis=0) + margin
    for s in strokes:
        s.points = s.points - low
    width, height = (high - low).tolist()
    return strokes, int(width), int(height)


def fit_scale(img_width, img_height, canvas_width, canvas_height):
    """Scale that makes the drawing fill DRAW_SCALE of the space below the status bar."""
    available_w = max(50, canvas_width - 32)
    available_h = max(50, canvas_height - STATUS_BAR - 24)
    return settings.draw_scale * min(available_w / img_width, available_h / img_height)


def build_point_mapper(img_width, img_height, scale=1.0, offset_y=0.0, center=(0.0, 0.0)):
    """Map image pixels to turtle coordinates around `center`, y pointing up, shifted down by offset_y."""
    cx, cy = center

    def map_point(px, py):
        tx = (px - img_width / 2) * scale + cx
        ty = (img_height / 2 - py) * scale - offset_y + cy
        return tx, ty

    return map_point


def speed_values(name):
    """Return (label, points per frame, pause in ms) for a speed name. 'custom' uses UPDATE_EVERY points per frame."""
    if name == "custom":
        return "Custom", settings.update_every, 10
    return SPEED_PRESETS.get(name, SPEED_PRESETS["normal"])


def ask_setup(screen):
    """Show the setup window and return the chosen style, colors, detail and speed."""
    import tkinter as tk

    root = screen.getcanvas().winfo_toplevel()
    win = tk.Toplevel(root)
    win.title("Turtle Image Sketcher")
    win.resizable(False, False)
    win.transient(root)
    win.configure(padx=22, pady=18)

    choices = {
        "mode": tk.StringVar(win, settings.mode),
        "palette": tk.StringVar(win, settings.palette),
        "detail": tk.StringVar(win, settings.detail),
        "speed": tk.StringVar(win, settings.speed if settings.speed in SPEED_PRESETS else "normal"),
    }
    sections = [
        ("Style", "mode", MODE_LABELS, "Auto picks Silhouette for two-tone images, Sketch for pencil drawings, Comic for the rest."),
        ("Colors", "palette", PALETTE_LABELS, None),
        ("Detail", "detail", DETAIL_LABELS, "Higher looks closer to the original but takes longer to draw."),
        ("Speed", "speed", {name: SPEED_PRESETS[name][0] for name in SPEED_PRESETS}, None),
    ]

    tk.Label(win, text="How should it draw?", font=("Segoe UI", 13, "bold")).grid(row=0, column=0, sticky="w")
    row = 1
    for title, key, labels, note in sections:
        tk.Label(win, text=title, font=("Segoe UI", 10, "bold")).grid(row=row, column=0, sticky="w", pady=(14, 2))
        line = tk.Frame(win)
        line.grid(row=row + 1, column=0, sticky="w")
        for value, label in labels.items():
            tk.Radiobutton(line, text=label, value=value, variable=choices[key], font=UI_FONT).pack(side="left", padx=(0, 10))
        row += 2
        if note:
            tk.Label(win, text=note, fg="#666666", font=("Segoe UI", 9)).grid(row=row, column=0, sticky="w")
            row += 1

    result = {}

    def start(_event=None):
        result.update({k: v.get() for k, v in choices.items()})
        win.destroy()

    tk.Label(win, text="While drawing: 1-4 change speed, Space pauses. Resize the window any time.",
             fg="#666666", font=("Segoe UI", 9)).grid(row=row, column=0, sticky="w", pady=(16, 0))
    tk.Button(win, text="Start drawing", font=("Segoe UI", 10, "bold"), default="active", padx=14, pady=4,
              command=start).grid(row=row + 1, column=0, sticky="e", pady=(12, 0))
    win.bind("<Return>", start)
    win.bind("<Escape>", start)
    win.protocol("WM_DELETE_WINDOW", start)

    win.update_idletasks()
    x = root.winfo_rootx() + (root.winfo_width() - win.winfo_width()) // 2
    y = root.winfo_rooty() + (root.winfo_height() - win.winfo_height()) // 3
    win.geometry(f"+{max(x, 0)}+{max(y, 0)}")
    win.grab_set()
    win.focus_force()
    root.wait_window(win)
    return result


class Sketch:
    """Draws strokes on the turtle screen, keeping the drawing fitted to the window as it resizes."""

    def __init__(self, screen, strokes, img_width, img_height, speed):
        self.screen = screen
        self.strokes = strokes
        self.img_size = (img_width, img_height)
        self.done = 0               # strokes fully drawn
        self.paused = False
        self.finished = False
        self.started = time.time()
        self.elapsed = 0.0

        self.pen = turtle.Turtle()
        self.pen.hideturtle()
        self.pen.pensize(settings.pen_size)
        self.status = turtle.Turtle()
        self.status.hideturtle()
        self.status.penup()
        self.status.color("#555555")

        self.set_speed(speed, redraw_status=False)
        self.layout()

    # --- layout -------------------------------------------------------------
    def canvas_size(self):
        canvas = self.screen.getcanvas()
        canvas.update_idletasks()
        return canvas.winfo_width(), canvas.winfo_height()

    def visible_area(self):
        """Top-left corner and center of the visible part of the canvas, in turtle coordinates.

        Turtle puts (0, 0) in the middle of its scroll region, which isn't always the middle of the
        window (for example after maximizing), so we ask the canvas what is actually on screen.
        """
        canvas = self.screen.getcanvas()
        width, height = self.size
        left, top = canvas.canvasx(0), -canvas.canvasy(0)
        return (left, top), (canvas.canvasx(width / 2), -canvas.canvasy(height / 2))

    def layout(self):
        self.size = self.canvas_size()
        scale = fit_scale(*self.img_size, *self.size)
        self.scale = scale
        self.top_left, center = self.visible_area()
        self.map_point = build_point_mapper(*self.img_size, scale=scale, offset_y=STATUS_BAR / 2, center=center)
        self.show_status()

    def resized(self):
        width, height = self.canvas_size()
        return abs(width - self.size[0]) > 4 or abs(height - self.size[1]) > 4

    def refit(self):
        """Redraw everything finished so far at the new window size, instantly."""
        self.layout()
        self.screen.tracer(0)
        self.pen.clear()
        for stroke in self.strokes[: self.done]:
            self.draw_stroke(stroke, animate=False)
        self.screen.update()
        self.show_status()

    # --- status bar ---------------------------------------------------------
    def show_status(self):
        self.status.clear()
        left, top = self.top_left
        self.status.goto(left + 16, top - 30)
        label = speed_values(self.speed)[0]
        if self.finished:
            count = len(self.strokes)
            text = (f"Done   ·   {count} stroke{'' if count == 1 else 's'} in {self.elapsed:.1f} s   ·   "
                    "Resize the window to redraw")
        else:
            percent = int(100 * self.done / max(1, len(self.strokes)))
            state = "Paused, press Space to resume" if self.paused else "1-4 speed   ·   Space pause"
            text = f"Drawing {percent}%   ·   Speed: {label}   ·   {state}"
        self.status.write(text, font=UI_FONT)
        self.screen.update()

    # --- speed --------------------------------------------------------------
    def set_speed(self, name, redraw_status=True):
        self.speed = name
        _, frame_points, pause_ms = speed_values(name)
        self.frame_points = max(1, frame_points)
        self.frame_pause = pause_ms / 1000
        # Turtle's own animation is turned off; we refresh the screen ourselves every few points
        # and pause briefly, which keeps every speed smooth and predictable.
        self.pen.speed(0)
        self.screen.tracer(0)
        if redraw_status:
            self.show_status()

    def toggle_pause(self):
        self.paused = not self.paused
        self.show_status()

    # --- drawing ------------------------------------------------------------
    def draw_stroke(self, stroke, animate=True):
        """Draw one stroke. Returns False if the window was resized midway, so the caller can refit and retry."""
        points = stroke.points
        if len(points) < 2:
            return True
        pen = self.pen
        pen.color(stroke.color)
        pen.pensize(max(settings.pen_size, round(stroke.width * self.scale * settings.pen_size)))
        x0, y0 = self.map_point(points[0][0], points[0][1])
        pen.penup()
        pen.goto(x0, y0)
        pen.pendown()
        if stroke.kind == "fill":
            pen.begin_fill()
        for i, (px, py) in enumerate(points[1:], start=1):
            pen.goto(*self.map_point(px, py))
            if animate and i % self.frame_points == 0:
                self.screen.update()
                if self.frame_pause:
                    time.sleep(self.frame_pause)
                while self.paused:
                    self.screen.update()
                    time.sleep(0.05)
            if animate and i % RESIZE_CHECK_EVERY == 0 and self.resized():
                if stroke.kind == "fill":
                    pen.end_fill()
                return False
        if stroke.kind == "fill":
            pen.goto(x0, y0)
            pen.end_fill()
        return True

    def run(self):
        for index, stroke in enumerate(self.strokes):
            if self.resized():
                self.refit()
            while not self.draw_stroke(stroke):
                self.refit()  # resized mid-stroke: redraw what's done at the new size, then retry
            self.done = index + 1
            if self.frame_pause:
                self.screen.update()  # Instant skips per-stroke refreshes; the status update below still shows progress
            if self.done % 25 == 0:
                self.show_status()
                print(f"  Drawn {self.done}/{len(self.strokes)} strokes...")
        self.finished = True
        self.elapsed = time.time() - self.started
        self.screen.update()
        self.show_status()
        print(f"Done: {len(self.strokes)} strokes in {self.elapsed:.1f} s.")
        self.watch_resizes()

    def watch_resizes(self):
        """After drawing, keep the picture fitted when the window is resized."""
        try:
            if self.resized():
                self.refit()
            self.screen.ontimer(self.watch_resizes, 300)
        except turtle.Terminator:
            pass  # the window was closed


def main():
    print(f"Loading image: {settings.image_source}")
    try:
        img = load_image(settings.image_source)
    except ImageLoadError as e:
        print(f"\nERROR: {e}")
        sys.exit(1)

    screen = turtle.Screen()
    screen.title("Turtle Image Sketcher")
    screen.bgcolor(settings.background_color)
    screen.setup(width=settings.window_width or 0.85, height=settings.window_height or 0.85)

    choice = ask_setup(screen) if settings.show_setup else {}
    mode, palette, detail = choice.get("mode"), choice.get("palette"), choice.get("detail")
    speed = choice.get("speed") or settings.speed

    print("Processing image...")
    strokes, width, height, mode_used = preprocess_image(img, mode, palette, detail)
    points = sum(len(s.points) for s in strokes)
    print(f"Style: {mode_used}, colors: {palette or settings.palette}, detail: {detail or settings.detail}. "
          f"{len(strokes)} strokes ({points} points) to draw.")

    sketch = Sketch(screen, strokes, width, height, speed)
    for key, name in SPEED_KEYS.items():
        screen.onkey(lambda n=name: sketch.set_speed(n), key)
    screen.onkey(sketch.toggle_pause, "space")
    screen.listen()
    sketch.run()

    if settings.save_output_path:
        try:
            screen.getcanvas().postscript(file=settings.save_output_path)
            print(f"Saved drawing to: {settings.save_output_path}")
        except Exception as e:
            print(f"Warning: could not save output ({e})")

    if settings.auto_close_after_seconds > 0:
        print(f"Auto-closing in {settings.auto_close_after_seconds}s...")
        screen.ontimer(screen.bye, settings.auto_close_after_seconds * 1000)
        turtle.mainloop()
    else:
        turtle.done()


if __name__ == "__main__":
    main()
