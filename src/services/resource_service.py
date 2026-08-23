"""
Discovery Resource service.

Discovery **consumes** Resource, so the shared consume surface is inherited
unchanged. The subclass exists so routes and Card lists bind to the local class
and any future Discovery-specific behaviour dispatches through `cls`.
"""

from api_utils.services import ResourceService as SharedResourceService


class ResourceService(SharedResourceService):
    """Discovery subclass of the shared Resource service (consume only)."""
