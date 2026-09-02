"""
Unit tests for the Discovery Notification service.

Dismiss and cancel each set exactly one breadcrumb field; missing and hidden
ids both surface as 404; MongoIO and Config are mocked so no database is
required.
"""

import unittest
from unittest.mock import MagicMock, patch

from bson import ObjectId

from api_utils.flask_utils.exceptions import HTTPForbidden, HTTPNotFound
from api_utils.services import NotificationService as SharedNotificationService
from src.services.notification_service import (
    CANCELLED_FIELD,
    DISMISSED_FIELD,
    NotificationCardService,
    NotificationService,
    active_match,
)

NOTIFICATION_ID = "665f1c2a9b1e4c0a1b2c3d4e"
PROFILE_ID = "665f1c2a9b1e4c0a1b2c3d01"
OTHER_PROFILE_ID = "665f1c2a9b1e4c0a1b2c3d02"
CUSTOMER_ID = "665f1c2a9b1e4c0a1b2c3d03"
MENTOR_ID = "665f1c2a9b1e4c0a1b2c3d04"

BREADCRUMB = {
    "from_ip": "127.0.0.1",
    "by_user": "test-user",
    "at_time": "2026-08-23T12:00:00",
    "correlation_id": "test-correlation",
}


def mock_config():
    """Config double carrying the real collection and role constants."""
    config = MagicMock()
    config.NOTIFICATION_COLLECTION_NAME = "Notification"
    config.ROLE_ADMIN = "admin"
    config.ROLE_CUSTOMER = "customer"
    config.ROLE_COORDINATOR = "coordinator"
    config.ROLE_MENTOR = "mentor"
    return config


def profile_token(profile_id=PROFILE_ID, roles=None):
    return {
        "user_id": "test-user",
        "profile_id": profile_id,
        "roles": roles if roles is not None else ["mentee"],
    }


def profile_notification(profile_id=PROFILE_ID):
    return {
        "_id": ObjectId(NOTIFICATION_ID),
        "name": "welcome",
        "message": "Welcome to Mentor Hub",
        "profile_id": ObjectId(profile_id),
        "status": "active",
    }


class NotificationServiceTestCase(unittest.TestCase):
    """Shared MongoIO / Config patching for the control mutations."""

    def setUp(self):
        self.mongo = MagicMock()
        self.config = mock_config()

        mongo_patcher = patch(
            "src.services.notification_service.MongoIO.get_instance",
            return_value=self.mongo,
        )
        config_patcher = patch(
            "src.services.notification_service.Config.get_instance",
            return_value=self.config,
        )
        self.addCleanup(mongo_patcher.stop)
        self.addCleanup(config_patcher.stop)
        mongo_patcher.start()
        config_patcher.start()


class TestSubclassSurface(unittest.TestCase):
    """The Discovery subclass inherits shared consume and create."""

    def test_subclasses_shared_service(self):
        self.assertTrue(issubclass(NotificationService, SharedNotificationService))

    def test_create_and_read_are_inherited(self):
        self.assertIs(
            NotificationService.create_notification.__func__,
            SharedNotificationService.create_notification.__func__,
        )
        self.assertIs(
            NotificationService.get_notifications.__func__,
            SharedNotificationService.get_notifications.__func__,
        )

    def test_dismiss_and_cancel_are_local_only(self):
        self.assertFalse(hasattr(SharedNotificationService, "dismiss_notification"))
        self.assertFalse(hasattr(SharedNotificationService, "cancel_notification"))
        self.assertTrue(hasattr(NotificationService, "dismiss_notification"))
        self.assertTrue(hasattr(NotificationService, "cancel_notification"))


