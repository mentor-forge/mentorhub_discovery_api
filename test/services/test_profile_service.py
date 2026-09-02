"""
Unit tests for Discovery ProfileService mentee identity scope.

`get_mentee_profiles` matches Profile.mentor_id to token.profile_id.
login.html mentor JWTs leave the mentor_id claim empty; that claim must not
scope the list. The id is encoded with encode_document before MongoIO.
Role gating lives on CardService, not here.
"""

import unittest
from unittest.mock import MagicMock, patch

from bson import ObjectId

from src.services.profile_service import ProfileService, mentor_scope_id

PROFILE_ID = "665f1c2a9b1e4c0a1b2c3d01"
MENTOR_CLAIM = "665f1c2a9b1e4c0a1b2c3d04"
MARTI_PROFILE_ID = "A00000000000000000000006"

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
    """mentor_scope_id is the caller's Profile _id (login.html profile_id)."""

    def test_uses_profile_id_even_when_mentor_id_claim_is_set(self):
        self.assertEqual(
            mentor_scope_id({"mentor_id": MENTOR_CLAIM, "profile_id": PROFILE_ID}),
            PROFILE_ID,
        )

    def test_empty_mentor_id_claim_uses_profile_id(self):
        self.assertEqual(
            mentor_scope_id({"mentor_id": "", "profile_id": MARTI_PROFILE_ID}),
            MARTI_PROFILE_ID,
        )

    def test_missing_profile_id_returns_none(self):
        self.assertIsNone(mentor_scope_id({"mentor_id": MENTOR_CLAIM}))
        self.assertIsNone(mentor_scope_id({}))
        self.assertIsNone(mentor_scope_id(None))


class TestGetMenteeProfiles(unittest.TestCase):
    """get_mentee_profiles encodes token.profile_id into the mentor_id match."""

    def setUp(self):
        self.config = MagicMock()
        self.config.PROFILE_COLLECTION_NAME = "Profile"

        config_patcher = patch(
            "src.services.profile_service.Config.get_instance",
            return_value=self.config,
        )
        query_patcher = patch("src.services.profile_service.execute_list_query")
        permission_patcher = patch.object(ProfileService, "_check_permission")

        self.addCleanup(config_patcher.stop)
        self.addCleanup(query_patcher.stop)
        self.addCleanup(permission_patcher.stop)

        config_patcher.start()
        self.mock_query = query_patcher.start()
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

    def test_encodes_profile_id_as_mentor_id_match(self):
        ProfileService.get_mentee_profiles(token(profile_id=PROFILE_ID), BREADCRUMB)

        self.mock_query.assert_called_once()
        self.assertEqual(self._mentor_id_in_match(), ObjectId(PROFILE_ID))
        _, kwargs = self.mock_query.call_args
        self.assertEqual(kwargs["match"]["status"], {"$ne": "archived"})

    def test_login_html_empty_mentor_id_uses_profile_id(self):
        ProfileService.get_mentee_profiles(
            token(
                user_id="marti",
                roles=["mentor"],
                profile_id=MARTI_PROFILE_ID,
                customer_id="",
                mentor_id="",
            ),
            BREADCRUMB,
        )

        self.mock_query.assert_called_once()
        self.assertEqual(self._mentor_id_in_match(), ObjectId(MARTI_PROFILE_ID))

    def test_ignores_token_mentor_id_claim(self):
        ProfileService.get_mentee_profiles(
            token(mentor_id=MENTOR_CLAIM, profile_id=PROFILE_ID), BREADCRUMB
        )

        self.mock_query.assert_called_once()
        self.assertEqual(self._mentor_id_in_match(), ObjectId(PROFILE_ID))
        self.assertNotEqual(self._mentor_id_in_match(), ObjectId(MENTOR_CLAIM))

    def test_empty_list_when_profile_id_missing(self):
        profiles = ProfileService.get_mentee_profiles(
            token(mentor_id=MENTOR_CLAIM), BREADCRUMB
        )

        self.mock_query.assert_not_called()
        self.assertEqual(profiles, [])

    def test_does_not_gate_on_mentor_role(self):
        ProfileService.get_mentee_profiles(
            token(roles=["customer"], profile_id=PROFILE_ID), BREADCRUMB
        )

        self.mock_query.assert_called_once()
        self.assertEqual(self._mentor_id_in_match(), ObjectId(PROFILE_ID))


class TestFullNamesForIds(unittest.TestCase):
    """Batch Profile display names for Event card descriptions."""

    def setUp(self):
        self.config = MagicMock()
        self.config.PROFILE_COLLECTION_NAME = "Profile"
        self.mongo = MagicMock()
        self.mongo.get_documents.return_value = []

        config_patcher = patch(
            "src.services.profile_service.Config.get_instance",
            return_value=self.config,
        )
        mongo_patcher = patch(
            "src.services.profile_service.MongoIO.get_instance",
            return_value=self.mongo,
        )
        self.addCleanup(config_patcher.stop)
        self.addCleanup(mongo_patcher.stop)
        config_patcher.start()
        mongo_patcher.start()

    def test_returns_empty_without_io_when_ids_missing(self):
        self.assertEqual(ProfileService.full_names_for_ids([]), {})
        self.assertEqual(ProfileService.full_names_for_ids([None, ""]), {})
        self.mongo.get_documents.assert_not_called()

    def test_batches_unique_ids_and_prefers_full_name(self):
        profile_oid = ObjectId(PROFILE_ID)
        other_oid = ObjectId("665f1c2a9b1e4c0a1b2c3d99")
        self.mongo.get_documents.return_value = [
            {"_id": profile_oid, "full_name": "Jane Explorer", "name": "jane"},
            {"_id": other_oid, "name": "pat"},
        ]

        names = ProfileService.full_names_for_ids([PROFILE_ID, profile_oid, other_oid])

        self.mongo.get_documents.assert_called_once_with(
            "Profile",
            match={"_id": {"$in": [profile_oid, other_oid]}},
            project={"full_name": 1, "name": 1},
        )
        self.assertEqual(
            names,
            {PROFILE_ID: "Jane Explorer", str(other_oid): "pat"},
        )


if __name__ == "__main__":
    unittest.main()
