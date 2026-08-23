"""
Discovery Path service.

Discovery **consumes** Path, so the shared consume surface is inherited
unchanged. The subclass exists so routes and Card lists bind to the local class
and any future Discovery-specific behaviour dispatches through `cls`.
"""

from api_utils.services import PathService as SharedPathService


class PathService(SharedPathService):
    """Discovery subclass of the shared Path service (consume only)."""
