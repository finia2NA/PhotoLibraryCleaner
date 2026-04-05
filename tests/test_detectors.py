"""Tests for the WhatsApp detector."""

import pytest
from pathlib import Path
from photo_cleaner.detectors.whatsapp import WhatsAppDetector


@pytest.fixture()
def det():
    return WhatsAppDetector()


@pytest.fixture()
def det_folder():
    return WhatsAppDetector(also_match_folder=True)


# ---------------------------------------------------------------------------
# Positive filename matches
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("prefix", ["IMG", "VID", "PTT", "AUD", "STK"])
def test_matches_all_prefixes(det, prefix):
    assert det.matches(Path(f"{prefix}-20210304-WA0001.jpg"))


@pytest.mark.parametrize("ext", ["jpg", "jpeg", "png", "mp4", "opus", "waptt", "m4a", "gif", "webp"])
def test_matches_all_extensions(det, ext):
    assert det.matches(Path(f"IMG-20210304-WA0001.{ext}"))


def test_matches_case_insensitive(det):
    assert det.matches(Path("img-20210304-wa0001.JPG"))


def test_matches_multi_digit_wa_number(det):
    assert det.matches(Path("IMG-20210304-WA0123.jpg"))


# ---------------------------------------------------------------------------
# Negative filename matches
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("name", [
    "photo.jpg",                          # plain photo, no WA pattern
    "IMG-2021034-WA0001.jpg",             # date too short (7 digits)
    "IMG-202103040-WA0001.jpg",           # date too long (9 digits)
    "IMG-20210304-0001.jpg",              # missing WA prefix
    "IMG-20210304-WA0001.bmp",            # unsupported extension
    "DOC-20210304-WA0001.jpg",            # unsupported type prefix
    "IMG_20210304_WA0001.jpg",            # underscores instead of dashes
    "IMG-20210304-WA.jpg",                # WA with no number
])
def test_no_match_invalid_names(det, name):
    assert not det.matches(Path(name))


# ---------------------------------------------------------------------------
# Folder matching
# ---------------------------------------------------------------------------

def test_folder_match_off_ignores_folder(det):
    p = Path("/media/WhatsApp/photo.jpg")
    assert not det.matches(p)


def test_folder_match_on_matches_whatsapp_folder(det_folder):
    p = Path("/media/WhatsApp/photo.jpg")
    assert det_folder.matches(p)


def test_folder_match_on_case_insensitive(det_folder):
    p = Path("/media/whatsapp images/photo.jpg")
    assert det_folder.matches(p)


def test_folder_match_on_substring_in_folder(det_folder):
    p = Path("/media/my_whatsapp_backup/photo.jpg")
    assert det_folder.matches(p)


def test_folder_match_on_wa_filename_still_matches(det_folder):
    # WA-named files match regardless of folder
    p = Path("/some/normal/folder/IMG-20210304-WA0001.jpg")
    assert det_folder.matches(p)


# ---------------------------------------------------------------------------
# description()
# ---------------------------------------------------------------------------

def test_description_without_folder(det):
    assert det.description() == "whatsapp (filename regex)"


def test_description_with_folder(det_folder):
    assert det_folder.description() == "whatsapp (filename regex + folder path)"
