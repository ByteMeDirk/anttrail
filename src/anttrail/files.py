"""File-based handlers for Graph Models."""
import re
from enum import Enum
from pathlib import Path


class SupportedReadFormats(Enum):
    """Formats that the Graph Model can consume."""
    MARKDOWN = {".md", ".markdown"}

    def check(self, path: Path) -> bool:
        """Return whether this format member supports ``path``."""
        return path.suffix.lower() in self.value

    @classmethod
    def supports(cls, path: Path) -> bool:
        """Return whether this format member supports ``path``."""
        return any(format_.check(path) for format_ in cls)


class SupportedWriteFormats(Enum):
    """Formats that the Graph Model can output."""
    JSON = {".json"}
    YAML = {".yaml"}
    TEXT = {".txt"}

    def check(self, path: Path) -> bool:
        """Return whether this format member supports ``path``."""
        return path.suffix.lower() in self.value
