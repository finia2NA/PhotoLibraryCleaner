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

```bash
git clone <repo-url>
cd PhotoLibraryCleaner
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

## Usage

All commands default to the current working directory as the library root. Use `--root` to specify a different path.

### Preview (dry run)

```bash
# Preview what would be quarantined (no files are moved)
python quarantine.py

# Scan a specific directory
python quarantine.py --root /path/to/photos
```

The dry run prints a directory tree with per-folder match counts and percentages.

### Execute

```bash
# Move matched files to <root>/quarantine/<id>/
python quarantine.py --execute
```

A UUID is printed after execution -- keep it to undo later.

### Undo

```bash
# Restore all files from a previous operation
python quarantine.py --undo <id>

# Restore only unrated files and files rated 1-2
python quarantine.py --undo <id> --rating none 1-2

# Restore only files rated 3 or higher (the keepers)
python quarantine.py --undo <id> --rating 3-5
```

The `--rating` flag accepts `none` (unrated), individual values (`1`, `2`, ..., `5`), and ranges (`3-5`). Embedded XMP is checked first, then sidecar `.xmp` files.

### List past operations

```bash
python quarantine.py --list
```

### Detector options

```bash
# Run only the whatsapp detector
python quarantine.py --detector whatsapp

# Also match files whose folder path contains "WhatsApp"
python quarantine.py --also-match-folder
```

## Detectors

Detectors decide which files to quarantine. They are registered in `detectors/__init__.py`.

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

Create a new file in `detectors/` and subclass `AbstractDetector`:

```python
from pathlib import Path
from .base import AbstractDetector

class MyDetector(AbstractDetector):
    name = "mydetector"

    def matches(self, filepath: Path) -> bool:
        # Return True if the file should be quarantined
        ...
```

Then register it in `detectors/__init__.py`:

```python
from .mydetector import MyDetector

DETECTORS = {
    "whatsapp": WhatsAppDetector,
    "mydetector": MyDetector,
}
```

## How it works

1. **Scan** -- recursively walks the target directory (skipping `quarantine/`), running each file through the active detectors.
2. **Quarantine** -- matched files (and their XMP sidecars) are moved into `<root>/quarantine/<uuid>/files/`, preserving the relative directory structure. A `manifest.json` records every moved file's original path.
3. **Undo** -- reads the manifest and moves files back to their original locations. If all files are restored, the quarantine folder is cleaned up automatically. The optional `--rating` filter lets you restore only a subset.

## License

[MIT](LICENSE)
