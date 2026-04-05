#!/usr/bin/env python3
"""
photo-quarantine: Move suspected unwanted media to a quarantine folder.

Usage:
  python quarantine.py                                     # preview (default)
  python quarantine.py --execute                           # move files
  python quarantine.py --undo <id>                        # restore files
  python quarantine.py --list                              # show past operations

Options:
  --root PATH          Directory to scan (default: current working directory).
                       The quarantine folder is always created here.
  --detector NAME ...  One or more detectors to run. If omitted, all
                       available detectors are run.
                       Available: whatsapp
  --also-match-folder  (whatsapp) Also match files whose parent folder
                       path contains 'WhatsApp', in addition to the
                       filename-based detection.
"""
import argparse
import json
import os
import shutil
import sys
import uuid
from datetime import datetime, timezone
from pathlib import Path

from photo_cleaner.detectors import DETECTORS
from photo_cleaner.xmp import find_sidecar, read_rating

try:
    from tqdm import tqdm as _tqdm
    _HAVE_TQDM = True
except ImportError:
    _HAVE_TQDM = False


# ---------------------------------------------------------------------------
# Scanning
# ---------------------------------------------------------------------------

def scan(scan_dir: Path, library_root: Path, detectors: list) -> tuple[list[Path], list[Path]]:
    """Walk scan_dir and return (matched files, all files).

    Always skips <library_root>/quarantine and <library_root>/tools.
    Shows a tqdm progress bar on stderr if tqdm is available.
    """
    quarantine_root = library_root / "quarantine"
    matched = []
    all_files = []

    bar = _tqdm(unit=" files", desc="Scanning", dynamic_ncols=True) if _HAVE_TQDM else None

    for dirpath, dirnames, filenames in os.walk(scan_dir):
        dirpath = Path(dirpath)

        # Skip quarantine folder (modify dirnames in-place to prune)
        pruned = []
        for d in list(dirnames):
            full = dirpath / d
            if full == quarantine_root or str(full).startswith(str(quarantine_root) + os.sep):
                continue
            pruned.append(d)
        dirnames[:] = pruned

        if bar is not None:
            try:
                bar.set_postfix_str(str(dirpath.relative_to(scan_dir)), refresh=False)
            except ValueError:
                bar.set_postfix_str(dirpath.name, refresh=False)

        for filename in filenames:
            filepath = dirpath / filename
            all_files.append(filepath)
            if any(det.matches(filepath) for det in detectors):
                matched.append(filepath)
            if bar is not None:
                bar.update(1)

    if bar is not None:
        bar.close()

    return matched, all_files


# ---------------------------------------------------------------------------
# Dry-run display
# ---------------------------------------------------------------------------

def _add_to_tree(tree: dict, filepath: Path, base: Path, matched_key: str) -> None:
    try:
        rel = filepath.relative_to(base)
    except ValueError:
        rel = filepath
    parts = rel.parts[:-1]
    node = tree
    for part in parts:
        node = node.setdefault(part, {})
    node[matched_key] = node.get(matched_key, 0) + 1


def build_tree(matched: list[Path], all_files: list[Path], base: Path) -> dict:
    """Build a nested dict with per-folder matched and total counts."""
    tree: dict = {}
    for f in matched:
        _add_to_tree(tree, f, base, "__matched__")
    for f in all_files:
        _add_to_tree(tree, f, base, "__total__")
    return tree


def _sum_key(node: dict, key: str) -> int:
    total = node.get(key, 0)
    for k, v in node.items():
        if not k.startswith("__") and isinstance(v, dict):
            total += _sum_key(v, key)
    return total


def _fmt(matched: int, total: int) -> str:
    pct = f"{matched / total * 100:.0f}%" if total else "n/a"
    return f"{matched}/{total} files, {pct}"


