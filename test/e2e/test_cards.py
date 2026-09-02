"""
E2E tests for the Card endpoints (consume-style, read-only).

These tests verify the GET /api/cards endpoints against a running server by
making actual HTTP requests. An empty array is a valid Card list, so the
assertions cover the contract — status, array body, Card shape, seed persona
projections, and role-gated link generation.

To run these tests:
1. Start the server: pipenv run dev (or pipenv run api for containerized)
2. Run E2E tests: pipenv run e2e

API runs on port 8397 (same for dev and api).
"""

import pytest
import requests

from .e2e_auth import (
    PERSONA_DANIEL,
    PERSONA_EMMA,
    PERSONA_MIKE,
    PERSONA_PAULA,
    PERSONA_STACEY,
    get_auth_token,
    get_persona_token,
)

BASE_URL = "http://localhost:8397"

# Card.yaml 0.0.0.0 (additionalProperties: false, nothing required).
CARD_PROPERTIES = {"_id", "name", "description", "link", "type"}

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

TYPED_CARD_PATHS = [
    "/api/cards/events",
    "/api/cards/notifications",
    "/api/cards/paths",
    "/api/cards/plans",
    "/api/cards/resources",
]

DOOMED_CARD_PATHS = [
    "/api/cards/customer",
    "/api/cards/members",
    "/api/cards/mentees",
    "/api/cards/products",
    "/api/cards/settings",
]

# Typed lists whose shared api-utils GET factory also mounts a GET by-id rule.
# The Card contract is list-only, so those URLs must not be routed.
LIST_ONLY_SHARED_CARD_PATHS = [
    "/api/cards/paths",
    "/api/cards/plans",
    "/api/cards/resources",
]

# Well-formed ObjectId; the URL is unrouted, so it never reaches a query.
CARD_ID = "665f1c2a9b1e4c0a1b2c3d21"

# Path segment -> Card `type` the list projects.
TYPED_CARD_TYPES = {
    "/api/cards/events": "Event",
    "/api/cards/notifications": "Notification",
    "/api/cards/paths": "Path",
    "/api/cards/plans": "Plan",
    "/api/cards/resources": "Resource",
}


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
def test_get_home_cards_honors_pagination_headers():
    """Test GET /api/cards paginates with the offset and size request headers."""
    response = requests.get(
        f"{BASE_URL}/api/cards", headers=_auth_headers(offset="0", size="2")
    )
    assert response.status_code == 200, _err(response, 200)

    cards = response.json()
    assert isinstance(cards, list), "Response should be a bare JSON array"
    assert len(cards) <= 2, f"Expected at most 2 cards, got {len(cards)}"


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


@pytest.mark.e2e
@pytest.mark.parametrize("path", TYPED_CARD_PATHS)
def test_typed_card_list_returns_an_array(path):
    """Test each typed GET /api/cards/{type} returns a JSON array of Cards."""
    response = requests.get(f"{BASE_URL}{path}", headers=_auth_headers())
    assert response.status_code == 200, _err(response, 200)

    cards = response.json()
    assert isinstance(cards, list), "Response should be a bare JSON array"
    _assert_card_shape(cards)


@pytest.mark.e2e
@pytest.mark.parametrize("path", TYPED_CARD_PATHS)
def test_typed_card_list_requires_auth(path):
    """Test each typed card list rejects an unauthenticated request."""
    response = requests.get(f"{BASE_URL}{path}")
    assert response.status_code == 401, _err(response, 401)


@pytest.mark.e2e
@pytest.mark.parametrize("path", DOOMED_CARD_PATHS)
def test_doomed_typed_card_list_is_not_routed(path):
    """Test doomed typed card routes were retired and return 404."""
    response = requests.get(f"{BASE_URL}{path}", headers=_auth_headers())
    assert response.status_code == 404, _err(response, 404)


