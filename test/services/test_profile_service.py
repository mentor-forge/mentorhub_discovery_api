"""
Unit tests for Discovery ProfileService mentee identity scope.

`get_mentee_profiles` scopes the `mentor_id` match with `mentor_scope_id`:
token `mentor_id` when present, otherwise `profile_id`. The id is encoded
with `encode_document` immediately before MongoIO / `execute_list_query`.
Role gating lives on CardService, not here.
"""

import unittest
from unittest.mock import MagicMock, patch

from bson import ObjectId

from src.services.profile_service import ProfileService, mentor_scope_id

PROFILE_ID = "665f1c2a9b1e4c0a1b2c3d01"
MENTOR_ID = "665f1c2a9b1e4c0a1b2c3d04"

BREADCRUMB = {
    "from_ip": "127.0.0.1",
    "by_user": "test-user",
    "at_time": "2026-08-23T12:00:00",
    "correlation_id": "test-correlation",
}


def token(**claims):
    base = {"user_id": "test-user", "roles": ["mentor"]}
    base.update(claims)
    return base


class TestMentorScopeId(unittest.TestCase):
    """mentor_scope_id prefers mentor_id, then profile_id."""

    def test_mentor_id_wins_over_profile_id(self):
        self.assertEqual(
            mentor_scope_id({"mentor_id": MENTOR_ID, "profile_id": PROFILE_ID}),
            MENTOR_ID,
        )

    def test_falls_back_to_profile_id(self):
        self.assertEqual(mentor_scope_id({"profile_id": PROFILE_ID}), PROFILE_ID)

    def test_missing_both_returns_none(self):
        self.assertIsNone(mentor_scope_id({}))
        self.assertIsNone(mentor_scope_id(None))


class TestGetMenteeProfiles(unittest.TestCase):
    """get_mentee_profiles encodes the resolved scope id into the mentor_id match."""

    def setUp(self):
        self.config = MagicMock()
        self.config.PROFILE_COLLECTION_NAME = "Profile"

        config_patcher = patch(
            "src.services.profile_service.Config.get_instance",
            return_value=self.config,
        )
        query_patcher = patch("src.services.profile_service.execute_list_query")
        outbound_patcher = patch.object(
            ProfileService,
            "_outbound_match",
            return_value={"status": {"$ne": "archived"}},
        )
        permission_patcher = patch.object(ProfileService, "_check_permission")

        self.addCleanup(config_patcher.stop)
        self.addCleanup(query_patcher.stop)
        self.addCleanup(outbound_patcher.stop)
        self.addCleanup(permission_patcher.stop)

        config_patcher.start()
        self.mock_query = query_patcher.start()
        outbound_patcher.start()
        permission_patcher.start()

        self.mock_query.return_value = []

    def _mentor_id_in_match(self):
        _, kwargs = self.mock_query.call_args
        match = kwargs.get("match") or {}
        if "mentor_id" in match:
            return match["mentor_id"]
        for clause in match.get("$and", []):
            if "mentor_id" in clause:
                return clause["mentor_id"]
        self.fail(f"mentor_id not found in match: {match}")

    def test_encodes_profile_id_when_mentor_id_absent(self):
        ProfileService.get_mentee_profiles(token(profile_id=PROFILE_ID), BREADCRUMB)

        self.mock_query.assert_called_once()
        self.assertEqual(self._mentor_id_in_match(), ObjectId(PROFILE_ID))
        _, kwargs = self.mock_query.call_args
        self.assertEqual(kwargs["match"]["status"], {"$ne": "archived"})

    def test_encodes_mentor_id_when_present(self):
        ProfileService.get_mentee_profiles(
            token(mentor_id=MENTOR_ID, profile_id=PROFILE_ID), BREADCRUMB
        )

        self.mock_query.assert_called_once()
        self.assertEqual(self._mentor_id_in_match(), ObjectId(MENTOR_ID))
        self.assertNotEqual(self._mentor_id_in_match(), ObjectId(PROFILE_ID))

    def test_empty_list_when_scope_id_missing(self):
        profiles = ProfileService.get_mentee_profiles(token(), BREADCRUMB)

        self.mock_query.assert_not_called()
        self.assertEqual(profiles, [])

    def test_does_not_gate_on_mentor_role(self):
        ProfileService.get_mentee_profiles(
            token(roles=["customer"], profile_id=PROFILE_ID), BREADCRUMB
        )

        self.mock_query.assert_called_once()
        self.assertEqual(self._mentor_id_in_match(), ObjectId(PROFILE_ID))


if __name__ == "__main__":
    unittest.main()
