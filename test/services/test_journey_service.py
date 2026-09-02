"""
Unit tests for Discovery JourneyService resource counts.

`resource_counts_for_profile` matches the active Journey for a profile via
MongoIO, encodes `profile_id`, and returns Library / Now / Next counts.
Missing journeys are zeros. Shared `get_journey_progress` is not called.
"""

import unittest
from unittest.mock import MagicMock, patch

from bson import ObjectId

from src.services.journey_service import JourneyService

PROFILE_ID = ObjectId("507f1f77bcf86cd799439011")

BREADCRUMB = {
    "from_ip": "127.0.0.1",
    "by_user": "test-user",
    "at_time": "2026-08-23T12:00:00",
    "correlation_id": "test-correlation",
}

TOKEN = {"user_id": "test-user", "roles": ["customer"], "customer_id": "c1"}


def _mock_config(mock_get_config):
    mock_config = MagicMock()
    mock_config.JOURNEY_COLLECTION_NAME = "Journey"
    mock_get_config.return_value = mock_config
    return mock_config


class TestResourceCountsForProfile(unittest.TestCase):
    """Active-journey resource counts without shared outbound RBAC."""

    @patch("src.services.journey_service.Config.get_instance")
    @patch("src.services.journey_service.MongoIO.get_instance")
    def test_counts_library_now_and_next_resources(
        self, mock_get_mongo, mock_get_config
    ):
        _mock_config(mock_get_config)
        mock_mongo = MagicMock()
        mock_mongo.get_documents.return_value = [
            {
                "profile_id": PROFILE_ID,
                "status": "active",
                "library": [1, 2, 3],
                "now": [1],
                "next": [
                    {"resources": ["a", "b"]},
                    {"resources": ["c"]},
                ],
            }
        ]
        mock_get_mongo.return_value = mock_mongo

        result = JourneyService.resource_counts_for_profile(
            PROFILE_ID, TOKEN, BREADCRUMB
        )

        self.assertEqual(result, {"library": 3, "now": 1, "next": 3})
        mock_mongo.get_documents.assert_called_once_with(
            "Journey", match={"profile_id": PROFILE_ID, "status": "active"}
        )

    @patch("src.services.journey_service.Config.get_instance")
    @patch("src.services.journey_service.MongoIO.get_instance")
    def test_missing_journey_returns_zeros(self, mock_get_mongo, mock_get_config):
        _mock_config(mock_get_config)
        mock_mongo = MagicMock()
        mock_mongo.get_documents.return_value = []
        mock_get_mongo.return_value = mock_mongo

        result = JourneyService.resource_counts_for_profile(
            PROFILE_ID, TOKEN, BREADCRUMB
        )

        self.assertEqual(result, {"library": 0, "now": 0, "next": 0})

    @patch("src.services.journey_service.Config.get_instance")
    @patch("src.services.journey_service.MongoIO.get_instance")
    def test_missing_scope_fields_are_zeros(self, mock_get_mongo, mock_get_config):
        _mock_config(mock_get_config)
        mock_mongo = MagicMock()
        mock_mongo.get_documents.return_value = [
            {
                "profile_id": PROFILE_ID,
                "status": "active",
                "library": None,
                "next": None,
            }
        ]
        mock_get_mongo.return_value = mock_mongo

        result = JourneyService.resource_counts_for_profile(
            PROFILE_ID, TOKEN, BREADCRUMB
        )

        self.assertEqual(result, {"library": 0, "now": 0, "next": 0})

    @patch("src.services.journey_service.Config.get_instance")
    @patch("src.services.journey_service.MongoIO.get_instance")
    def test_encodes_string_profile_id(self, mock_get_mongo, mock_get_config):
        _mock_config(mock_get_config)
        mock_mongo = MagicMock()
        mock_mongo.get_documents.return_value = []
        mock_get_mongo.return_value = mock_mongo

        JourneyService.resource_counts_for_profile(str(PROFILE_ID), TOKEN, BREADCRUMB)

        mock_mongo.get_documents.assert_called_once_with(
            "Journey", match={"profile_id": PROFILE_ID, "status": "active"}
        )

    @patch("src.services.journey_service.Config.get_instance")
    @patch("src.services.journey_service.MongoIO.get_instance")
    def test_empty_profile_id_returns_zeros_without_io(
        self, mock_get_mongo, mock_get_config
    ):
        result = JourneyService.resource_counts_for_profile(None, TOKEN, BREADCRUMB)

        self.assertEqual(result, {"library": 0, "now": 0, "next": 0})
        mock_get_mongo.assert_not_called()
        mock_get_config.assert_not_called()

    @patch("api_utils.services.journey_service.JourneyService.get_journey_progress")
    @patch("src.services.journey_service.Config.get_instance")
    @patch("src.services.journey_service.MongoIO.get_instance")
    def test_does_not_call_shared_get_journey_progress(
        self, mock_get_mongo, mock_get_config, mock_progress
    ):
        _mock_config(mock_get_config)
        mock_mongo = MagicMock()
        mock_mongo.get_documents.return_value = []
        mock_get_mongo.return_value = mock_mongo

        JourneyService.resource_counts_for_profile(PROFILE_ID, TOKEN, BREADCRUMB)

        mock_progress.assert_not_called()


if __name__ == "__main__":
    unittest.main()
