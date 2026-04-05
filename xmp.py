"""XMP rating utilities: read xmp:Rating from embedded XMP or sidecar files."""

import xml.etree.ElementTree as ET
from pathlib import Path

_XMP_NS = "http://ns.adobe.com/xap/1.0/"
_RDF_NS = "http://www.w3.org/1999/02/22-rdf-syntax-ns#"


def _parse_xmp_text(xmp_text: str) -> int | None:
    """Parse XMP XML and return xmp:Rating as int, or None if absent."""
    try:
        root = ET.fromstring(xmp_text)
        # Attribute form: <rdf:Description xmp:Rating="3" .../>
        for desc in root.iter(f'{{{_RDF_NS}}}Description'):
            val = desc.get(f'{{{_XMP_NS}}}Rating')
            if val is not None:
                return int(float(val))
        # Element form: <xmp:Rating>3</xmp:Rating>
        for el in root.iter(f'{{{_XMP_NS}}}Rating'):
            if el.text:
                return int(float(el.text))
    except Exception:
        pass
    return None


def _embedded_rating(filepath: Path) -> int | None:
    """Extract xmp:Rating from an embedded XMP packet in the file bytes."""
    try:
        data = filepath.read_bytes()
        start = data.find(b'<x:xmpmeta')
        if start == -1:
            return None
        end = data.find(b'</x:xmpmeta>', start)
        if end == -1:
            return None
        chunk = data[start : end + len(b'</x:xmpmeta>')]
        return _parse_xmp_text(chunk.decode('utf-8', errors='replace'))
    except OSError:
        return None


def _sidecar_candidates(filepath: Path) -> list[Path]:
    return [filepath.with_suffix('.xmp'), Path(str(filepath) + '.xmp')]


def find_sidecar(filepath: Path) -> Path | None:
    """Return the first existing sidecar .xmp file for filepath, or None."""
    for candidate in _sidecar_candidates(filepath):
        if candidate.exists():
            return candidate
    return None


def read_rating(filepath: Path) -> int:
    """Return the XMP rating for a file (0 = unrated).

    Checks embedded XMP first, then sidecar .xmp files.
    Negative ratings (e.g. Lightroom 'rejected' = -1) are clamped to 0.
    """
    rating = _embedded_rating(filepath)
    if rating is None:
        sidecar = find_sidecar(filepath)
        if sidecar is not None:
            try:
                rating = _parse_xmp_text(sidecar.read_text(encoding='utf-8', errors='replace'))
            except OSError:
                pass
    return max(0, rating) if rating is not None else 0
