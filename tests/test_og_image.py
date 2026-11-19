"""The share image is a 1200x630 PNG."""

import struct
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def test_og_image_is_1200_by_630_png():
    data = (ROOT / "static" / "og-image.png").read_bytes()
    assert data[:8] == b"\x89PNG\r\n\x1a\n"
    width, height = struct.unpack(">II", data[16:24])
    assert (width, height) == (1200, 630)

