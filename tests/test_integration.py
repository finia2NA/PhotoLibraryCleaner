"""Integration tests: scan, execute, undo, list — using tmp_path."""

import json
import pytest
from pathlib import Path

from quarantine import scan, execute, undo, list_ops, build_detectors
from tests.conftest import (
    make_jpeg_with_xmp,
    make_xmp,
    wa_filename,
    MINIMAL_JPEG,
)


def make_detectors(also_match_folder=False):
    return build_detectors(["whatsapp"], also_match_folder)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def quarantine_files_dir(library: Path) -> Path:
    """Return the files/ dir of the single quarantine operation present."""
    ops = list((library / "quarantine").iterdir())
    assert len(ops) == 1, f"Expected 1 quarantine op, found {len(ops)}"
    return ops[0] / "files"


def manifest_of(library: Path) -> dict:
    ops = list((library / "quarantine").iterdir())
    assert len(ops) == 1
    return json.loads((ops[0] / "manifest.json").read_text())


def op_id_of(library: Path) -> str:
    ops = list((library / "quarantine").iterdir())
    assert len(ops) == 1
    return ops[0].name


# ---------------------------------------------------------------------------
# Scan
# ---------------------------------------------------------------------------

def test_scan_finds_wa_files(library):
    (library / wa_filename(1)).write_bytes(MINIMAL_JPEG)
    (library / wa_filename(2)).write_bytes(MINIMAL_JPEG)
    (library / "holiday.jpg").write_bytes(MINIMAL_JPEG)

    matched, all_files = scan(library, library, make_detectors())

    assert len(matched) == 2
    assert len(all_files) == 3
    assert all(wa_filename(i) in {f.name for f in matched} for i in (1, 2))


def test_scan_skips_quarantine_folder(library):
    wa = library / wa_filename(1)
    wa.write_bytes(MINIMAL_JPEG)
    detectors = make_detectors()

    # Execute so a file ends up in quarantine/
    execute(library, library, detectors, [wa], {})

    # Scan again — should find 0 matched (quarantine skipped, original is gone)
    matched, all_files = scan(library, library, detectors)
    assert len(matched) == 0


# ---------------------------------------------------------------------------
# Execute
# ---------------------------------------------------------------------------

def test_execute_moves_files_and_writes_manifest(library):
    f = library / wa_filename(1)
    f.write_bytes(MINIMAL_JPEG)

    execute(library, library, make_detectors(), [f], {})

    assert not f.exists()
    files_dir = quarantine_files_dir(library)
    assert (files_dir / wa_filename(1)).exists()

    m = manifest_of(library)
    assert m["moved"] == 1
    assert len(m["files"]) == 1
    assert m["files"][0]["original"] == str(f)


def test_execute_moves_sidecar_with_photo(library):
    f = library / wa_filename(1)
    f.write_bytes(MINIMAL_JPEG)
    sidecar = library / (wa_filename(1).replace(".jpg", ".xmp"))
    sidecar.write_text(make_xmp(3))

    execute(library, library, make_detectors(), [f], {})

    files_dir = quarantine_files_dir(library)
    assert (files_dir / sidecar.name).exists()
    assert not sidecar.exists()


# ---------------------------------------------------------------------------
# Undo — full restore
# ---------------------------------------------------------------------------

def test_undo_restores_all_files(library):
    f = library / wa_filename(1)
    f.write_bytes(MINIMAL_JPEG)
    detectors = make_detectors()
    execute(library, library, detectors, [f], {})
    op_id = op_id_of(library)

    undo(library, op_id)

    assert f.exists()
    assert not (library / "quarantine" / op_id).exists()


def test_undo_restores_sidecar_with_photo(library):
    f = library / wa_filename(1)
    f.write_bytes(MINIMAL_JPEG)
    sidecar = library / (wa_filename(1).replace(".jpg", ".xmp"))
    sidecar.write_text(make_xmp(3))
    execute(library, library, make_detectors(), [f], {})
    op_id = op_id_of(library)

    undo(library, op_id)

    assert f.exists()
    assert sidecar.exists()


# ---------------------------------------------------------------------------
# Undo — rating filter
# ---------------------------------------------------------------------------

