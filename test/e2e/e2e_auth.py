"""E2E Bearer JWT for black-box API tests (Developer Edition ``login.html`` persona defaults).

Uses ``JWT_SECRET``, ``JWT_ISSUER``, ``JWT_AUDIENCE``, and ``JWT_ALGORITHM`` from the
environment when set (``pipenv run e2e`` exports the Developer Edition defaults). Override
those variables to match a non-default API stack (same values the container / compose uses).
"""

from __future__ import annotations

import os
import time

import jwt

# Defaults match login.html / compose JWT settings (HS256, iss dev-idp, aud dev-api) and Pipfile dev/e2e.
_DEFAULT_JWT_SECRET = "local-dev-jwt-secret-fixed"
_DEFAULT_JWT_ISSUER = "dev-idp"
_DEFAULT_JWT_AUDIENCE = "dev-api"
_DEFAULT_JWT_ALGORITHM = "HS256"

_E2E_SUBJECT = "adam"
_E2E_ROLES = ("admin",)

# api-utils 1.0.0 rejects a token without a ``profile_id`` claim, so the persona
# needs one. Matches the seeded admin Profile id (Profile.0.1.0.0 test data).
_E2E_PROFILE_ID = "A00000000000000000000001"

# Developer Edition seed persona configurations
PERSONA_MIKE = {
    "sub": "mike",
    "profile_id": "A00000000000000000000001",
    "roles": ["admin"],
}

PERSONA_DANIEL = {
    "sub": "daniel",
    "profile_id": "A00000000000000000000002",
    "roles": ["mentee"],
    "customer_id": "D00000000000000000000002",
    "mentor_id": "A00000000000000000000010",
}

PERSONA_STACEY = {
    "sub": "stacey",
    "profile_id": "A00000000000000000000008",
    "roles": ["customer"],
    "customer_id": "D00000000000000000000002",
}

PERSONA_EMMA = {
    "sub": "emma",
    "profile_id": "A00000000000000000000007",
    "roles": ["coordinator"],
    "customer_id": "D00000000000000000000002",
}

# Home Mentee cards also resolve from profile_id when mentor_id is absent (D110).
PERSONA_PAULA = {
    "sub": "paula",
    "profile_id": "A00000000000000000000010",
    "roles": ["mentor"],
    "mentor_id": "A00000000000000000000010",
}


def get_auth_token(**claims) -> str:
    """
    Mint a short-lived admin persona JWT for black-box tests.

    Keyword arguments override or add payload claims, so a test that needs a
    different scope (another `profile_id`, a `customer_id`, non-admin `roles`)
    can borrow the same signing settings.
    """
    secret = os.environ.get("JWT_SECRET") or _DEFAULT_JWT_SECRET
    issuer = os.environ.get("JWT_ISSUER") or _DEFAULT_JWT_ISSUER
    audience = os.environ.get("JWT_AUDIENCE") or _DEFAULT_JWT_AUDIENCE
    algorithm = os.environ.get("JWT_ALGORITHM") or _DEFAULT_JWT_ALGORITHM
    now = int(time.time())
    payload = {
        "iss": issuer,
        "aud": audience,
        "sub": _E2E_SUBJECT,
        "iat": now,
        "exp": now + 10 * 365 * 24 * 60 * 60,
        "roles": list(_E2E_ROLES),
        "profile_id": _E2E_PROFILE_ID,
    }
    payload.update(claims)
    token = jwt.encode(payload, secret, algorithm=algorithm)
    if isinstance(token, bytes):
        return token.decode("ascii")
    return token


def get_persona_token(persona: dict, **extra) -> str:
    """Mint a JWT for one of the Developer Edition seed personas."""
    claims = dict(persona)
    claims.update(extra)
    return get_auth_token(**claims)
