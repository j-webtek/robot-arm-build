"""Pure design for a reverse-direction held-out shoulder-pair comparison."""
from copy import deepcopy

from .characterization_admission import encode_manifest
from .local_pair_offset import pair
from .stateful_pair_compensation import propose


UPPER = [2389, 1725]
LOWER = [2377, 1737]
DESIRED = [2387, 1729]


def _manifest(goals, bounds):
    value = dict(goals=deepcopy(goals), bounds=deepcopy(bounds), maximum_us=60000000)
    encode_manifest(value, campaign="00" * 32, reference="00" * 32)
    if any(sum(pair(goal)) != 4114 for goal in goals):
        raise ValueError("Coupled shoulder targets required")
    return value


def draft(frozen, bounds, *, evidence_export, evidence_model_sha256,
          current_position=(2390, 1724), campaign_anchor=(2391, 1724)):
    """Freeze a candidate/control pair without reading or contacting hardware."""
    if frozen.get("sha256") != evidence_model_sha256:
        raise ValueError("Consolidated evidence and frozen model differ")
    if type(evidence_export) is not str or not evidence_export.startswith("wizard-"):
        raise ValueError("Consolidated evidence export required")
    if type(bounds) not in (list, tuple) or len(bounds) != 7:
        raise ValueError("Seven reviewed joint bounds required")
    current_position = pair(current_position)
    proposal = propose(
        frozen, current_goals=UPPER, current_positions=current_position,
        desired=DESIRED, bounds=bounds[1:3], tested_primary_range=(2377, 2389),
        campaign_anchor=campaign_anchor)
    if (proposal["proposed_goals"] != [2378, 1736] or
            proposal["uncompensated_coupled_goals"] != [2386, 1728] or
            proposal["predictions"]["stateful_band"] != [2387.6666666666665, 1729]):
        raise ValueError("Frozen reverse held-out proposal differs")

    # Both terminal trials approach from LOWER through UPPER. The control needs
    # one additional setup leg because its predecessor is the candidate target;
    # starting with LOWER there would be a one-count command and is intentionally
    # rejected by the clear-response policy.
    candidate = [LOWER, UPPER, proposal["proposed_goals"]]
    control = [UPPER, LOWER, UPPER, proposal["uncompensated_coupled_goals"]]
    return dict(
        schema="rocell.second_heldout_pair_validation.v1",
        source_bidirectional_evidence_export=evidence_export,
        frozen_model_sha256=frozen["sha256"], model_refitted=False,
        desired=DESIRED, expected_common_trial_start=[2391, 1724],
        matched_start_tolerance_counts=1,
        candidate=dict(manifest=_manifest(candidate, bounds),
                       roles=["conditioning_lower", "conditioning_upper", "heldout_candidate"],
                       frozen_prediction=proposal["predictions"]["stateful_band"]),
        control=dict(manifest=_manifest(control, bounds),
                     roles=["setup_upper", "conditioning_lower", "conditioning_upper", "heldout_control"],
                     frozen_prediction=[2390, 1724]),
        proposal=proposal, execution_order=["candidate", "control"],
        endpoint_is_new=True, command_is_interpolation=True,
        automatic_retry=False, automatic_return=False,
        separate_campaign_admission_required=True,
        fresh_pose_reacquisition_required=True,
        physical_clearance_must_be_reconfirmed=True,
        hardware_access=False, movement_authorized=False,
        physical_accuracy_verified=False, general_compensation_validated=False)
