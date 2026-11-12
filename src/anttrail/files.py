"""File-based handlers for Graph Models."""

from enum import Enum
from pathlib import Path


class SupportedWriteFormats(Enum):
    """Formats that the Graph Model can output."""

    JSON = {".json"}
    YAML = {".yaml"}

    def check(self, path: Path) -> bool:
        """Return whether this format member supports ``path``."""
        return path.suffix.lower() in self.value
