"""
Unit tests for the Discovery Card service and the Card-projecting subclasses of
the consume services.

`project` must emit only Card schema properties, and `get_home_cards` must
assemble its sections in the documented order, gate them on the token roles,
and paginate the combined list. The typed lists must project whatever their
source service returns, without projecting the reads the Notification control
endpoints depend on. Source services are mocked; no database is required.
"""

import unittest
from unittest.mock import MagicMock, patch

from bson import ObjectId

from api_utils.flask_utils.exceptions import HTTPBadRequest
from src.services.event_service import EventCardService
from src.services.notification_service import (
    NotificationCardService,
    NotificationService,
)
from src.services.path_service import PathCardService
from src.services.plan_service import PlanCardService
from src.services.resource_service import ResourceCardService
from src.services.card_service import (
    CARD_TYPE_CUSTOMER,
    CARD_TYPE_EVENT,
    CARD_TYPE_EVENTS,
    CARD_TYPE_MEMBERS,
    CARD_TYPE_MENTEES,
    CARD_TYPE_NOTIFICATIONS,
    CARD_TYPE_PATHS,
    CARD_TYPE_PLANS,
    CARD_TYPE_RESOURCES,
    CardService,
)

# Card.yaml 0.0.0.0 properties (additionalProperties: false, nothing required).
CARD_PROPERTIES = {"_id", "name", "description", "link", "type"}

# F100 Card.type enum: collection-aligned values plus Discovery synthetics.
CARD_TYPE_ENUM = {
    "Customer",
    "Discounts",
    "Event",
    "Journey",
    "Logs",
    "Member",
    "Mentee",
    "Notification",
    "Path",
    "Plan",
    "Products",
    "Resource",
}

PROFILE_ID = "665f1c2a9b1e4c0a1b2c3d01"
CUSTOMER_ID = "665f1c2a9b1e4c0a1b2c3d03"
MENTOR_ID = "665f1c2a9b1e4c0a1b2c3d04"

BREADCRUMB = {
    "from_ip": "127.0.0.1",
    "by_user": "test-user",
    "at_time": "2026-08-23T12:00:00",
    "correlation_id": "test-correlation",
}


def mock_config():
    config = MagicMock()
    config.CUSTOMER_COLLECTION_NAME = "Customer"
    config.SETTING_COLLECTION_NAME = "Setting"
    config.PROFILE_COLLECTION_NAME = "Profile"
    config.NOTIFICATION_COLLECTION_NAME = "Notification"
    config.ROLE_ADMIN = "admin"
    config.ROLE_CUSTOMER = "customer"
    config.ROLE_COORDINATOR = "coordinator"
    config.ROLE_MENTOR = "mentor"
    config.ROLE_MENTEE = "mentee"
    return config


def token(roles=None, **claims):
    base = {"user_id": "test-user", "roles": roles if roles is not None else []}
    base.update(claims)
    return base


def documents(prefix, count):
    return [
        {"_id": ObjectId(), "name": f"{prefix}-{index}", "description": f"d{index}"}
        for index in range(count)
    ]


