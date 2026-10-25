"""Default alert-setup recommendations (catalog + dismiss + apply)."""

from .catalog import AlertRecommendationCatalog
from .service import AlertRecommendations

__all__ = [
    "AlertRecommendationCatalog",
    "AlertRecommendations",
]
