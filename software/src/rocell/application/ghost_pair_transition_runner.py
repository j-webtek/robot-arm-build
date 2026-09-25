"""Exact-route runner for a ghost-pair transition campaign.

This class has no transport construction or startup authority. The caller must
provide a fresh authenticated client and an independently reviewed start gate.
"""
from __future__ import annotations

from .ghost_pair_transition_campaign import plan_ghost_pair_transition_campaign
from .local_pair_mapping_runner import LocalPairMappingRunner


class GhostPairTransitionRunner(LocalPairMappingRunner):
    plan_factory=staticmethod(plan_ghost_pair_transition_campaign)
    initial_goals=(2389,1725)
    initial_positions=(2391,1724)
    initial_tolerance=1
    start_attachment='ghost-pair-transition-session-start.json'
    result_attachment='ghost-pair-transition-session-result.json'
    result_schema='rocell.ghost_pair_transition_session_result.v1'