class TestProject(unittest.TestCase):
    """project maps a source document onto the Card schema."""

    def test_project_emits_only_card_properties(self):
        source = {
            "_id": ObjectId(),
            "name": "Learn Python",
            "description": "A path",
            "status": "active",
            "created": BREADCRUMB,
            "saved": BREADCRUMB,
        }

        card = CardService.project(CARD_TYPE_PATHS, source)

        self.assertTrue(set(card).issubset(CARD_PROPERTIES))
        self.assertNotIn("status", card)
        self.assertNotIn("created", card)

    def test_project_carries_source_id_unchanged(self):
        source_id = ObjectId()

        card = CardService.project(CARD_TYPE_PATHS, {"_id": source_id, "name": "p"})

        self.assertIs(card["_id"], source_id)

    def test_project_omits_absent_fields(self):
        card = CardService.project(CARD_TYPE_PATHS, {})

        self.assertNotIn("_id", card)
        self.assertNotIn("name", card)
        self.assertNotIn("description", card)
        self.assertNotIn("link", card)

    def test_project_notification_uses_message_as_description(self):
        source = {"_id": ObjectId(), "name": "welcome", "message": "Hello there"}

        card = CardService.project(CARD_TYPE_NOTIFICATIONS, source)

        self.assertEqual(card["name"], "welcome")
        self.assertEqual(card["description"], "Hello there")
        self.assertEqual(card["type"], "Notification")

    def test_project_member_uses_display_name(self):
        source = {"_id": ObjectId(), "display_name": "Jane Doe"}

        card = CardService.project(CARD_TYPE_MEMBERS, source)

        self.assertEqual(card["name"], "Jane Doe")
        self.assertEqual(card["type"], "Member")

    def test_project_member_does_not_use_stale_name(self):
        card = CardService.project(CARD_TYPE_MEMBERS, {"_id": ObjectId(), "name": "j"})

        self.assertNotIn("name", card)

    def test_project_member_keeps_source_description(self):
        """project is a pure field map; enrichment happens before it is called."""
        card = CardService.project(
            CARD_TYPE_MEMBERS,
            {"_id": ObjectId(), "name": "j", "description": "original prose"},
        )

        self.assertEqual(card["description"], "original prose")

    def test_project_resource_links_mentor_vs_non_mentor(self):
        source_id = ObjectId()
        source = {"_id": source_id, "name": "Docs", "url": "https://example.com"}

        card_mentor = CardService.project(
            CARD_TYPE_RESOURCES, source, token=token(roles=["mentor"])
        )
        self.assertEqual(card_mentor["link"], f"mentor/resource/{source_id}")
        self.assertEqual(card_mentor["type"], "Resource")

        card_mentee = CardService.project(
            CARD_TYPE_RESOURCES, source, token=token(roles=["mentee"])
        )
        self.assertEqual(card_mentee["link"], f"mentee/resource/{source_id}")

        card_no_roles = CardService.project(CARD_TYPE_RESOURCES, source)
        self.assertEqual(card_no_roles["link"], f"mentee/resource/{source_id}")

    def test_project_path_links_mentor_vs_non_mentor(self):
        source_id = ObjectId()
        source = {"_id": source_id, "name": "Python Path"}

        card_mentor = CardService.project(
            CARD_TYPE_PATHS, source, token=token(roles=["mentor"])
        )
        self.assertEqual(card_mentor["link"], f"mentor/path/{source_id}")
        self.assertEqual(card_mentor["type"], "Path")

        card_mentee = CardService.project(
            CARD_TYPE_PATHS, source, token=token(roles=["mentee"])
        )
        self.assertEqual(card_mentee["link"], f"mentee/path/{source_id}")

    def test_project_plan_links_mentor_path(self):
        source_id = ObjectId()
        source = {"_id": source_id, "name": "Study Plan"}

        card = CardService.project(
            CARD_TYPE_PLANS, source, token=token(roles=["mentee"])
        )
        self.assertEqual(card["link"], f"mentor/plan/{source_id}")
        self.assertEqual(card["type"], "Plan")

    def test_project_member_and_mentee_links(self):
        source_id = ObjectId()
        member_card = CardService.project(
            CARD_TYPE_MEMBERS, {"_id": source_id, "name": "Member"}
        )
        self.assertEqual(member_card["link"], f"customer/profile/{source_id}")

        mentee_card = CardService.project(
            CARD_TYPE_MENTEES, {"_id": source_id, "name": "Mentee"}
        )
        self.assertEqual(mentee_card["link"], f"mentor/mentee/{source_id}")

    def test_project_notification_always_sets_link(self):
        source_id = ObjectId()
        source = {"_id": source_id, "name": "N", "message": "msg"}

        card = CardService.project(CARD_TYPE_NOTIFICATIONS, source)
        self.assertEqual(card["link"], f"discovery/notification/{source_id}")

    def test_project_event(self):
        source_id = ObjectId()
        source = {
            "_id": source_id,
            "type": "login",
            "context": {"profile_id": PROFILE_ID},
            "created": BREADCRUMB,
        }

        card = CardService.project(CARD_TYPE_EVENTS, source)

        self.assertEqual(card["_id"], source_id)
        self.assertEqual(card["name"], "login")
        self.assertEqual(card["type"], "Event")
        self.assertNotIn("link", card)
        self.assertNotIn("context", card)
        self.assertNotIn("created", card)

    def test_project_typed_sources_use_enum_values(self):
        expected = {
            CARD_TYPE_CUSTOMER: "Customer",
            CARD_TYPE_EVENTS: "Event",
            CARD_TYPE_MEMBERS: "Member",
            CARD_TYPE_MENTEES: "Mentee",
            CARD_TYPE_NOTIFICATIONS: "Notification",
            CARD_TYPE_PATHS: "Path",
            CARD_TYPE_PLANS: "Plan",
            CARD_TYPE_RESOURCES: "Resource",
        }

        for card_type, enum_value in expected.items():
            with self.subTest(card_type=card_type):
                card = CardService.project(
                    card_type, {"_id": ObjectId(), "name": "n", "type": "n"}
                )
                self.assertEqual(card["type"], enum_value)
                self.assertIn(card["type"], CARD_TYPE_ENUM)

    def test_project_customer_emits_type(self):
        card = CardService.project(CARD_TYPE_CUSTOMER, {"_id": ObjectId(), "name": "n"})
        self.assertEqual(card["type"], "Customer")
        self.assertIn(card["type"], CARD_TYPE_ENUM)
        self.assertTrue(set(card).issubset(CARD_PROPERTIES))

    def test_synthetic_card_emits_type_and_link_without_id(self):
        card = CardService._synthetic_card(
            "Products",
            "Manage subscription products",
            "Products",
            "admin/settings",
        )
        self.assertEqual(card["type"], "Products")
        self.assertEqual(card["link"], "admin/settings")
        self.assertNotIn("_id", card)
        self.assertTrue(set(card).issubset(CARD_PROPERTIES))
        self.assertIn(card["type"], CARD_TYPE_ENUM)

    def test_project_unknown_type_raises_bad_request(self):
        with self.assertRaises(HTTPBadRequest):
            CardService.project("journeys", {"_id": ObjectId()})


