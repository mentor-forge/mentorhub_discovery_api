"""
Discovery Card projection and orchestration service.

`Card` is a configurator-only projection schema (`Card.yaml`, version
`0.0.0.0`) rather than a persisted MongoDB collection: Discovery projects
source documents onto the Card shape and assembles the composite home list.

Source reads go through the local Notification and Profile services, or through
`execute_list_query` for the Customer and Setting collections that have no
shared service class. Ids stay as `ObjectId` on the way out; the Flask
`MongoJSONEncoder` decodes them at the serialization boundary.
"""

import logging

from api_utils import Config
from api_utils.flask_utils.exceptions import HTTPBadRequest
from api_utils.mongo_utils import encode_document
from api_utils.mongo_utils.list_query import (
    DEFAULT_OFFSET,
    DEFAULT_SIZE,
    MAX_SIZE,
    build_sort_by,
    execute_list_query,
    validate_pagination,
)
from api_utils.services.profile_service import PROFILE_LIST_ORDER
from api_utils.services.rbac import EMPTY_SCOPE_MATCH, build_outbound_match

from src.services.notification_service import NotificationService
from src.services.profile_service import ProfileService, mentor_scope_id

logger = logging.getLogger(__name__)

ARCHIVED_STATUS = "archived"
CARD_DESCRIPTION_MAX_LENGTH = 4096
CARD_NOTES_EMPTY = "*No notes*"

CARD_TYPE_CUSTOMER = "customer"
CARD_TYPE_EVENT = "event"
CARD_TYPE_EVENTS = "events"
CARD_TYPE_MEMBER = "member"
CARD_TYPE_MEMBERS = "members"
CARD_TYPE_MENTEE = "mentee"
CARD_TYPE_MENTEES = "mentees"
CARD_TYPE_NOTIFICATION = "notification"
CARD_TYPE_NOTIFICATIONS = "notifications"
CARD_TYPE_PATHS = "paths"
CARD_TYPE_PLANS = "plans"
CARD_TYPE_RESOURCES = "resources"

# Card field -> ordered source field candidates; the first present value wins.
_NAMED_FIELDS = {"name": ("name",), "description": ("description",)}
_PROFILE_FIELDS = {"name": ("full_name", "name"), "description": ("description",)}
_NOTIFICATION_FIELDS = {"name": ("name",), "description": ("message",)}
_EVENT_FIELDS = {"name": ("type",), "description": ("description",)}

# `type` is optional in the Card schema. Mongo-backed projections stamp the
# enum value from this table; home synthetics (Products, Discounts, Logs,
# Journey) are built by `_synthetic_card` instead.
CARD_TYPE_SPECS = {
    CARD_TYPE_CUSTOMER: {"type": "Customer", "fields": _NAMED_FIELDS},
    CARD_TYPE_EVENT: {"type": "Event", "fields": _EVENT_FIELDS},
    CARD_TYPE_EVENTS: {"type": "Event", "fields": _EVENT_FIELDS},
    CARD_TYPE_MEMBER: {"type": "Member", "fields": _PROFILE_FIELDS},
    CARD_TYPE_MEMBERS: {"type": "Member", "fields": _PROFILE_FIELDS},
    CARD_TYPE_MENTEE: {"type": "Mentee", "fields": _PROFILE_FIELDS},
    CARD_TYPE_MENTEES: {"type": "Mentee", "fields": _PROFILE_FIELDS},
    CARD_TYPE_NOTIFICATION: {"type": "Notification", "fields": _NOTIFICATION_FIELDS},
    CARD_TYPE_NOTIFICATIONS: {"type": "Notification", "fields": _NOTIFICATION_FIELDS},
    CARD_TYPE_PATHS: {"type": "Path", "fields": _NAMED_FIELDS},
    CARD_TYPE_PLANS: {"type": "Plan", "fields": _NAMED_FIELDS},
    CARD_TYPE_RESOURCES: {"type": "Resource", "fields": _NAMED_FIELDS},
}


