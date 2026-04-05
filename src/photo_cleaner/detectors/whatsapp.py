import re
from pathlib import Path

from .base import AbstractDetector

# Android WhatsApp media filename pattern:
#   IMG-20210304-WA0001.jpg
#   VID-20210304-WA0001.mp4
#   PTT-20210304-WA0001.opus
#   AUD-20210304-WA0001.m4a
#   STK-20210304-WA0001.webp
_WA_PATTERN = re.compile(
    r"^(IMG|VID|PTT|AUD|STK)-\d{8}-WA\d+\.(jpg|jpeg|png|mp4|opus|waptt|m4a|gif|webp)$",
    re.IGNORECASE,
)


class WhatsAppDetector(AbstractDetector):
    name = "whatsapp"

    def __init__(self, also_match_folder: bool = False):
        self.also_match_folder = also_match_folder

    def matches(self, filepath: Path) -> bool:
        if _WA_PATTERN.match(filepath.name):
            return True
        if self.also_match_folder:
            # Match any file inside a folder path containing "WhatsApp"
            for part in filepath.parts[:-1]:
                if "whatsapp" in part.lower():
                    return True
        return False

    def description(self) -> str:
        base = "whatsapp (filename regex"
        if self.also_match_folder:
            base += " + folder path"
        return base + ")"
