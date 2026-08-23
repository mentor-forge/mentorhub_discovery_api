"""
Unit tests for the Discovery Card routes.

The route layer is HTTP only: read the token, build the breadcrumb, parse the
pagination headers, call `CardService.get_home_cards`, and return the array
unchanged. The service and the token/breadcrumb helpers are mocked, so no
database or JWT is required.
"""

import unittest
from unittest.mock import patch

from flask import Flask

from api_utils.flask_utils.exceptions import HTTPUnauthorized
from api_utils.mongo_utils.list_query import DEFAULT_OFFSET, DEFAULT_SIZE, MAX_SIZE

from src.routes.card_routes import create_cards_get_routes

TOKEN = {
    "user_id": "test-user",
    "roles": ["customer", "mentor"],
    "profile_id": "665f1c2a9b1e4c0a1b2c3d01",
    "customer_id": "665f1c2a9b1e4c0a1b2c3d03",
    "mentor_id": "665f1c2a9b1e4c0a1b2c3d04",
}

BREADCRUMB = {
    "from_ip": "127.0.0.1",
    "by_user": "test-user",
    "at_time": "2026-08-23T12:00:00",
    "correlation_id": "test-correlation",
}

HOME_CARDS = [
    {
        "_id": "665f1c2a9b1e4c0a1b2c3d10",
        "name": "welcome",
        "description": "Hello",
        "type": "Notification",
    },
    {"_id": "665f1c2a9b1e4c0a1b2c3d11", "name": "Jane Doe", "type": "Member"},
]


class CardRoutesTestCase(unittest.TestCase):
    """Mount the blueprint on a throwaway app with the HTTP helpers mocked."""

    def setUp(self):
        token_patcher = patch(
            "src.routes.card_routes.create_flask_token", return_value=TOKEN
        )
        breadcrumb_patcher = patch(
            "src.routes.card_routes.create_flask_breadcrumb", return_value=BREADCRUMB
        )
        service_patcher = patch("src.routes.card_routes.CardService.get_home_cards")

        self.addCleanup(token_patcher.stop)
        self.addCleanup(breadcrumb_patcher.stop)
        self.addCleanup(service_patcher.stop)

        self.mock_token = token_patcher.start()
        self.mock_breadcrumb = breadcrumb_patcher.start()
        self.mock_get_home_cards = service_patcher.start()
        self.mock_get_home_cards.return_value = HOME_CARDS

        app = Flask(__name__)
        app.register_blueprint(create_cards_get_routes(), url_prefix="/api/cards")
        self.client = app.test_client()


class TestGetHomeCards(CardRoutesTestCase):
    """GET /api/cards returns the composite home array."""

    def test_returns_200_with_an_array_body(self):
        response = self.client.get("/api/cards")

        self.assertEqual(response.status_code, 200)
        body = response.get_json()
        self.assertIsInstance(body, list)
        self.assertEqual(body, HOME_CARDS)

    def test_returns_an_empty_array_when_the_service_has_nothing(self):
        self.mock_get_home_cards.return_value = []

        response = self.client.get("/api/cards")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.get_json(), [])

    def test_calls_the_service_with_token_breadcrumb_and_pagination(self):
        self.client.get("/api/cards", headers={"offset": "5", "size": "10"})

        args, kwargs = self.mock_get_home_cards.call_args
        self.assertEqual(args, (TOKEN, BREADCRUMB, 5, 10))
        self.assertEqual(kwargs, {})

    def test_defaults_pagination_when_the_headers_are_absent(self):
        self.client.get("/api/cards")

        args, _ = self.mock_get_home_cards.call_args
        self.assertEqual(args[2:], (DEFAULT_OFFSET, DEFAULT_SIZE))

    def test_builds_the_breadcrumb_from_the_token(self):
        self.client.get("/api/cards")

        self.mock_token.assert_called_once_with()
        self.mock_breadcrumb.assert_called_once_with(TOKEN)

    def test_route_does_not_reshape_the_service_payload(self):
        card = {"_id": "665f1c2a9b1e4c0a1b2c3d12", "name": "As-is", "type": "Path"}
        self.mock_get_home_cards.return_value = [card]

        response = self.client.get("/api/cards")

        self.assertEqual(response.get_json(), [card])


class TestGetHomeCardsErrors(CardRoutesTestCase):
    """Failures map through handle_route_exceptions."""

    def test_returns_401_when_the_token_is_missing_or_invalid(self):
        self.mock_token.side_effect = HTTPUnauthorized(
            "Missing or invalid Authorization header"
        )

        response = self.client.get("/api/cards")

        self.assertEqual(response.status_code, 401)
        self.assertIn("error", response.get_json())
        self.mock_get_home_cards.assert_not_called()

    def test_returns_400_for_pagination_outside_the_allowed_range(self):
        response = self.client.get("/api/cards", headers={"size": str(MAX_SIZE + 1)})

        self.assertEqual(response.status_code, 400)
        self.assertIn("error", response.get_json())
        self.mock_get_home_cards.assert_not_called()

    def test_returns_500_when_the_service_fails(self):
        self.mock_get_home_cards.side_effect = Exception("boom")

        response = self.client.get("/api/cards")

        self.assertEqual(response.status_code, 500)
        self.assertIn("error", response.get_json())


if __name__ == "__main__":
    unittest.main()
