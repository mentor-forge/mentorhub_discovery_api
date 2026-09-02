"""
Discovery Journey service.

Discovery **consumes** Journey for Member card progress counts. The shared
consume surface is inherited unchanged. `resource_counts_for_profile` reads
the active Journey for an already-authorized Member Profile via MongoIO and
does **not** call shared `get_journey_progress` (mentor/admin outbound).
"""

import logging

from api_utils import Config, MongoIO
from api_utils.mongo_utils import encode_document
from api_utils.services import JourneyService as SharedJourneyService
from api_utils.services.journey_service import JOURNEY_ID_PROPERTIES

logger = logging.getLogger(__name__)

_ZERO_COUNTS = {"library": 0, "now": 0, "next": 0}


class JourneyService(SharedJourneyService):
    """Discovery subclass of the shared Journey service (consume only)."""

    @classmethod
    def resource_counts_for_profile(cls, profile_id, token, breadcrumb):
        """
        Count Library / Now / Next resources on the active Journey for a profile.

        Uses the same arithmetic as shared ``get_journey_progress`` (``library``
        and ``now`` are ``len`` of those arrays; ``next`` sums ``resources``
        across Next topics) but skips shared outbound RBAC. Callers must already
        have this Profile on the Member home section.

        Args:
            profile_id: Profile ``_id`` to match on Journey ``profile_id``
            token: Authentication token
            breadcrumb: Audit breadcrumb

        Returns:
            dict: ``{"library": int, "now": int, "next": int}``; zeros when
            there is no matching active Journey
        """
        if not profile_id:
            return dict(_ZERO_COUNTS)

        mongo = MongoIO.get_instance()
        config = Config.get_instance()
        match = {"profile_id": profile_id, "status": "active"}
        encode_document(match, JOURNEY_ID_PROPERTIES, [])
        journeys = mongo.get_documents(
            config.JOURNEY_COLLECTION_NAME,
            match=match,
        )
        if not journeys:
            return dict(_ZERO_COUNTS)

        journey = journeys[0]
        next_resources = sum(
            len(topic.get("resources") or []) for topic in (journey.get("next") or [])
        )
        counts = {
            "library": len(journey.get("library") or []),
            "now": len(journey.get("now") or []),
            "next": next_resources,
        }
        logger.info(
            f"Journey resource counts for profile {profile_id} "
            f"for user {token.get('user_id')}: {counts}"
        )
        return counts
