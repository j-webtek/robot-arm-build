"""Reuse the finite publish-before-progression loop for the fixed wrist pair."""
from .compensated_elbow_cycle import CompensatedElbowCycle
from .wrist_shared_pair import pair_candidate


class CompensatedWristCycle(CompensatedElbowCycle):
    MODES=('down','up')
    JOINT=4
    SCHEMA='rocell.compensated_wrist_cycle.v1'

    def candidate(self,mode):
        return pair_candidate(mode)
