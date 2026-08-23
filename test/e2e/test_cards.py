"""
E2E tests for the Card endpoints (consume-style, read-only).

These tests verify GET /api/cards against a running server by making actual
HTTP requests. An empty array is a valid composite home list, so the assertions
cover the contract — status, array body, Card shape — and the one test that
needs seeded documents skips when the persona has none.

To run these tests:
1. Start the server: pipenv run dev (or pipenv run api for containerized)
2. Run E2E tests: pipenv run e2e

API runs on port 8397 (same for dev and api).
"""

import pytest
import requests

from .e2e_auth import get_auth_token

BASE_URL = "http://localhost:8397"

# Card.yaml 0.0.0.0 (additionalProperties: false, nothing required).
CARD_PROPERTIES = {"_id", "name", "description", "link", "type"}

CARD_TYPE_ENUM = {
    "Event",
    "Member",
    "Mentee",
    "Notification",
    "Path",
    "Plan",
    "Resource",
}

# Developer Edition seed persona with a profile-scoped active Notification
# (Daniel the Mentee, Profile.0.1.0.0 / Notification test data).
NOTIFIED_PROFILE_ID = "A00000000000000000000002"
NOTIFIED_PROFILE_ROLES = ["mentee"]


def _err(response, expected):
    """Format assertion error with response body for debugging."""
    body = response.text[:300] if response.text else "(empty)"
    return f"Expected {expected}, got {response.status_code}. Response: {body}"


def _auth_headers(token=None, **extra):
    headers = {"Authorization": f"Bearer {token or get_auth_token()}"}
    headers.update(extra)
    return headers


def _assert_card_shape(cards):
    for card in cards:
        assert isinstance(card, dict), f"Card should be an object: {card}"
        assert set(card).issubset(CARD_PROPERTIES), f"Unexpected Card fields: {card}"
        if "type" in card:
            assert card["type"] in CARD_TYPE_ENUM, f"Unexpected Card type: {card}"


@pytest.mark.e2e
def test_get_home_cards_returns_an_array():
    """Test GET /api/cards returns a JSON array of Cards."""
    response = requests.get(f"{BASE_URL}/api/cards", headers=_auth_headers())
    assert response.status_code == 200, _err(response, 200)

    cards = response.json()
    assert isinstance(cards, list), "Response should be a bare JSON array"
    _assert_card_shape(cards)


@pytest.mark.e2e
def test_get_home_cards_projects_active_notifications():
    """Test GET /api/cards projects the caller's active notifications as Cards."""
    token = get_auth_token(
        profile_id=NOTIFIED_PROFILE_ID, roles=NOTIFIED_PROFILE_ROLES, sub="daniel"
    )
    response = requests.get(f"{BASE_URL}/api/cards", headers=_auth_headers(token))
    assert response.status_code == 200, _err(response, 200)

    cards = response.json()
    assert isinstance(cards, list), "Response should be a bare JSON array"
    _assert_card_shape(cards)

    if not cards:
        pytest.skip("no seeded active notification for the persona profile_id")
    assert any(
        card.get("type") == "Notification" for card in cards
    ), f"Expected a Notification card, got {cards}"


@pytest.mark.e2e
def test_get_home_cards_honors_pagination_headers():
    """Test GET /api/cards paginates with the offset and size request headers."""
    response = requests.get(
        f"{BASE_URL}/api/cards", headers=_auth_headers(offset="0", size="5")
    )
    assert response.status_code == 200, _err(response, 200)

    cards = response.json()
    assert isinstance(cards, list), "Response should be a bare JSON array"
    assert len(cards) <= 5, f"Expected at most 5 cards, got {len(cards)}"


@pytest.mark.e2e
def test_get_home_cards_rejects_an_oversized_page():
    """Test GET /api/cards rejects a size above the shared maximum of 100."""
    response = requests.get(f"{BASE_URL}/api/cards", headers=_auth_headers(size="101"))
    assert response.status_code == 400, _err(response, 400)


@pytest.mark.e2e
def test_card_endpoints_require_auth():
    """Test that card endpoints require authentication."""
    response = requests.get(f"{BASE_URL}/api/cards")
    assert response.status_code == 401, _err(response, 401)
