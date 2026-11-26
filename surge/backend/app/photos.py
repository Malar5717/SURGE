"""Validate, re-encode and fingerprint posted photos."""

import uuid
from dataclasses import dataclass
from io import BytesIO
from pathlib import Path

from PIL import Image, ImageOps, UnidentifiedImageError

MAX_UPLOAD_MB = 5
MAX_UPLOAD_BYTES = MAX_UPLOAD_MB * 1024 * 1024
MAX_LONG_SIDE = 1600
THUMB_LONG_SIDE = 400
JPEG_QUALITY = 85
DUP_HAMMING_MAX = 5
DUP_WINDOW_DAYS = 30
ALLOWED_FORMATS = ("JPEG", "PNG")


class InvalidPhoto(Exception):
    """The uploaded bytes are not a usable JPEG or PNG."""


class PhotoTooLarge(Exception):
    """The uploaded file is larger than MAX_UPLOAD_MB."""


@dataclass(frozen=True)
class ProcessedPhoto:
    photo_file: str
    thumb_file: str
    phash: str


def _load(data: bytes) -> Image.Image:
    """Open and verify JPEG/PNG bytes, returning a fresh decoded image."""
    if len(data) > MAX_UPLOAD_BYTES:
        raise PhotoTooLarge
    try:
        probe = Image.open(BytesIO(data))
        if probe.format not in ALLOWED_FORMATS:
            raise InvalidPhoto
        probe.verify()
        return Image.open(BytesIO(data))
    except (UnidentifiedImageError, OSError) as exc:
        raise InvalidPhoto from exc


def dhash(image: Image.Image) -> str:
    """Return a 64-bit difference hash as 16 hex characters."""
    gray = image.convert("L").resize((9, 8), Image.LANCZOS)
    pixels = gray.load()
    bits = 0
    for y in range(8):
        for x in range(8):
            bit = 1 if pixels[x, y] > pixels[x + 1, y] else 0
            bits = (bits << 1) | bit
    return f"{bits:016x}"


def hamming_distance(first: str, second: str) -> int:
    """Return how many bits differ between two hex hashes."""
    return (int(first, 16) ^ int(second, 16)).bit_count()


def process_photo(data: bytes, upload_dir: Path) -> ProcessedPhoto:
    """Re-encode a photo without metadata and write the full and thumb files."""
    image = _load(data)
    image = ImageOps.exif_transpose(image).convert("RGB")
    image.thumbnail((MAX_LONG_SIDE, MAX_LONG_SIDE))
    thumb = image.copy()
    thumb.thumbnail((THUMB_LONG_SIDE, THUMB_LONG_SIDE))
    phash = dhash(image)

    upload_dir.mkdir(parents=True, exist_ok=True)
    name = uuid.uuid4().hex
    photo_file = f"{name}.jpg"
    thumb_file = f"{name}_t.jpg"
    image.save(upload_dir / photo_file, "JPEG", quality=JPEG_QUALITY)
    thumb.save(upload_dir / thumb_file, "JPEG", quality=JPEG_QUALITY)
    return ProcessedPhoto(photo_file=photo_file, thumb_file=thumb_file, phash=phash)


def remove_photos(upload_dir: Path, *names: str) -> None:
    """Delete stored photo files, ignoring names that are gone."""
    for name in names:
        (upload_dir / name).unlink(missing_ok=True)
