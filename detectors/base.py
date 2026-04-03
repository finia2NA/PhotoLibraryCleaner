from abc import ABC, abstractmethod
from pathlib import Path


class AbstractDetector(ABC):
    name: str = ""

    @abstractmethod
    def matches(self, filepath: Path) -> bool:
        """Return True if this file should be quarantined."""
        ...

    def description(self) -> str:
        return self.name