class TestDismissNotification(NotificationServiceTestCase):
    """dismiss_notification sets only the dismissed breadcrumb."""

    def test_dismiss_sets_only_dismissed(self):
        self.mongo.get_document.return_value = profile_notification()
        self.mongo.update_document.return_value = {"_id": ObjectId(NOTIFICATION_ID)}

        NotificationService.dismiss_notification(
            NOTIFICATION_ID, profile_token(), BREADCRUMB
        )

        _, kwargs = self.mongo.update_document.call_args
        self.assertEqual(kwargs["set_data"], {DISMISSED_FIELD: BREADCRUMB})

    def test_dismiss_does_not_set_saved(self):
        self.mongo.get_document.return_value = profile_notification()

        NotificationService.dismiss_notification(
            NOTIFICATION_ID, profile_token(), BREADCRUMB
        )

        _, kwargs = self.mongo.update_document.call_args
        self.assertNotIn("saved", kwargs["set_data"])

    def test_dismiss_targets_the_notification_collection_by_id(self):
        self.mongo.get_document.return_value = profile_notification()

        NotificationService.dismiss_notification(
            NOTIFICATION_ID, profile_token(), BREADCRUMB
        )

        self.mongo.get_document.assert_called_once_with("Notification", NOTIFICATION_ID)
        args, _ = self.mongo.update_document.call_args
        self.assertEqual(args, ("Notification", NOTIFICATION_ID))

    def test_dismiss_returns_updated_document(self):
        updated = {"_id": ObjectId(NOTIFICATION_ID), DISMISSED_FIELD: BREADCRUMB}
        self.mongo.get_document.return_value = profile_notification()
        self.mongo.update_document.return_value = updated

        result = NotificationService.dismiss_notification(
            NOTIFICATION_ID, profile_token(), BREADCRUMB
        )

        self.assertEqual(result, updated)

    def test_dismiss_missing_id_raises_not_found(self):
        self.mongo.get_document.return_value = None

        with self.assertRaises(HTTPNotFound):
            NotificationService.dismiss_notification(
                NOTIFICATION_ID, profile_token(), BREADCRUMB
            )

        self.mongo.update_document.assert_not_called()

    def test_dismiss_hidden_id_raises_not_found(self):
        hidden = profile_notification(OTHER_PROFILE_ID)
        hidden["status"] = "archived"
        self.mongo.get_document.return_value = hidden

        with self.assertRaises(HTTPNotFound):
            NotificationService.dismiss_notification(
                NOTIFICATION_ID, profile_token(), BREADCRUMB
            )

        self.mongo.update_document.assert_not_called()

    def test_dismiss_another_profiles_notification_raises_not_found(self):
        # Outbound RBAC hides a notification targeting someone else, so the
        # caller gets 404 rather than a 403 that would confirm the id exists.
        self.mongo.get_document.return_value = profile_notification(OTHER_PROFILE_ID)

        with self.assertRaises(HTTPNotFound):
            NotificationService.dismiss_notification(
                NOTIFICATION_ID, profile_token(), BREADCRUMB
            )

        self.mongo.update_document.assert_not_called()

    def test_dismiss_allowed_for_customer_target(self):
        notification = {
            "_id": ObjectId(NOTIFICATION_ID),
            "name": "seats",
            "customer_id": ObjectId(CUSTOMER_ID),
            "status": "active",
        }
        self.mongo.get_document.return_value = notification
        token = {
            "user_id": "test-user",
            "customer_id": CUSTOMER_ID,
            "roles": ["customer"],
        }

        NotificationService.dismiss_notification(NOTIFICATION_ID, token, BREADCRUMB)

        _, kwargs = self.mongo.update_document.call_args
        self.assertEqual(kwargs["set_data"], {DISMISSED_FIELD: BREADCRUMB})

    def test_dismiss_allowed_for_mentor_target(self):
        notification = {
            "_id": ObjectId(NOTIFICATION_ID),
            "name": "encounter",
            "mentor_id": ObjectId(MENTOR_ID),
            "status": "active",
        }
        self.mongo.get_document.return_value = notification
        token = {"user_id": "test-user", "mentor_id": MENTOR_ID, "roles": ["mentor"]}

        NotificationService.dismiss_notification(NOTIFICATION_ID, token, BREADCRUMB)

        self.mongo.update_document.assert_called_once()

    def test_dismiss_allowed_for_admin(self):
        # Global notification: no target id, so only admin may retire it.
        notification = {
            "_id": ObjectId(NOTIFICATION_ID),
            "name": "release",
            "global": BREADCRUMB,
            "status": "active",
        }
        self.mongo.get_document.return_value = notification
        token = {"user_id": "admin-user", "roles": ["admin"]}

        NotificationService.dismiss_notification(NOTIFICATION_ID, token, BREADCRUMB)

        self.mongo.update_document.assert_called_once()

    def test_dismiss_forbidden_for_global_notification_without_admin(self):
        notification = {
            "_id": ObjectId(NOTIFICATION_ID),
            "name": "release",
            "global": BREADCRUMB,
            "status": "active",
        }
        self.mongo.get_document.return_value = notification

        with self.assertRaises(HTTPForbidden):
            NotificationService.dismiss_notification(
                NOTIFICATION_ID, profile_token(), BREADCRUMB
            )


