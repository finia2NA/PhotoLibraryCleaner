# PhotoLibraryCleaner

Python tool to sort through a large photo library and "quarantine" files according to configurable rules. Matched files are moved (not copied) to a quarantine folder and can be restored at any time.

## Features

- **Dry-run by default** -- preview what would be moved in a tree view before touching any files.
- **Reversible** -- every operation writes a manifest so it can be fully undone with `--undo`.
- **XMP rating filter** -- selectively restore files based on embedded or sidecar XMP ratings, for integration with manual culling workflows (e.g. rate quarantined files in Lightroom, then restore only the keepers).
- **Extensible detector architecture** -- add new filter criteria by subclassing `AbstractDetector` without touching the main script.
- **Progress bar** -- optional `tqdm` progress bar during scanning.

## Requirements

- Python 3.10+
- No required external dependencies (stdlib only)
- **Optional:** `tqdm` for progress bars during scanning

## Installation

### pipx (recommended)

[pipx](https://pipx.pypa.io/) installs the tool in an isolated environment and puts the `photo-cleaner` command on your `$PATH`:

```bash
pipx install git+https://github.com/finia2NA/PhotoLibraryCleaner.git

# With optional progress bar support:
pipx install "photo-library-cleaner[progress] @ git+https://github.com/finia2NA/PhotoLibraryCleaner.git"
```

If you don't have pipx yet:

```bash
# macOS
brew install pipx && pipx ensurepath

# Linux (Debian/Ubuntu)
sudo apt install pipx && pipx ensurepath
```

### pip

```bash
pip install git+https://github.com/finia2NA/PhotoLibraryCleaner.git
```

### From source (development)

```bash
git clone https://github.com/finia2NA/PhotoLibraryCleaner.git
cd PhotoLibraryCleaner
python3 -m venv .venv
source .venv/bin/activate
pip install -e ".[progress]"
```

## Usage

All commands default to the current working directory as the library root. Use `--root` to specify a different path.

### Preview (dry run)

```bash
# Preview what would be quarantined (no files are moved)
photo-cleaner

# Scan a specific directory
photo-cleaner --root /path/to/photos
```

The dry run prints a directory tree with per-folder match counts and percentages.

### Execute

```bash
# Move matched files to <root>/quarantine/<id>/
photo-cleaner --execute
```

A UUID is printed after execution -- keep it to undo later.

### Undo

```bash
# Restore all files from a previous operation
photo-cleaner --undo <id>

# Restore only unrated files and files rated 1-2
photo-cleaner --undo <id> --rating none 1-2

# Restore only files rated 3 or higher (the keepers)
photo-cleaner --undo <id> --rating 3-5
```

The `--rating` flag accepts `none` (unrated), individual values (`1`, `2`, ..., `5`), and ranges (`3-5`). Embedded XMP is checked first, then sidecar `.xmp` files.

### List past operations

```bash
photo-cleaner --list
```

### Detector options

```bash
# Run only the whatsapp detector
photo-cleaner --detector whatsapp

# Also match files whose folder path contains "WhatsApp"
photo-cleaner --also-match-folder
```

## Detectors

Detectors decide which files to quarantine. They are registered in `src/photo_cleaner/detectors/__init__.py`.

### whatsapp

Matches Android WhatsApp media files by filename pattern:

```
IMG-20210304-WA0001.jpg
VID-20210304-WA0001.mp4
PTT-20210304-WA0001.opus
AUD-20210304-WA0001.m4a
STK-20210304-WA0001.webp
```

With `--also-match-folder`, also flags any file inside a directory path containing "WhatsApp".

### Writing a custom detector

Create a new file in `src/photo_cleaner/detectors/` and subclass `AbstractDetector`:

```python
from pathlib import Path
from .base import AbstractDetector

class MyDetector(AbstractDetector):
    name = "mydetector"

    def matches(self, filepath: Path) -> bool:
        # Return True if the file should be quarantined
        ...
```

Then register it in `src/photo_cleaner/detectors/__init__.py`:

```python
from .mydetector import MyDetector

DETECTORS = {
    "whatsapp": WhatsAppDetector,
    "mydetector": MyDetector,
}
```

## Development

### Running the tests

Install the dev dependencies into a virtual environment and run pytest:

```bash
git clone https://github.com/finia2NA/PhotoLibraryCleaner.git
cd PhotoLibraryCleaner
python3 -m venv .venv
source .venv/bin/activate        # Windows: .venv\Scripts\activate
pip install -e ".[progress,dev]"
pytest tests/ -v
```

The test suite uses pytest's `tmp_path` fixture so no files are written outside a temporary directory — safe to run anywhere.

### Test structure

| File | What it covers |
|------|----------------|
| `tests/test_detectors.py` | `WhatsAppDetector`: all filename patterns, folder matching, `description()` |
| `tests/test_xmp.py` | `read_rating` (embedded + sidecar), priority rules, `find_sidecar`, malformed XML |
| `tests/test_rating_filter.py` | `parse_rating_filter`: `none`, integers, ranges, combinations |
| `tests/test_integration.py` | Full scan → execute → undo workflow, manifest updates, `list_ops`, dry-run, `--also-match-folder` |

## How it works

1. **Scan** -- recursively walks the target directory (skipping `quarantine/`), running each file through the active detectors.
2. **Quarantine** -- matched files (and their XMP sidecars) are moved into `<root>/quarantine/<uuid>/files/`, preserving the relative directory structure. A `manifest.json` records every moved file's original path.
3. **Undo** -- reads the manifest and moves files back to their original locations. If all files are restored, the quarantine folder is cleaned up automatically. The optional `--rating` filter lets you restore only a subset.

## License

[MIT](LICENSE)
