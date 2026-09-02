"""
Discovery Notification service.

Discovery **controls** Notification. Create and read are inherited from the
shared service; dismiss and cancel are Discovery-only control mutations that
set a single breadcrumb field and nothing else. `dismissed` and `cancelled`
are breadcrumbs, not booleans, and Notification has no `saved` field.
"""

import logging

from api_utils import Config, MongoIO
from api_utils.flask_utils.exceptions import HTTPForbidden
from api_utils.mongo_utils.list_query import DEFAULT_OFFSET, DEFAULT_SIZE, and_match
from api_utils.services import NotificationService as SharedNotificationService
from api_utils.services.rbac import is_admin, require_outbound

logger = logging.getLogger(__name__)

DISMISSED_FIELD = "dismissed"
CANCELLED_FIELD = "cancelled"

# Notification target scopes a caller may claim from the token.
TARGET_FIELDS = ("profile_id", "customer_id", "mentor_id")


def active_match():
    """Match for notifications that carry neither breadcrumb."""
    return {
        DISMISSED_FIELD: {"$exists": False},
        CANCELLED_FIELD: {"$exists": False},
    }


def _notification_cards(notifications, token=None):
    """
    Project Notification documents onto Notification Cards.

    `card_service` imports this module for the composite home list, so the Card
    import happens at call time rather than at module scope.
    """
    from src.services.card_service import CARD_TYPE_NOTIFICATIONS, CardService

    return CardService.project_all(
        CARD_TYPE_NOTIFICATIONS,
        notifications,
        token=token,
    )


class NotificationService(SharedNotificationService):
    """
    Discovery subclass of the shared Notification service.

    Inherits `create_notification` and `get_notifications` (outbound RBAC lives
    on the shared class) and adds the dismiss / cancel control mutations plus
    the active-notification read used by the composite home Card list.
    """

    @classmethod
    def _check_permission(cls, token, operation, notification=None):
        """
        Inbound write check for the control mutations.

        Reads and creates keep the shared behaviour (authenticated caller). A
        dismiss or cancel additionally requires the caller to be an admin or to
        hold the token claim naming the notification's target. A globally
        scoped notification carries no target id, so only an admin may retire
        it for every reader.
        """
        if notification is None:
            return

        if is_admin(token):
            return

        for field in TARGET_FIELDS:
            target = notification.get(field)
            claim = token.get(field)
            if target is not None and claim and str(target) == str(claim):
                return

        raise HTTPForbidden(f"Not permitted to {operation} this notification")

    @classmethod
    def _set_control_breadcrumb(
        cls, notification_id, token, breadcrumb, field, operation
    ):
        """Set exactly one control breadcrumb on a visible, permitted notification."""
        mongo = MongoIO.get_instance()
        config = Config.get_instance()

        notification = mongo.get_document(
            config.NOTIFICATION_COLLECTION_NAME, notification_id
        )
        require_outbound(
            notification,
            cls._outbound_match(token),
            not_found_message=f"Notification {notification_id} not found",
        )
        cls._check_permission(token, operation, notification=notification)

        updated = mongo.update_document(
            config.NOTIFICATION_COLLECTION_NAME,
            notification_id,
            set_data={field: breadcrumb},
        )

        logger.info(
            f"Set {field} on notification {notification_id} "
            f"for user {token.get('user_id')}"
        )
        return updated

    @classmethod
    def dismiss_notification(cls, notification_id, token, breadcrumb):
        """
        Set the `dismissed` breadcrumb on a notification.

        Args:
            notification_id: The Notification ID to dismiss
            token: Token dictionary with user_id and roles
            breadcrumb: Breadcrumb dictionary stored as `dismissed`

        Returns:
            dict: The updated notification document

        Raises:
            HTTPNotFound: If the notification is missing or hidden by outbound RBAC
            HTTPForbidden: If the caller does not hold the notification's target claim
        """
        return cls._set_control_breadcrumb(
            notification_id, token, breadcrumb, DISMISSED_FIELD, "dismiss"
        )

    @classmethod
    def cancel_notification(cls, notification_id, token, breadcrumb):
        """
        Set the `cancelled` breadcrumb on a notification.

        Args:
            notification_id: The Notification ID to cancel
            token: Token dictionary with user_id and roles
            breadcrumb: Breadcrumb dictionary stored as `cancelled`

        Returns:
            dict: The updated notification document

        Raises:
            HTTPNotFound: If the notification is missing or hidden by outbound RBAC
            HTTPForbidden: If the caller does not hold the notification's target claim
        """
        return cls._set_control_breadcrumb(
            notification_id, token, breadcrumb, CANCELLED_FIELD, "cancel"
        )

    @classmethod
    def get_active_notifications(
        cls,
        token,
        breadcrumb,
        *,
        offset=DEFAULT_OFFSET,
        size=DEFAULT_SIZE,
        match=None,
    ):
        """
        Get notifications that have been neither dismissed nor cancelled.

        Args:
            token: Authentication token
            breadcrumb: Audit breadcrumb
            offset: Zero-based start index
            size: Number of documents to return
            match: Optional MongoDB match AND'd with the active and outbound scopes

        Returns:
            list: Active notification documents newest first by created.at_time
        """
        return cls.get_notifications(
            token,
            breadcrumb,
            offset=offset,
            size=size,
            match=and_match(active_match(), match or {}),
        )


class NotificationCardService(NotificationService):
    """
    Notification read surface projected onto the Card schema.

    Bound to `create_notification_get_routes` for `/api/cards/notifications`.
    Projection lives here and not on `NotificationService` so create, dismiss,
    and cancel keep returning the Notification document.
    """

    @classmethod
    def get_notifications(
        cls,
        token,
        breadcrumb,
        *,
        offset=DEFAULT_OFFSET,
        size=DEFAULT_SIZE,
        match=None,
    ):
        """Get the visible Notifications as Cards."""
        notifications = super().get_notifications(
            token, breadcrumb, offset=offset, size=size, match=match
        )
        return _notification_cards(notifications, token=token)
