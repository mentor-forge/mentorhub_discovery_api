"""
Unit tests for GET /api/cards/notifications.

The local list-only factory parses pagination and admin-only name/status
filters, then hands off to NotificationCardService. RBAC lives in the service;
the route still maps HTTPForbidden to 403 and missing tokens to 401. There is
no by-id GET.
"""

import unittest
from unittest.mock import patch

from flask import Flask

from api_utils.flask_utils.exceptions import HTTPUnauthorized
from api_utils.mongo_utils.list_query import DEFAULT_OFFSET, DEFAULT_SIZE, MAX_SIZE

from src.routes.card_routes import create_notification_card_get_routes
from src.services.notification_service import NotificationCardService

ADMIN_TOKEN = {
    "user_id": "admin-user",
    "roles": ["admin"],
    "profile_id": "665f1c2a9b1e4c0a1b2c3d01",
}

NON_ADMIN_TOKEN = {
    "user_id": "test-user",
    "roles": ["mentee"],
    "profile_id": "665f1c2a9b1e4c0a1b2c3d01",
}

BREADCRUMB = {
    "from_ip": "127.0.0.1",
    "by_user": "test-user",
    "at_time": "2026-08-23T12:00:00",
    "correlation_id": "test-correlation",
}

NOTIFICATION_CARDS = [
    {
        "_id": "665f1c2a9b1e4c0a1b2c3d20",
        "name": "Invite",
        "type": "Notification",
        "link": "discovery/notification/665f1c2a9b1e4c0a1b2c3d20",
    }
]

CARD_ID = "665f1c2a9b1e4c0a1b2c3d21"


class NotificationCardRoutesTestCase(unittest.TestCase):
    """Mount the local factory with token/breadcrumb helpers mocked."""

    token = ADMIN_TOKEN

    def setUp(self):
        token_patcher = patch(
            "src.routes.card_routes.create_flask_token", return_value=self.token
        )
        breadcrumb_patcher = patch(
            "src.routes.card_routes.create_flask_breadcrumb", return_value=BREADCRUMB
        )

        self.addCleanup(token_patcher.stop)
        self.addCleanup(breadcrumb_patcher.stop)

        self.mock_token = token_patcher.start()
        breadcrumb_patcher.start()

        app = Flask(__name__)
        app.register_blueprint(
            create_notification_card_get_routes(),
            url_prefix="/api/cards/notifications",
        )
        self.client = app.test_client()


class TestGetNotificationCards(NotificationCardRoutesTestCase):
    """Admin callers: parsed filters are forwarded to the service."""

    def setUp(self):
        super().setUp()
        service_patcher = patch.object(NotificationCardService, "get_notifications")
        self.addCleanup(service_patcher.stop)
        self.mock_list = service_patcher.start()
        self.mock_list.return_value = NOTIFICATION_CARDS

    def test_returns_200_with_an_array_body(self):
        response = self.client.get("/api/cards/notifications")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.get_json(), NOTIFICATION_CARDS)

    def test_returns_an_empty_array_when_the_service_has_nothing(self):
        self.mock_list.return_value = []

        response = self.client.get("/api/cards/notifications")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.get_json(), [])

    def test_passes_parsed_name_filter(self):
        self.client.get("/api/cards/notifications?name=Invite")

        _, kwargs = self.mock_list.call_args
        self.assertEqual(kwargs["filters"], {"name": "Invite"})

    def test_passes_parsed_status_in_list_filter(self):
        self.client.get("/api/cards/notifications?status=active,archived")

        _, kwargs = self.mock_list.call_args
        self.assertEqual(kwargs["filters"], {"status": ["active", "archived"]})

    def test_passes_combined_name_and_status_filters(self):
        self.client.get("/api/cards/notifications?name=Invite&status=active")

        _, kwargs = self.mock_list.call_args
        self.assertEqual(kwargs["filters"], {"name": "Invite", "status": ["active"]})

    def test_preserves_empty_name_param_for_service_rbac(self):
        self.client.get("/api/cards/notifications?name=")

        _, kwargs = self.mock_list.call_args
        self.assertIn("name", kwargs["filters"])

    def test_passes_token_breadcrumb_and_pagination(self):
        self.client.get(
            "/api/cards/notifications", headers={"offset": "5", "size": "10"}
        )

        args, kwargs = self.mock_list.call_args
        self.assertEqual(args[:2], (ADMIN_TOKEN, BREADCRUMB))
        self.assertEqual(kwargs["offset"], 5)
        self.assertEqual(kwargs["size"], 10)

    def test_defaults_pagination_when_the_headers_are_absent(self):
        self.client.get("/api/cards/notifications")

        _, kwargs = self.mock_list.call_args
        self.assertEqual(kwargs["offset"], DEFAULT_OFFSET)
        self.assertEqual(kwargs["size"], DEFAULT_SIZE)

    def test_returns_400_for_pagination_outside_the_allowed_range(self):
        response = self.client.get(
            "/api/cards/notifications", headers={"size": str(MAX_SIZE + 1)}
        )

        self.assertEqual(response.status_code, 400)
        self.mock_list.assert_not_called()

    def test_returns_400_for_unsupported_sort_by(self):
        response = self.client.get("/api/cards/notifications?sort_by=name")

        self.assertEqual(response.status_code, 400)
        self.mock_list.assert_not_called()


class TestGetNotificationCardsForbidden(NotificationCardRoutesTestCase):
    """Non-admin tokens with name/status query params are 403 (service RBAC)."""

    token = NON_ADMIN_TOKEN

    def test_returns_403_when_non_admin_sends_name(self):
        response = self.client.get("/api/cards/notifications?name=Invite")

        self.assertEqual(response.status_code, 403)
        self.assertIn("error", response.get_json())

    def test_returns_403_when_non_admin_sends_status(self):
        response = self.client.get("/api/cards/notifications?status=active")

        self.assertEqual(response.status_code, 403)

    def test_returns_403_when_non_admin_sends_empty_name(self):
        response = self.client.get("/api/cards/notifications?name=")

        self.assertEqual(response.status_code, 403)


class TestGetNotificationCardsUnauthorized(NotificationCardRoutesTestCase):
    """Missing bearer is 401 before the service runs."""

    def test_returns_401_without_a_token(self):
        self.mock_token.side_effect = HTTPUnauthorized("Missing Authorization header")
        service_patcher = patch.object(NotificationCardService, "get_notifications")
        self.addCleanup(service_patcher.stop)
        mock_list = service_patcher.start()

        response = self.client.get("/api/cards/notifications")

        self.assertEqual(response.status_code, 401)
        self.assertIn("error", response.get_json())
        mock_list.assert_not_called()


class TestNotificationCardListOnly(unittest.TestCase):
    """The local factory mounts the list rule only."""

    def setUp(self):
        app = Flask(__name__)
        app.register_blueprint(
            create_notification_card_get_routes(),
            url_prefix="/api/cards/notifications",
        )
        self.app = app
        self.client = app.test_client()

    def test_mounts_the_list_rule(self):
        rules = [rule.rule for rule in self.app.url_map.iter_rules()]
        self.assertIn("/api/cards/notifications", rules)

    def test_has_no_by_id_rule(self):
        rules = [rule.rule for rule in self.app.url_map.iter_rules()]
        self.assertFalse(
            any(rule.startswith("/api/cards/notifications/") for rule in rules),
            f"by-id rule registered: {rules}",
        )

    def test_a_by_id_request_is_404(self):
        response = self.client.get(f"/api/cards/notifications/{CARD_ID}")
        self.assertEqual(response.status_code, 404)


if __name__ == "__main__":
    unittest.main()
