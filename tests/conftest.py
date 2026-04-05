"""Shared fixtures and file-creation helpers for photo-quarantine tests."""

import struct
import pytest
from pathlib import Path


# ---------------------------------------------------------------------------
# XMP / JPEG builders
# ---------------------------------------------------------------------------

def make_xmp(rating: int) -> str:
    """Return a minimal XMP string with xmp:Rating set to *rating*."""
    return (
        '<?xpacket begin="" id="W5M0MpCehiHzreSzNTczkc9d"?>\n'
        '<x:xmpmeta xmlns:x="adobe:ns:meta/" x:xmptk="Test">\n'
        '  <rdf:RDF xmlns:rdf="http://www.w3.org/1999/02/22-rdf-syntax-ns#">\n'
        f'    <rdf:Description rdf:about="" xmlns:xmp="http://ns.adobe.com/xap/1.0/" xmp:Rating="{rating}"/>\n'
        '  </rdf:RDF>\n'
        '</x:xmpmeta>\n'
        '<?xpacket end="w"?>'
    )


def make_xmp_element_form(rating: int) -> str:
    """Return an XMP string using the element form of xmp:Rating."""
    return (
        '<?xpacket begin="" id="W5M0MpCehiHzreSzNTczkc9d"?>\n'
        '<x:xmpmeta xmlns:x="adobe:ns:meta/">\n'
        '  <rdf:RDF xmlns:rdf="http://www.w3.org/1999/02/22-rdf-syntax-ns#">\n'
        '    <rdf:Description rdf:about="" xmlns:xmp="http://ns.adobe.com/xap/1.0/">\n'
        f'      <xmp:Rating>{rating}</xmp:Rating>\n'
        '    </rdf:Description>\n'
        '  </rdf:RDF>\n'
        '</x:xmpmeta>\n'
        '<?xpacket end="w"?>'
    )


def make_jpeg_with_xmp(rating: int) -> bytes:
    """Return minimal JPEG bytes with an embedded XMP APP1 segment."""
    xmp_bytes = make_xmp(rating).encode("utf-8")
    ns = b"http://ns.adobe.com/xap/1.0/\x00"
    payload = ns + xmp_bytes
    app1 = b"\xFF\xE1" + struct.pack(">H", 2 + len(payload)) + payload
    return b"\xFF\xD8" + app1 + b"\xFF\xD9"


MINIMAL_JPEG = b"\xFF\xD8\xFF\xD9"


# ---------------------------------------------------------------------------
# Filename helpers
# ---------------------------------------------------------------------------

def wa_filename(n: int, prefix: str = "IMG", ext: str = "jpg") -> str:
    """Return a WhatsApp-style filename, e.g. IMG-20210304-WA0001.jpg."""
    return f"{prefix}-20210304-WA{n:04d}.{ext}"


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture()
def library(tmp_path: Path) -> Path:
    """Return a fresh, empty directory to use as the library root."""
    return tmp_path