def print_tree(tree: dict, prefix: str = "") -> None:
    keys = sorted(k for k in tree if not k.startswith("__"))
    here_matched = tree.get("__matched__", 0)
    here_total = tree.get("__total__", 0)

    if here_matched:
        print(f"{prefix}  ({_fmt(here_matched, here_total)} here)")

    for i, key in enumerate(keys):
        is_last = i == len(keys) - 1
        connector = "└── " if is_last else "├── "
        child = tree[key]
        child_matched = _sum_key(child, "__matched__")
        child_total = _sum_key(child, "__total__")
        print(f"{prefix}{connector}{key}/  ({_fmt(child_matched, child_total)})")
        extension = "    " if is_last else "│   "
        print_tree(child, prefix + extension)


def dry_run(scan_dir: Path, detectors: list, matched: list[Path], all_files: list[Path]) -> None:
    det_names = ", ".join(d.description() for d in detectors)
    print(f"[dry-run] Detectors : {det_names}")
    print(f"[dry-run] Scan dir  : {scan_dir}")
    print()
    if not matched:
        print("No matching files found.")
        return

    tree = build_tree(matched, all_files, scan_dir)
    print(f"{scan_dir.name}/")
    print_tree(tree, prefix="")
    print()
    print(f"Total: {len(matched)} file{'s' if len(matched) != 1 else ''} would be moved to quarantine.")
    print("Run with --execute to proceed.")


# ---------------------------------------------------------------------------
# Execute
# ---------------------------------------------------------------------------

def execute(library_root: Path, scan_dir: Path, detectors: list, files: list[Path], options: dict) -> str:
    op_id = str(uuid.uuid4())
    quarantine_dir = library_root / "quarantine" / op_id
    files_dir = quarantine_dir / "files"
    files_dir.mkdir(parents=True, exist_ok=True)

    manifest_entries = []
    moved = 0
    errors = []

    for src in files:
        try:
            rel = src.relative_to(library_root)
        except ValueError:
            # File is outside library_root — store absolute path as-is
            rel = Path(str(src).lstrip("/"))
        dest = files_dir / rel
        dest.parent.mkdir(parents=True, exist_ok=True)
        try:
            shutil.move(str(src), str(dest))
            manifest_entries.append({
                "original": str(src),
                "quarantine_relative": str(rel),
            })
            moved += 1
        except Exception as e:
            errors.append({"file": str(src), "error": str(e)})
            continue

        # Move sidecar .xmp alongside the photo (non-fatal if absent or fails)
        sidecar_src = find_sidecar(src)
        if sidecar_src is not None:
            sidecar_dest = dest.parent / sidecar_src.name
            try:
                shutil.move(str(sidecar_src), str(sidecar_dest))
            except Exception as e:
                errors.append({"file": str(sidecar_src), "error": f"sidecar move failed: {e}"})

    manifest = {
        "id": op_id,
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "detectors": [d.name for d in detectors],
        "library_root": str(library_root),
        "scan_dir": str(scan_dir),
        "options": options,
        "moved": moved,
        "errors": errors,
        "files": manifest_entries,
    }
    manifest_path = quarantine_dir / "manifest.json"
    with open(manifest_path, "w") as f:
        json.dump(manifest, f, indent=2)

    print(f"Moved {moved} file{'s' if moved != 1 else ''} to quarantine.")
    if errors:
        print(f"  {len(errors)} error(s) — see manifest for details.")
    print(f"Quarantine ID : {op_id}")
    print(f"Manifest      : {manifest_path}")
    print(f"\nTo undo: python quarantine.py --undo {op_id}")
    return op_id


# ---------------------------------------------------------------------------
# Rating filter helpers
# ---------------------------------------------------------------------------

def parse_rating_filter(rating_args: list[str]) -> set[int]:
    """Parse ['none', '1', '2', '3-5'] into {0, 1, 2, 3, 4, 5}.

    'none' maps to 0 (unrated / no XMP rating present).
    Ranges like '3-5' are expanded to {3, 4, 5}.
    """
    result: set[int] = set()
    for arg in rating_args:
        if arg.lower() == "none":
            result.add(0)
        elif "-" in arg:
            lo_s, hi_s = arg.split("-", 1)
            result.update(range(int(lo_s), int(hi_s) + 1))
        else:
            result.add(int(arg))
    return result


# ---------------------------------------------------------------------------
# Undo
# ---------------------------------------------------------------------------

