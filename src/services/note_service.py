"""
Discovery Note service.

Discovery **consumes** Note for Mentee card markdown. The shared
resource-scoped list is inherited unchanged and must **not** be used for
mentee notes (`get_notes_for_resource` is own-profile outbound).
`notes_for_profile` reads Notes whose subject is an already-authorized
Mentee Profile via MongoIO.
"""

import logging

from api_utils import Config
from api_utils.mongo_utils import encode_document
from api_utils.mongo_utils.list_query import build_sort_by, execute_list_query
from api_utils.services import NoteService as SharedNoteService
from api_utils.services.note_service import (
    ARCHIVED_STATUS,
    NOTE_ID_PROPERTIES,
    NOTE_LIST_ORDER,
)

logger = logging.getLogger(__name__)

NOTE_CARD_LIMIT = 3


class NoteService(SharedNoteService):
    """Discovery subclass of the shared Note service (consume only)."""

    @classmethod
    def notes_for_profile(cls, profile_id, token, breadcrumb):
        """
        Return the caller's newest notes whose subject is the mentee profile.

        Matches live ``Note.yaml``: ``profile_id`` is the subject Profile,
        ``note`` is the body, ``created.by_user`` is the author. When the
        token carries ``user_id``, AND it with ``created.by_user`` so the
        card shows the caller's notes on that Mentee. Newest
        ``created.at_time`` first, capped at ``NOTE_CARD_LIMIT``.

        Args:
            profile_id: Mentee Profile ``_id``
            token: Authentication token
            breadcrumb: Audit breadcrumb

        Returns:
            list: Note documents, or an empty list when none match
        """
        if not profile_id:
            return []

        match = {
            "profile_id": profile_id,
            "status": {"$ne": ARCHIVED_STATUS},
        }
        encode_document(match, NOTE_ID_PROPERTIES, [])

        user_id = (token or {}).get("user_id")
        if user_id:
            match["created.by_user"] = user_id

        default = NOTE_LIST_ORDER["default"]
        sort_by = build_sort_by(default["field"], default["order"], NOTE_LIST_ORDER)

        config = Config.get_instance()
        notes = execute_list_query(
            config.NOTE_COLLECTION_NAME,
            match=match,
            sort_by=sort_by,
            offset=0,
            size=NOTE_CARD_LIMIT,
        )
        logger.info(
            f"Retrieved {len(notes)} notes for profile {profile_id} "
            f"for user {token.get('user_id')}"
        )
        return notes
