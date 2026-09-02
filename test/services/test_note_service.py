"""
Unit tests for Discovery NoteService mentee notes.

`notes_for_profile` matches Notes whose subject is the mentee `profile_id`,
prefers the caller's `created.by_user` when `token.user_id` is present, and
returns an empty list when none match. Shared `get_notes_for_resource` is
not used.
"""

import unittest
from unittest.mock import MagicMock, patch

from bson import ObjectId

from src.services.note_service import NOTE_CARD_LIMIT, NoteService

PROFILE_ID = ObjectId("507f1f77bcf86cd799439011")
USER_ID = "mentor-user"

BREADCRUMB = {
    "from_ip": "127.0.0.1",
    "by_user": USER_ID,
    "at_time": "2026-08-23T12:00:00",
    "correlation_id": "test-correlation",
}

TOKEN = {
    "user_id": USER_ID,
    "roles": ["mentor"],
    "profile_id": "665f1c2a9b1e4c0a1b2c3d04",
}


class TestNotesForProfile(unittest.TestCase):
    """Mentee notes filtered to the caller when created.by_user exists."""

    def setUp(self):
        self.config = MagicMock()
        self.config.NOTE_COLLECTION_NAME = "Note"

        config_patcher = patch(
            "src.services.note_service.Config.get_instance",
            return_value=self.config,
        )
        query_patcher = patch("src.services.note_service.execute_list_query")

        self.addCleanup(config_patcher.stop)
        self.addCleanup(query_patcher.stop)

        config_patcher.start()
        self.mock_query = query_patcher.start()
        self.mock_query.return_value = []

    def test_filters_to_caller_user_id_and_encoded_profile(self):
        notes = [{"_id": ObjectId(), "note": "Keep going", "profile_id": PROFILE_ID}]
        self.mock_query.return_value = notes

        result = NoteService.notes_for_profile(PROFILE_ID, TOKEN, BREADCRUMB)

        self.assertEqual(result, notes)
        self.mock_query.assert_called_once()
        args, kwargs = self.mock_query.call_args
        self.assertEqual(args[0], "Note")
        self.assertEqual(kwargs["match"]["profile_id"], PROFILE_ID)
        self.assertEqual(kwargs["match"]["created.by_user"], USER_ID)
        self.assertEqual(kwargs["match"]["status"], {"$ne": "archived"})
        self.assertEqual(kwargs["sort_by"], [("created.at_time", -1), ("_id", -1)])
        self.assertEqual(kwargs["offset"], 0)
        self.assertEqual(kwargs["size"], NOTE_CARD_LIMIT)

    def test_encodes_string_profile_id(self):
        NoteService.notes_for_profile(str(PROFILE_ID), TOKEN, BREADCRUMB)

        _, kwargs = self.mock_query.call_args
        self.assertEqual(kwargs["match"]["profile_id"], PROFILE_ID)

    def test_empty_list_when_none_match(self):
        self.mock_query.return_value = []

        result = NoteService.notes_for_profile(PROFILE_ID, TOKEN, BREADCRUMB)

        self.assertEqual(result, [])

    def test_empty_profile_id_returns_empty_without_io(self):
        result = NoteService.notes_for_profile(None, TOKEN, BREADCRUMB)

        self.assertEqual(result, [])
        self.mock_query.assert_not_called()

    def test_omits_by_user_when_token_has_no_user_id(self):
        token = {"roles": ["mentor"]}

        NoteService.notes_for_profile(PROFILE_ID, token, BREADCRUMB)

        _, kwargs = self.mock_query.call_args
        self.assertNotIn("created.by_user", kwargs["match"])
        self.assertEqual(kwargs["match"]["profile_id"], PROFILE_ID)

    @patch("api_utils.services.note_service.NoteService.get_notes_for_resource")
    def test_does_not_use_shared_resource_notes(self, mock_shared):
        NoteService.notes_for_profile(PROFILE_ID, TOKEN, BREADCRUMB)

        mock_shared.assert_not_called()


if __name__ == "__main__":
    unittest.main()