class TestCancelNotification(NotificationServiceTestCase):
    """cancel_notification sets only the cancelled breadcrumb."""

    def test_cancel_sets_only_cancelled(self):
        self.mongo.get_document.return_value = profile_notification()

        NotificationService.cancel_notification(
            NOTIFICATION_ID, profile_token(), BREADCRUMB
        )

        _, kwargs = self.mongo.update_document.call_args
        self.assertEqual(kwargs["set_data"], {CANCELLED_FIELD: BREADCRUMB})

    def test_cancel_does_not_touch_dismissed_or_saved(self):
        self.mongo.get_document.return_value = profile_notification()

        NotificationService.cancel_notification(
            NOTIFICATION_ID, profile_token(), BREADCRUMB
        )

        _, kwargs = self.mongo.update_document.call_args
        self.assertNotIn(DISMISSED_FIELD, kwargs["set_data"])
        self.assertNotIn("saved", kwargs["set_data"])

    def test_cancel_missing_id_raises_not_found(self):
        self.mongo.get_document.return_value = None

        with self.assertRaises(HTTPNotFound):
            NotificationService.cancel_notification(
                NOTIFICATION_ID, profile_token(), BREADCRUMB
            )

    def test_cancel_forbidden_for_global_notification_without_admin(self):
        notification = {
            "_id": ObjectId(NOTIFICATION_ID),
            "name": "release",
            "global": BREADCRUMB,
            "status": "active",
        }
        self.mongo.get_document.return_value = notification

        with self.assertRaises(HTTPForbidden):
            NotificationService.cancel_notification(
                NOTIFICATION_ID, profile_token(), BREADCRUMB
            )

        self.mongo.update_document.assert_not_called()

    def test_cancel_another_profiles_notification_raises_not_found(self):
        self.mongo.get_document.return_value = profile_notification(OTHER_PROFILE_ID)

        with self.assertRaises(HTTPNotFound):
            NotificationService.cancel_notification(
                NOTIFICATION_ID, profile_token(), BREADCRUMB
            )

        self.mongo.update_document.assert_not_called()


class TestActiveNotifications(unittest.TestCase):
    """Active means neither breadcrumb is present."""

    def test_active_match_uses_breadcrumb_absence(self):
        self.assertEqual(
            active_match(),
            {
                DISMISSED_FIELD: {"$exists": False},
                CANCELLED_FIELD: {"$exists": False},
            },
        )

    def test_active_match_has_no_saved_field(self):
        self.assertNotIn("saved", active_match())

    @patch("src.services.notification_service.NotificationService.get_notifications")
    def test_get_active_notifications_delegates_with_active_match(self, mock_get):
        mock_get.return_value = []

        NotificationService.get_active_notifications(
            profile_token(), BREADCRUMB, offset=0, size=5
        )

        _, kwargs = mock_get.call_args
        self.assertEqual(kwargs["offset"], 0)
        self.assertEqual(kwargs["size"], 5)
        self.assertEqual(kwargs["match"][DISMISSED_FIELD], {"$exists": False})
        self.assertEqual(kwargs["match"][CANCELLED_FIELD], {"$exists": False})

    @patch("src.services.notification_service.NotificationService.get_notifications")
    def test_get_active_notifications_merges_caller_match(self, mock_get):
        mock_get.return_value = []

        NotificationService.get_active_notifications(
            profile_token(), BREADCRUMB, match={"profile_id": PROFILE_ID}
        )

        _, kwargs = mock_get.call_args
        self.assertEqual(kwargs["match"]["profile_id"], PROFILE_ID)
        self.assertEqual(kwargs["match"][DISMISSED_FIELD], {"$exists": False})


