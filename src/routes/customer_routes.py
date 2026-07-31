"""
Customer routes for Flask API.

Provides endpoints for Customer domain:
- GET /api/customer - Get all customer documents
- GET /api/customer/<id> - Get a specific customer document by ID
"""

from flask import Blueprint, jsonify, request
from api_utils.flask_utils.token import create_flask_token
from api_utils.flask_utils.breadcrumb import create_flask_breadcrumb
from api_utils.flask_utils.route_wrapper import handle_route_exceptions
from src.services.customer_service import CustomerService

import logging

logger = logging.getLogger(__name__)


def create_customer_routes():
    """
    Create a Flask Blueprint exposing customer endpoints.

    Returns:
        Blueprint: Flask Blueprint with customer routes
    """
    customer_routes = Blueprint("customer_routes", __name__)

    @customer_routes.route("", methods=["GET"])
    @handle_route_exceptions
    def get_customers():
        """
        GET /api/customer - Retrieve infinite scroll batch of sorted, filtered customer documents.

        Query Parameters:
            name: Optional name filter
            after_id: Cursor for infinite scroll (ID of last item from previous batch, omit for first request)
            limit: Items per batch (default: 10, max: 100)
            sort_by: Field to sort by (default: 'name')
            order: Sort order 'asc' or 'desc' (default: 'asc')

        Returns:
            JSON response with infinite scroll results: {
                'items': [...],
                'limit': int,
                'has_more': bool,
                'next_cursor': str|None
            }

        Raises:
            400 Bad Request: If invalid parameters provided
        """
        token = create_flask_token()
        breadcrumb = create_flask_breadcrumb(token)

        # Get query parameters
        name = request.args.get("name")
        after_id = request.args.get("after_id")
        limit = request.args.get("limit", 10, type=int)
        sort_by = request.args.get("sort_by", "name")
        order = request.args.get("order", "asc")

        # Service layer validates parameters and raises HTTPBadRequest if invalid
        # @handle_route_exceptions decorator will catch and format the exception
        result = CustomerService.get_customers(
            token,
            breadcrumb,
            name=name,
            after_id=after_id,
            limit=limit,
            sort_by=sort_by,
            order=order,
        )

        logger.info(
            f"get_customers Success {str(breadcrumb['at_time'])}, {breadcrumb['correlation_id']}"
        )
        return jsonify(result), 200

    @customer_routes.route("/<customer_id>", methods=["GET"])
    @handle_route_exceptions
    def get_customer(customer_id):
        """
        GET /api/customer/<id> - Retrieve a specific customer document by ID.

        Args:
            customer_id: The customer ID to retrieve

        Returns:
            JSON response with the customer document
        """
        token = create_flask_token()
        breadcrumb = create_flask_breadcrumb(token)

        customer = CustomerService.get_customer(customer_id, token, breadcrumb)
        logger.info(
            f"get_customer Success {str(breadcrumb['at_time'])}, {breadcrumb['correlation_id']}"
        )
        return jsonify(customer), 200

    logger.info("Customer Flask Routes Registered")
    return customer_routes