class HomeCardsTestCase(unittest.TestCase):
    """Patch the source services so the home list is assembled from fixtures."""

    def setUp(self):
        self.config = mock_config()

        config_patcher = patch(
            "src.services.card_service.Config.get_instance", return_value=self.config
        )
        notifications_patcher = patch(
            "src.services.card_service.NotificationService.get_active_notifications"
        )
        members_patcher = patch(
            "src.services.card_service.ProfileService.get_member_profiles"
        )
        mentees_patcher = patch(
            "src.services.card_service.ProfileService.get_mentee_profiles"
        )
        query_patcher = patch("src.services.card_service.execute_list_query")
        journey_patcher = patch(
            "src.services.journey_service.JourneyService.resource_counts_for_profile",
            return_value={"library": 0, "now": 0, "next": 0},
        )
        event_count_patcher = patch(
            "src.services.event_service.EventService.recent_event_count_for_profile",
            return_value=0,
        )
        notes_patcher = patch(
            "src.services.note_service.NoteService.notes_for_profile",
            return_value=[],
        )

        self.addCleanup(config_patcher.stop)
        self.addCleanup(notifications_patcher.stop)
        self.addCleanup(members_patcher.stop)
        self.addCleanup(mentees_patcher.stop)
        self.addCleanup(query_patcher.stop)
        self.addCleanup(journey_patcher.stop)
        self.addCleanup(event_count_patcher.stop)
        self.addCleanup(notes_patcher.stop)

        config_patcher.start()
        self.mock_notifications = notifications_patcher.start()
        self.mock_members = members_patcher.start()
        self.mock_mentees = mentees_patcher.start()
        self.mock_query = query_patcher.start()
        self.mock_journey_counts = journey_patcher.start()
        self.mock_event_count = event_count_patcher.start()
        self.mock_notes = notes_patcher.start()

        self.mock_notifications.return_value = []
        self.mock_members.return_value = []
        self.mock_mentees.return_value = []
        self.mock_query.return_value = []


class TestHomeCardNotifications(HomeCardsTestCase):
    """Section one: active notifications for the token profile_id."""

    def test_notifications_included_for_profile_id(self):
        self.mock_notifications.return_value = [
            {"_id": ObjectId(), "name": "welcome", "message": "Hi"}
        ]

        cards = CardService.get_home_cards(token(profile_id=PROFILE_ID), BREADCRUMB)

        self.assertEqual(len(cards), 1)
        self.assertEqual(cards[0]["type"], "Notification")
        self.assertEqual(cards[0]["description"], "Hi")
        self.assertEqual(cards[0]["link"], f"discovery/notification/{cards[0]['_id']}")

    def test_notifications_scoped_to_token_profile_id(self):
        CardService.get_home_cards(token(profile_id=PROFILE_ID), BREADCRUMB)

        _, kwargs = self.mock_notifications.call_args
        self.assertEqual(kwargs["match"], {"profile_id": PROFILE_ID})
        self.assertEqual(kwargs["offset"], 0)

    def test_notifications_skipped_without_profile_id(self):
        cards = CardService.get_home_cards(token(), BREADCRUMB)

        self.mock_notifications.assert_not_called()
        self.assertEqual(cards, [])


