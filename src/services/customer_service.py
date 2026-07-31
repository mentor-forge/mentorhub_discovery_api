"""
Customer service for business logic and RBAC.

Handles RBAC checks and MongoDB operations for Customer domain.
"""

from api_utils import MongoIO, Config
from api_utils.flask_utils.exceptions import (
    HTTPBadRequest,
    HTTPForbidden,
    HTTPNotFound,
    HTTPInternalServerError,
)
from api_utils.mongo_utils import execute_infinite_scroll_query
import logging

logger = logging.getLogger(__name__)

# Allowed sort fields for Customer domain
ALLOWED_SORT_FIELDS = ["name", "description"]


class CustomerService:
    """
    Service class for Customer domain operations.

    Handles:
    - RBAC authorization checks (placeholder for future implementation)
    - MongoDB operations via MongoIO singleton
    - Business logic for Customer domain (read-only)
    """

    @staticmethod
    def _check_permission(token, operation):
        """
        Check if the user has permission to perform an operation.

        Args:
            token: Token dictionary with user_id and roles
            operation: The operation being performed (e.g., 'read')

        Raises:
            HTTPForbidden: If user doesn't have required permission

        Note: This is a placeholder for future RBAC implementation.
        For now, all operations require a valid token (authentication only).

        Example RBAC implementation:
            if operation == 'read':
                # Read requires any authenticated user (no additional check needed)
                # For stricter requirements, you could require specific roles:
                # if not any(role in token.get('roles', []) for role in ['staff', 'admin', 'viewer']):
                #     raise HTTPForbidden("Insufficient permissions to read customer documents")
                pass
        """
        pass

    @staticmethod
    def get_customers(
        token,
        breadcrumb,
        name=None,
        after_id=None,
        limit=10,
        sort_by="name",
        order="asc",
    ):
        """
        Get infinite scroll batch of sorted, filtered customer documents.

        Args:
            token: Authentication token
            breadcrumb: Audit breadcrumb
            name: Optional name filter (simple search)
            after_id: Cursor (ID of last item from previous batch, None for first request)
            limit: Items per batch
            sort_by: Field to sort by
            order: Sort order ('asc' or 'desc')

        Returns:
            dict: {
                'items': [...],
                'limit': int,
                'has_more': bool,
                'next_cursor': str|None  # ID of last item, or None if no more
            }

        Raises:
            HTTPBadRequest: If invalid parameters provided
        """
        try:
            CustomerService._check_permission(token, "read")
            mongo = MongoIO.get_instance()
            config = Config.get_instance()
            collection = mongo.get_collection(config.CUSTOMER_COLLECTION_NAME)
            result = execute_infinite_scroll_query(
                collection,
                name=name,
                after_id=after_id,
                limit=limit,
                sort_by=sort_by,
                order=order,
                allowed_sort_fields=ALLOWED_SORT_FIELDS,
            )
            logger.info(
                f"Retrieved {len(result['items'])} customers (has_more={result['has_more']}) "
                f"for user {token.get('user_id')}"
            )
            return result
        except HTTPBadRequest:
            raise
        except Exception as e:
            logger.error(f"Error retrieving customers: {str(e)}")
            raise HTTPInternalServerError("Failed to retrieve customers")

    @staticmethod
    def get_customer(customer_id, token, breadcrumb):
        """
        Retrieve a specific customer document by ID.

        Args:
            customer_id: The customer ID to retrieve
            token: Token dictionary with user_id and roles
            breadcrumb: Breadcrumb dictionary for logging

        Returns:
            dict: The customer document

        Raises:
            HTTPNotFound: If customer is not found
        """
        try:
            CustomerService._check_permission(token, "read")

            mongo = MongoIO.get_instance()
            config = Config.get_instance()
            customer = mongo.get_document(config.CUSTOMER_COLLECTION_NAME, customer_id)
            if customer is None:
                raise HTTPNotFound(f"Customer { customer_id} not found")

            logger.info(
                f"Retrieved customer { customer_id} for user {token.get('user_id')}"
            )
            return customer
        except HTTPNotFound:
            raise
        except Exception as e:
            logger.error(f"Error retrieving customer { customer_id}: {str(e)}")
            raise HTTPInternalServerError(f"Failed to retrieve customer { customer_id}")
