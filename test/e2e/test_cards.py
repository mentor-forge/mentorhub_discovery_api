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


HOME_PAGE_HEADERS = {"offset": "0", "size": "100"}

ADMIN_EXCLUDED_HOME_TYPES = {
    "Customer",
    "Member",
    "Mentee",
    "Journey",
}

PAULA_MENTOR_SCOPE_ID = PERSONA_PAULA["mentor_id"]


def _assert_card_shape(cards):
    for card in cards:
        assert isinstance(card, dict), f"Card should be an object: {card}"
        assert set(card).issubset(CARD_PROPERTIES), f"Unexpected Card fields: {card}"
        if "type" in card:
            assert card["type"] in CARD_TYPE_ENUM, f"Unexpected Card type: {card}"


def _assert_home_notification_links(cards):
    for card in cards:
        if card.get("type") == "Notification":
            assert "_id" in card, f"Notification card missing _id: {card}"
            assert (
                card.get("link") == f"discovery/notification/{card['_id']}"
            ), f"Home Notification card must include discovery/notification/{{id}}: {card}"


def _assert_member_markdown(card):
    description = card.get("description") or ""
    assert "**Progress**" in description, f"Member markdown missing Progress: {card}"
    assert "Library" in description, f"Member markdown missing Library: {card}"
    assert "Now" in description, f"Member markdown missing Now: {card}"
    assert "Next" in description, f"Member markdown missing Next: {card}"
    assert "**Activity**" in description, f"Member markdown missing Activity: {card}"
    assert "30 days" in description, f"Member markdown missing 30 days: {card}"


def _assert_mentee_markdown(card):
    description = card.get("description") or ""
    assert "**Activity**" in description, f"Mentee markdown missing Activity: {card}"
    assert "30 days" in description, f"Mentee markdown missing 30 days: {card}"
    assert "**Notes**" in description, f"Mentee markdown missing Notes: {card}"


def _home_cards(token):
    response = requests.get(
        f"{BASE_URL}/api/cards",
        headers=_auth_headers(token, **HOME_PAGE_HEADERS),
    )
    assert response.status_code == 200, _err(response, 200)
    cards = response.json()
    assert isinstance(cards, list), "Response should be a bare JSON array"
    _assert_card_shape(cards)
    _assert_home_notification_links(cards)
    return cards


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
    cards = _home_cards(get_persona_token(PERSONA_MIKE))

    products = next((c for c in cards if c.get("type") == "Products"), None)
    discounts = next((c for c in cards if c.get("type") == "Discounts"), None)
    logs = next((c for c in cards if c.get("type") == "Logs"), None)
    assert products is not None, "Expected a Products card for admin"
    assert discounts is not None, "Expected a Discounts card for admin"
    assert logs is not None, "Expected a Logs card for admin"
    assert products.get("link") == "admin/settings"
    assert discounts.get("link") == "admin/settings?tab=discounts"
    assert logs.get("link") == "admin/logs"

    assert not any(
        c.get("type") in ADMIN_EXCLUDED_HOME_TYPES for c in cards
    ), f"Admin home must not include Customer/Member/Mentee/Journey: {cards}"
    assert not any(c.get("link", "").startswith("customer/") for c in cards)
    assert not any(c.get("link", "").startswith("mentor/") for c in cards)
    assert not any(c.get("link", "").startswith("mentee/") for c in cards)


@pytest.mark.e2e
def test_home_cards_persona_daniel_mentee():
    """Persona Daniel (mentee): Notification with link, Learning Journey (type Journey)."""
    cards = _home_cards(get_persona_token(PERSONA_DANIEL))

    assert len(cards) >= 1
    last_card = cards[-1]
    assert last_card.get("name") == "Learning Journey"
    assert last_card.get("link") == "mentee/journey"
    assert last_card.get("type") == "Journey"

    assert not any(c.get("link", "").startswith("admin/") for c in cards)
    assert not any(c.get("link", "").startswith("customer/") for c in cards)


@pytest.mark.e2e
def test_home_cards_persona_stacey_customer():
    """Persona Stacey (customer): Customer card, then Member cards with Progress markdown."""
    cards = _home_cards(get_persona_token(PERSONA_STACEY))

    customer_cards = [c for c in cards if c.get("type") == "Customer"]
    if not customer_cards:
        pytest.skip(
            f"no seeded Customer {PERSONA_STACEY['customer_id']} for Stacey home"
        )
    expected_customer_link = f"customer/customer/{PERSONA_STACEY['customer_id']}"
    for card in customer_cards:
        assert (card.get("link") or "").lower() == expected_customer_link.lower()

    member_cards = [c for c in cards if c.get("type") == "Member"]
    if not member_cards:
        pytest.skip("no seeded Member Profiles for Stacey customer_id")
    for card in member_cards:
        assert card.get("link", "").startswith("customer/profile/")
        _assert_member_markdown(card)


@pytest.mark.e2e
def test_home_cards_persona_emma_coordinator():
    """Persona Emma (coordinator): Member cards only, no Customer singleton."""
    cards = _home_cards(get_persona_token(PERSONA_EMMA))

    assert not any(c.get("type") == "Customer" for c in cards)
    assert not any(c.get("link", "").startswith("customer/customer/") for c in cards)

    member_cards = [c for c in cards if c.get("type") == "Member"]
    if not member_cards:
        pytest.skip("no seeded Member Profiles for Emma customer_id")
    for card in member_cards:
        assert card.get("link", "").startswith("customer/profile/")
        _assert_member_markdown(card)


@pytest.mark.e2e
def test_home_cards_persona_paula_mentor():
    """Persona Paula (mentor): Mentee cards when seed mentees exist (D110)."""
    cards = _home_cards(get_persona_token(PERSONA_PAULA))

    mentee_cards = [c for c in cards if c.get("type") == "Mentee"]
    if not mentee_cards:
        pytest.skip(
            "no seeded mentee Profiles for mentor_id/profile_id "
            f"{PAULA_MENTOR_SCOPE_ID}"
        )
    for card in mentee_cards:
        assert card.get("link", "").startswith("mentor/mentee/")
        _assert_mentee_markdown(card)


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
    if not cards:
        pytest.skip("no seeded notifications matching name=Invite")
    _assert_card_shape(cards)
    for card in cards:
        assert card.get("type") == "Notification"
        assert "Invite".lower() in (card.get("name") or "").lower()
        assert card.get("link") == f"discovery/notification/{card['_id']}"


@pytest.mark.e2e
def test_typed_notifications_admin_status_filter_ok():
    """Admin GET /api/cards/notifications?status=active is 200 with a Card array."""
    token = get_persona_token(PERSONA_MIKE)
    response = requests.get(
        f"{BASE_URL}/api/cards/notifications",
        headers=_auth_headers(token),
        params={"status": "active"},
    )
    assert response.status_code == 200, _err(response, 200)
    cards = response.json()
    assert isinstance(cards, list)
    if not cards:
        pytest.skip("no seeded notifications with status=active")
    _assert_card_shape(cards)
    for card in cards:
        assert card.get("type") == "Notification"
        assert card.get("link") == f"discovery/notification/{card['_id']}"


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
def test_typed_notifications_mentee_status_filter_forbidden():
    """Mentee GET /api/cards/notifications?status=active is 403."""
    token = get_persona_token(PERSONA_DANIEL)
    response = requests.get(
        f"{BASE_URL}/api/cards/notifications",
        headers=_auth_headers(token),
        params={"status": "active"},
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
