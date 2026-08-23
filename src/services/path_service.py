"""
Discovery Path service.

Discovery **consumes** Path, so the shared consume surface is inherited
unchanged. The subclass exists so routes and Card lists bind to the local class
and any future Discovery-specific behaviour dispatches through `cls`.
"""

from api_utils.mongo_utils.list_query import DEFAULT_OFFSET, DEFAULT_SIZE
from api_utils.services import PathService as SharedPathService

from src.services.card_service import CARD_TYPE_PATHS, CardService


class PathService(SharedPathService):
    """Discovery subclass of the shared Path service (consume only)."""


class PathCardService(PathService):
    """
    Path consume surface projected onto the Card schema.

    Bound to `create_path_get_routes` so `/api/cards/paths` returns `Card[]`;
    the unprojected documents stay available on `PathService`.
    """

    @classmethod
    def get_paths(
        cls,
        token,
        breadcrumb,
        offset=DEFAULT_OFFSET,
        size=DEFAULT_SIZE,
        filters=None,
        sort_by=None,
    ):
        """Get the visible Paths as Cards."""
        paths = super().get_paths(token, breadcrumb, offset, size, filters, sort_by)
        return CardService.project_all(CARD_TYPE_PATHS, paths)
