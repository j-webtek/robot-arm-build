"""Offline diagnostic proposals and classification, never movement authority.

Keep small-response observations separate from both endpoint success and unsafe
evidence. The installed firmware's stop policy is deliberately not changed here.
"""
from .local_pair_offset import pair
from .shoulder_characterization import assess_leg

MATRIX_OFFSETS = (-4, 0, -8, 0, -12, 0) * 2
MAPPING_BATCH_PRIMARY = (2377, 2389, 2379, 2387, 2381, 2389,
                         2377, 2385, 2389, 2383, 2377, 2388)
SEPARATED_MAPPING_BATCH_PRIMARY = (2389, 2377, 2385, 2389, 2383, 2377,
                                   2388, 2377, 2381, 2389, 2377, 2387)
FINE_LOOKUP_VALIDATION_PRIMARY = (2377, 2385, 2389, 2377, 2385, 2389,
                                  2377, 2388, 2389, 2377, 2388, 2389)
LOCAL_INTERVAL_CAMPAIGN_PRIMARY = (2377,2383,2389,2377,2385,2389,
                                   2377,2388,2389,2377,2389)
GHOST_PAIR_TRANSITION_PRIMARY = (2377,2386,2388,2386,2388,2386,
                                 2377,2386,2388,2386,2388,2389)


def matrix_anchor(targets):
    """Recognize only the exact signed target matrix; no implicit legacy opt-in."""
    if len(targets) != len(MATRIX_OFFSETS):
        return None
    anchor = pair(targets[1])
    if sum(anchor) != 4114:
        return None
    expected = [[anchor[0]+offset, anchor[1]-offset] for offset in MATRIX_OFFSETS]
    return anchor if [list(target) for target in targets] == expected else None


def is_mapping_batch(targets):
    """Recognize only the exact r48/r49 routes for retained-small review."""
    actual = [list(target) for target in targets]
    return any(actual == [[primary, 4114-primary] for primary in route]
               for route in (MAPPING_BATCH_PRIMARY, SEPARATED_MAPPING_BATCH_PRIMARY,
                             FINE_LOOKUP_VALIDATION_PRIMARY,LOCAL_INTERVAL_CAMPAIGN_PRIMARY,
                             GHOST_PAIR_TRANSITION_PRIMARY))


def is_ghost_pair_transition(targets):
    """Select the stricter direct-transition policy only for its exact route."""
    return [list(target) for target in targets]==[
        [primary,4114-primary] for primary in GHOST_PAIR_TRANSITION_PRIMARY]


def draft_matrix(goals, positions, *, previous_targets=()):
    goals, positions = pair(goals), pair(positions)
    if sum(goals) != 4114:
        raise ValueError('Reviewed paired coupling required')
    history = {pair(target) for target in previous_targets}
    # Two repeats per magnitude; explicit reposition legs also produce evidence.
    # Relative register excursions, not promises of physical displacement.
    offsets = MATRIX_OFFSETS
    legs, previous = [], goals
    for index, offset in enumerate(offsets):
        target = pair((goals[0]+offset, goals[1]-offset))
        if any(abs(g-p)>32 for g,p in zip(target,positions)):
            raise ValueError('Target outside measured-anchor envelope')
        delta = [g-p for g,p in zip(target,previous)]
        if not 0 < abs(delta[0]) <= 24 or delta[0] != -delta[1]:
            raise ValueError('Invalid register step')
        legs.append(dict(leg=index, targets=list(target), register_delta=delta,
                         target_minus_initial_measured=[g-p for g,p in zip(target,positions)],
                         previously_visited_target=target in history,
                         speed=20, acceleration=1))
        history.add(target); previous=target
    return dict(schema='rocell.shoulder_movement_matrix.v1', basis='OFFLINE_PROPOSAL',
                anchor_goals=list(goals), anchor_positions=list(positions), legs=legs,
                maximum_selected_excursion_counts=32, maximum_neighbour_excursion_counts=2,
                compensation_enabled=False, movement_authorized=False,
                physical_clearance_verified=False, measured_travel_prediction=None)


def classify_observation(before, goals, samples, *, bounds, delivery_confirmed,
                         export_verified, consecutive_small=0):
    """Describe retained data without altering assess_leg or issuing a receipt.

    Candidate progression is a review decision only: at most one consecutive
    small response, settled valid feedback, bounded residuals, and no unsafe
    direction. Runtime adoption still requires matched host/native contracts.
    """
    if type(consecutive_small) is not int or consecutive_small < 0:
        raise ValueError('Invalid small-response history')
    assessment=assess_leg(before,goals,samples,bounds=bounds,
                          delivery_confirmed=delivery_confirmed,export_verified=export_verified)
    result=dict(assessment=assessment, movement_authorized=False, receipt_issued=False,
                candidate_progression_eligible=False, classification='UNSAFE_OR_UNVERIFIED')
    if assessment['reason'] not in ('MEASUREMENT_RETAINED','NO_CLEAR_RESPONSE'):
        return result
    net=[samples[-1].positions[i]-before.positions[i] for i in (1,2)]
    peak=[max(abs(p.positions[i]-before.positions[i]) for p in samples) for i in (1,2)]
    residual=[samples[-1].positions[i]-goals[i-1] for i in (1,2)]
    small=assessment['reason']=='NO_CLEAR_RESPONSE'
    if not small:
        label=assessment['status']
    elif any(p>=2 and abs(n)<2 for p,n in zip(peak,net)):
        label='TRANSIENT_THEN_SMALL_NET_RESPONSE'
    elif any(peak):
        label='SMALL_SETTLED_RESPONSE'
    else:
        label='NO_SAMPLED_DISPLACEMENT'
    result.update(classification=label, final_net_counts=net,
                  sampled_peak_absolute_counts=peak, endpoint_error=residual,
                  sampled_motion_observed=any(peak), continuous_motion_verified=False,
                  next_consecutive_small=consecutive_small+1 if small else 0,
                  candidate_progression_eligible=max(map(abs,residual))<=12 and
                      (not small or consecutive_small==0))
    return result