@pytest.mark.e2e
@pytest.mark.parametrize("path", LIST_ONLY_SHARED_CARD_PATHS)
def test_typed_card_by_id_is_not_routed(path):
    """Test a by-id Card URL 404s for an authenticated caller."""
    response = requests.get(f"{BASE_URL}{path}/{CARD_ID}", headers=_auth_headers())
    assert response.status_code == 404, _err(response, 404)


@pytest.mark.e2e
@pytest.mark.parametrize("path", LIST_ONLY_SHARED_CARD_PATHS)
def test_typed_card_by_id_is_not_routed_without_auth(path):
    """Test a by-id Card URL 404s before auth runs, so it never returns 401."""
    response = requests.get(f"{BASE_URL}{path}/{CARD_ID}")
    assert response.status_code == 404, _err(response, 404)


@pytest.mark.e2e
@pytest.mark.parametrize("path,card_type", sorted(TYPED_CARD_TYPES.items()))
def test_typed_card_list_projects_its_card_type(path, card_type):
    """Test a typed list stamps every card with its own Card type."""
    response = requests.get(f"{BASE_URL}{path}", headers=_auth_headers())
    assert response.status_code == 200, _err(response, 200)

    cards = response.json()
    if not cards:
        pytest.skip(f"no seeded documents behind {path}")
    assert all(
        card.get("type") == card_type for card in cards
    ), f"Expected every card to be {card_type}, got {cards}"


@pytest.mark.e2e
def test_typed_card_list_honors_pagination_headers():
    """Test a typed card list paginates with the offset and size headers."""
    response = requests.get(
        f"{BASE_URL}/api/cards/resources", headers=_auth_headers(size="2")
    )
    assert response.status_code == 200, _err(response, 200)
    assert len(response.json()) <= 2, "Expected at most 2 cards"


@pytest.mark.e2e
def test_typed_card_list_accepts_a_name_filter():
    """Test a typed card list accepts its documented name contains filter."""
    response = requests.get(
        f"{BASE_URL}/api/cards/resources?name=zzz-no-such-resource",
        headers=_auth_headers(),
    )
    assert response.status_code == 200, _err(response, 200)
    assert response.json() == [], "Expected no cards for an unmatched name filter"


@pytest.mark.e2e
def test_typed_card_list_rejects_an_unsupported_sort_field():
    """Test a typed card list rejects a sort_by outside its allowed order spec."""
    response = requests.get(
        f"{BASE_URL}/api/cards/resources?sort_by=not_a_field", headers=_auth_headers()
    )
    assert response.status_code == 400, _err(response, 400)


# =========================================================================
# Seed Persona Home Card Composite Tests
# =========================================================================


@pytest.mark.e2e
def test_home_cards_persona_mike_admin():
    """Persona Mike (admin): Products, Discounts, Logs cards with admin/* links."""
    token = get_persona_token(PERSONA_MIKE)
    response = requests.get(f"{BASE_URL}/api/cards", headers=_auth_headers(token))
    assert response.status_code == 200, _err(response, 200)

    cards = response.json()
    _assert_card_shape(cards)

    # Mike has admin role and no profile notifications:
    # Expected synthetic cards: Products, Discounts, Logs
    synthetic_links = [c.get("link") for c in cards]
    assert "admin/settings" in synthetic_links
    assert "admin/settings?tab=discounts" in synthetic_links
    assert "admin/logs" in synthetic_links

    products = next(c for c in cards if c.get("name") == "Products")
    discounts = next(c for c in cards if c.get("name") == "Discounts")
    logs = next(c for c in cards if c.get("name") == "Logs")
    assert products.get("type") == "Products"
    assert discounts.get("type") == "Discounts"
    assert logs.get("type") == "Logs"

    # No customer / member / mentee / journey sections
    assert not any(c.get("link", "").startswith("customer/") for c in cards)
    assert not any(c.get("link", "").startswith("mentee/") for c in cards)


