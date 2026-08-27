"""
Flask blueprint factories for the Discovery Card GET endpoints.

`GET /api/cards` is the composite home list: the route layer only reads the
token, builds the breadcrumb, parses the pagination headers, and hands off to
`CardService`. Home aggregates multiple sources, so it cannot use a shared GET
factory, and it paginates only — the typed `/api/cards/{type}` lists carry the
per-type filter and order parameters.

Every typed Card list is a shared `create_*_get_routes` factory bound to a
Card-projecting service subclass. Several of those shared factories also mount a
GET by-id rule, which the Discovery Card contract does not include, so
`server.py` registers them through `register_list_only_blueprint`.
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


def register_list_only_blueprint(app, blueprint, url_prefix):
    """
    Register a blueprint, keeping only the rules that take no path argument.

    The shared `create_*_get_routes` factories mount a GET `/<id>` rule beside
    the list GET. The Discovery Card surface is `Card[]` only, so those by-id
    rules are dropped as the blueprint registers: the shared factories stay
    unforked, and neither the URL map nor `app.view_functions` ever carries a
    route Discovery does not document.

    Args:
        app: Flask application
        blueprint: Blueprint from a shared GET factory
        url_prefix: Mount point, e.g. `/api/cards/resources`
    """
    add_url_rule = app.add_url_rule

    def add_argument_free_rules(rule, endpoint=None, view_func=None, **options):
        # BlueprintSetupState resolves the prefix before it delegates here, so a
        # `<` in the rule marks a by-id route rather than the list route.
        if "<" in rule:
            logger.info(f"Suppressed by-id route {rule}")
            return None
        return add_url_rule(rule, endpoint, view_func, **options)

    app.add_url_rule = add_argument_free_rules
    try:
        app.register_blueprint(blueprint, url_prefix=url_prefix)
    finally:
        del app.add_url_rule


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
