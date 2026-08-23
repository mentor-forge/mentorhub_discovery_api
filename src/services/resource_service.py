"""
Discovery Resource service.

Discovery **consumes** Resource, so the shared consume surface is inherited
unchanged. The subclass exists so routes and Card lists bind to the local class
and any future Discovery-specific behaviour dispatches through `cls`.
"""

from api_utils.mongo_utils.list_query import DEFAULT_OFFSET, DEFAULT_SIZE
from api_utils.services import ResourceService as SharedResourceService

from src.services.card_service import CARD_TYPE_RESOURCES, CardService


class ResourceService(SharedResourceService):
    """Discovery subclass of the shared Resource service (consume only)."""


class ResourceCardService(ResourceService):
    """
    Resource consume surface projected onto the Card schema.

    Bound to `create_resource_get_routes` so `/api/cards/resources` returns
    `Card[]`; the unprojected documents stay available on `ResourceService`.
    """

    @classmethod
    def get_resources(
        cls,
        token,
        breadcrumb,
        offset=DEFAULT_OFFSET,
        size=DEFAULT_SIZE,
        filters=None,
        sort_by=None,
    ):
        """Get the visible Resources as Cards."""
        resources = super().get_resources(
            token, breadcrumb, offset, size, filters, sort_by
        )
        return CardService.project_all(CARD_TYPE_RESOURCES, resources)