@pytest.mark.e2e
def test_home_cards_persona_daniel_mentee():
    """Persona Daniel (mentee): Notification with link, Learning Journey (type Journey)."""
    token = get_persona_token(PERSONA_DANIEL)
    response = requests.get(f"{BASE_URL}/api/cards", headers=_auth_headers(token))
    assert response.status_code == 200, _err(response, 200)

    cards = response.json()
    _assert_card_shape(cards)

    # Daniel has mentee role -> Learning Journey is at the end
    assert len(cards) >= 1
    last_card = cards[-1]
    assert last_card.get("name") == "Learning Journey"
    assert last_card.get("link") == "mentee/journey"
    assert last_card.get("type") == "Journey"

    notifications = [c for c in cards if c.get("type") == "Notification"]
    for notif in notifications:
        assert notif.get("link") == f"discovery/notification/{notif['_id']}"

    # No admin or customer links
    assert not any(c.get("link", "").startswith("admin/") for c in cards)
    assert not any(c.get("link", "").startswith("customer/") for c in cards)


@pytest.mark.e2e
def test_home_cards_persona_stacey_customer():
    """Persona Stacey (customer): Customer card, then Member cards."""
    token = get_persona_token(PERSONA_STACEY)
    response = requests.get(f"{BASE_URL}/api/cards", headers=_auth_headers(token))
    assert response.status_code == 200, _err(response, 200)

    cards = response.json()
    _assert_card_shape(cards)

    customer_cards = [
        c
        for c in cards
        if c.get("link") == f"customer/customer/{PERSONA_STACEY['customer_id']}"
    ]
    if customer_cards:
        cust_card = customer_cards[0]
        assert cust_card.get("type") == "Customer"

    # Member cards should have customer/profile/{id} links
    member_cards = [c for c in cards if c.get("type") == "Member"]
    for m in member_cards:
        assert m.get("link", "").startswith("customer/profile/")


@pytest.mark.e2e
def test_home_cards_persona_emma_coordinator():
    """Persona Emma (coordinator): Member cards only, no Customer singleton."""
    token = get_persona_token(PERSONA_EMMA)
    response = requests.get(f"{BASE_URL}/api/cards", headers=_auth_headers(token))
    assert response.status_code == 200, _err(response, 200)

    cards = response.json()
    _assert_card_shape(cards)

    # Coordinator does not get Customer singleton
    assert not any(c.get("link", "").startswith("customer/customer/") for c in cards)


@pytest.mark.e2e
def test_home_cards_persona_paula_mentor():
    """Persona Paula (mentor): Mentee cards with mentor/mentee/{id} links."""
    token = get_persona_token(PERSONA_PAULA)
    response = requests.get(f"{BASE_URL}/api/cards", headers=_auth_headers(token))
    assert response.status_code == 200, _err(response, 200)

    cards = response.json()
    _assert_card_shape(cards)

    mentee_cards = [c for c in cards if c.get("type") == "Mentee"]
    for m in mentee_cards:
        assert m.get("link", "").startswith("mentor/mentee/")


# =========================================================================
# Typed List Link Projection Tests
# =========================================================================


@pytest.mark.e2e
def test_typed_notifications_project_link():
    """GET /api/cards/notifications projects discovery/notification/{id} links."""
    token = get_persona_token(PERSONA_DANIEL)
    response = requests.get(
        f"{BASE_URL}/api/cards/notifications", headers=_auth_headers(token)
    )
    assert response.status_code == 200, _err(response, 200)

    cards = response.json()
    if not cards:
        pytest.skip("no seeded notifications")
    for card in cards:
        assert card.get("type") == "Notification"
        assert card.get("link") == f"discovery/notification/{card['_id']}"


