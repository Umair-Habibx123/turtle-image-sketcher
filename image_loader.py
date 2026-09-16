"""
image_loader.py
----------------
Resolves an IMAGE_SOURCE value (from .env) into a local OpenCV image,
transparently handling either:
  - a local file path (relative or absolute)
  - a remote URL (http:// or https://), which gets downloaded to a
    temp file first.
"""

import os
import tempfile
from urllib.parse import urlparse

import cv2
import requests


class ImageLoadError(Exception):
    """Raised when the configured image source cannot be loaded."""


def _is_url(source: str) -> bool:
    parsed = urlparse(source)
    return parsed.scheme in ("http", "https")


def _download_image(url: str) -> str:
    """Download a remote image to a temp file and return its local path."""
    try:
        response = requests.get(url, timeout=15, headers={"User-Agent": "Mozilla/5.0"})
        response.raise_for_status()
    except requests.RequestException as e:
        raise ImageLoadError(f"Failed to download image from URL:\n  {url}\n  Reason: {e}")

    content_type = response.headers.get("Content-Type", "")
    if "image" not in content_type and not url.lower().endswith(
        (".png", ".jpg", ".jpeg", ".bmp", ".webp")
    ):
        raise ImageLoadError(
            f"URL did not return an image (Content-Type: {content_type or 'unknown'}):\n  {url}"
        )

    suffix = os.path.splitext(urlparse(url).path)[1] or ".png"
    tmp = tempfile.NamedTemporaryFile(delete=False, suffix=suffix)
    tmp.write(response.content)
    tmp.close()
    return tmp.name


def load_image(source: str):
    """
    Resolve IMAGE_SOURCE (local path or URL) and return a cv2 image (BGR numpy array).
    Raises ImageLoadError with a clear message on any failure.
    """
    if not source or not source.strip():
        raise ImageLoadError(
            "IMAGE_SOURCE is empty. Set it in your .env file to either a local file "
            "path (e.g. spiderman.png) or a URL (e.g. https://example.com/pic.png)."
        )

    source = source.strip()
    local_path = source

    if _is_url(source):
        print(f"Downloading image from URL: {source}")
        local_path = _download_image(source)

    if not os.path.isfile(local_path):
        raise ImageLoadError(
            f"Image file not found: {local_path}\n"
            "  Check that IMAGE_SOURCE in your .env points to an existing file, "
            "or a valid image URL."
        )

    img = cv2.imread(local_path)
    if img is None:
        raise ImageLoadError(
            f"OpenCV could not read the image at: {local_path}\n"
            "  The file may be corrupted or in an unsupported format."
        )

    return img