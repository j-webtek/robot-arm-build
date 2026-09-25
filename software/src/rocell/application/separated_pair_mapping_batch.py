"""Frozen r49 separated-probe mapping batch; planning only, no device access."""
from __future__ import annotations

from dataclasses import dataclass
import hashlib
import json


PRIMARY_TARGETS = (2389, 2377, 2385, 2389, 2383, 2377,
                   2388, 2377, 2381, 2389, 2377, 2387)
PAIR_SUM = 4114
INITIAL_GOALS = (2381, 1733)
INITIAL_POSITIONS = (2387, 1728)
INITIAL_TOLERANCE = 1


def _canonical(value: object) -> bytes:
    return json.dumps(value, sort_keys=True, separators=(",", ":")).encode("utf-8")


@dataclass(frozen=True)
class SeparatedPairMappingBatch:
    primary_targets: tuple[int, ...] = PRIMARY_TARGETS

    def __post_init__(self) -> None:
        if self.primary_targets != PRIMARY_TARGETS:
            raise ValueError("Exact reviewed separated mapping route required")

    @property
    def goals(self) -> tuple[tuple[int, int], ...]:
        return tuple((primary, PAIR_SUM-primary) for primary in self.primary_targets)

    def to_dict(self) -> dict[str, object]:
        goals=[list(pair) for pair in self.goals]
        deltas=[goals[index][0]-goals[index-1][0] for index in range(1,len(goals))]
        document: dict[str, object]={
            "schema":"rocell.separated_pair_mapping_batch.v1",
            "revision":49,
            "purpose":"encoder_mapping_with_separated_plateau_probes",
            "source_partial_map":"wizard-20260920T214732246917Z-16d2099d2e1747f5bc0d6082c99501bf",
            "initial_gate":{"goals":list(INITIAL_GOALS),"positions":list(INITIAL_POSITIONS),
                            "position_tolerance_counts":INITIAL_TOLERANCE},
            "manifest":{"goals":goals,"pair_sum":PAIR_SUM,"legs":len(goals)},
            "primary_step_deltas":deltas,
            "design":{"minimum_step_counts":min(map(abs,deltas)),
                      "plateau_probes_are_adjacent":False,
                      "repeated_lower_anchor":2377,"repeated_upper_anchor":2389},
            "limits":{"maximum_primary_step_counts":max(map(abs,deltas)),
                      "maximum_initial_excursion_counts":max(
                          abs(primary-INITIAL_POSITIONS[0]) for primary in self.primary_targets),
                      "writes_per_leg":1,"automatic_retry":False},
            "claims":{"general_compensation_validated":False,
                      "cartesian_accuracy_validated":False,"stylus_accuracy_validated":False,
                      "hardware_access_during_planning":False},
        }
        document["plan_sha256"]=hashlib.sha256(_canonical(document)).hexdigest()
        return document


def plan_separated_mapping_batch() -> dict[str, object]:
    return SeparatedPairMappingBatch().to_dict()
