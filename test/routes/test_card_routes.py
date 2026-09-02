"""
Unit tests for the Discovery Card routes.

The route layer is HTTP only: read the token, build the breadcrumb, parse the
list request, call the service, and return the array unchanged. Services and
the token/breadcrumb helpers are mocked, so no database or JWT is required.

`GET /api/cards` is the composite home list.
Typed lists other than notifications are shared `create_*_get_routes` factories
bound to Card-projecting service subclasses. Notification cards have a local
list-only factory (see `test_notification_card_routes.py`). Several shared
factories also mount a GET by-id rule the Card contract does not include, so
`register_list_only_blueprint` is covered here too.
"""

import unittest
from unittest.mock import patch

from flask import Flask

from api_utils.flask_utils.exceptions import HTTPUnauthorized
from api_utils.mongo_utils.list_query import DEFAULT_OFFSET, DEFAULT_SIZE, MAX_SIZE
from api_utils.routes.shared_get_routes import (
    create_event_get_routes,
    create_path_get_routes,
    create_plan_get_routes,
    create_resource_get_routes,
)

from src.routes.card_routes import (
    create_cards_get_routes,
    register_list_only_blueprint,
)
from src.services.event_service import EventCardService
from src.services.path_service import PathCardService
from src.services.plan_service import PlanCardService
from src.services.resource_service import ResourceCardService

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


TYPED_CARDS = [
    {"_id": "665f1c2a9b1e4c0a1b2c3d20", "name": "One", "description": "First"}
]

# Shared-factory typed lists: (path segment, factory, service class, list method).
SHARED_TYPED_LISTS = [
    ("resources", create_resource_get_routes, ResourceCardService, "get_resources"),
    ("paths", create_path_get_routes, PathCardService, "get_paths"),
    ("plans", create_plan_get_routes, PlanCardService, "get_plans"),
    ("events", create_event_get_routes, EventCardService, "get_events"),
]

# The shared factories above that also mount a GET by-id rule, which Discovery
# suppresses: (path segment, factory, service class).
BY_ID_SHARED_TYPED_LISTS = [
    (segment, factory, service_cls)
    for segment, factory, service_cls, _ in SHARED_TYPED_LISTS
    if segment not in ("notifications", "events")
]

CARD_ID = "665f1c2a9b1e4c0a1b2c3d21"


class TestSharedFactoryTypedCardLists(unittest.TestCase):
    """The shared GET factories return whatever the Card subclass hands back."""

    def setUp(self):
        token_patcher = patch(
            "api_utils.routes.shared_get_routes.create_flask_token", return_value=TOKEN
        )
        breadcrumb_patcher = patch(
            "api_utils.routes.shared_get_routes.create_flask_breadcrumb",
            return_value=BREADCRUMB,
        )

        self.addCleanup(token_patcher.stop)
        self.addCleanup(breadcrumb_patcher.stop)

        self.mock_token = token_patcher.start()
        breadcrumb_patcher.start()

    def _client(self, factory, service_cls, segment):
        app = Flask(__name__)
        app.register_blueprint(
            factory(service_cls, name=f"{segment}_card_routes"),
            url_prefix=f"/api/cards/{segment}",
        )
        return app.test_client()

    def _patch_list(self, service_cls, method_name):
        patcher = patch.object(service_cls, method_name)
        self.addCleanup(patcher.stop)
        return patcher.start()

    def test_returns_200_with_an_array_body(self):
        for segment, factory, service_cls, method_name in SHARED_TYPED_LISTS:
            with self.subTest(segment=segment):
                self._patch_list(service_cls, method_name).return_value = TYPED_CARDS

                client = self._client(factory, service_cls, segment)
                response = client.get(f"/api/cards/{segment}")

                self.assertEqual(response.status_code, 200)
                body = response.get_json()
                self.assertIsInstance(body, list)
                self.assertEqual(body, TYPED_CARDS)

    def test_returns_an_empty_array_when_the_service_has_nothing(self):
        for segment, factory, service_cls, method_name in SHARED_TYPED_LISTS:
            with self.subTest(segment=segment):
                self._patch_list(service_cls, method_name).return_value = []

                client = self._client(factory, service_cls, segment)
                response = client.get(f"/api/cards/{segment}")

                self.assertEqual(response.status_code, 200)
                self.assertEqual(response.get_json(), [])

    def test_returns_401_without_a_token(self):
        self.mock_token.side_effect = HTTPUnauthorized("Missing Authorization header")

        for segment, factory, service_cls, method_name in SHARED_TYPED_LISTS:
            with self.subTest(segment=segment):
                mock_list = self._patch_list(service_cls, method_name)

                client = self._client(factory, service_cls, segment)
                response = client.get(f"/api/cards/{segment}")

                self.assertEqual(response.status_code, 401)
                self.assertIn("error", response.get_json())
                mock_list.assert_not_called()

    def test_passes_the_token_breadcrumb_and_pagination(self):
        for segment, factory, service_cls, method_name in SHARED_TYPED_LISTS:
            with self.subTest(segment=segment):
                mock_list = self._patch_list(service_cls, method_name)
                mock_list.return_value = TYPED_CARDS

                client = self._client(factory, service_cls, segment)
                client.get(
                    f"/api/cards/{segment}", headers={"offset": "5", "size": "10"}
                )

                args, kwargs = mock_list.call_args
                self.assertEqual(args[:2], (TOKEN, BREADCRUMB))
                pagination = args[2:4] or (kwargs.get("offset"), kwargs.get("size"))
                self.assertEqual(tuple(pagination), (5, 10))

    def test_returns_400_for_pagination_outside_the_allowed_range(self):
        for segment, factory, service_cls, method_name in SHARED_TYPED_LISTS:
            with self.subTest(segment=segment):
                mock_list = self._patch_list(service_cls, method_name)

                client = self._client(factory, service_cls, segment)
                response = client.get(
                    f"/api/cards/{segment}", headers={"size": str(MAX_SIZE + 1)}
                )

                self.assertEqual(response.status_code, 400)
                mock_list.assert_not_called()