@pytest.mark.e2e
def test_typed_notifications_admin_name_filter_ok():
    """Admin GET /api/cards/notifications?name= is 200 with a Card array."""
    token = get_persona_token(PERSONA_MIKE)
    response = requests.get(
        f"{BASE_URL}/api/cards/notifications",
        headers=_auth_headers(token),
        params={"name": "Invite"},
    )
    assert response.status_code == 200, _err(response, 200)
    cards = response.json()
    assert isinstance(cards, list)
    for card in cards:
        assert card.get("type") == "Notification"
        assert "Invite".lower() in (card.get("name") or "").lower()


@pytest.mark.e2e
def test_typed_notifications_mentee_name_filter_forbidden():
    """Mentee GET /api/cards/notifications?name=x is 403."""
    token = get_persona_token(PERSONA_DANIEL)
    response = requests.get(
        f"{BASE_URL}/api/cards/notifications",
        headers=_auth_headers(token),
        params={"name": "x"},
    )
    assert response.status_code == 403, _err(response, 403)


@pytest.mark.e2e
def test_typed_resources_links_mentor_vs_mentee():
    """GET /api/cards/resources emits mentor/resource/* for Mentor, mentee/resource/* otherwise."""
    paula_token = get_persona_token(PERSONA_PAULA)
    res_mentor = requests.get(
        f"{BASE_URL}/api/cards/resources", headers=_auth_headers(paula_token)
    )
    assert res_mentor.status_code == 200, _err(res_mentor, 200)
    mentor_cards = res_mentor.json()

    daniel_token = get_persona_token(PERSONA_DANIEL)
    res_mentee = requests.get(
        f"{BASE_URL}/api/cards/resources", headers=_auth_headers(daniel_token)
    )
    assert res_mentee.status_code == 200, _err(res_mentee, 200)
    mentee_cards = res_mentee.json()

    if mentor_cards:
        for c in mentor_cards:
            assert c.get("link", "").startswith("mentor/resource/")

    if mentee_cards:
        for c in mentee_cards:
            assert c.get("link", "").startswith("mentee/resource/")


@pytest.mark.e2e
def test_typed_paths_links_mentor_vs_mentee():
    """GET /api/cards/paths emits mentor/path/* for Mentor, mentee/path/* otherwise."""
    paula_token = get_persona_token(PERSONA_PAULA)
    res_mentor = requests.get(
        f"{BASE_URL}/api/cards/paths", headers=_auth_headers(paula_token)
    )
    assert res_mentor.status_code == 200, _err(res_mentor, 200)
    mentor_cards = res_mentor.json()

    daniel_token = get_persona_token(PERSONA_DANIEL)
    res_mentee = requests.get(
        f"{BASE_URL}/api/cards/paths", headers=_auth_headers(daniel_token)
    )
    assert res_mentee.status_code == 200, _err(res_mentee, 200)
    mentee_cards = res_mentee.json()

    if mentor_cards:
        for c in mentor_cards:
            assert c.get("link", "").startswith("mentor/path/")

    if mentee_cards:
        for c in mentee_cards:
            assert c.get("link", "").startswith("mentee/path/")


@pytest.mark.e2e
def test_typed_plans_links_mentor_prefix():
    """GET /api/cards/plans emits mentor/plan/* links."""
    token = get_persona_token(PERSONA_DANIEL)
    response = requests.get(f"{BASE_URL}/api/cards/plans", headers=_auth_headers(token))
    assert response.status_code == 200, _err(response, 200)

    cards = response.json()
    if not cards:
        pytest.skip("no seeded plans")
    for c in cards:
        assert c.get("link", "").startswith("mentor/plan/")


@pytest.mark.e2e
def test_typed_events_links_mentee_prefix():
    """GET /api/cards/events emits type: Event and mentee/event/* links."""
    token = get_persona_token(PERSONA_DANIEL)
    response = requests.get(
        f"{BASE_URL}/api/cards/events", headers=_auth_headers(token)
    )
    assert response.status_code == 200, _err(response, 200)

    cards = response.json()
    if not cards:
        pytest.skip("no seeded events")
    for c in cards:
        assert c.get("type") == "Event"
        assert c.get("link", "").startswith("mentee/event/")
