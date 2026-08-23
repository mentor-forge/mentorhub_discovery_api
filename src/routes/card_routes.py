"""
Flask blueprint factory for the Discovery Card GET endpoints.

`GET /api/cards` is the composite home list: the route layer only reads the
token, builds the breadcrumb, parses the pagination headers, and hands off to
`CardService`. Home aggregates three sources, so it cannot use a shared GET
factory, and it paginates only — the typed `/api/cards/{type}` lists carry the
per-type filter and order parameters.
"""

import logging

from flask import Blueprint, jsonify, request

from api_utils.flask_utils.breadcrumb import create_flask_breadcrumb
from api_utils.flask_utils.list_request import parse_pagination_headers
from api_utils.flask_utils.route_wrapper import handle_route_exceptions
from api_utils.flask_utils.token import create_flask_token

from src.services.card_service import CardService

logger = logging.getLogger(__name__)


def _auth_context():
    """Create token and breadcrumb for a route handler."""
    token = create_flask_token()
    breadcrumb = create_flask_breadcrumb(token)
    return token, breadcrumb


def _json_ok(data):
    """Return a 200 JSON response."""
    return jsonify(data), 200


def create_cards_get_routes(*, name="card_routes"):
    """GET composite home card list."""
    bp = Blueprint(name, __name__)

    @bp.route("", methods=["GET"])
    @handle_route_exceptions
    def get_home_cards():
        token, breadcrumb = _auth_context()
        offset, size = parse_pagination_headers(request)
        cards = CardService.get_home_cards(token, breadcrumb, offset, size)
        logger.info(
            f"get_home_cards Success {breadcrumb['at_time']}, {breadcrumb['correlation_id']}"
        )
        return _json_ok(cards)

    logger.info("Card GET Flask Routes Registered")
    return bp
