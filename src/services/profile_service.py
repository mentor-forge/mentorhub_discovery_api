"""
Discovery Profile service.

Discovery **consumes** Profile: the shared consume surface (get-by-token,
get-by-id, paginated list) is inherited unchanged. The Discovery-only additions
are the identity-scoped Member and Mentee lists that back the composite home
Card endpoints.
"""

import logging

from api_utils import Config
from api_utils.mongo_utils import encode_document
from api_utils.mongo_utils.list_query import (
    DEFAULT_OFFSET,
    DEFAULT_SIZE,
    and_match,
    build_match_filter,
    build_sort_by,
    execute_list_query,
)
from api_utils.services import ProfileService as SharedProfileService
from api_utils.services.profile_service import (
    ARCHIVED_STATUS,
    DATE_PROPERTIES,
    ID_PROPERTIES,
    PROFILE_LIST_FILTERS,
    PROFILE_LIST_ORDER,
)

logger = logging.getLogger(__name__)


def mentor_scope_id(token):
    """The caller's Profile ``_id`` used to find Mentee Profiles.

    Developer Edition ``login.html`` / ``welcome-auth.js`` mint mentor JWTs
    with ``roles`` containing ``mentor``, ``profile_id`` set to the mentor's
    Profile ``_id``, and ``mentor_id`` empty. Seed mentee Profiles store that
    same id on ``mentor_id``. The ``mentor_id`` *claim* is the caller's mentor
    (used on mentee tokens) and must not scope this list.
    """
    token = token or {}
    return token.get("profile_id") or None


# `card_service` imports this module to assemble the composite home list, so the
# two helpers below import CardService at call time rather than at module scope.


def _member_cards(profiles, token=None):
    """Project Profile documents onto Member Cards."""
    from src.services.card_service import CARD_TYPE_MEMBERS, CardService

    return CardService.project_all(CARD_TYPE_MEMBERS, profiles, token=token)


def _mentee_cards(profiles, token=None):
    """Project Profile documents onto Mentee Cards."""
    from src.services.card_service import CARD_TYPE_MENTEES, CardService

    return CardService.project_all(CARD_TYPE_MENTEES, profiles, token=token)


class ProfileService(SharedProfileService):
    """
    Discovery subclass of the shared Profile service (consume only).

    Adds the two token-scoped lists the Card layer projects onto Member and
    Mentee cards. Both AND their identity scope onto the shared outbound match,
    so an out-of-scope or archived Profile stays hidden.
    """

    @classmethod
    def _scoped_profiles(
        cls,
        token,
        breadcrumb,
        scope_field,
        scope_value,
        offset,
        size,
        filters,
        sort_by,
    ):
        """Run the shared Profile list with an extra identity scope AND'd on."""
        cls._check_permission(token, "read")

        if not scope_value:
            return []

        scope = {scope_field: scope_value}
        encode_document(scope, ID_PROPERTIES, DATE_PROPERTIES)

        match = and_match(
            build_match_filter(
                cls._outbound_match(token), filters or {}, PROFILE_LIST_FILTERS
            ),
            scope,
        )
        if sort_by is None:
            default = PROFILE_LIST_ORDER["default"]
            sort_by = build_sort_by(
                default["field"], default["order"], PROFILE_LIST_ORDER
            )

        config = Config.get_instance()
        profiles = execute_list_query(
            config.PROFILE_COLLECTION_NAME,
            match=match,
            sort_by=sort_by,
            offset=offset,
            size=size,
        )

        logger.info(
            f"Retrieved {len(profiles)} profiles scoped by {scope_field} "
            f"for user {token.get('user_id')}"
        )
        return profiles

    @classmethod
    def get_member_profiles(
        cls,
        token,
        breadcrumb,
        offset=DEFAULT_OFFSET,
        size=DEFAULT_SIZE,
        filters=None,
        sort_by=None,
    ):
        """
        Get the Profiles belonging to the token `customer_id`.

        Returns an empty list when the token carries no `customer_id`. Role
        gating for the composite home list lives on CardService.

        Args:
            token: Authentication token
            breadcrumb: Audit breadcrumb
            offset: Zero-based start index
            size: Number of documents to return
            filters: Parsed filter dict from parse_filter_params
            sort_by: PyMongo sort list from build_sort_by; default name asc

        Returns:
            list: Profile documents for the caller's customer
        """
        return cls._scoped_profiles(
            token,
            breadcrumb,
            "customer_id",
            token.get("customer_id"),
            offset,
            size,
            filters,
            sort_by,
        )

    @classmethod
    def get_mentee_profiles(
        cls,
        token,
        breadcrumb,
        offset=DEFAULT_OFFSET,
        size=DEFAULT_SIZE,
        filters=None,
        sort_by=None,
    ):
        """
        Get Profiles whose ``mentor_id`` equals the token ``profile_id``.

        This is the Mentor home list: login.html mentor personas (Marti,
        Paula, Elon, Danny, Melinda) carry ``profile_id`` and an empty
        ``mentor_id`` claim. Do not AND shared Profile identity ``$or`` —
        that clause uses the ``mentor_id`` *claim* and would miss mentees.

        Archived Profiles stay hidden. Role gating lives on CardService.

        Args:
            token: Authentication token
            breadcrumb: Audit breadcrumb
            offset: Zero-based start index
            size: Number of documents to return
            filters: Parsed filter dict from parse_filter_params
            sort_by: PyMongo sort list from build_sort_by; default name asc

        Returns:
            list: Profile documents for the caller's mentees
        """
        cls._check_permission(token, "read")

        profile_id = mentor_scope_id(token)
        if not profile_id:
            return []

        scope = {"mentor_id": profile_id}
        encode_document(scope, ID_PROPERTIES, DATE_PROPERTIES)

        match = and_match(
            build_match_filter(
                {"status": {"$ne": ARCHIVED_STATUS}},
                filters or {},
                PROFILE_LIST_FILTERS,
            ),
            scope,
        )
        if sort_by is None:
            default = PROFILE_LIST_ORDER["default"]
            sort_by = build_sort_by(
                default["field"], default["order"], PROFILE_LIST_ORDER
            )

        config = Config.get_instance()
        profiles = execute_list_query(
            config.PROFILE_COLLECTION_NAME,
            match=match,
            sort_by=sort_by,
            offset=offset,
            size=size,
        )

        logger.info(
            f"Retrieved {len(profiles)} mentee profiles for mentor "
            f"{profile_id} user {token.get('user_id')}"
        )
        return profiles
