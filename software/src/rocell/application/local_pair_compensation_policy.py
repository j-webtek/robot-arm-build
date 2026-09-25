"""Evidence-bound local shoulder-pair command policy; no transport or motion API."""
from copy import deepcopy

from .local_pair_offset import pair


MODEL = "963df1b4975ca385e6b8d9cd9509695fdfa4838f0cab9bcde9444e28c28452e5"
DESIRED = (2387, 1729)
APPROACH_GOALS = (2389, 1725)
APPROACH_POSITIONS = (2391, 1724)
CANDIDATE_COMMAND = (2378, 1736)
CONTROL_COMMAND = (2386, 1728)


def promote(comparison, candidate_manifest, *, comparison_export, comparison_sha256):
    """Promote only the exact independently compared reverse-direction action."""
    if (comparison.get("schema") != "rocell.second_heldout_candidate_control_comparison.v1" or
            comparison.get("comparison_eligible") is not True or
            comparison.get("local_reverse_compensation_supported") is not True or
            comparison.get("candidate_improves_all_primary_metrics") is not True or
            comparison.get("model_sha256") != MODEL or comparison.get("model_refitted") is not False or
            comparison.get("general_compensation_validated") is not False or
            comparison.get("desired") != list(DESIRED) or
            comparison.get("candidate_before") != list(APPROACH_POSITIONS) or
            comparison.get("control_before") != list(APPROACH_POSITIONS) or
            comparison.get("candidate_error") != [0, 1] or
            comparison.get("control_terminal_outcome") != "NO_CLEAR_RESPONSE"):
        raise ValueError("Exact eligible second held-out comparison required")
    goals = candidate_manifest.get("goals") if type(candidate_manifest) is dict else None
    if goals != [[2377, 1737], list(APPROACH_GOALS), list(CANDIDATE_COMMAND)]:
        raise ValueError("Exact r46 candidate manifest required")
    if (type(comparison_export) is not str or not comparison_export.startswith("wizard-") or
            type(comparison_sha256) is not str or len(comparison_sha256) != 64):
        raise ValueError("Verified comparison provenance required")
    return dict(schema="rocell.local_pair_compensation_policy.v1",
        scope="EXACT_REVERSE_ENDPOINT_FROM_MATCHED_UPPER_APPROACH",
        frozen_model_sha256=MODEL, comparison_export=comparison_export,
        comparison_sha256=comparison_sha256,
        required_current_goals=list(APPROACH_GOALS),
        required_current_positions=list(APPROACH_POSITIONS),
        current_position_tolerance_counts=1,
        desired_positions=list(DESIRED), command_goals=list(CANDIDATE_COMMAND),
        rejected_direct_control_goals=list(CONTROL_COMMAND),
        observed_candidate_positions=deepcopy(comparison["candidate_actual"]),
        observed_candidate_error=deepcopy(comparison["candidate_error"]),
        observed_control_positions=deepcopy(comparison["control_actual"]),
        observed_control_error=deepcopy(comparison["control_error"]),
        encoder_endpoint_validated=True, cartesian_accuracy_validated=False,
        stylus_accuracy_validated=False, general_compensation_validated=False,
        automatic_retry=False, automatic_return=False,
        hardware_access=False, movement_authorized=False)


def resolve(policy, *, current_goals, current_positions, desired_positions):
    """Resolve the one validated action; reject extrapolation and stale state."""
    if (policy.get("schema") != "rocell.local_pair_compensation_policy.v1" or
            policy.get("frozen_model_sha256") != MODEL or
            policy.get("encoder_endpoint_validated") is not True or
            policy.get("general_compensation_validated") is not False):
        raise ValueError("Validated local policy required")
    goals, positions, desired = map(pair, (current_goals, current_positions, desired_positions))
    if goals != APPROACH_GOALS or desired != DESIRED:
        raise ValueError("Requested action is outside validated local scope")
    tolerance = policy.get("current_position_tolerance_counts")
    if type(tolerance) is not int or tolerance != 1 or any(
            abs(a-b) > tolerance for a, b in zip(positions, APPROACH_POSITIONS)):
        raise ValueError("Fresh current position differs from validated approach state")
    return dict(schema="rocell.local_pair_compensation_resolution.v1",
        desired_positions=list(desired), command_goals=list(CANDIDATE_COMMAND),
        expected_encoder_positions=deepcopy(policy["observed_candidate_positions"]),
        policy_comparison_export=policy["comparison_export"],
        compensation_applied=True, encoder_endpoint_validated=True,
        cartesian_accuracy_validated=False, movement_authorized=False,
        fresh_feedback_required=True, automatic_retry=False)
