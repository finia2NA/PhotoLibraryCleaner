"""Tests for xmp.py: read_rating and find_sidecar."""

import pytest
from pathlib import Path
from photo_cleaner.xmp import read_rating, find_sidecar
from tests.conftest import make_xmp, make_xmp_element_form, make_jpeg_with_xmp, MINIMAL_JPEG


# ---------------------------------------------------------------------------
# Embedded XMP
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("rating", [1, 3, 5])
def test_embedded_rating(tmp_path, rating):
    f = tmp_path / "photo.jpg"
    f.write_bytes(make_jpeg_with_xmp(rating))
    assert read_rating(f) == rating


def test_embedded_no_xmp_returns_zero(tmp_path):
    f = tmp_path / "photo.jpg"
    f.write_bytes(MINIMAL_JPEG)
    assert read_rating(f) == 0


def test_embedded_negative_rating_clamped_to_zero(tmp_path):
    f = tmp_path / "photo.jpg"
    f.write_bytes(make_jpeg_with_xmp(-1))
    assert read_rating(f) == 0


# ---------------------------------------------------------------------------
# Sidecar XMP (.xmp suffix replacement)
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("rating", [3, 5])
def test_sidecar_xmp_suffix(tmp_path, rating):
    f = tmp_path / "photo.jpg"
    f.write_bytes(MINIMAL_JPEG)
    (tmp_path / "photo.xmp").write_text(make_xmp(rating))
    assert read_rating(f) == rating


# ---------------------------------------------------------------------------
# Sidecar XMP (.jpg.xmp appended)
# ---------------------------------------------------------------------------

def test_sidecar_appended_xmp(tmp_path):
    f = tmp_path / "photo.jpg"
    f.write_bytes(MINIMAL_JPEG)
    (tmp_path / "photo.jpg.xmp").write_text(make_xmp(3))
    assert read_rating(f) == 3


# ---------------------------------------------------------------------------
# Embedded takes priority over sidecar
# ---------------------------------------------------------------------------

def test_embedded_takes_priority_over_sidecar(tmp_path):
    f = tmp_path / "photo.jpg"
    f.write_bytes(make_jpeg_with_xmp(5))
    (tmp_path / "photo.xmp").write_text(make_xmp(3))
    assert read_rating(f) == 5


# ---------------------------------------------------------------------------
# XMP element form vs attribute form
# ---------------------------------------------------------------------------

def test_sidecar_element_form(tmp_path):
    f = tmp_path / "photo.jpg"
    f.write_bytes(MINIMAL_JPEG)
    (tmp_path / "photo.xmp").write_text(make_xmp_element_form(4))
    assert read_rating(f) == 4


# ---------------------------------------------------------------------------
# Malformed XMP
# ---------------------------------------------------------------------------

def test_malformed_xmp_returns_zero(tmp_path):
    f = tmp_path / "photo.jpg"
    f.write_bytes(MINIMAL_JPEG)
    (tmp_path / "photo.xmp").write_text("this is not xml <<<<")
    assert read_rating(f) == 0


# ---------------------------------------------------------------------------
# find_sidecar
# ---------------------------------------------------------------------------

def test_find_sidecar_dot_xmp(tmp_path):
    f = tmp_path / "photo.jpg"
    f.write_bytes(MINIMAL_JPEG)
    sidecar = tmp_path / "photo.xmp"
    sidecar.write_text(make_xmp(3))
    assert find_sidecar(f) == sidecar


def test_find_sidecar_appended(tmp_path):
    f = tmp_path / "photo.jpg"
    f.write_bytes(MINIMAL_JPEG)
    sidecar = tmp_path / "photo.jpg.xmp"
    sidecar.write_text(make_xmp(3))
    assert find_sidecar(f) == sidecar


def test_find_sidecar_prefers_dot_xmp(tmp_path):
    f = tmp_path / "photo.jpg"
    f.write_bytes(MINIMAL_JPEG)
    dot_xmp = tmp_path / "photo.xmp"
    dot_xmp.write_text(make_xmp(3))
    (tmp_path / "photo.jpg.xmp").write_text(make_xmp(4))
    assert find_sidecar(f) == dot_xmp


def test_find_sidecar_none_when_absent(tmp_path):
    f = tmp_path / "photo.jpg"
    f.write_bytes(MINIMAL_JPEG)
    assert find_sidecar(f) is None
