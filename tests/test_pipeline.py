"""Tests for the image pipeline. They run without opening a turtle window."""

import os
import sys
import types

import cv2
import numpy as np
import pytest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
os.environ.setdefault("IMAGE_SOURCE", os.path.join(ROOT, "spiderman.png"))
sys.modules.setdefault("turtle", types.ModuleType("turtle"))

import config  # noqa: E402
import main  # noqa: E402
import sketch_modes  # noqa: E402
from image_loader import ImageLoadError, load_image  # noqa: E402

SAMPLE = os.path.join(ROOT, "spiderman.png")


def colorful_scene():
    """A small illustration-like test image: dark sky, a bright moon and a red figure."""
    img = np.zeros((200, 300, 3), np.uint8)
    img[:] = (90, 40, 20)                                      # dark blue sky (BGR)
    cv2.circle(img, (60, 50), 25, (200, 240, 255), -1)          # pale moon
    cv2.rectangle(img, (150, 60), (230, 190), (30, 30, 200), -1)  # red figure
    cv2.circle(img, (190, 45), 20, (120, 190, 240), -1)         # skin-tone head
    return img


def test_sample_silhouette_is_chosen_and_keeps_one_shape():
    strokes, width, height, mode = main.preprocess_image(load_image(SAMPLE))
    assert mode == "silhouette"
    assert strokes and all(s.kind == "fill" for s in strokes)
    assert 0 < height <= config.settings.target_height + 24 and width > 0   # cropped to the drawing, plus a margin


def test_colorful_image_gets_comic_mode_with_colors_and_lines():
    strokes, mode = sketch_modes.build_strokes(colorful_scene(), "auto")
    assert mode == "comic"
    kinds = {s.kind for s in strokes}
    assert kinds == {"fill", "line"}
    colors = {s.color for s in strokes if s.kind == "fill"}
    assert len(colors) >= 3 and all(c.startswith("#") for c in colors)


def test_silhouette_works_on_dark_backgrounds():
    img = np.zeros((100, 100, 3), np.uint8)
    cv2.circle(img, (50, 50), 30, (255, 255, 255), -1)     # light shape on black
    strokes = sketch_modes.silhouette(img)
    assert len(strokes) == 1
    area = cv2.contourArea(strokes[0].points.reshape(-1, 1, 2))
    assert 2000 < area < 3200                                # the circle, not the whole frame


def test_lineart_draws_open_lines():
    strokes = sketch_modes.lineart(colorful_scene())
    assert strokes and all(s.kind == "line" for s in strokes)


def test_unknown_mode_is_rejected():
    with pytest.raises(ValueError, match="Unknown mode"):
        sketch_modes.build_strokes(colorful_scene(), "watercolor")


def test_drawing_grows_and_shrinks_with_the_window():
    small = main.fit_scale(1200, 700, 800, 600)
    large = main.fit_scale(1200, 700, 1900, 1000)
    assert large > small                      # maximizing makes the drawing bigger
    assert 1200 * small <= 800                # and it always fits the width
    assert 700 * large <= 1000 - main.STATUS_BAR


def test_palettes_change_the_colors():
    scene = colorful_scene()
    gray, _ = sketch_modes.build_strokes(scene, "color", palette="grayscale")
    assert all(s.color[1:3] == s.color[3:5] == s.color[5:7] for s in gray)    # r == g == b
    bw, _ = sketch_modes.build_strokes(scene, "comic", palette="bw")
    assert {s.color for s in bw} <= {"#000000", "#ffffff"}
    original, _ = sketch_modes.build_strokes(scene, "color", palette="original")
    assert len({s.color for s in original}) > len({s.color for s in gray if s.color != gray[0].color}) - 1


def test_higher_detail_keeps_more_colors_and_starts_with_a_base_layer():
    scene = colorful_scene()
    low = sketch_modes.color_regions(scene, "low")
    high = sketch_modes.color_regions(scene, "high")
    assert len(high) >= len(low)
    h, w = scene.shape[:2]
    assert low[0].kind == "fill" and abs(sketch_modes._area(low[0].points) - (w - 1) * (h - 1)) < 1


def test_image_center_maps_to_turtle_origin():
    to_turtle = main.build_point_mapper(400, 700, scale=1.0)
    assert to_turtle(200, 350) == (0, 0)
    shifted = main.build_point_mapper(400, 700, scale=1.0, offset_y=20)
    assert shifted(200, 350) == (0, -20)     # moved down to leave room for the status bar
    x, y = to_turtle(0, 0)
    assert x < 0 and y > 0


