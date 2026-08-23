"""
Flask blueprint factory for the Discovery Notification control endpoints.

Discovery **controls** Notification, so create, dismiss, and cancel live here
under `/api/notification` and return Notification documents. The SPA read
surface is a separate concern: `GET /api/cards/notifications` (F050) projects
the same collection onto Cards through `NotificationCardService`.

The route layer is HTTP only: read the token, build the breadcrumb, parse the
create body, call `NotificationService`, and jsonify what comes back. Mutations
reach MongoDB through the service; routes never open a collection.
"""

import logging

from flask import Blueprint, jsonify, request

from api_utils.flask_utils.breadcrumb import create_flask_breadcrumb
from api_utils.flask_utils.exceptions import HTTPBadRequest
from api_utils.flask_utils.route_wrapper import handle_route_exceptions
from api_utils.flask_utils.token import create_flask_token

from src.services.notification_service import NotificationService

logger = logging.getLogger(__name__)


def _auth_context():
    """Create token and breadcrumb for a route handler."""
    token = create_flask_token()
    breadcrumb = create_flask_breadcrumb(token)
    return token, breadcrumb


def _request_document():
    """
    Parsed JSON request body.

    Parsing only — the service strips `SYSTEM_MANAGED_FIELDS` and owns every
    other rule. A missing or malformed body is the documented 400 rather than
    the 500 an unhandled parse error would produce.
    """
    data = request.get_json(silent=True)
    if not isinstance(data, dict):
        raise HTTPBadRequest("Request body must be a JSON object")
    return data


def _log_success(operation, breadcrumb):
    logger.info(
        f"{operation} Success {breadcrumb['at_time']}, {breadcrumb['correlation_id']}"
    )


def create_notification_routes(*, name="notification_routes"):
    """POST create + POST dismiss / cancel by notification_id."""
    bp = Blueprint(name, __name__)

    @bp.route("", methods=["POST"])
    @handle_route_exceptions
    def create_notification():
        token, breadcrumb = _auth_context()
        notification = NotificationService.create_notification(
            _request_document(), token, breadcrumb
        )
        _log_success("create_notification", breadcrumb)
        return jsonify(notification), 201

    @bp.route("/dismiss/<notification_id>", methods=["POST"])
    @handle_route_exceptions
    def dismiss_notification(notification_id):
        token, breadcrumb = _auth_context()
        notification = NotificationService.dismiss_notification(
            notification_id, token, breadcrumb
        )
        _log_success("dismiss_notification", breadcrumb)
        return jsonify(notification), 200

    @bp.route("/cancel/<notification_id>", methods=["POST"])
    @handle_route_exceptions
    def cancel_notification(notification_id):
        token, breadcrumb = _auth_context()
        notification = NotificationService.cancel_notification(
            notification_id, token, breadcrumb
        )
        _log_success("cancel_notification", breadcrumb)
        return jsonify(notification), 200

    logger.info("Notification Control Flask Routes Registered")
    return bp