def undo(library_root: Path, op_id: str, rating_filter: set[int] | None = None) -> None:
    quarantine_dir = library_root / "quarantine" / op_id
    manifest_path = quarantine_dir / "manifest.json"

    if not manifest_path.exists():
        print(f"Error: manifest not found at {manifest_path}", file=sys.stderr)
        sys.exit(1)

    with open(manifest_path) as f:
        manifest = json.load(f)

    files_dir = quarantine_dir / "files"
    restored = 0
    skipped = 0
    errors = []
    remaining_entries = []

    for entry in manifest["files"]:
        original = Path(entry["original"])
        rel = entry["quarantine_relative"]
        src = files_dir / rel

        if not src.exists():
            errors.append({"file": str(original), "error": "quarantine file not found"})
            continue

        if rating_filter is not None:
            if read_rating(src) not in rating_filter:
                skipped += 1
                remaining_entries.append(entry)
                continue

        original.parent.mkdir(parents=True, exist_ok=True)
        try:
            shutil.move(str(src), str(original))
            restored += 1
        except Exception as e:
            errors.append({"file": str(original), "error": str(e)})
            remaining_entries.append(entry)
            continue

        # Move sidecar .xmp alongside the restored file (non-fatal if missing)
        sidecar_src = find_sidecar(src)
        if sidecar_src is not None:
            sidecar_dest = original.parent / sidecar_src.name
            try:
                shutil.move(str(sidecar_src), str(sidecar_dest))
            except Exception as e:
                errors.append({"file": str(sidecar_src), "error": f"sidecar move failed: {e}"})

    print(f"Restored {restored} file{'s' if restored != 1 else ''}.")
    if skipped:
        print(f"  {skipped} file{'s' if skipped != 1 else ''} skipped (rating filter).")
    if errors:
        print(f"  {len(errors)} error(s):")
        for e in errors:
            print(f"    {e['file']}: {e['error']}")

    if remaining_entries:
        manifest["files"] = remaining_entries
        manifest["moved"] = len(remaining_entries)
        with open(manifest_path, "w") as f:
            json.dump(manifest, f, indent=2)
    else:
        try:
            shutil.rmtree(str(quarantine_dir))
            print(f"Removed quarantine folder: {quarantine_dir}")
        except Exception as e:
            print(f"Warning: could not remove quarantine folder: {e}")


# ---------------------------------------------------------------------------
# List previous operations
# ---------------------------------------------------------------------------

def list_ops(library_root: Path) -> None:
    quarantine_root = library_root / "quarantine"
    if not quarantine_root.exists():
        print("No quarantine operations found.")
        return

    ops = []
    for d in sorted(quarantine_root.iterdir()):
        manifest_path = d / "manifest.json"
        if manifest_path.exists():
            with open(manifest_path) as f:
                m = json.load(f)
            ops.append(m)

    if not ops:
        print("No quarantine operations found.")
        return

    print(f"{'ID':<38}  {'Timestamp':<26}  {'Detectors':<16}  {'Scan dir':<40}  {'Flags':<24}  {'Files':>6}")
    print("-" * 160)
    for m in ops:
        dets = ", ".join(m.get("detectors", [m.get("detector", "?")]))
        scan_d = m.get("scan_dir", m.get("library_root", "?"))
        opts = m.get("options", {})
        flags = []
        if opts.get("also_match_folder"):
            flags.append("--also-match-folder")
        flags_str = " ".join(flags) if flags else "-"
        print(f"{m['id']:<38}  {m['timestamp']:<26}  {dets:<16}  {scan_d:<40}  {flags_str:<24}  {m['moved']:>6}")


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

DETECTOR_NAMES = sorted(DETECTORS.keys())


def build_detectors(names: list[str], also_match_folder: bool) -> list:
    detectors = []
    for name in names:
        cls = DETECTORS[name]
        kwargs = {}
        if name == "whatsapp":
            kwargs["also_match_folder"] = also_match_folder
        detectors.append(cls(**kwargs))
    return detectors