def _setup_mixed_library(library):
    """Create one 3-star and one 5-star WA photo, execute quarantine."""
    f3 = library / wa_filename(1)
    f3.write_bytes(make_jpeg_with_xmp(3))
    f5 = library / wa_filename(2)
    f5.write_bytes(make_jpeg_with_xmp(5))
    execute(library, library, make_detectors(), [f3, f5], {})
    return f3, f5


def test_undo_rating_filter_restores_subset(library):
    f3, f5 = _setup_mixed_library(library)
    op_id = op_id_of(library)

    undo(library, op_id, rating_filter={4, 5})

    assert f5.exists()
    assert not f3.exists()


def test_undo_rating_filter_updates_manifest(library):
    f3, f5 = _setup_mixed_library(library)
    op_id = op_id_of(library)

    undo(library, op_id, rating_filter={4, 5})

    m = manifest_of(library)
    assert m["moved"] == 1
    assert len(m["files"]) == 1
    assert m["files"][0]["original"] == str(f3)


def test_undo_rating_filter_twice_no_error(library, capsys):
    f3, f5 = _setup_mixed_library(library)
    op_id = op_id_of(library)

    undo(library, op_id, rating_filter={4, 5})
    # f5 is gone from quarantine; second call should not crash
    undo(library, op_id, rating_filter={4, 5})

    out = capsys.readouterr().out
    assert "Restored 0" in out


def test_undo_full_after_partial_cleans_up(library):
    f3, f5 = _setup_mixed_library(library)
    op_id = op_id_of(library)

    undo(library, op_id, rating_filter={4, 5})
    undo(library, op_id)  # restore the rest

    assert f3.exists()
    assert f5.exists()
    assert not (library / "quarantine" / op_id).exists()


def test_undo_rating_filter_with_sidecar(library):
    f3 = library / wa_filename(1)
    f3.write_bytes(MINIMAL_JPEG)
    s3 = library / (wa_filename(1).replace(".jpg", ".xmp"))
    s3.write_text(make_xmp(3))

    f5 = library / wa_filename(2)
    f5.write_bytes(MINIMAL_JPEG)
    s5 = library / (wa_filename(2).replace(".jpg", ".xmp"))
    s5.write_text(make_xmp(5))

    execute(library, library, make_detectors(), [f3, f5], {})
    op_id = op_id_of(library)

    undo(library, op_id, rating_filter={4, 5})

    assert f5.exists()
    assert s5.exists()   # sidecar came back with the photo
    assert not f3.exists()
    assert not s3.exists()


# ---------------------------------------------------------------------------
# List operations
# ---------------------------------------------------------------------------

def test_list_ops_shows_operation(library, capsys):
    f = library / wa_filename(1)
    f.write_bytes(MINIMAL_JPEG)
    execute(library, library, make_detectors(), [f], {})
    op_id = op_id_of(library)

    list_ops(library)
    out = capsys.readouterr().out

    assert op_id in out
    assert "1" in out   # moved count


def test_list_ops_empty(library, capsys):
    list_ops(library)
    out = capsys.readouterr().out
    assert "No quarantine operations found" in out


# ---------------------------------------------------------------------------
# Dry-run: no files touched
# ---------------------------------------------------------------------------

def test_dry_run_does_not_move_files(library):
    f = library / wa_filename(1)
    f.write_bytes(MINIMAL_JPEG)

    # scan without execute — just check files are untouched
    matched, _ = scan(library, library, make_detectors())
    assert len(matched) == 1
    assert f.exists()
    assert not (library / "quarantine").exists()


# ---------------------------------------------------------------------------
# also_match_folder
# ---------------------------------------------------------------------------

def test_also_match_folder(library):
    wa_folder = library / "WhatsApp Images"
    wa_folder.mkdir()
    regular_photo = wa_folder / "holiday.jpg"
    regular_photo.write_bytes(MINIMAL_JPEG)

    detectors_with_folder = make_detectors(also_match_folder=True)
    matched, _ = scan(library, library, detectors_with_folder)

    assert regular_photo in matched


def test_also_match_folder_off_ignores_folder(library):
    wa_folder = library / "WhatsApp Images"
    wa_folder.mkdir()
    regular_photo = wa_folder / "holiday.jpg"
    regular_photo.write_bytes(MINIMAL_JPEG)

    matched, _ = scan(library, library, make_detectors())
    assert regular_photo not in matched
