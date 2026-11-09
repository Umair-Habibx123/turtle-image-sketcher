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
    assert height == config.settings.target_height and width > 0


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


def test_drawing_is_scaled_to_fit_the_window():
    scale = main.fit_scale(3000, 700)
    assert scale <= config.settings.draw_scale
    assert 3000 * scale <= config.settings.window_width


def test_image_center_maps_to_turtle_origin():
    to_turtle = main.build_point_mapper(400, 700, scale=1.0)
    assert to_turtle(200, 350) == (0, 0)
    x, y = to_turtle(0, 0)
    assert x < 0 and y > 0


def test_missing_file_gives_a_clear_error():
    with pytest.raises(ImageLoadError, match="not found"):
        load_image(os.path.join(ROOT, "does-not-exist.png"))


def test_empty_source_gives_a_clear_error():
    with pytest.raises(ImageLoadError, match="empty"):
        load_image("   ")


def test_speed_presets_get_faster_and_keys_cover_them():
    refresh = [main.speed_values(name)[2] for name in ("slow", "normal", "fast", "instant")]
    assert refresh == sorted(refresh)
    assert set(main.SPEED_KEYS.values()) == set(main.SPEED_PRESETS)


def test_settings_fall_back_safely(monkeypatch):
    monkeypatch.setenv("SPEED", "warp")
    monkeypatch.setenv("MODE", "watercolor")
    monkeypatch.setenv("THRESHOLD", "auto")
    monkeypatch.setenv("AUTO_CLOSE_AFTER_SECONDS", "0")
    s = config.load_settings()
    assert (s.speed, s.mode, s.threshold) == ("ask", "auto", None)
    monkeypatch.setenv("SPEED", "ask")
    monkeypatch.setenv("AUTO_CLOSE_AFTER_SECONDS", "5")
    assert config.load_settings().speed == "custom"  # unattended runs don't wait for a click


def test_invalid_numbers_fall_back_to_defaults(monkeypatch):
    monkeypatch.setenv("TARGET_HEIGHT", "not-a-number")
    assert config._get_int("TARGET_HEIGHT", 700) == 700
    monkeypatch.setenv("DRAW_SCALE", "")
    assert config._get_float("DRAW_SCALE", 0.8) == 0.8