class TestHomeCardAdmin(HomeCardsTestCase):
    """Sections 2-4: synthetic cards for Admin callers."""

    def test_admin_includes_products_discounts_logs_in_order(self):
        cards = CardService.get_home_cards(token(roles=["admin"]), BREADCRUMB)

        self.assertEqual(len(cards), 3)
        self.assertEqual(
            cards[0],
            {
                "name": "Products",
                "description": "Manage subscription products",
                "type": "Products",
                "link": "admin/settings",
            },
        )
        self.assertEqual(
            cards[1],
            {
                "name": "Discounts",
                "description": "Manage discount codes",
                "type": "Discounts",
                "link": "admin/settings?tab=discounts",
            },
        )
        self.assertEqual(
            cards[2],
            {
                "name": "Logs",
                "description": "View system logs",
                "type": "Logs",
                "link": "admin/logs",
            },
        )
        for card in cards:
            self.assertIn(card["type"], CARD_TYPE_ENUM)
            self.assertNotIn("_id", card)

    def test_admin_omitted_without_admin_role(self):
        cards = CardService.get_home_cards(token(roles=["customer"]), BREADCRUMB)
        self.assertEqual(cards, [])


class TestHomeCardCustomer(HomeCardsTestCase):
    """Section 5: Customer singleton for Customer callers."""

    def test_customer_card_included_for_customer_role(self):
        cust_id = ObjectId(CUSTOMER_ID)
        self.mock_query.return_value = [
            {"_id": cust_id, "name": "Acme Corp", "description": "Acme customer"}
        ]

        cards = CardService.get_home_cards(
            token(roles=["customer"], customer_id=CUSTOMER_ID), BREADCRUMB
        )

        self.assertEqual(len(cards), 1)
        self.assertEqual(cards[0]["name"], "Acme Corp")
        self.assertEqual(cards[0]["description"], "Acme customer")
        self.assertEqual(cards[0]["link"], f"customer/customer/{CUSTOMER_ID}")
        self.assertEqual(cards[0]["type"], "Customer")

    def test_customer_card_omitted_for_coordinator_only(self):
        self.mock_query.return_value = [
            {"_id": ObjectId(CUSTOMER_ID), "name": "Acme Corp"}
        ]

        cards = CardService.get_home_cards(
            token(roles=["coordinator"], customer_id=CUSTOMER_ID), BREADCRUMB
        )

        self.mock_query.assert_not_called()
        self.assertEqual(cards, [])

    def test_customer_card_omitted_without_customer_id(self):
        cards = CardService.get_home_cards(token(roles=["customer"]), BREADCRUMB)

        self.mock_query.assert_not_called()
        self.assertEqual(cards, [])


class TestHomeCardMembers(HomeCardsTestCase):
    """Section 6: members for Customer or Coordinator callers."""

    def test_members_included_for_customer_role(self):
        self.mock_members.return_value = documents("member", 2)

        cards = CardService.get_home_cards(
            token(roles=["customer"], customer_id=CUSTOMER_ID), BREADCRUMB
        )

        self.assertEqual([card["type"] for card in cards], ["Member", "Member"])
        _, kwargs = self.mock_members.call_args
        self.assertEqual(kwargs["sort_by"], [("saved.at_time", -1), ("_id", -1)])

    def test_members_included_for_coordinator_role(self):
        self.mock_members.return_value = documents("member", 1)

        cards = CardService.get_home_cards(
            token(roles=["coordinator"], customer_id=CUSTOMER_ID), BREADCRUMB
        )

        self.assertEqual(len(cards), 1)
        _, kwargs = self.mock_members.call_args
        self.assertEqual(kwargs["sort_by"], [("saved.at_time", -1), ("_id", -1)])

    def test_members_omitted_without_customer_or_coordinator_role(self):
        self.mock_members.return_value = documents("member", 3)

        cards = CardService.get_home_cards(
            token(roles=["mentee"], customer_id=CUSTOMER_ID), BREADCRUMB
        )

        self.mock_members.assert_not_called()
        self.assertEqual([c for c in cards if c.get("type") == "Member"], [])

    def test_members_omitted_without_customer_id(self):
        cards = CardService.get_home_cards(token(roles=["customer"]), BREADCRUMB)

        self.mock_members.assert_not_called()
        self.assertEqual(cards, [])