def test_missing_file_gives_a_clear_error():
    with pytest.raises(ImageLoadError, match="not found"):
        load_image(os.path.join(ROOT, "does-not-exist.png"))


def test_empty_source_gives_a_clear_error():
    with pytest.raises(ImageLoadError, match="empty"):
        load_image("   ")


def test_speed_presets_get_faster_and_keys_cover_them():
    per_frame = [main.speed_values(name)[1] for name in ("slow", "normal", "fast", "instant")]
    pauses = [main.speed_values(name)[2] for name in ("slow", "normal", "fast", "instant")]
    assert per_frame == sorted(per_frame) and pauses == sorted(pauses, reverse=True)
    assert set(main.SPEED_KEYS.values()) == set(main.SPEED_PRESETS)
    assert set(main.PALETTE_LABELS) == set(sketch_modes.PALETTES)
    assert set(main.DETAIL_LABELS) == set(sketch_modes.DETAILS)


def test_settings_fall_back_safely(monkeypatch):
    monkeypatch.setenv("SPEED", "warp")
    monkeypatch.setenv("MODE", "watercolor")
    monkeypatch.setenv("PALETTE", "sepia")
    monkeypatch.setenv("THRESHOLD", "auto")
    monkeypatch.setenv("DRAW_SCALE", "7")
    monkeypatch.setenv("AUTO_CLOSE_AFTER_SECONDS", "0")
    s = config.load_settings()
    assert (s.speed, s.mode, s.palette, s.threshold, s.draw_scale) == ("normal", "auto", "original", None, 0.95)
    monkeypatch.setenv("SPEED", "ask")                 # older .env files
    assert config.load_settings().show_setup is True
    monkeypatch.setenv("AUTO_CLOSE_AFTER_SECONDS", "5")
    assert config.load_settings().show_setup is False  # unattended runs don't wait for a click


def test_invalid_numbers_fall_back_to_defaults(monkeypatch):
    monkeypatch.setenv("TARGET_HEIGHT", "not-a-number")
    assert config._get_int("TARGET_HEIGHT", 700) == 700
    monkeypatch.setenv("DRAW_SCALE", "")
    assert config._get_float("DRAW_SCALE", 0.8) == 0.8


def pencil_drawing():
    """A light, colorless image with soft gray pencil-like strokes on a gray gradient."""
    img = np.tile(np.linspace(215, 235, 300, dtype=np.uint8), (200, 1))
    img = cv2.cvtColor(img, cv2.COLOR_GRAY2BGR)
    cv2.circle(img, (150, 100), 50, (110, 110, 110), 3)
    cv2.line(img, (60, 170), (240, 170), (130, 130, 130), 2)
    return img


def test_pencil_drawings_get_the_sketch_style():
    strokes, mode = sketch_modes.build_strokes(pencil_drawing(), "auto")
    assert mode == "sketch"
    assert strokes and all(s.kind == "line" and s.color == sketch_modes.PENCIL for s in strokes)


def test_nearest_path_visits_every_point_and_lifts_the_pen_for_long_jumps():
    near = np.array([[0, 0], [1, 0], [2, 0], [3, 1]])
    far = np.array([[100, 100], [101, 100], [102, 101]])
    points = np.vstack([near, far])
    runs = sketch_modes.nearest_path(points, max_jump=5)
    assert sum(len(r) for r in runs) == len(points)
    assert len(runs) == 2                                # one pen lift between the two groups
    assert sketch_modes.nearest_path(np.empty((0, 2), int), 5) == []


def test_more_sketch_detail_keeps_more_pencil_marks():
    gray = cv2.cvtColor(pencil_drawing(), cv2.COLOR_BGR2GRAY)
    assert len(sketch_modes.dark_pixels(gray, "high")) >= len(sketch_modes.dark_pixels(gray, "low"))


def test_small_drawings_on_a_plain_page_are_cropped_to_the_subject():
    page = np.full((400, 300, 3), 230, np.uint8)
    cv2.circle(page, (150, 200), 30, (120, 120, 120), 3)           # a small sketch in the middle of the page
    cropped = main.crop_to_subject(page)
    assert cropped.shape[0] < 120 and cropped.shape[1] < 120        # the empty page around it is gone
    strokes, width, height, _ = main.preprocess_image(page, mode="sketch")
    points = np.vstack([s.points for s in strokes])
    assert points.min() >= 0 and points[:, 0].max() <= width and points[:, 1].max() <= height


def test_full_frame_pictures_are_not_cropped():
    scene = colorful_scene()                                          # dark background, fills the frame
    assert main.crop_to_subject(scene).shape == scene.shape
