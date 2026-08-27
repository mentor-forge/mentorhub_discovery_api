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
    and_match,
    build_match_filter,
    build_sort_by,
    execute_list_query,
    validate_pagination,
)
from api_utils.services.profile_service import PROFILE_LIST_ORDER
from api_utils.services.rbac import EMPTY_SCOPE_MATCH, build_outbound_match

from src.services.notification_service import NotificationService
from src.services.profile_service import ProfileService

logger = logging.getLogger(__name__)

ARCHIVED_STATUS = "archived"

# Setting is a polymorphic bag; `type` selects the Product catalog variant.
SETTING_TYPE_PRODUCT = "Product"

CARD_TYPE_CUSTOMER = "customer"
CARD_TYPE_MEMBER = "member"
CARD_TYPE_MEMBERS = "members"
CARD_TYPE_MENTEE = "mentee"
CARD_TYPE_MENTEES = "mentees"
CARD_TYPE_NOTIFICATION = "notification"
CARD_TYPE_NOTIFICATIONS = "notifications"
CARD_TYPE_PATHS = "paths"
CARD_TYPE_PLANS = "plans"
CARD_TYPE_PRODUCTS = "products"
CARD_TYPE_RESOURCES = "resources"
CARD_TYPE_SETTINGS = "settings"

# Card field -> ordered source field candidates; the first present value wins.
_NAMED_FIELDS = {"name": ("name",), "description": ("description",)}
_PROFILE_FIELDS = {"name": ("full_name", "name"), "description": ("description",)}
_NOTIFICATION_FIELDS = {"name": ("name",), "description": ("message",)}

# `type` is optional in the Card schema and its enum is
# Event | Member | Mentee | Notification | Path | Plan | Resource. Customer,
# Product, and Setting sources have no enum value, so their cards omit `type`
# rather than emit a value the schema rejects.
CARD_TYPE_SPECS = {
    CARD_TYPE_CUSTOMER: {"type": None, "fields": _NAMED_FIELDS},
    CARD_TYPE_MEMBER: {"type": "Member", "fields": _PROFILE_FIELDS},
    CARD_TYPE_MEMBERS: {"type": "Member", "fields": _PROFILE_FIELDS},
    CARD_TYPE_MENTEE: {"type": "Mentee", "fields": _PROFILE_FIELDS},
    CARD_TYPE_MENTEES: {"type": "Mentee", "fields": _PROFILE_FIELDS},
    CARD_TYPE_NOTIFICATION: {"type": "Notification", "fields": _NOTIFICATION_FIELDS},
    CARD_TYPE_NOTIFICATIONS: {"type": "Notification", "fields": _NOTIFICATION_FIELDS},
    CARD_TYPE_PATHS: {"type": "Path", "fields": _NAMED_FIELDS},
    CARD_TYPE_PLANS: {"type": "Plan", "fields": _NAMED_FIELDS},
    CARD_TYPE_PRODUCTS: {"type": None, "fields": _NAMED_FIELDS},
    CARD_TYPE_RESOURCES: {"type": "Resource", "fields": _NAMED_FIELDS},
    CARD_TYPE_SETTINGS: {"type": None, "fields": _NAMED_FIELDS},
}

# Filter and order specs for the collections with no shared service class.
NAME_LIST_FILTERS = {"name": {"type": "contains", "field": "name"}}
NAME_LIST_ORDER = {
    "default": {"field": "name", "order": "asc"},
    "allowed": {"name": ("asc", "desc")},
}

CUSTOMER_LIST_FILTERS = NAME_LIST_FILTERS
CUSTOMER_LIST_ORDER = NAME_LIST_ORDER
PRODUCT_LIST_FILTERS = NAME_LIST_FILTERS
PRODUCT_LIST_ORDER = NAME_LIST_ORDER
SETTING_LIST_FILTERS = NAME_LIST_FILTERS
SETTING_LIST_ORDER = NAME_LIST_ORDER


