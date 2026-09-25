"""Host runner for one exact r51 local-interval startup session."""
from __future__ import annotations

from .local_interval_campaign import plan_local_interval_campaign
from .local_pair_mapping_runner import LocalPairMappingRunner


class LocalIntervalRunner(LocalPairMappingRunner):
    plan_factory=staticmethod(plan_local_interval_campaign)
    initial_goals=(2389,1725)
    initial_positions=(2391,1724)
    initial_tolerance=1
    start_attachment='local-interval-session-start.json'
    result_attachment='local-interval-session-result.json'
    result_schema='rocell.local_interval_session_result.v1'