def main():
    parser = argparse.ArgumentParser(
        description=(
            "Quarantine unwanted media from a photo library.\n\n"
            "Files are moved (not copied) to a quarantine folder and can be\n"
            "restored at any time using --undo <id>."
        ),
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=f"""
available detectors:
  {", ".join(DETECTOR_NAMES)}

examples:
  # Preview what would be moved (default — no files touched)
  python quarantine.py

  # Scan a specific directory
  python quarantine.py --root /path/to/photos

  # Run only the whatsapp detector
  python quarantine.py --detector whatsapp

  # Run all detectors with folder-path matching enabled
  python quarantine.py --also-match-folder

  # Execute the move
  python quarantine.py --execute

  # Restore a previous operation
  python quarantine.py --undo 3f2a1b4c-...

  # Show all past quarantine operations
  python quarantine.py --list
""",
    )

    parser.add_argument(
        "--root",
        type=Path,
        default=None,
        metavar="PATH",
        help=(
            "Directory to scan. The quarantine folder is created here. "
            "Defaults to the current working directory."
        ),
    )
    parser.add_argument(
        "--detector",
        nargs="+",
        choices=DETECTOR_NAMES,
        default=None,
        metavar="NAME",
        dest="detectors",
        help=(
            f"One or more detectors to run. If omitted, all detectors are used. "
            f"Available: {', '.join(DETECTOR_NAMES)}. "
            "Example: --detector whatsapp"
        ),
    )
    parser.add_argument(
        "--also-match-folder",
        action="store_true",
        help=(
            "(whatsapp detector) In addition to filename matching, also flag any "
            "file whose parent folder path contains the word 'WhatsApp'. "
            "Broadens detection at the cost of possible false positives."
        ),
    )

    mode = parser.add_mutually_exclusive_group()
    mode.add_argument(
        "--execute",
        action="store_true",
        help=(
            "Move all matched files to <root>/quarantine/<id>/. "
            "A manifest.json is written so the operation can be undone."
        ),
    )
    mode.add_argument(
        "--undo",
        metavar="ID",
        help=(
            "Restore files from a previous --execute operation. "
            "ID is the quarantine UUID printed after --execute."
        ),
    )
    mode.add_argument(
        "--list",
        action="store_true",
        help="List all previous quarantine operations stored under <root>/quarantine/.",
    )

    parser.add_argument(
        "--rating",
        nargs="+",
        metavar="RATING",
        help=(
            "With --undo: only restore files whose XMP rating matches. "
            "Values: none (unrated), 1–5, or ranges like 3-5. "
            "Embedded XMP is checked first, then sidecar .xmp files. "
            "Example: --rating none 1 2  or  --rating 3-5"
        ),
    )

    args = parser.parse_args()

    # Resolve root (scan dir + quarantine home): explicit arg or cwd
    library_root = (args.root if args.root is not None else Path.cwd()).resolve()
    if not library_root.exists():
        print(f"Error: --root path does not exist: {library_root}", file=sys.stderr)
        sys.exit(1)

    scan_dir = library_root

    # --list and --undo don't need detectors
    if args.list:
        list_ops(library_root)
        return

    if args.rating and not args.undo:
        parser.error("--rating can only be used with --undo")

    if args.undo:
        rating_filter = parse_rating_filter(args.rating) if args.rating else None
        undo(library_root, args.undo, rating_filter)
        return

    # Build detectors (default: all)
    detector_names = args.detectors if args.detectors else DETECTOR_NAMES
    detectors = build_detectors(detector_names, args.also_match_folder)

    print(f"Scanning {scan_dir} ...")
    files, all_files = scan(scan_dir, library_root, detectors)
    total = len(all_files)
    pct = f"{len(files) / total * 100:.0f}%" if total else "n/a"
    print(f"Found {len(files)}/{total} files ({pct}).")
    print()

    if args.execute:
        if not files:
            print("Nothing to do.")
            return
        options = {"also_match_folder": args.also_match_folder}
        execute(library_root, scan_dir, detectors, files, options)
    else:
        dry_run(scan_dir, detectors, files, all_files)


if __name__ == "__main__":
    main()
