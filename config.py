"""
config.py
---------
Loads and validates all settings from the .env file, with sane defaults
for anything not set. Import `settings` from this module elsewhere.
"""

import os
import sys
from dataclasses import dataclass

from dotenv import load_dotenv

load_dotenv()  # reads the .env file next to this project

SPEED_CHOICES = ("slow", "normal", "fast", "instant", "custom")
MODE_CHOICES = ("auto", "silhouette", "lineart", "color", "comic", "sketch")
PALETTE_CHOICES = ("original", "grayscale", "bw")
DETAIL_CHOICES = ("low", "medium", "high")
WINDOW_FRACTION = 0.85  # default window size, as a share of the screen


def _get_int(key: str, default: int) -> int:
    val = os.getenv(key)
    if val is None or val.strip() == "":
        return default
    try:
        return int(val)
    except ValueError:
        print(f"Warning: {key}='{val}' is not a valid integer, using default {default}.")
        return default


def _get_float(key: str, default: float) -> float:
    val = os.getenv(key)
    if val is None or val.strip() == "":
        return default
    try:
        return float(val)
    except ValueError:
        print(f"Warning: {key}='{val}' is not a valid number, using default {default}.")
        return default


def _get_auto_int(key: str):
    """Return an int, or None when the value is empty or 'auto'."""
    val = os.getenv(key)
    if val is None or val.strip().lower() in ("", "auto"):
        return None
    try:
        return int(val)
    except ValueError:
        print(f"Warning: {key}='{val}' is not a valid integer, using auto.")
        return None


def _get_auto_float(key: str):
    """Return a float, or None when the value is empty or 'auto'."""
    val = os.getenv(key)
    if val is None or val.strip().lower() in ("", "auto"):
        return None
    try:
        return float(val)
    except ValueError:
        print(f"Warning: {key}='{val}' is not a valid number, using auto.")
        return None


def _get_str(key: str, default: str) -> str:
    val = os.getenv(key)
    if val is None or val.strip() == "":
        return default
    return val.strip()


def _get_bool(key: str, default: bool) -> bool:
    val = os.getenv(key)
    if val is None or val.strip() == "":
        return default
    return val.strip().lower() in ("1", "true", "yes", "on")


def _choice(key: str, default: str, choices) -> str:
    val = _get_str(key, default).lower()
    if val not in choices:
        print(f"Warning: {key}='{val}' is not one of {', '.join(choices)}, using {default}.")
        return default
    return val


@dataclass
class Settings:
    image_source: str
    show_setup: bool
    mode: str
    palette: str
    detail: str
    speed: str
    colors: int | None        # None means use the DETAIL preset
    threshold: int | None     # None means pick automatically
    target_height: int
    min_contour_area: float
    draw_scale: float         # share of the window the drawing fills, 0.1-1.0
    window_width: int | None  # None means 85% of the screen
    window_height: int | None
    update_every: int
    pen_size: int
    background_color: str
    pen_color: str
    save_output_path: str
    auto_close_after_seconds: int


def load_settings() -> Settings:
    speed_raw = _get_str("SPEED", "normal").lower()
    settings = Settings(
        image_source=_get_str("IMAGE_SOURCE", ""),
        show_setup=_get_bool("SHOW_SETUP", True),
        mode=_choice("MODE", "auto", MODE_CHOICES),
        palette=_choice("PALETTE", "original", PALETTE_CHOICES),
        detail=_choice("DETAIL", "high", DETAIL_CHOICES),
        speed="normal" if speed_raw == "ask" else _choice("SPEED", "normal", SPEED_CHOICES),
        colors=_get_auto_int("COLORS"),
        threshold=_get_auto_int("THRESHOLD"),
        target_height=_get_int("TARGET_HEIGHT", 700),
        min_contour_area=_get_float("MIN_CONTOUR_AREA", 15),
        draw_scale=_get_auto_float("DRAW_SCALE") or 0.95,
        window_width=_get_auto_int("WINDOW_WIDTH"),
        window_height=_get_auto_int("WINDOW_HEIGHT"),
        update_every=_get_int("UPDATE_EVERY", 3),
        pen_size=_get_int("PEN_SIZE", 1),
        background_color=_get_str("BACKGROUND_COLOR", "white"),
        pen_color=_get_str("PEN_COLOR", "black"),
        save_output_path=_get_str("SAVE_OUTPUT_PATH", ""),
        auto_close_after_seconds=_get_int("AUTO_CLOSE_AFTER_SECONDS", 0),
    )

    if speed_raw == "ask":  # older .env files used SPEED=ask for the picker
        settings.show_setup = True
    if settings.auto_close_after_seconds > 0:
        settings.show_setup = False  # unattended runs shouldn't wait for a click

    if not settings.image_source:
        print(
            "ERROR: IMAGE_SOURCE is not set.\n"
            "  1. Copy .env.example to .env\n"
            "  2. Set IMAGE_SOURCE to a local file path or an image URL\n"
        )
        sys.exit(1)

    if settings.colors is not None and not 2 <= settings.colors <= 32:
        print(f"Warning: COLORS={settings.colors} must be between 2 and 32, using the DETAIL preset.")
        settings.colors = None
    if settings.threshold is not None and not 0 <= settings.threshold <= 255:
        print(f"Warning: THRESHOLD={settings.threshold} out of range 0-255, clamping.")
        settings.threshold = max(0, min(255, settings.threshold))
    if not 0.1 <= settings.draw_scale <= 1.0:
        print(f"Warning: DRAW_SCALE={settings.draw_scale} must be between 0.1 and 1.0, using 0.95.")
        settings.draw_scale = 0.95
    if settings.update_every < 1:
        print("Warning: UPDATE_EVERY must be >= 1, using 1.")
        settings.update_every = 1

    return settings


settings = load_settings()