class CardService:
    """
    Projection and orchestration layer for Discovery Card lists.

    Handles:
    - Projecting a source document onto the Card schema
    - Assembling the composite home Card list from the local services
    """

    @classmethod
    def _synthetic_card(cls, name, description, card_type, link):
        """Build a non-persisted home Card (no `_id`)."""
        return {
            "name": name,
            "description": description,
            "type": card_type,
            "link": link,
        }

    @classmethod
    def project(cls, card_type, document, token=None):
        """
        Project a source document onto the Card schema.

        Only Card properties are emitted (`additionalProperties: false`), and a
        property whose source value is absent is omitted rather than set to
        null. `_id` is the source document id, passed through unchanged.

        Args:
            card_type: One of the keys in CARD_TYPE_SPECS
            document: The source document to project
            token: Authentication token dictionary (optional)

        Returns:
            dict: The Card projection

        Raises:
            HTTPBadRequest: If card_type is not a known Card source
        """
        spec = CARD_TYPE_SPECS.get(card_type)
        if spec is None:
            raise HTTPBadRequest(f"Unsupported card type: {card_type}")

        source = document or {}
        card = {}

        if source.get("_id") is not None:
            card["_id"] = source["_id"]

        for card_field, candidates in spec["fields"].items():
            for candidate in candidates:
                value = source.get(candidate)
                if value is not None:
                    card[card_field] = value
                    break

        if spec["type"] is not None:
            card["type"] = spec["type"]

        token_dict = token or {}
        roles = token_dict.get("roles") or []
        config = Config.get_instance()
        doc_id = source.get("_id")
        id_str = str(doc_id) if doc_id is not None else None

        if id_str is not None:
            if card_type in (CARD_TYPE_NOTIFICATION, CARD_TYPE_NOTIFICATIONS):
                card["link"] = f"discovery/notification/{id_str}"
            elif card_type in (CARD_TYPE_MEMBER, CARD_TYPE_MEMBERS):
                card["link"] = f"customer/profile/{id_str}"
            elif card_type in (CARD_TYPE_MENTEE, CARD_TYPE_MENTEES):
                card["link"] = f"mentor/mentee/{id_str}"
            elif card_type in (CARD_TYPE_EVENT, CARD_TYPE_EVENTS):
                card["link"] = f"mentee/event/{id_str}"
            elif card_type == CARD_TYPE_CUSTOMER:
                card["link"] = f"customer/customer/{id_str}"
            elif card_type == CARD_TYPE_RESOURCES:
                prefix = "mentor" if config.ROLE_MENTOR in roles else "mentee"
                card["link"] = f"{prefix}/resource/{id_str}"
            elif card_type == CARD_TYPE_PATHS:
                prefix = "mentor" if config.ROLE_MENTOR in roles else "mentee"
                card["link"] = f"{prefix}/path/{id_str}"
            elif card_type == CARD_TYPE_PLANS:
                card["link"] = f"mentor/plan/{id_str}"

        return card

    @classmethod
    def project_all(cls, card_type, documents, token=None):
        """
        Project a list of source documents onto the Card schema.

        Args:
            card_type: One of the keys in CARD_TYPE_SPECS
            documents: The source documents to project
            token: Authentication token dictionary (optional)

        Returns:
            list: The Card projections
        """
        return [
            cls.project(card_type, document, token=token)
            for document in documents or []
        ]

    @classmethod
    def _member_description(cls, counts, event_count):
        """Markdown for a Member card: Journey progress plus 30-day activity."""
        from src.services.event_service import CARD_ACTIVITY_WINDOW_DAYS

        counts = counts or {}
        return (
            "**Progress**\n"
            f"- Library: {counts.get('library', 0)}\n"
            f"- Now: {counts.get('now', 0)}\n"
            f"- Next: {counts.get('next', 0)}\n"
            "\n"
            "**Activity**\n"
            f"- {event_count} events in the last {CARD_ACTIVITY_WINDOW_DAYS} days"
        )

    @classmethod
    def _mentee_description(cls, event_count, notes):
        """Markdown for a Mentee card: 30-day activity plus the caller's notes."""
        from src.services.event_service import CARD_ACTIVITY_WINDOW_DAYS

        header = (
            "**Activity**\n"
            f"- {event_count} events in the last {CARD_ACTIVITY_WINDOW_DAYS} days\n"
            "\n"
            "**Notes**\n"
        )
        bodies = []
        for note in notes or []:
            text = note.get("note")
            if not text:
                continue
            bodies.append(" ".join(str(text).split()))
        if not bodies:
            return header + f"- {CARD_NOTES_EMPTY}"

        lines = []
        for body in bodies:
            prefix = "- "
            joiner = "\n" if lines else ""
            available = (
                CARD_DESCRIPTION_MAX_LENGTH
                - len(header)
                - len("\n".join(lines))
                - len(joiner)
                - len(prefix)
            )
            if available <= 0:
                break
            if len(body) > available:
                body = body[:available]
            if not body:
                break
            lines.append(prefix + body)
        if not lines:
            return header + f"- {CARD_NOTES_EMPTY}"
        return (header + "\n".join(lines))[:CARD_DESCRIPTION_MAX_LENGTH]

    @classmethod
    def _project_member_cards(cls, members, token, breadcrumb):
        """Copy each Member Profile, set Markdown description, then project."""
        from src.services.event_service import EventService
        from src.services.journey_service import JourneyService

        cards = []
        for member in members or []:
            source = dict(member)
            profile_id = source.get("_id")
            counts = JourneyService.resource_counts_for_profile(
                profile_id, token, breadcrumb
            )
            event_count = EventService.recent_event_count_for_profile(
                profile_id, token, breadcrumb
            )
            source["description"] = cls._member_description(counts, event_count)
            cards.append(cls.project(CARD_TYPE_MEMBERS, source, token=token))
        return cards

    @classmethod
    def _project_mentee_cards(cls, mentees, token, breadcrumb):
        """Copy each Mentee Profile, set Markdown description, then project."""
        from src.services.event_service import EventService
        from src.services.note_service import NoteService

        cards = []
        for mentee in mentees or []:
            source = dict(mentee)
            profile_id = source.get("_id")
            event_count = EventService.recent_event_count_for_profile(
                profile_id, token, breadcrumb
            )
            notes = NoteService.notes_for_profile(profile_id, token, breadcrumb)
            source["description"] = cls._mentee_description(event_count, notes)
            cards.append(cls.project(CARD_TYPE_MENTEES, source, token=token))
        return cards

    @classmethod
    def _customer_home_card(cls, token, breadcrumb):
        """Fetch the caller's Customer document and project it as a Customer card."""
        config = Config.get_instance()
        customer_id = token.get("customer_id")
        if not customer_id:
            return None
        match = cls._customer_match(token)
        customers = execute_list_query(
            config.CUSTOMER_COLLECTION_NAME,
            match=match,
            sort_by=[("name", 1)],
            offset=0,
            size=1,
        )
        if customers:
            return cls.project(CARD_TYPE_CUSTOMER, customers[0], token=token)
        return None

    @classmethod
    def get_home_cards(
        cls, token, breadcrumb, offset=DEFAULT_OFFSET, size=DEFAULT_SIZE
    ):
        """
        Build the composite home Card list for the caller.

        Sections are assembled in the documented order:
        1. Active Notifications for token `profile_id` (newest created first)
        2. Admin synthetic: Products
        3. Admin synthetic: Discounts
        4. Admin synthetic: Logs
        5. Customer singleton for token `customer_id` (Customer role only)
        6. Members for token `customer_id` (Customer or Coordinator roles only, newest saved first)
        7. Mentees for token `mentor_id` or `profile_id` (Mentor role only, newest saved first)
        8. Mentee synthetic: Learning Journey

        `offset`/`size` apply to the combined list.

        Args:
            token: Authentication token
            breadcrumb: Audit breadcrumb
            offset: Zero-based start index into the combined list
            size: Number of cards to return

        Returns:
            list: Card projections for the requested page
        """
        validate_pagination(offset, size)

        config = Config.get_instance()
        roles = token.get("roles") or []
        section_size = min(offset + size, MAX_SIZE)

        cards = []

        # 1. Active Notifications for token profile_id
        profile_id = token.get("profile_id")
        if profile_id:
            notifications = NotificationService.get_active_notifications(
                token,
                breadcrumb,
                offset=0,
                size=section_size,
                match={"profile_id": profile_id},
            )
            cards.extend(
                cls.project_all(
                    CARD_TYPE_NOTIFICATIONS,
                    notifications,
                    token=token,
                )
            )

        # 2-4. Admin synthetic cards
        if config.ROLE_ADMIN in roles:
            cards.append(
                cls._synthetic_card(
                    "Products",
                    "Manage subscription products",
                    "Products",
                    "admin/settings",
                )
            )
            cards.append(
                cls._synthetic_card(
                    "Discounts",
                    "Manage discount codes",
                    "Discounts",
                    "admin/settings?tab=discounts",
                )
            )
            cards.append(
                cls._synthetic_card(
                    "Logs",
                    "View system logs",
                    "Logs",
                    "admin/logs",
                )
            )

        # 5. Customer card for token customer_id
        if config.ROLE_CUSTOMER in roles and token.get("customer_id"):
            customer_card = cls._customer_home_card(token, breadcrumb)
            if customer_card:
                cards.append(customer_card)

        # 6. Member cards for Profiles with token customer_id, saved.at_time desc
        is_member_reader = (
            config.ROLE_CUSTOMER in roles or config.ROLE_COORDINATOR in roles
        )
        if token.get("customer_id") and is_member_reader:
            saved_desc = build_sort_by("saved.at_time", "desc", PROFILE_LIST_ORDER)
            members = ProfileService.get_member_profiles(
                token,
                breadcrumb,
                offset=0,
                size=section_size,
                sort_by=saved_desc,
            )
            cards.extend(cls._project_member_cards(members, token, breadcrumb))

        # 7. Mentee cards for Profiles with token mentor_id or profile_id, saved.at_time desc
        if config.ROLE_MENTOR in roles and mentor_scope_id(token):
            saved_desc = build_sort_by("saved.at_time", "desc", PROFILE_LIST_ORDER)
            mentees = ProfileService.get_mentee_profiles(
                token,
                breadcrumb,
                offset=0,
                size=section_size,
                sort_by=saved_desc,
            )
            cards.extend(cls._project_mentee_cards(mentees, token, breadcrumb))

        # 8. Mentee synthetic card (Learning Journey)
        if config.ROLE_MENTEE in roles:
            cards.append(
                cls._synthetic_card(
                    "Learning Journey",
                    "Continue your learning journey",
                    "Journey",
                    "mentee/journey",
                )
            )

        page = cards[offset : offset + size]
        logger.info(
            f"Assembled {len(page)} home cards from {len(cards)} sourced cards "
            f"(offset={offset}, size={size}) for user {token.get('user_id')}"
        )
        return page

    @classmethod
    def _customer_match(cls, token):
        """Outbound scope for Customer: the caller's own customer, not archived."""
        customer_id = token.get("customer_id")
        if customer_id:
            identity = {"_id": customer_id}
            encode_document(identity, ["_id"], [])
        else:
            identity = EMPTY_SCOPE_MATCH
        return build_outbound_match(
            token, [{"status": {"$ne": ARCHIVED_STATUS}}, identity]
        )