class TestHomeCardMentees(HomeCardsTestCase):
    """Section 7: mentees for Mentor callers."""

    def test_mentees_included_for_mentor_role(self):
        self.mock_mentees.return_value = documents("mentee", 2)

        cards = CardService.get_home_cards(
            token(roles=["mentor"], profile_id=PROFILE_ID), BREADCRUMB
        )

        self.assertEqual([card["type"] for card in cards], ["Mentee", "Mentee"])
        self.assertTrue(cards[0]["link"].startswith("mentor/mentee/"))
        self.mock_mentees.assert_called_once()
        _, kwargs = self.mock_mentees.call_args
        self.assertEqual(kwargs["sort_by"], [("saved.at_time", -1), ("_id", -1)])

    def test_mentees_included_with_profile_id_only(self):
        self.mock_mentees.return_value = documents("mentee", 2)

        cards = CardService.get_home_cards(
            token(roles=["mentor"], profile_id=PROFILE_ID, mentor_id=""), BREADCRUMB
        )

        self.assertEqual([card["type"] for card in cards], ["Mentee", "Mentee"])
        self.mock_mentees.assert_called_once()
        _, kwargs = self.mock_mentees.call_args
        self.assertEqual(kwargs["sort_by"], [("saved.at_time", -1), ("_id", -1)])

    def test_mentees_included_when_profile_id_wins_over_mentor_id_claim(self):
        self.mock_mentees.return_value = documents("mentee", 1)

        cards = CardService.get_home_cards(
            token(roles=["mentor"], mentor_id=MENTOR_ID, profile_id=PROFILE_ID),
            BREADCRUMB,
        )

        self.assertEqual([card["type"] for card in cards], ["Mentee"])
        self.mock_mentees.assert_called_once()

    def test_mentees_omitted_without_mentor_role(self):
        self.mock_mentees.return_value = documents("mentee", 3)

        cards = CardService.get_home_cards(
            token(roles=["customer"], mentor_id=MENTOR_ID, profile_id=PROFILE_ID),
            BREADCRUMB,
        )

        self.mock_mentees.assert_not_called()
        self.assertEqual([c for c in cards if c.get("type") == "Mentee"], [])

    def test_mentees_omitted_without_profile_id(self):
        cards = CardService.get_home_cards(
            token(roles=["mentor"], mentor_id=MENTOR_ID), BREADCRUMB
        )

        self.mock_mentees.assert_not_called()
        self.assertEqual(cards, [])


class TestHomeCardMenteeJourney(HomeCardsTestCase):
    """Section 8: Learning Journey synthetic card for Mentee callers."""

    def test_mentee_includes_learning_journey_card(self):
        cards = CardService.get_home_cards(token(roles=["mentee"]), BREADCRUMB)

        self.assertEqual(len(cards), 1)
        self.assertEqual(
            cards[0],
            {
                "name": "Learning Journey",
                "description": "Continue your learning journey",
                "type": "Journey",
                "link": "mentee/journey",
            },
        )
        self.assertNotIn("_id", cards[0])

    def test_learning_journey_omitted_without_mentee_role(self):
        cards = CardService.get_home_cards(token(roles=["mentor"]), BREADCRUMB)
        self.assertEqual(cards, [])


