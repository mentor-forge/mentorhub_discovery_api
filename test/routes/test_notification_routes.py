"""
Unit tests for the Discovery Notification control routes.

The route layer is HTTP only: read the token, build the breadcrumb, call
`NotificationService`, and return the document unchanged. The service methods
and the token / breadcrumb helpers are mocked, so no database or JWT is
required.

The bound service matters here. Create, dismiss, and cancel go to
`NotificationService` and return Notification documents; the Card projection
belongs to `NotificationCardService` and `GET /api/cards/notifications`.
"""

import unittest
from unittest.mock import patch

from flask import Flask

from api_utils.flask_utils.exceptions import (
    HTTPForbidden,
    HTTPNotFound,
    HTTPUnauthorized,
)

from src.routes.notification_routes import create_notification_routes

NOTIFICATION_ID = "665f1c2a9b1e4c0a1b2c3d4e"

TOKEN = {
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

NEW_NOTIFICATION = {
    "name": "welcome",
    "message": "Welcome to Mentor Hub",
    "profile_id": "665f1c2a9b1e4c0a1b2c3d01",
}

# What the service returns: a Notification document, not a Card.
NOTIFICATION = {
    "_id": NOTIFICATION_ID,
    "name": "welcome",
    "message": "Welcome to Mentor Hub",
    "profile_id": "665f1c2a9b1e4c0a1b2c3d01",
    "status": "active",
    "created": BREADCRUMB,
}

DISMISSED_NOTIFICATION = {**NOTIFICATION, "dismissed": BREADCRUMB}
CANCELLED_NOTIFICATION = {**NOTIFICATION, "cancelled": BREADCRUMB}

# Card properties that must never appear on a control response.
CARD_ONLY_PROPERTIES = {"type", "link"}


class NotificationRoutesTestCase(unittest.TestCase):
    """Mount the blueprint on a throwaway app with the service mocked."""

    def setUp(self):
        token_patcher = patch(
            "src.routes.notification_routes.create_flask_token", return_value=TOKEN
        )
        breadcrumb_patcher = patch(
            "src.routes.notification_routes.create_flask_breadcrumb",
            return_value=BREADCRUMB,
        )
        create_patcher = patch(
            "src.routes.notification_routes.NotificationService.create_notification"
        )
        dismiss_patcher = patch(
            "src.routes.notification_routes.NotificationService.dismiss_notification"
        )
        cancel_patcher = patch(
            "src.routes.notification_routes.NotificationService.cancel_notification"
        )

        for patcher in (
            token_patcher,
            breadcrumb_patcher,
            create_patcher,
            dismiss_patcher,
            cancel_patcher,
        ):
            self.addCleanup(patcher.stop)

        self.mock_token = token_patcher.start()
        self.mock_breadcrumb = breadcrumb_patcher.start()
        self.mock_create = create_patcher.start()
        self.mock_dismiss = dismiss_patcher.start()
        self.mock_cancel = cancel_patcher.start()

        self.mock_create.return_value = NOTIFICATION
        self.mock_dismiss.return_value = DISMISSED_NOTIFICATION
        self.mock_cancel.return_value = CANCELLED_NOTIFICATION

        app = Flask(__name__)
        app.register_blueprint(
            create_notification_routes(), url_prefix="/api/notification"
        )
        self.client = app.test_client()

    def dismiss(self, notification_id=NOTIFICATION_ID):
        return self.client.post(f"/api/notification/dismiss/{notification_id}")

    def cancel(self, notification_id=NOTIFICATION_ID):
        return self.client.post(f"/api/notification/cancel/{notification_id}")

    def create(self, json=None):
        return self.client.post(
            "/api/notification", json=NEW_NOTIFICATION if json is None else json
        )


class TestCreateNotification(NotificationRoutesTestCase):
    """POST /api/notification creates and returns the Notification."""

    def test_returns_201_with_the_created_document(self):
        response = self.create()

        self.assertEqual(response.status_code, 201)
        self.assertEqual(response.get_json(), NOTIFICATION)

    def test_calls_the_service_with_body_token_and_breadcrumb(self):
        self.create()

        args, kwargs = self.mock_create.call_args
        self.assertEqual(args, (NEW_NOTIFICATION, TOKEN, BREADCRUMB))
        self.assertEqual(kwargs, {})

    def test_builds_the_breadcrumb_from_the_token(self):
        self.create()

        self.mock_token.assert_called_once_with()
        self.mock_breadcrumb.assert_called_once_with(TOKEN)

    def test_returns_a_notification_document_not_a_card(self):
        response = self.create()

        body = response.get_json()
        self.assertEqual(body["_id"], NOTIFICATION_ID)
        self.assertIn("message", body)
        self.assertFalse(CARD_ONLY_PROPERTIES.intersection(body))

    def test_route_does_not_reshape_the_service_payload(self):
        self.mock_create.return_value = {"_id": NOTIFICATION_ID, "global": BREADCRUMB}

        response = self.create()

        self.assertEqual(
            response.get_json(), {"_id": NOTIFICATION_ID, "global": BREADCRUMB}
        )

    def test_returns_400_when_the_body_is_not_a_json_object(self):
        response = self.client.post("/api/notification", data="not json")

        self.assertEqual(response.status_code, 400)
        self.assertIn("error", response.get_json())
        self.mock_create.assert_not_called()

    def test_returns_401_without_a_token(self):
        self.mock_token.side_effect = HTTPUnauthorized("Missing Authorization header")

        response = self.create()

        self.assertEqual(response.status_code, 401)
        self.assertIn("error", response.get_json())
        self.mock_create.assert_not_called()

    def test_returns_500_when_the_service_fails(self):
        self.mock_create.side_effect = Exception("boom")

        response = self.create()

        self.assertEqual(response.status_code, 500)
        self.assertIn("error", response.get_json())

    def test_get_is_not_allowed(self):
        response = self.client.get("/api/notification")

        self.assertEqual(response.status_code, 405)


class TestDismissNotification(NotificationRoutesTestCase):
    """POST /api/notification/dismiss/<id> sets the dismissed breadcrumb."""

    def test_returns_200_with_the_updated_document(self):
        response = self.dismiss()

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.get_json(), DISMISSED_NOTIFICATION)

    def test_calls_the_service_with_id_token_and_breadcrumb(self):
        self.dismiss()

        args, kwargs = self.mock_dismiss.call_args
        self.assertEqual(args, (NOTIFICATION_ID, TOKEN, BREADCRUMB))
        self.assertEqual(kwargs, {})

    def test_returns_a_notification_document_not_a_card(self):
        body = self.dismiss().get_json()

        self.assertIn("dismissed", body)
        self.assertFalse(CARD_ONLY_PROPERTIES.intersection(body))

    def test_returns_401_without_a_token(self):
        self.mock_token.side_effect = HTTPUnauthorized("Missing Authorization header")

        response = self.dismiss()

        self.assertEqual(response.status_code, 401)
        self.mock_dismiss.assert_not_called()

    def test_returns_403_when_the_caller_may_not_dismiss(self):
        self.mock_dismiss.side_effect = HTTPForbidden(
            "Not permitted to dismiss this notification"
        )

        response = self.dismiss()

        self.assertEqual(response.status_code, 403)
        self.assertIn("error", response.get_json())

    def test_returns_404_for_a_missing_or_hidden_id(self):
        self.mock_dismiss.side_effect = HTTPNotFound("Notification not found")

        response = self.dismiss()

        self.assertEqual(response.status_code, 404)
        self.assertIn("error", response.get_json())

    def test_returns_500_when_the_service_fails(self):
        self.mock_dismiss.side_effect = Exception("boom")

        response = self.dismiss()

        self.assertEqual(response.status_code, 500)