class CardService:
    """
    Projection and orchestration layer for Discovery Card lists.

    Handles:
    - Projecting a source document onto the Card schema
    - Assembling the composite home Card list from the local services
    - Typed Card lists for Customer, Product, and Setting, which have no
      shared service class of their own
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
        7. Mentees for token `mentor_id` (Mentor role only, newest saved first)
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

        # 7. Mentee cards for Profiles with token mentor_id, saved.at_time desc
        if token.get("mentor_id") and config.ROLE_MENTOR in roles:
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

    @classmethod
    def _setting_match(cls, token):
        """Outbound scope for Setting: catalog consume, nothing archived."""
        return build_outbound_match(token, [{"status": {"$ne": ARCHIVED_STATUS}}])

    @classmethod
    def _list_cards(
        cls, card_type, collection_name, match, order_spec, offset, size, sort_by
    ):
        if sort_by is None:
            default = order_spec["default"]
            sort_by = build_sort_by(default["field"], default["order"], order_spec)

        documents = execute_list_query(
            collection_name,
            match=match,
            sort_by=sort_by,
            offset=offset,
            size=size,
        )
        return cls.project_all(card_type, documents)

    @classmethod
    def get_customer_cards(
        cls,
        token,
        breadcrumb,
        offset=DEFAULT_OFFSET,
        size=DEFAULT_SIZE,
        filters=None,
        sort_by=None,
    ):
        """
        Get Customer Cards visible to the caller.

        Args:
            token: Authentication token
            breadcrumb: Audit breadcrumb
            offset: Zero-based start index
            size: Number of cards to return
            filters: Parsed filter dict from parse_filter_params
            sort_by: PyMongo sort list from build_sort_by; default name asc

        Returns:
            list: Card projections of Customer documents
        """
        config = Config.get_instance()
        match = build_match_filter(
            cls._customer_match(token), filters or {}, CUSTOMER_LIST_FILTERS
        )
        return cls._list_cards(
            CARD_TYPE_CUSTOMER,
            config.CUSTOMER_COLLECTION_NAME,
            match,
            CUSTOMER_LIST_ORDER,
            offset,
            size,
            sort_by,
        )

    @classmethod
    def get_product_cards(
        cls,
        token,
        breadcrumb,
        offset=DEFAULT_OFFSET,
        size=DEFAULT_SIZE,
        filters=None,
        sort_by=None,
    ):
        """
        Get Product Cards visible to the caller.

        Product is not a collection of its own: it is the `Product` variant of
        the polymorphic Setting collection, so the discriminator is AND'd on
        outside the outbound match (an admin's unrestricted scope must still
        exclude Discount rows).

        Args:
            token: Authentication token
            breadcrumb: Audit breadcrumb
            offset: Zero-based start index
            size: Number of cards to return
            filters: Parsed filter dict from parse_filter_params
            sort_by: PyMongo sort list from build_sort_by; default name asc

        Returns:
            list: Card projections of Product Setting documents
        """
        config = Config.get_instance()
        match = and_match(
            {"type": SETTING_TYPE_PRODUCT},
            build_match_filter(
                cls._setting_match(token), filters or {}, PRODUCT_LIST_FILTERS
            ),
        )
        return cls._list_cards(
            CARD_TYPE_PRODUCTS,
            config.SETTING_COLLECTION_NAME,
            match,
            PRODUCT_LIST_ORDER,
            offset,
            size,
            sort_by,
        )

    @classmethod
    def get_settings_cards(
        cls,
        token,
        breadcrumb,
        offset=DEFAULT_OFFSET,
        size=DEFAULT_SIZE,
        filters=None,
        sort_by=None,
    ):
        """
        Get Setting Cards visible to the caller across every Setting variant.

        Args:
            token: Authentication token
            breadcrumb: Audit breadcrumb
            offset: Zero-based start index
            size: Number of cards to return
            filters: Parsed filter dict from parse_filter_params
            sort_by: PyMongo sort list from build_sort_by; default name asc

        Returns:
            list: Card projections of Setting documents
        """
        config = Config.get_instance()
        match = build_match_filter(
            cls._setting_match(token), filters or {}, SETTING_LIST_FILTERS
        )
        return cls._list_cards(
            CARD_TYPE_SETTINGS,
            config.SETTING_COLLECTION_NAME,
            match,
            SETTING_LIST_ORDER,
            offset,
            size,
            sort_by,
        )