class TestHomeCardComposition(HomeCardsTestCase):
    """Ordering and pagination across the combined list."""

    def setUp(self):
        super().setUp()
        self.mock_notifications.return_value = [
            {"_id": ObjectId(), "name": "note-0", "message": "m0"},
            {"_id": ObjectId(), "name": "note-1", "message": "m1"},
        ]
        self.cust_id = ObjectId(CUSTOMER_ID)
        self.mock_query.return_value = [
            {
                "_id": self.cust_id,
                "name": "Acme Corp",
                "description": "Customer singleton",
            }
        ]
        self.mock_members.return_value = documents("member", 2)
        self.mock_mentees.return_value = documents("mentee", 2)
        self.token = token(
            roles=["admin", "customer", "coordinator", "mentor", "mentee"],
            profile_id=PROFILE_ID,
            customer_id=CUSTOMER_ID,
            mentor_id=MENTOR_ID,
        )

    def test_sections_concatenate_in_order(self):
        cards = CardService.get_home_cards(self.token, BREADCRUMB)

        # 1. 2 Notifications
        # 2-4. Products, Discounts, Logs
        # 5. Customer singleton
        # 6. 2 Members
        # 7. 2 Mentees
        # 8. Learning Journey
        self.assertEqual(len(cards), 11)
        self.assertEqual(cards[0]["type"], "Notification")
        self.assertEqual(cards[0]["link"], f"discovery/notification/{cards[0]['_id']}")
        self.assertEqual(cards[1]["type"], "Notification")
        self.assertEqual(cards[2]["name"], "Products")
        self.assertEqual(cards[2]["type"], "Products")
        self.assertEqual(cards[2]["link"], "admin/settings")
        self.assertEqual(cards[3]["name"], "Discounts")
        self.assertEqual(cards[3]["type"], "Discounts")
        self.assertEqual(cards[3]["link"], "admin/settings?tab=discounts")
        self.assertEqual(cards[4]["name"], "Logs")
        self.assertEqual(cards[4]["type"], "Logs")
        self.assertEqual(cards[4]["link"], "admin/logs")
        self.assertEqual(cards[5]["name"], "Acme Corp")
        self.assertEqual(cards[5]["type"], "Customer")
        self.assertEqual(cards[5]["link"], f"customer/customer/{CUSTOMER_ID}")
        self.assertEqual(cards[6]["type"], "Member")
        self.assertEqual(cards[7]["type"], "Member")
        self.assertEqual(cards[8]["type"], "Mentee")
        self.assertTrue(cards[8]["link"].startswith("mentor/mentee/"))
        self.assertEqual(cards[9]["type"], "Mentee")
        self.assertEqual(cards[10]["name"], "Learning Journey")
        self.assertEqual(cards[10]["type"], "Journey")
        self.assertEqual(cards[10]["link"], "mentee/journey")

    def test_offset_and_size_slice_the_combined_list(self):
        cards = CardService.get_home_cards(self.token, BREADCRUMB, offset=2, size=3)

        self.assertEqual(len(cards), 3)
        self.assertEqual([c["name"] for c in cards], ["Products", "Discounts", "Logs"])

    def test_offset_past_the_end_returns_empty(self):
        cards = CardService.get_home_cards(self.token, BREADCRUMB, offset=20, size=5)

        self.assertEqual(cards, [])

    def test_sections_are_fetched_from_the_start_of_each_source(self):
        CardService.get_home_cards(self.token, BREADCRUMB, offset=2, size=3)

        for mock_source in (
            self.mock_notifications,
            self.mock_members,
            self.mock_mentees,
        ):
            _, kwargs = mock_source.call_args
            self.assertEqual(kwargs["offset"], 0)
            self.assertEqual(kwargs["size"], 5)

    def test_section_size_is_capped_at_the_shared_page_ceiling(self):
        CardService.get_home_cards(self.token, BREADCRUMB, offset=99, size=100)

        _, kwargs = self.mock_notifications.call_args
        self.assertEqual(kwargs["size"], 100)

    def test_invalid_pagination_raises_bad_request(self):
        with self.assertRaises(HTTPBadRequest):
            CardService.get_home_cards(self.token, BREADCRUMB, offset=-1, size=10)

        with self.assertRaises(HTTPBadRequest):
            CardService.get_home_cards(self.token, BREADCRUMB, offset=0, size=101)


# (Card subclass, list method, patched source, expected Card type). The source
# is patched one level up the MRO, so each test covers the projection only.
CARD_SUBCLASS_LISTS = [
    (
        ResourceCardService,
        "get_resources",
        "api_utils.services.resource_service.ResourceService.get_resources",
        "Resource",
    ),
    (
        PathCardService,
        "get_paths",
        "api_utils.services.path_service.PathService.get_paths",
        "Path",
    ),
    (
        PlanCardService,
        "get_plans",
        "api_utils.services.plan_service.PlanService.get_plans",
        "Plan",
    ),
    (
        EventCardService,
        "get_events",
        "api_utils.services.event_service.EventService.get_events",
        "Event",
    ),
]


# (Card subclass, inherited by-id read the suppressed routes used to call).
CARD_SUBCLASS_BY_ID_GETTERS = [
    (ResourceCardService, "get_resource"),
    (PathCardService, "get_path"),
    (PlanCardService, "get_plan"),
    (EventCardService, "get_event"),
]