class TestListOnlyBlueprintRegistration(unittest.TestCase):
    """A shared GET factory mounts its list rule only, never its by-id rule."""

    def _register(self, factory, service_cls, segment):
        app = Flask(__name__)
        register_list_only_blueprint(
            app,
            factory(service_cls, name=f"{segment}_card_routes"),
            f"/api/cards/{segment}",
        )
        return app

    def test_mounts_the_list_rule(self):
        for segment, factory, service_cls in BY_ID_SHARED_TYPED_LISTS:
            with self.subTest(segment=segment):
                app = self._register(factory, service_cls, segment)

                rules = [rule.rule for rule in app.url_map.iter_rules()]
                self.assertIn(f"/api/cards/{segment}", rules)

    def test_drops_the_by_id_rule(self):
        for segment, factory, service_cls in BY_ID_SHARED_TYPED_LISTS:
            with self.subTest(segment=segment):
                app = self._register(factory, service_cls, segment)

                rules = [rule.rule for rule in app.url_map.iter_rules()]
                self.assertFalse(
                    any(rule.startswith(f"/api/cards/{segment}/") for rule in rules),
                    f"by-id rule survived for {segment}: {rules}",
                )

    def test_drops_the_by_id_view_function(self):
        for segment, factory, service_cls in BY_ID_SHARED_TYPED_LISTS:
            with self.subTest(segment=segment):
                app = self._register(factory, service_cls, segment)

                endpoints = [
                    endpoint
                    for endpoint in app.view_functions
                    if endpoint.startswith(f"{segment}_card_routes.")
                ]
                self.assertEqual(len(endpoints), 1, f"Unexpected views: {endpoints}")

    def test_a_by_id_request_is_404(self):
        for segment, factory, service_cls in BY_ID_SHARED_TYPED_LISTS:
            with self.subTest(segment=segment):
                client = self._register(factory, service_cls, segment).test_client()

                response = client.get(f"/api/cards/{segment}/{CARD_ID}")

                self.assertEqual(response.status_code, 404)

    def test_leaves_a_list_only_blueprint_intact(self):
        app = Flask(__name__)
        register_list_only_blueprint(
            app,
            create_event_get_routes(EventCardService, name="event_card_routes"),
            "/api/cards/events",
        )

        rules = [rule.rule for rule in app.url_map.iter_rules()]
        self.assertIn("/api/cards/events", rules)

    def test_restores_add_url_rule_for_later_registrations(self):
        app = self._register(
            create_resource_get_routes, ResourceCardService, "resources"
        )

        app.register_blueprint(
            create_resource_get_routes(ResourceCardService, name="plain_routes"),
            url_prefix="/plain",
        )

        rules = [rule.rule for rule in app.url_map.iter_rules()]
        self.assertIn("/plain/<resource_id>", rules)


if __name__ == "__main__":
    unittest.main()
