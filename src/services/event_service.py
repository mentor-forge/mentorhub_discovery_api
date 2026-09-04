"""
Discovery Event service.

Discovery **consumes** Event for Card projections and creates Event records.
The EventCardService subclass binds to `create_event_get_routes` so
`/api/cards/events` returns `Card[]`. Member/Mentee activity counts use
`recent_event_count_for_profile` (MongoIO on the target profile) rather than
shared `get_events`, which is own-profile outbound.
"""

from datetime import datetime, timedelta, timezone

from api_utils import Config, MongoIO
from api_utils.mongo_utils import encode_document
from api_utils.mongo_utils.list_query import DEFAULT_OFFSET, DEFAULT_SIZE
from api_utils.services import EventService as SharedEventService
from api_utils.services.event_service import DATE_PROPERTIES, EVENT_ID_PROPERTIES

from src.services.card_service import CARD_TYPE_EVENTS, CardService
from src.services.profile_service import ProfileService

CARD_ACTIVITY_WINDOW_DAYS = 30


class EventService(SharedEventService):
    """Discovery subclass of the shared Event service."""

    @classmethod
    def recent_event_count_for_profile(
        cls, profile_id, token, breadcrumb, *, days=CARD_ACTIVITY_WINDOW_DAYS
    ):
        """
        Count Events for a profile in the last ``days`` (UTC).

        Live ``Event.yaml`` identity is ``context.profile_id``; also match
        top-level ``profile_id`` the way shared Event identity does. Time
        field is ``created.at_time``. Does **not** use shared ``get_events``
        (own-profile outbound). Callers must already have this Profile on
        the Member or Mentee home section.

        Args:
            profile_id: Profile ``_id`` to count Events for
            token: Authentication token
            breadcrumb: Audit breadcrumb
            days: Activity window in days (default ``CARD_ACTIVITY_WINDOW_DAYS``)

        Returns:
            int: Number of matching Event documents
        """
        if not profile_id:
            return 0

        context_clause = {"context": {"profile_id": profile_id}}
        encode_document(context_clause, EVENT_ID_PROPERTIES, DATE_PROPERTIES)
        top_clause = {"profile_id": profile_id}
        encode_document(top_clause, EVENT_ID_PROPERTIES, DATE_PROPERTIES)

        cutoff = datetime.now(timezone.utc) - timedelta(days=days)
        match = {
            "$or": [context_clause, top_clause],
            "created.at_time": {"$gte": cutoff},
        }

        mongo = MongoIO.get_instance()
        config = Config.get_instance()
        docs = mongo.get_documents(config.EVENT_COLLECTION_NAME, match=match)
        return len(docs)


class EventCardService(EventService):
    """
    Event consume surface projected onto the Card schema.

    Bound to `create_event_get_routes` so `/api/cards/events` returns `Card[]`;
    the unprojected documents stay available on `EventService`. Event cards have
    no `link`. Card `name` is the Event `type`; `description` is Markdown with
    the Event `type`, Profile `display_name`, and `created.at_time`.
    """

    @classmethod
    def _event_profile_id(cls, event):
        """Profile id on live ``context.profile_id`` or legacy top-level field."""
        event = event or {}
        context = event.get("context") or {}
        return context.get("profile_id") or event.get("profile_id")

    @classmethod
    def _format_at_time(cls, value):
        """Stringify ``created.at_time`` for Card description Markdown."""
        if value is None:
            return None
        if isinstance(value, datetime):
            if value.tzinfo is not None:
                value = value.astimezone(timezone.utc).replace(tzinfo=None)
            text = value.isoformat()
            if text.endswith("+00:00"):
                return text[:-6] + "Z"
            return text
        return str(value)

    @classmethod
    def _event_description(cls, event_type, display_name, at_time):
        """Markdown body: event type, Profile display_name, and created.at_time."""
        lines = []
        if event_type:
            lines.append(str(event_type))
        if display_name:
            lines.append(str(display_name))
        formatted = cls._format_at_time(at_time)
        if formatted:
            lines.append(formatted)
        if not lines:
            return None
        return "\n\n".join(lines)

    @classmethod
    def _enrich_events(cls, events):
        """Copy each Event and set Card description from type, name, and time."""
        events = events or []
        names = ProfileService.display_names_for_ids(
            [cls._event_profile_id(event) for event in events]
        )
        enriched = []
        for event in events:
            source = dict(event)
            profile_id = cls._event_profile_id(event)
            display_name = (
                names.get(str(profile_id)) if profile_id is not None else None
            )
            created = event.get("created") or {}
            description = cls._event_description(
                event.get("type"), display_name, created.get("at_time")
            )
            if description:
                source["description"] = description
            enriched.append(source)
        return enriched

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
        return CardService.project_all(
            CARD_TYPE_EVENTS, cls._enrich_events(events), token=token
        )
