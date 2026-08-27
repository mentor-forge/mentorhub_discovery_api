"""
Unit tests for EventCardService and EventService.
"""

import unittest
from unittest.mock import patch

from bson import ObjectId

from api_utils.mongo_utils.list_query import DEFAULT_OFFSET, DEFAULT_SIZE
from src.services.event_service import EventCardService, EventService

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


if __name__ == "__main__":
    unittest.main()
