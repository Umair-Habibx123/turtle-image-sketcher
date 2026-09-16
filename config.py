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

load_dotenv()  # reads .env in the current working directory


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


def _get_str(key: str, default: str) -> str:
    val = os.getenv(key)
    if val is None or val.strip() == "":
        return default
    return val.strip()


@dataclass
class Settings:
    image_source: str
    target_height: int
    threshold: int
    min_contour_area: float
    draw_scale: float
    window_width: int
    window_height: int
    pen_speed: int
    update_every: int
    pen_size: int
    background_color: str
    pen_color: str
    save_output_path: str
    auto_close_after_seconds: int


def load_settings() -> Settings:
    image_source = _get_str("IMAGE_SOURCE", "")

    settings = Settings(
        image_source=image_source,
        target_height=_get_int("TARGET_HEIGHT", 700),
        threshold=_get_int("THRESHOLD", 180),
        min_contour_area=_get_float("MIN_CONTOUR_AREA", 15),
        draw_scale=_get_float("DRAW_SCALE", 0.8),
        window_width=_get_int("WINDOW_WIDTH", 800),
        window_height=_get_int("WINDOW_HEIGHT", 575),
        pen_speed=_get_int("PEN_SPEED", 3),
        update_every=_get_int("UPDATE_EVERY", 3),
        pen_size=_get_int("PEN_SIZE", 1),
        background_color=_get_str("BACKGROUND_COLOR", "white"),
        pen_color=_get_str("PEN_COLOR", "black"),
        save_output_path=_get_str("SAVE_OUTPUT_PATH", ""),
        auto_close_after_seconds=_get_int("AUTO_CLOSE_AFTER_SECONDS", 0),
    )

    if not settings.image_source:
        print(
            "ERROR: IMAGE_SOURCE is not set.\n"
            "  1. Copy .env.example to .env\n"
            "  2. Set IMAGE_SOURCE to a local file path or an image URL\n"
        )
        sys.exit(1)

    if not (0 <= settings.threshold <= 255):
        print(f"Warning: THRESHOLD={settings.threshold} out of range 0-255, clamping.")
        settings.threshold = max(0, min(255, settings.threshold))

    if settings.update_every < 1:
        print("Warning: UPDATE_EVERY must be >= 1, using 1.")
        settings.update_every = 1

    return settings


settings = load_settings()