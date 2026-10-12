"""Stable catalog fields for one download format."""

from dataclasses import dataclass


@dataclass(frozen=True)
class ExportSpec:
    """Catalog id, label, media type, and file suffix for one exporter."""

    format_id: str
    label: str
    media_type: str
    suffix: str

    def catalog_entry(self) -> dict[str, str]:
        return {
            "id": self.format_id,
            "label": self.label,
            "media_type": self.media_type,
            "suffix": self.suffix,
        }
