from io import BytesIO

import pytest
from PIL import Image

from app.photos import (
    DUP_HAMMING_MAX,
    InvalidPhoto,
    hamming_distance,
    process_photo,
)

GPS_EXIF = {
    1: "N",
    2: (13.0, 4.0, 0.0),
    3: "E",
    4: (80.0, 15.0, 0.0),
}


def _exif_with_gps():
    exif = Image.Exif()
    exif[0x010F] = "TestCamera"
    exif[0x8825] = GPS_EXIF
    return exif


def _open(path):
    return Image.open(path)


def test_exif_gps_does_not_survive_processing(tmp_path, make_jpeg):
    source = make_jpeg(seed=1, size=(1200, 900), exif=_exif_with_gps())
    assert Image.open(BytesIO(source)).getexif().get_ifd(0x8825)

    result = process_photo(source, tmp_path)

    stored = _open(tmp_path / result.photo_file)
    assert dict(stored.getexif()) == {}
    thumb = _open(tmp_path / result.thumb_file)
    assert dict(thumb.getexif()) == {}


def test_large_image_is_shrunk_and_thumb_is_smaller(tmp_path, make_jpeg):
    result = process_photo(make_jpeg(seed=2, size=(3200, 2000)), tmp_path)

    full = _open(tmp_path / result.photo_file)
    thumb = _open(tmp_path / result.thumb_file)
    assert max(full.size) == 1600
    assert max(thumb.size) == 400
    assert full.format == "JPEG"
    assert thumb.format == "JPEG"


def test_small_image_is_not_enlarged(tmp_path, make_jpeg):
    result = process_photo(make_jpeg(seed=3, size=(320, 240)), tmp_path)

    assert _open(tmp_path / result.photo_file).size == (320, 240)


def test_plain_bytes_are_rejected(tmp_path):
    with pytest.raises(InvalidPhoto):
        process_photo(b"this is not an image at all", tmp_path)


def test_text_file_renamed_to_jpg_is_rejected(tmp_path):
    fake = b"hello, I am only text pretending to be a photo"
    assert fake[:2] != b"\xff\xd8"
    with pytest.raises(InvalidPhoto):
        process_photo(fake, tmp_path)


def test_same_image_gives_the_same_hash(tmp_path, make_jpeg):
    data = make_jpeg(seed=4, size=(900, 700))

    first = process_photo(data, tmp_path)
    second = process_photo(data, tmp_path)
    assert first.phash == second.phash
    assert len(first.phash) == 16


def test_different_images_are_far_apart(tmp_path, make_jpeg):
    first = process_photo(make_jpeg(seed=5, size=(900, 700)), tmp_path)
    second = process_photo(make_jpeg(seed=6, size=(900, 700)), tmp_path)

    assert hamming_distance(first.phash, second.phash) > DUP_HAMMING_MAX


def test_slightly_resaved_copy_stays_close(tmp_path, make_jpeg):
    original = process_photo(make_jpeg(seed=7, size=(900, 700)), tmp_path)
    resaved = BytesIO()
    _open(tmp_path / original.photo_file).save(resaved, "JPEG", quality=70)

    copy = process_photo(resaved.getvalue(), tmp_path)
    assert hamming_distance(original.phash, copy.phash) <= DUP_HAMMING_MAX
