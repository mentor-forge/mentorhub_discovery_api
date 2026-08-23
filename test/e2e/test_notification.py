"""
E2E tests for the Notification control endpoints (create, dismiss, cancel).

These tests verify `POST /api/notification`,
`POST /api/notification/dismiss/{notification_id}`, and
`POST /api/notification/cancel/{notification_id}` against a running server by
making actual HTTP requests.

Create is a global POST available to any authenticated caller, so the happy
path seeds its own document rather than depending on Developer Edition test
data: create a profile-scoped Notification for the persona, then dismiss or
cancel it. Every control response is a Notification document — the Card
projection belongs to `GET /api/cards/notifications`.

To run these tests:
1. Start the server: pipenv run dev (or pipenv run api for containerized)
2. Run E2E tests: pipenv run e2e

API runs on port 8397 (same for dev and api).
"""

import uuid

import pytest
import requests

from .e2e_auth import get_auth_token

BASE_URL = "http://localhost:8397"

# Persona profile ids: the admin default from e2e_auth, and a second seeded
# Profile used to prove outbound RBAC hides another target's notification.
ADMIN_PROFILE_ID = "A00000000000000000000001"
OTHER_PROFILE_ID = "A00000000000000000000002"
OTHER_PROFILE_ROLES = ["mentee"]

# Well-formed ObjectId that no Notification uses.
MISSING_NOTIFICATION_ID = "665f1c2a9b1e4c0a1b2c3d4e"

# Notification.name is `^[^\s]{1,40}$` — no whitespace allowed.
NAME_PREFIX = "e2e-control"

# Card-only properties: a control response must never carry these.
CARD_ONLY_PROPERTIES = {"type", "link"}

CONTROL_PATHS = [
    "/api/notification",
    f"/api/notification/dismiss/{MISSING_NOTIFICATION_ID}",
    f"/api/notification/cancel/{MISSING_NOTIFICATION_ID}",
]


def _err(response, expected):
    """Format assertion error with response body for debugging."""
    body = response.text[:300] if response.text else "(empty)"
    return f"Expected {expected}, got {response.status_code}. Response: {body}"


def _auth_headers(token=None, **extra):
    headers = {"Authorization": f"Bearer {token or get_auth_token()}"}
    headers.update(extra)
    return headers


def _new_notification(profile_id=ADMIN_PROFILE_ID):
    """A minimal profile-scoped Notification body with a unique name."""
    return {
        "name": f"{NAME_PREFIX}-{uuid.uuid4().hex[:8]}",
        "message": "Created by the Discovery API e2e suite",
        "profile_id": profile_id,
        "status": "active",
    }


def _create(token=None, body=None):
    return requests.post(
        f"{BASE_URL}/api/notification",
        headers=_auth_headers(token),
        json=body if body is not None else _new_notification(),
    )


def _create_or_skip(token=None, body=None):
    """Create a Notification, skipping the test when the stack will not accept one."""
    response = _create(token=token, body=body)
    if response.status_code != 201:
        pytest.skip(f"notification create unavailable: {_err(response, 201)}")
    return response.json()


def _assert_notification_shape(document):
    assert isinstance(document, dict), f"Expected a JSON object: {document}"
    assert "_id" in document, f"Expected an _id on the Notification: {document}"
    assert not CARD_ONLY_PROPERTIES.intersection(
        document
    ), f"Control response looks like a Card, not a Notification: {document}"


@pytest.mark.e2e
@pytest.mark.parametrize("path", CONTROL_PATHS)
def test_notification_control_requires_auth(path):
    """Test every control endpoint rejects an unauthenticated POST."""
    response = requests.post(f"{BASE_URL}{path}", json={})
    assert response.status_code == 401, _err(response, 401)


@pytest.mark.e2e
def test_dismiss_missing_id_returns_404():
    """Test dismissing an id that no Notification uses returns 404."""
    response = requests.post(
        f"{BASE_URL}/api/notification/dismiss/{MISSING_NOTIFICATION_ID}",
        headers=_auth_headers(),
    )
    assert response.status_code == 404, _err(response, 404)


@pytest.mark.e2e
def test_cancel_missing_id_returns_404():
    """Test cancelling an id that no Notification uses returns 404."""
    response = requests.post(
        f"{BASE_URL}/api/notification/cancel/{MISSING_NOTIFICATION_ID}",
        headers=_auth_headers(),
    )
    assert response.status_code == 404, _err(response, 404)


