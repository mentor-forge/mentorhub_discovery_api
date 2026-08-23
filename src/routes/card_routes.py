"""
Flask blueprint factories for the Discovery Card GET endpoints that have no
shared GET factory behind them.

`GET /api/cards` is the composite home list: the route layer only reads the
token, builds the breadcrumb, parses the pagination headers, and hands off to
`CardService`. Home aggregates three sources, so it cannot use a shared GET
factory, and it paginates only — the typed `/api/cards/{type}` lists carry the
per-type filter and order parameters.

Customer, Product, and Setting have no shared service class, so their typed
lists are local blueprints that mirror the shared HTTP layer. Every other typed
list is a shared `create_*_get_routes` factory bound to a Card-projecting
service subclass.
"""

import logging

from flask import Blueprint, jsonify, request

from api_utils.flask_utils.breadcrumb import create_flask_breadcrumb
from api_utils.flask_utils.list_request import (
    parse_list_request,
    parse_pagination_headers,
)
from api_utils.flask_utils.route_wrapper import handle_route_exceptions
from api_utils.flask_utils.token import create_flask_token

from src.services.card_service import (
    CUSTOMER_LIST_FILTERS,
    CUSTOMER_LIST_ORDER,
    PRODUCT_LIST_FILTERS,
    PRODUCT_LIST_ORDER,
    SETTING_LIST_FILTERS,
    SETTING_LIST_ORDER,
    CardService,
)

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


def _create_typed_cards_get_routes(getter_name, filter_spec, order_spec, *, name):
    """Blueprint with a single typed Card list GET served by a CardService getter."""
    bp = Blueprint(name, __name__)

    @bp.route("", methods=["GET"])
    @handle_route_exceptions
    def get_typed_cards():
        token, breadcrumb = _auth_context()
        offset, size, filters, sort_by = parse_list_request(
            request, filter_spec, order_spec
        )
        cards = getattr(CardService, getter_name)(
            token, breadcrumb, offset, size, filters, sort_by
        )
        logger.info(
            f"{getter_name} Success {breadcrumb['at_time']}, {breadcrumb['correlation_id']}"
        )
        return _json_ok(cards)

    logger.info(f"Card GET Flask Route Registered for {getter_name}")
    return bp


def create_customer_cards_get_routes(*, name="customer_card_routes"):
    """GET the Customer Card list."""
    return _create_typed_cards_get_routes(
        "get_customer_cards",
        CUSTOMER_LIST_FILTERS,
        CUSTOMER_LIST_ORDER,
        name=name,
    )


def create_product_cards_get_routes(*, name="product_card_routes"):
    """GET the Product Card list."""
    return _create_typed_cards_get_routes(
        "get_product_cards",
        PRODUCT_LIST_FILTERS,
        PRODUCT_LIST_ORDER,
        name=name,
    )


def create_settings_cards_get_routes(*, name="settings_card_routes"):
    """GET the Setting Card list."""
    return _create_typed_cards_get_routes(
        "get_settings_cards",
        SETTING_LIST_FILTERS,
        SETTING_LIST_ORDER,
        name=name,
    )