class TestNotificationCardFilters(unittest.TestCase):
    """Admin-only name/status filters on the Card list; projection stays Cards."""

    def setUp(self):
        self.notifications = [profile_notification()]
        patcher = patch(
            "api_utils.services.notification_service.NotificationService"
            ".get_notifications",
            return_value=self.notifications,
        )
        self.addCleanup(patcher.stop)
        self.mock_get = patcher.start()

    def test_admin_name_filter_is_applied_as_contains_match(self):
        cards = NotificationCardService.get_notifications(
            {"user_id": "admin-user", "roles": ["admin"]},
            BREADCRUMB,
            filters={"name": "Invite"},
        )

        _, kwargs = self.mock_get.call_args
        match = kwargs["match"]
        self.assertEqual(match["name"]["$regex"], "Invite")
        self.assertEqual(match["name"]["$options"], "i")
        self.assertEqual(cards[0]["type"], "Notification")
        self.assertEqual(
            cards[0]["link"],
            f"discovery/notification/{self.notifications[0]['_id']}",
        )

    def test_admin_status_filter_is_applied_as_in_list_match(self):
        NotificationCardService.get_notifications(
            {"user_id": "admin-user", "roles": ["admin"]},
            BREADCRUMB,
            filters={"status": ["active", "archived"]},
        )

        _, kwargs = self.mock_get.call_args
        self.assertEqual(kwargs["match"]["status"], {"$in": ["active", "archived"]})

    def test_admin_name_and_status_filters_and_together(self):
        NotificationCardService.get_notifications(
            {"user_id": "admin-user", "roles": ["admin"]},
            BREADCRUMB,
            filters={"name": "Invite", "status": ["active"]},
        )

        _, kwargs = self.mock_get.call_args
        match = kwargs["match"]
        self.assertEqual(match["name"]["$regex"], "Invite")
        self.assertEqual(match["status"], {"$in": ["active"]})

    def test_admin_empty_filter_values_do_not_become_match_clauses(self):
        NotificationCardService.get_notifications(
            {"user_id": "admin-user", "roles": ["admin"]},
            BREADCRUMB,
            filters={"name": "", "status": []},
        )

        _, kwargs = self.mock_get.call_args
        self.assertIsNone(kwargs.get("match"))

    def test_non_admin_with_name_filter_raises_forbidden_before_query(self):
        with self.assertRaises(HTTPForbidden):
            NotificationCardService.get_notifications(
                profile_token(), BREADCRUMB, filters={"name": "Invite"}
            )

        self.mock_get.assert_not_called()

    def test_non_admin_with_status_filter_raises_forbidden_before_query(self):
        with self.assertRaises(HTTPForbidden):
            NotificationCardService.get_notifications(
                profile_token(), BREADCRUMB, filters={"status": ["active"]}
            )

        self.mock_get.assert_not_called()

    def test_non_admin_with_empty_name_param_raises_forbidden(self):
        with self.assertRaises(HTTPForbidden):
            NotificationCardService.get_notifications(
                profile_token(), BREADCRUMB, filters={"name": ""}
            )

        self.mock_get.assert_not_called()

    def test_non_admin_without_filters_still_lists(self):
        cards = NotificationCardService.get_notifications(profile_token(), BREADCRUMB)

        self.mock_get.assert_called_once()
        _, kwargs = self.mock_get.call_args
        self.assertIsNone(kwargs.get("match"))
        self.assertEqual(cards[0]["type"], "Notification")
        self.assertEqual(
            cards[0]["link"],
            f"discovery/notification/{self.notifications[0]['_id']}",
        )

    def test_non_admin_filters_are_not_applied_even_if_rbac_were_skipped(self):
        """Least privilege: Coordinator/Mentor/Mentee must not search by name."""
        with self.assertRaises(HTTPForbidden):
            NotificationCardService.get_notifications(
                profile_token(roles=["coordinator"]),
                BREADCRUMB,
                filters={"name": "seats"},
            )

        self.mock_get.assert_not_called()


if __name__ == "__main__":
    unittest.main()
