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

# `type` is optional in the Card schema and its enum is
# Event | Member | Mentee | Notification | Path | Plan | Resource. Customer
# source has no enum value, so its card omits `type` rather than emit a value
# the schema rejects.
CARD_TYPE_SPECS = {
    CARD_TYPE_CUSTOMER: {"type": None, "fields": _NAMED_FIELDS},
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
    def project(cls, card_type, document, token=None, *, notification_link=False):
        """
        Project a source document onto the Card schema.

        Only Card properties are emitted (`additionalProperties: false`), and a
        property whose source value is absent is omitted rather than set to
        null. `_id` is the source document id, passed through unchanged.

        Args:
            card_type: One of the keys in CARD_TYPE_SPECS
            document: The source document to project
            token: Authentication token dictionary (optional)
            notification_link: Whether to emit link for Notification cards

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
                if notification_link:
                    card["link"] = f"discovery/notification/{id_str}"
            elif card_type in (CARD_TYPE_MEMBER, CARD_TYPE_MEMBERS):
                card["link"] = f"customer/profile/{id_str}"
            elif card_type in (CARD_TYPE_MENTEE, CARD_TYPE_MENTEES):
                card["link"] = f"mentee/mentee/{id_str}"
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
    def project_all(cls, card_type, documents, token=None, *, notification_link=False):
        """
        Project a list of source documents onto the Card schema.

        Args:
            card_type: One of the keys in CARD_TYPE_SPECS
            documents: The source documents to project
            token: Authentication token dictionary (optional)
            notification_link: Whether to emit link for Notification cards

        Returns:
            list: The Card projections
        """
        return [
            cls.project(
                card_type,
                document,
                token=token,
                notification_link=notification_link,
            )
            for document in documents or []
        ]

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
                    notification_link=False,
                )
            )

        # 2-4. Admin synthetic cards
        if config.ROLE_ADMIN in roles:
            cards.append(
                {
                    "name": "Products",
                    "description": "Manage subscription products",
                    "link": "admin/products",
                }
            )
            cards.append(
                {
                    "name": "Discounts",
                    "description": "Manage discount codes",
                    "link": "admin/discounts",
                }
            )
            cards.append(
                {
                    "name": "Logs",
                    "description": "View system logs",
                    "link": "admin/logs",
                }
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
            cards.extend(cls.project_all(CARD_TYPE_MEMBERS, members, token=token))

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
            cards.extend(cls.project_all(CARD_TYPE_MENTEES, mentees, token=token))

        # 8. Mentee synthetic card (Learning Journey)
        if config.ROLE_MENTEE in roles:
            cards.append(
                {
                    "name": "Learning Journey",
                    "description": "Continue your learning journey",
                    "link": "mentee/journey",
                }
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
