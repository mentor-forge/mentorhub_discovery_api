"""
E2E tests for Customer endpoints (consume-style, read-only).

These tests verify that Customer endpoints work correctly by making
actual HTTP requests to a running server.

To run these tests:
1. Start the server: pipenv run dev (or pipenv run api for containerized)
2. Run E2E tests: pipenv run e2e

API runs on port 8397 (same for dev and api).
"""

import pytest
import requests

from .e2e_auth import get_auth_token

BASE_URL = "http://localhost:8397"


def _err(response, expected):
    """Format assertion error with response body for debugging."""
    body = response.text[:300] if response.text else "(empty)"
    return f"Expected {expected}, got {response.status_code}. Response: {body}"


@pytest.mark.e2e
def test_get_customers_endpoint():
    """Test GET /api/customer endpoint."""
    token = get_auth_token()
    headers = {"Authorization": f"Bearer {token}"}
    response = requests.get(f"{BASE_URL}/api/customer", headers=headers)
    assert response.status_code == 200, _err(response, 200)

    response_data = response.json()
    assert isinstance(
        response_data, dict
    ), "Response should be a dict (infinite scroll format)"
    assert "items" in response_data, "Response should have 'items' key"
    assert "limit" in response_data, "Response should have 'limit' key"
    assert "has_more" in response_data, "Response should have 'has_more' key"
    assert "next_cursor" in response_data, "Response should have 'next_cursor' key"
    assert isinstance(response_data["items"], list), "Items should be a list"


@pytest.mark.e2e
def test_get_customers_with_name_filter():
    """Test GET /api/customer with name query parameter."""
    token = get_auth_token()
    headers = {"Authorization": f"Bearer {token}"}
    response = requests.get(f"{BASE_URL}/api/customer?name=test", headers=headers)
    assert response.status_code == 200, _err(response, 200)

    response_data = response.json()
    assert isinstance(
        response_data, dict
    ), "Response should be a dict (infinite scroll format)"
    assert "items" in response_data, "Response should have 'items' key"
    assert isinstance(response_data["items"], list), "Items should be a list"


@pytest.mark.e2e
def test_get_customer_not_found():
    """Test GET /api/customer/<id> with non-existent ID."""
    token = get_auth_token()
    headers = {"Authorization": f"Bearer {token}"}
    response = requests.get(
        f"{BASE_URL}/api/customer/000000000000000000000000",
        headers=headers,
    )
    assert response.status_code == 404, _err(response, 404)


@pytest.mark.e2e
def test_customer_endpoints_require_auth():
    """Test that customer endpoints require authentication."""
    response = requests.get(f"{BASE_URL}/api/customer")
    assert response.status_code == 401, f"Expected 401, got {response.status_code}"
