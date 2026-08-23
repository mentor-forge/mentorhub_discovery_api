"""
Discovery Plan service.

Discovery **consumes** Plan, so the shared consume surface is inherited
unchanged. The subclass exists so routes and Card lists bind to the local class
and any future Discovery-specific behaviour dispatches through `cls`.
"""

from api_utils.mongo_utils.list_query import DEFAULT_OFFSET, DEFAULT_SIZE
from api_utils.services import PlanService as SharedPlanService

from src.services.card_service import CARD_TYPE_PLANS, CardService


class PlanService(SharedPlanService):
    """Discovery subclass of the shared Plan service (consume only)."""


class PlanCardService(PlanService):
    """
    Plan consume surface projected onto the Card schema.

    Bound to `create_plan_get_routes` so `/api/cards/plans` returns `Card[]`;
    the unprojected documents stay available on `PlanService`.
    """

    @classmethod
    def get_plans(
        cls,
        token,
        breadcrumb,
        offset=DEFAULT_OFFSET,
        size=DEFAULT_SIZE,
        filters=None,
        sort_by=None,
    ):
        """Get the visible Plans as Cards."""
        plans = super().get_plans(token, breadcrumb, offset, size, filters, sort_by)
        return CardService.project_all(CARD_TYPE_PLANS, plans)
