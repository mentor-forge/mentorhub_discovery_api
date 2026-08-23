"""
Discovery Plan service.

Discovery **consumes** Plan, so the shared consume surface is inherited
unchanged. The subclass exists so routes and Card lists bind to the local class
and any future Discovery-specific behaviour dispatches through `cls`.
"""

from api_utils.services import PlanService as SharedPlanService


class PlanService(SharedPlanService):
    """Discovery subclass of the shared Plan service (consume only)."""
