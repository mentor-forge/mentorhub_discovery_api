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
from src.services.notification_service import (
    NotificationCardService,
    NotificationService,
)
from src.services.path_service import PathCardService
from src.services.plan_service import PlanCardService
from src.services.profile_service import MemberCardService, MenteeCardService
from src.services.resource_service import ResourceCardService
from src.services.card_service import (
    CARD_TYPE_CUSTOMER,
    CARD_TYPE_MEMBERS,
    CARD_TYPE_MENTEES,
    CARD_TYPE_NOTIFICATIONS,
    CARD_TYPE_PATHS,
    CARD_TYPE_PLANS,
    CARD_TYPE_PRODUCTS,
    CARD_TYPE_RESOURCES,
    CARD_TYPE_SETTINGS,
    SETTING_TYPE_PRODUCT,
    CardService,
)

# Card.yaml 0.0.0.0 properties (additionalProperties: false, nothing required).
CARD_PROPERTIES = {"_id", "name", "description", "link", "type"}

# The Card `type` enum has no Customer, Product, or Setting value.
CARD_TYPE_ENUM = {
    "Event",
    "Member",
    "Mentee",
    "Notification",
    "Path",
    "Plan",
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

    def test_project_member_prefers_full_name(self):
        source = {"_id": ObjectId(), "name": "jdoe", "full_name": "Jane Doe"}

        card = CardService.project(CARD_TYPE_MEMBERS, source)

        self.assertEqual(card["name"], "Jane Doe")
        self.assertEqual(card["type"], "Member")

    def test_project_member_falls_back_to_name(self):
        card = CardService.project(CARD_TYPE_MEMBERS, {"_id": ObjectId(), "name": "j"})

        self.assertEqual(card["name"], "j")

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
        self.assertEqual(mentee_card["link"], f"mentee/mentee/{source_id}")

    def test_project_notification_link_flag(self):
        source_id = ObjectId()
        source = {"_id": source_id, "name": "N", "message": "msg"}

        card_home = CardService.project(
            CARD_TYPE_NOTIFICATIONS, source, notification_link=False
        )
        self.assertNotIn("link", card_home)

        card_typed = CardService.project(
            CARD_TYPE_NOTIFICATIONS, source, notification_link=True
        )
        self.assertEqual(card_typed["link"], f"discovery/notification/{source_id}")

    def test_project_typed_sources_use_enum_values(self):
        expected = {
            CARD_TYPE_MEMBERS: "Member",
            CARD_TYPE_MENTEES: "Mentee",
            CARD_TYPE_NOTIFICATIONS: "Notification",
            CARD_TYPE_PATHS: "Path",
            CARD_TYPE_PLANS: "Plan",
            CARD_TYPE_RESOURCES: "Resource",
        }

        for card_type, enum_value in expected.items():
            with self.subTest(card_type=card_type):
                card = CardService.project(card_type, {"_id": ObjectId(), "name": "n"})
                self.assertEqual(card["type"], enum_value)
                self.assertIn(card["type"], CARD_TYPE_ENUM)

    def test_project_omits_type_for_sources_without_enum_value(self):
        for card_type in (CARD_TYPE_CUSTOMER, CARD_TYPE_PRODUCTS, CARD_TYPE_SETTINGS):
            with self.subTest(card_type=card_type):
                card = CardService.project(card_type, {"_id": ObjectId(), "name": "n"})
                self.assertNotIn("type", card)
                self.assertTrue(set(card).issubset(CARD_PROPERTIES))

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

        self.addCleanup(config_patcher.stop)
        self.addCleanup(notifications_patcher.stop)
        self.addCleanup(members_patcher.stop)
        self.addCleanup(mentees_patcher.stop)

        config_patcher.start()
        self.mock_notifications = notifications_patcher.start()
        self.mock_members = members_patcher.start()
        self.mock_mentees = mentees_patcher.start()

        self.mock_notifications.return_value = []
        self.mock_members.return_value = []
        self.mock_mentees.return_value = []


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

    def test_notifications_scoped_to_token_profile_id(self):
        CardService.get_home_cards(token(profile_id=PROFILE_ID), BREADCRUMB)

        _, kwargs = self.mock_notifications.call_args
        self.assertEqual(kwargs["match"], {"profile_id": PROFILE_ID})
        self.assertEqual(kwargs["offset"], 0)

    def test_notifications_skipped_without_profile_id(self):
        cards = CardService.get_home_cards(token(), BREADCRUMB)

        self.mock_notifications.assert_not_called()
        self.assertEqual(cards, [])


class TestHomeCardMembers(HomeCardsTestCase):
    """Section two: members for Customer or Coordinator callers."""

    def test_members_included_for_customer_role(self):
        self.mock_members.return_value = documents("member", 2)

        cards = CardService.get_home_cards(
            token(roles=["customer"], customer_id=CUSTOMER_ID), BREADCRUMB
        )

        self.assertEqual([card["type"] for card in cards], ["Member", "Member"])

    def test_members_included_for_coordinator_role(self):
        self.mock_members.return_value = documents("member", 1)

        cards = CardService.get_home_cards(
            token(roles=["coordinator"], customer_id=CUSTOMER_ID), BREADCRUMB
        )

        self.assertEqual(len(cards), 1)

    def test_members_omitted_without_customer_or_coordinator_role(self):
        self.mock_members.return_value = documents("member", 3)

        cards = CardService.get_home_cards(
            token(roles=["mentee"], customer_id=CUSTOMER_ID), BREADCRUMB
        )

        self.mock_members.assert_not_called()
        self.assertEqual(cards, [])

    def test_members_omitted_without_customer_id(self):
        self.mock_members.return_value = documents("member", 3)

        cards = CardService.get_home_cards(token(roles=["customer"]), BREADCRUMB)

        self.mock_members.assert_not_called()
        self.assertEqual(cards, [])


class TestHomeCardMentees(HomeCardsTestCase):
    """Section three: mentees for Mentor callers."""

    def test_mentees_included_for_mentor_role(self):
        self.mock_mentees.return_value = documents("mentee", 2)

        cards = CardService.get_home_cards(
            token(roles=["mentor"], mentor_id=MENTOR_ID), BREADCRUMB
        )

        self.assertEqual([card["type"] for card in cards], ["Mentee", "Mentee"])

    def test_mentees_omitted_without_mentor_role(self):
        self.mock_mentees.return_value = documents("mentee", 3)

        cards = CardService.get_home_cards(
            token(roles=["customer"], mentor_id=MENTOR_ID), BREADCRUMB
        )

        self.mock_mentees.assert_not_called()
        self.assertEqual(cards, [])

    def test_mentees_omitted_without_mentor_id(self):
        self.mock_mentees.return_value = documents("mentee", 3)

        cards = CardService.get_home_cards(token(roles=["mentor"]), BREADCRUMB)

        self.mock_mentees.assert_not_called()
        self.assertEqual(cards, [])


class TestHomeCardComposition(HomeCardsTestCase):
    """Ordering and pagination across the combined list."""

    def setUp(self):
        super().setUp()
        self.mock_notifications.return_value = [
            {"_id": ObjectId(), "name": "note-0", "message": "m0"},
            {"_id": ObjectId(), "name": "note-1", "message": "m1"},
        ]
        self.mock_members.return_value = documents("member", 2)
        self.mock_mentees.return_value = documents("mentee", 2)
        self.token = token(
            roles=["customer", "mentor"],
            profile_id=PROFILE_ID,
            customer_id=CUSTOMER_ID,
            mentor_id=MENTOR_ID,
        )

    def test_sections_concatenate_in_order(self):
        cards = CardService.get_home_cards(self.token, BREADCRUMB)

        self.assertEqual(
            [card["type"] for card in cards],
            ["Notification", "Notification", "Member", "Member", "Mentee", "Mentee"],
        )

    def test_offset_and_size_slice_the_combined_list(self):
        cards = CardService.get_home_cards(self.token, BREADCRUMB, offset=1, size=3)

        self.assertEqual(len(cards), 3)
        self.assertEqual(
            [card["type"] for card in cards], ["Notification", "Member", "Member"]
        )

    def test_offset_past_the_end_returns_empty(self):
        cards = CardService.get_home_cards(self.token, BREADCRUMB, offset=10, size=5)

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


class TypedCardListTestCase(unittest.TestCase):
    """Customer / Product / Setting lists have no shared service class."""

    def setUp(self):
        self.config = mock_config()

        config_patcher = patch(
            "src.services.card_service.Config.get_instance", return_value=self.config
        )
        query_patcher = patch("src.services.card_service.execute_list_query")

        self.addCleanup(config_patcher.stop)
        self.addCleanup(query_patcher.stop)

        config_patcher.start()
        self.mock_query = query_patcher.start()
        self.mock_query.return_value = documents("row", 2)


class TestCustomerCards(TypedCardListTestCase):
    def test_reads_the_customer_collection(self):
        CardService.get_customer_cards(
            token(roles=["customer"], customer_id=CUSTOMER_ID), BREADCRUMB
        )

        args, _ = self.mock_query.call_args
        self.assertEqual(args, ("Customer",))

    def test_projects_customer_cards_without_a_type(self):
        cards = CardService.get_customer_cards(
            token(roles=["customer"], customer_id=CUSTOMER_ID), BREADCRUMB
        )

        self.assertEqual(len(cards), 2)
        for card in cards:
            self.assertNotIn("type", card)
            self.assertTrue(set(card).issubset(CARD_PROPERTIES))

    def test_scopes_a_caller_without_a_customer_id_to_nothing(self):
        CardService.get_customer_cards(token(roles=["mentee"]), BREADCRUMB)

        _, kwargs = self.mock_query.call_args
        self.assertEqual(kwargs["match"]["_id"], {"$in": []})


class TestProductCards(TypedCardListTestCase):
    def test_reads_the_setting_collection_filtered_to_products(self):
        CardService.get_product_cards(token(roles=["customer"]), BREADCRUMB)

        args, kwargs = self.mock_query.call_args
        self.assertEqual(args, ("Setting",))
        self.assertEqual(kwargs["match"].get("type"), SETTING_TYPE_PRODUCT)

    def test_product_discriminator_survives_the_admin_outbound_scope(self):
        CardService.get_product_cards(token(roles=["admin"]), BREADCRUMB)

        _, kwargs = self.mock_query.call_args
        self.assertEqual(kwargs["match"], {"type": SETTING_TYPE_PRODUCT})

    def test_projects_product_cards_without_a_type(self):
        cards = CardService.get_product_cards(token(roles=["customer"]), BREADCRUMB)

        for card in cards:
            self.assertNotIn("type", card)


class TestSettingsCards(TypedCardListTestCase):
    def test_reads_every_setting_variant(self):
        CardService.get_settings_cards(token(roles=["customer"]), BREADCRUMB)

        args, kwargs = self.mock_query.call_args
        self.assertEqual(args, ("Setting",))
        self.assertNotIn("type", kwargs["match"])

    def test_projects_settings_cards_without_a_type(self):
        cards = CardService.get_settings_cards(token(roles=["customer"]), BREADCRUMB)

        self.assertEqual(len(cards), 2)
        for card in cards:
            self.assertNotIn("type", card)


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
        MemberCardService,
        "get_profiles",
        "src.services.profile_service.ProfileService.get_member_profiles",
        "Member",
    ),
    (
        MenteeCardService,
        "get_profiles",
        "src.services.profile_service.ProfileService.get_mentee_profiles",
        "Mentee",
    ),
]


# (Card subclass, inherited by-id read the suppressed routes used to call).
CARD_SUBCLASS_BY_ID_GETTERS = [
    (ResourceCardService, "get_resource"),
    (PathCardService, "get_path"),
    (PlanCardService, "get_plan"),
    (MemberCardService, "get_profile"),
    (MenteeCardService, "get_profile"),
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

                args, _ = mock_source.call_args
                self.assertEqual(args[-4:], (5, 10, {"name": "a"}, sort_by))

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


if __name__ == "__main__":
    unittest.main()