class TestCardProjectingSubclasses(unittest.TestCase):
    """The subclasses bound to the shared GET factories return Cards."""

    def test_lists_project_their_source_documents(self):
        for service_cls, method, source, card_type in CARD_SUBCLASS_LISTS:
            with self.subTest(service=service_cls.__name__):
                with patch(source, return_value=documents("row", 2)) as mock_source:
                    cards = getattr(service_cls, method)(token(), BREADCRUMB)

                mock_source.assert_called_once()
                self.assertEqual(len(cards), 2)
                for card in cards:
                    self.assertEqual(card["type"], card_type)
                    self.assertTrue(set(card).issubset(CARD_PROPERTIES))

    def test_lists_pass_the_list_request_through(self):
        sort_by = [("name", 1)]
        for service_cls, method, source, _ in CARD_SUBCLASS_LISTS:
            with self.subTest(service=service_cls.__name__):
                with patch(source, return_value=[]) as mock_source:
                    getattr(service_cls, method)(
                        token(), BREADCRUMB, 5, 10, {"name": "a"}, sort_by
                    )

                args, kwargs = mock_source.call_args
                pagination = args[2:4] or (kwargs.get("offset"), kwargs.get("size"))
                self.assertEqual(tuple(pagination), (5, 10))
                passed_filters = args[4] if len(args) > 4 else kwargs.get("filters")
                self.assertEqual(passed_filters, {"name": "a"})
                passed_sort = args[5] if len(args) > 5 else kwargs.get("sort_by")
                self.assertEqual(passed_sort, sort_by)

    def test_subclasses_do_not_project_a_single_document(self):
        """Card by-id GETs are suppressed, so no subclass overrides a by-id read."""
        for service_cls, getter in CARD_SUBCLASS_BY_ID_GETTERS:
            with self.subTest(service=service_cls.__name__):
                self.assertNotIn(getter, vars(service_cls))


class TestNotificationCardIsolation(unittest.TestCase):
    """Projection is confined to the cards subclass, not the control service."""

    def setUp(self):
        self.notifications = [{"_id": ObjectId(), "name": "welcome", "message": "Hi"}]
        patcher = patch(
            "api_utils.services.notification_service.NotificationService"
            ".get_notifications",
            return_value=self.notifications,
        )
        self.addCleanup(patcher.stop)
        self.mock_source = patcher.start()

    def test_cards_subclass_projects_the_list(self):
        cards = NotificationCardService.get_notifications(token(), BREADCRUMB)

        self.assertEqual(len(cards), 1)
        self.assertEqual(cards[0]["type"], "Notification")
        self.assertEqual(cards[0]["description"], "Hi")
        self.assertEqual(
            cards[0]["link"],
            f"discovery/notification/{self.notifications[0]['_id']}",
        )

    def test_control_service_still_returns_notification_documents(self):
        notifications = NotificationService.get_notifications(token(), BREADCRUMB)

        self.assertEqual(notifications, self.notifications)
        self.assertIn("message", notifications[0])

    def test_active_read_returns_notification_documents(self):
        notifications = NotificationService.get_active_notifications(
            token(), BREADCRUMB
        )

        self.assertEqual(notifications, self.notifications)


class TestHomeCardMemberMarkdown(HomeCardsTestCase):
    """Member cards replace Profile description with progress + activity Markdown."""

    def test_member_description_contains_progress_and_activity(self):
        self.mock_members.return_value = [
            {
                "_id": ObjectId(),
                "display_name": "Jane Doe",
                "description": "original prose",
            }
        ]
        self.mock_journey_counts.return_value = {"library": 4, "now": 2, "next": 7}
        self.mock_event_count.return_value = 5

        cards = CardService.get_home_cards(
            token(roles=["customer"], customer_id=CUSTOMER_ID), BREADCRUMB
        )

        self.assertEqual(len(cards), 1)
        description = cards[0]["description"]
        self.assertIn("Library", description)
        self.assertIn("Now", description)
        self.assertIn("Next", description)
        self.assertIn("30 days", description)
        self.assertIn("- Library: 4", description)
        self.assertIn("- Now: 2", description)
        self.assertIn("- Next: 7", description)
        self.assertIn("5 events in the last 30 days", description)
        self.assertNotIn("original prose", description)
        self.assertEqual(cards[0]["type"], "Member")
        self.assertTrue(cards[0]["link"].startswith("customer/profile/"))

    def test_member_description_zeros_when_helpers_return_empty(self):
        self.mock_members.return_value = documents("member", 1)

        cards = CardService.get_home_cards(
            token(roles=["customer"], customer_id=CUSTOMER_ID), BREADCRUMB
        )

        description = cards[0]["description"]
        self.assertIn("- Library: 0", description)
        self.assertIn("- Now: 0", description)
        self.assertIn("- Next: 0", description)
        self.assertIn("0 events in the last 30 days", description)
        self.assertIsNotNone(description)

    def test_customer_member_enrichment_does_not_require_mentor_role(self):
        self.mock_members.return_value = documents("member", 1)

        CardService.get_home_cards(
            token(roles=["customer"], customer_id=CUSTOMER_ID), BREADCRUMB
        )

        self.mock_journey_counts.assert_called_once()
        self.mock_event_count.assert_called_once()
        self.mock_notes.assert_not_called()

    def test_coordinator_member_enrichment_does_not_require_mentor_role(self):
        self.mock_members.return_value = documents("member", 1)

        CardService.get_home_cards(
            token(roles=["coordinator"], customer_id=CUSTOMER_ID), BREADCRUMB
        )

        self.mock_journey_counts.assert_called_once()
        self.mock_event_count.assert_called_once()
        self.mock_notes.assert_not_called()


