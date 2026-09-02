"""
Unit tests for EventCardService and EventService.
"""

import unittest
from datetime import datetime, timedelta, timezone
from unittest.mock import MagicMock, patch

from bson import ObjectId

from api_utils.mongo_utils.list_query import DEFAULT_OFFSET, DEFAULT_SIZE
from src.services.event_service import (
    CARD_ACTIVITY_WINDOW_DAYS,
    EventCardService,
    EventService,
)

PROFILE_ID = "665f1c2a9b1e4c0a1b2c3d01"

BREADCRUMB = {
    "from_ip": "127.0.0.1",
    "by_user": "test-user",
    "at_time": "2026-08-23T12:00:00",
    "correlation_id": "test-correlation",
}

TOKEN = {
    "user_id": "test-user",
    "roles": ["mentor", "mentee"],
    "profile_id": PROFILE_ID,
}


class TestEventCardService(unittest.TestCase):
    """EventCardService projects Event documents onto Card schemas."""

    def test_get_events_projects_cards(self):
        event_id = ObjectId()
        events = [
            {
                "_id": event_id,
                "type": "login",
                "context": {"profile_id": PROFILE_ID},
                "created": BREADCRUMB,
            }
        ]

        with patch(
            "api_utils.services.event_service.EventService.get_events",
            return_value=events,
        ) as mock_super:
            cards = EventCardService.get_events(
                TOKEN, BREADCRUMB, profile_id=PROFILE_ID
            )

        mock_super.assert_called_once_with(
            TOKEN,
            BREADCRUMB,
            offset=DEFAULT_OFFSET,
            size=DEFAULT_SIZE,
            filters=None,
            sort_by=None,
            profile_id=PROFILE_ID,
        )
        self.assertEqual(len(cards), 1)
        self.assertEqual(cards[0]["_id"], event_id)
        self.assertEqual(cards[0]["name"], "login")
        self.assertEqual(cards[0]["type"], "Event")
        self.assertEqual(cards[0]["link"], f"mentee/event/{event_id}")

    def test_get_events_passes_pagination_filters_sort(self):
        with patch(
            "api_utils.services.event_service.EventService.get_events",
            return_value=[],
        ) as mock_super:
            EventCardService.get_events(
                TOKEN,
                BREADCRUMB,
                offset=5,
                size=20,
                filters={"type": ["login", "logout"]},
                sort_by=[("created.at_time", -1)],
            )

        mock_super.assert_called_once_with(
            TOKEN,
            BREADCRUMB,
            offset=5,
            size=20,
            filters={"type": ["login", "logout"]},
            sort_by=[("created.at_time", -1)],
        )


class TestRecentEventCountForProfile(unittest.TestCase):
    """Count Events for another profile inside the 30-day window."""

    def setUp(self):
        self.config = MagicMock()
        self.config.EVENT_COLLECTION_NAME = "Event"
        self.mongo = MagicMock()
        self.mongo.get_documents.return_value = []

        config_patcher = patch(
            "src.services.event_service.Config.get_instance",
            return_value=self.config,
        )
        mongo_patcher = patch(
            "src.services.event_service.MongoIO.get_instance",
            return_value=self.mongo,
        )
        self.addCleanup(config_patcher.stop)
        self.addCleanup(mongo_patcher.stop)
        config_patcher.start()
        mongo_patcher.start()

    def test_window_match_uses_created_at_time_and_profile_identity(self):
        profile_oid = ObjectId(PROFILE_ID)
        self.mongo.get_documents.return_value = [
            {"_id": ObjectId()},
            {"_id": ObjectId()},
        ]
        before = datetime.now(timezone.utc) - timedelta(days=CARD_ACTIVITY_WINDOW_DAYS)

        count = EventService.recent_event_count_for_profile(
            PROFILE_ID, TOKEN, BREADCRUMB
        )
        after = datetime.now(timezone.utc) - timedelta(days=CARD_ACTIVITY_WINDOW_DAYS)

        self.assertEqual(count, 2)
        self.mongo.get_documents.assert_called_once()
        _, kwargs = self.mongo.get_documents.call_args
        self.assertEqual(self.mongo.get_documents.call_args[0][0], "Event")
        match = kwargs["match"]
        self.assertEqual(
            match["$or"],
            [
                {"context": {"profile_id": profile_oid}},
                {"profile_id": profile_oid},
            ],
        )
        cutoff = match["created.at_time"]["$gte"]
        self.assertGreaterEqual(cutoff, before)
        self.assertLessEqual(cutoff, after)

    def test_unrelated_profile_id_is_not_in_the_match(self):
        other_id = ObjectId("665f1c2a9b1e4c0a1b2c3d99")
        EventService.recent_event_count_for_profile(PROFILE_ID, TOKEN, BREADCRUMB)

        match = self.mongo.get_documents.call_args[1]["match"]
        encoded = ObjectId(PROFILE_ID)
        self.assertEqual(
            match["$or"],
            [
                {"context": {"profile_id": encoded}},
                {"profile_id": encoded},
            ],
        )
        serialized = str(match)
        self.assertNotIn(str(other_id), serialized)

    def test_empty_profile_id_returns_zero_without_io(self):
        count = EventService.recent_event_count_for_profile(None, TOKEN, BREADCRUMB)

        self.assertEqual(count, 0)
        self.mongo.get_documents.assert_not_called()

    def test_does_not_use_shared_get_events(self):
        with patch(
            "api_utils.services.event_service.EventService.get_events"
        ) as mock_shared:
            EventService.recent_event_count_for_profile(PROFILE_ID, TOKEN, BREADCRUMB)

        mock_shared.assert_not_called()


if __name__ == "__main__":
    unittest.main()
