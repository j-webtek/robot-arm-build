"""Host runner for the fixed r61 visible shoulder interval campaign."""
from __future__ import annotations

from .local_pair_mapping_runner import LocalPairMappingRunner
from .visible_interval_campaign import (
    SOURCE_GOALS, SOURCE_POSITIONS, plan_visible_interval_campaign,
)


class VisibleIntervalRunner(LocalPairMappingRunner):
    plan_factory = staticmethod(plan_visible_interval_campaign)
    initial_goals = SOURCE_GOALS
    initial_positions = SOURCE_POSITIONS
    initial_tolerance = 1
    start_attachment = "visible-interval-campaign-start.json"
    result_attachment = "visible-interval-campaign-result.json"
    result_schema = "rocell.visible_interval_campaign_result.v1"

