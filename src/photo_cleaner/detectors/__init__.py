from .whatsapp import WhatsAppDetector

DETECTORS = {
    "whatsapp": WhatsAppDetector,
}

__all__ = ["DETECTORS", "WhatsAppDetector"]
