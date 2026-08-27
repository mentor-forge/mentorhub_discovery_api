"""
Discovery Event service.

Discovery **consumes** Event for Card projections and creates Event records.
The EventCardService subclass binds to `create_event_get_routes` so
`/api/cards/events` returns `Card[]`.
"""

from api_utils.mongo_utils.list_query import DEFAULT_OFFSET, DEFAULT_SIZE
from api_utils.services import EventService as SharedEventService

from src.services.card_service import CARD_TYPE_EVENTS, CardService


class EventService(SharedEventService):
    """Discovery subclass of the shared Event service."""


class EventCardService(EventService):
    """
    Event consume surface projected onto the Card schema.

    Bound to `create_event_get_routes` so `/api/cards/events` returns `Card[]`;
    the unprojected documents stay available on `EventService`.
    """

    @classmethod
    def get_events(
        cls,
        token,
        breadcrumb,
        offset=DEFAULT_OFFSET,
        size=DEFAULT_SIZE,
        filters=None,
        sort_by=None,
        *,
        profile_id=None,
    ):
        """Get the visible Events as Cards."""
        kwargs = {}
        if profile_id is not None:
            kwargs["profile_id"] = profile_id
        events = super().get_events(
            token,
            breadcrumb,
            offset=offset,
            size=size,
            filters=filters,
            sort_by=sort_by,
            **kwargs,
        )
        return CardService.project_all(CARD_TYPE_EVENTS, events, token=token)