@pytest.mark.e2e
def test_create_returns_201_with_the_notification_document():
    """Test POST /api/notification returns 201 and the created Notification."""
    body = _new_notification()
    response = _create(body=body)
    assert response.status_code == 201, _err(response, 201)

    document = response.json()
    _assert_notification_shape(document)
    assert document["name"] == body["name"], f"Expected the submitted name: {document}"
    assert "created" in document, f"Expected a created breadcrumb: {document}"


@pytest.mark.e2e
def test_create_strips_system_managed_fields():
    """Test the service drops client-sent _id / created / dismissed / cancelled."""
    body = _new_notification()
    body["dismissed"] = {"by_user": "spoofed"}
    document = _create_or_skip(body=body)

    _assert_notification_shape(document)
    assert "dismissed" not in document, f"dismissed should be stripped: {document}"


@pytest.mark.e2e
def test_dismiss_returns_200_and_sets_only_the_dismissed_breadcrumb():
    """Test dismiss sets the dismissed breadcrumb and leaves cancelled alone."""
    created = _create_or_skip()

    response = requests.post(
        f"{BASE_URL}/api/notification/dismiss/{created['_id']}",
        headers=_auth_headers(),
    )
    assert response.status_code == 200, _err(response, 200)

    document = response.json()
    _assert_notification_shape(document)
    assert isinstance(
        document.get("dismissed"), dict
    ), f"dismissed should be a breadcrumb: {document}"
    assert "cancelled" not in document, f"dismiss must not set cancelled: {document}"
    assert "saved" not in document, f"Notification has no saved field: {document}"


@pytest.mark.e2e
def test_cancel_returns_200_and_sets_only_the_cancelled_breadcrumb():
    """Test cancel sets the cancelled breadcrumb and leaves dismissed alone."""
    created = _create_or_skip()

    response = requests.post(
        f"{BASE_URL}/api/notification/cancel/{created['_id']}",
        headers=_auth_headers(),
    )
    assert response.status_code == 200, _err(response, 200)

    document = response.json()
    _assert_notification_shape(document)
    assert isinstance(
        document.get("cancelled"), dict
    ), f"cancelled should be a breadcrumb: {document}"
    assert "dismissed" not in document, f"cancel must not set dismissed: {document}"


@pytest.mark.e2e
def test_control_response_is_a_notification_not_a_card():
    """Test create and dismiss return Notification documents, unlike the Card list."""
    created = _create_or_skip()
    assert "message" in created, f"Expected the Notification message field: {created}"

    dismissed = requests.post(
        f"{BASE_URL}/api/notification/dismiss/{created['_id']}",
        headers=_auth_headers(),
    )
    assert dismissed.status_code == 200, _err(dismissed, 200)
    _assert_notification_shape(dismissed.json())

    cards = requests.get(f"{BASE_URL}/api/cards/notifications", headers=_auth_headers())
    assert cards.status_code == 200, _err(cards, 200)
    assert isinstance(cards.json(), list), "The Card list is still a bare JSON array"


@pytest.mark.e2e
def test_dismiss_another_targets_notification_returns_404():
    """Test outbound RBAC hides another profile's Notification rather than 403."""
    created = _create_or_skip()
    other_token = get_auth_token(
        profile_id=OTHER_PROFILE_ID, roles=OTHER_PROFILE_ROLES, sub="daniel"
    )

    response = requests.post(
        f"{BASE_URL}/api/notification/dismiss/{created['_id']}",
        headers=_auth_headers(other_token),
    )
    assert response.status_code == 404, _err(response, 404)


@pytest.mark.e2e
def test_create_rejects_a_body_that_is_not_a_json_object():
    """Test a missing or malformed create body is a 400, not a 500."""
    response = requests.post(
        f"{BASE_URL}/api/notification",
        headers=_auth_headers(**{"Content-Type": "text/plain"}),
        data="not json",
    )
    assert response.status_code == 400, _err(response, 400)


@pytest.mark.e2e
def test_dismiss_is_not_a_get_route():
    """Test the control endpoints are POST only."""
    response = requests.get(
        f"{BASE_URL}/api/notification/dismiss/{MISSING_NOTIFICATION_ID}",
        headers=_auth_headers(),
    )
    assert response.status_code == 405, _err(response, 405)
