"""Host review for the exact r49 separated-probe mapping campaign."""
from __future__ import annotations

from .local_pair_mapping_runner import LocalPairMappingRunner
from .separated_pair_mapping_batch import (
    INITIAL_GOALS,
    INITIAL_POSITIONS,
    INITIAL_TOLERANCE,
    plan_separated_mapping_batch,
)


class SeparatedPairMappingRunner(LocalPairMappingRunner):
    """Bind execution to r49's fixed route and retained r48 terminal state."""

    plan_factory = staticmethod(plan_separated_mapping_batch)
    initial_goals = INITIAL_GOALS
    initial_positions = INITIAL_POSITIONS
    initial_tolerance = INITIAL_TOLERANCE
    start_attachment = "separated-pair-mapping-start.json"
    result_attachment = "separated-pair-mapping-result.json"
    result_schema = "rocell.separated_pair_mapping_result.v1"
