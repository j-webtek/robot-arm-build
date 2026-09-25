"""Host runner for the exact r50 fine-endpoint repeat-validation batch."""
from __future__ import annotations

from .fine_pair_lookup_validation import (
    INITIAL_GOALS,INITIAL_POSITIONS,INITIAL_TOLERANCE,plan_fine_lookup_validation)
from .local_pair_mapping_runner import LocalPairMappingRunner


class FinePairLookupRunner(LocalPairMappingRunner):
    plan_factory=staticmethod(plan_fine_lookup_validation)
    initial_goals=INITIAL_GOALS
    initial_positions=INITIAL_POSITIONS
    initial_tolerance=INITIAL_TOLERANCE
    start_attachment='fine-pair-lookup-start.json'
    result_attachment='fine-pair-lookup-result.json'
    result_schema='rocell.fine_pair_lookup_result.v1'