class TestCancelNotification(NotificationRoutesTestCase):
    """POST /api/notification/cancel/<id> sets the cancelled breadcrumb."""

    def test_returns_200_with_the_updated_document(self):
        response = self.cancel()

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.get_json(), CANCELLED_NOTIFICATION)

    def test_calls_the_service_with_id_token_and_breadcrumb(self):
        self.cancel()

        args, kwargs = self.mock_cancel.call_args
        self.assertEqual(args, (NOTIFICATION_ID, TOKEN, BREADCRUMB))
        self.assertEqual(kwargs, {})

    def test_returns_a_notification_document_not_a_card(self):
        body = self.cancel().get_json()

        self.assertIn("cancelled", body)
        self.assertFalse(CARD_ONLY_PROPERTIES.intersection(body))

    def test_returns_401_without_a_token(self):
        self.mock_token.side_effect = HTTPUnauthorized("Missing Authorization header")

        response = self.cancel()

        self.assertEqual(response.status_code, 401)
        self.mock_cancel.assert_not_called()

    def test_returns_403_when_the_caller_may_not_cancel(self):
        self.mock_cancel.side_effect = HTTPForbidden(
            "Not permitted to cancel this notification"
        )

        response = self.cancel()

        self.assertEqual(response.status_code, 403)

    def test_returns_404_for_a_missing_or_hidden_id(self):
        self.mock_cancel.side_effect = HTTPNotFound("Notification not found")

        response = self.cancel()

        self.assertEqual(response.status_code, 404)

    def test_dismiss_and_cancel_do_not_share_a_service_method(self):
        self.cancel()

        self.mock_cancel.assert_called_once()
        self.mock_dismiss.assert_not_called()


class TestControlRoutesBindTheControlService(unittest.TestCase):
    """The blueprint calls NotificationService, never the Card projector."""

    def test_module_imports_the_control_service(self):
        from src.routes import notification_routes
        from src.services.notification_service import (
            NotificationCardService,
            NotificationService,
        )

        self.assertIs(notification_routes.NotificationService, NotificationService)
        self.assertIsNot(
            notification_routes.NotificationService, NotificationCardService
        )

    def test_registered_rules_match_the_openapi_paths(self):
        app = Flask(__name__)
        app.register_blueprint(
            create_notification_routes(), url_prefix="/api/notification"
        )

        rules = {rule.rule for rule in app.url_map.iter_rules()}

        self.assertIn("/api/notification", rules)
        self.assertIn("/api/notification/dismiss/<notification_id>", rules)
        self.assertIn("/api/notification/cancel/<notification_id>", rules)


if __name__ == "__main__":
    unittest.main()