class TestHomeCardMenteeMarkdown(HomeCardsTestCase):
    """Mentee cards replace Profile description with activity + notes Markdown."""

    def test_mentee_description_contains_activity_and_notes(self):
        self.mock_mentees.return_value = [
            {
                "_id": ObjectId(),
                "display_name": "Daniel",
                "description": "original prose",
            }
        ]
        self.mock_event_count.return_value = 3
        self.mock_notes.return_value = [{"note": "Ask about the path"}]

        cards = CardService.get_home_cards(
            token(roles=["mentor"], profile_id=PROFILE_ID, mentor_id=""), BREADCRUMB
        )

        self.assertEqual(len(cards), 1)
        description = cards[0]["description"]
        self.assertIn("30 days", description)
        self.assertIn("**Notes**", description)
        self.assertIn("3 events in the last 30 days", description)
        self.assertIn("Ask about the path", description)
        self.assertNotIn("original prose", description)
        self.assertEqual(cards[0]["type"], "Mentee")
        self.assertTrue(cards[0]["link"].startswith("mentor/mentee/"))

    def test_mentee_description_empty_notes_line_when_helpers_return_empty(self):
        self.mock_mentees.return_value = documents("mentee", 1)

        cards = CardService.get_home_cards(
            token(roles=["mentor"], profile_id=PROFILE_ID, mentor_id=""), BREADCRUMB
        )

        description = cards[0]["description"]
        self.assertIn("0 events in the last 30 days", description)
        self.assertIn("**Notes**", description)
        self.assertIn("*No notes*", description)
        self.assertIsNotNone(description)

    def test_mentor_mentee_enrichment_does_not_require_customer_role(self):
        self.mock_mentees.return_value = documents("mentee", 1)

        CardService.get_home_cards(
            token(roles=["mentor"], profile_id=PROFILE_ID, mentor_id=""), BREADCRUMB
        )

        self.mock_notes.assert_called_once()
        self.mock_event_count.assert_called_once()
        self.mock_journey_counts.assert_not_called()


class TestHomeCardEnrichmentGates(HomeCardsTestCase):
    """Non-member / non-mentee home paths must not call enrichment helpers."""

    def test_mentee_only_path_does_not_call_enrichment_helpers(self):
        cards = CardService.get_home_cards(token(roles=["mentee"]), BREADCRUMB)

        self.mock_journey_counts.assert_not_called()
        self.mock_event_count.assert_not_called()
        self.mock_notes.assert_not_called()
        self.assertEqual(cards[0]["type"], "Journey")

    def test_admin_only_path_does_not_call_enrichment_helpers(self):
        CardService.get_home_cards(token(roles=["admin"]), BREADCRUMB)

        self.mock_journey_counts.assert_not_called()
        self.mock_event_count.assert_not_called()
        self.mock_notes.assert_not_called()

    def test_typed_lists_do_not_call_enrichment_helpers(self):
        with patch(
            "api_utils.services.resource_service.ResourceService.get_resources",
            return_value=documents("row", 1),
        ):
            ResourceCardService.get_resources(token(), BREADCRUMB)

        self.mock_journey_counts.assert_not_called()
        self.mock_event_count.assert_not_called()
        self.mock_notes.assert_not_called()


if __name__ == "__main__":
    unittest.main()
