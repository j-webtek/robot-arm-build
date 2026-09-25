"""Offline encoder-endpoint hypotheses; never converts fits into motion commands."""
from statistics import mean


def compare_models(rows, *, training_count=6):
    """Freeze fits on the first cycle, then score later legs without refitting.

    The stateful band model clips each measured starting position to a band
    around the target. Band edges come only from clearly moving training legs.
    This is a one-step prediction using the measured start, not a free-running
    trajectory simulation or proof of backlash/deadband in the mechanism.
    """
    if not 1 < training_count < len(rows):
        raise ValueError('Separate chronological training and evaluation required')
    if [r['leg'] for r in rows] != list(range(len(rows))):
        raise ValueError('Unique contiguous ordered legs required')
    for row in rows:
        for key in ('target', 'before', 'actual', 'goal_delta'):
            if len(row[key]) != 2 or any(type(v) is not int for v in row[key]):
                raise ValueError('Two integer joint values required')
        if sum(row['target']) != 4114 or not row['goal_delta'][0] or sum(row['goal_delta']):
            raise ValueError('Coupled nonzero target change required')
    train, held = rows[:training_count], rows[training_count:]
    def residual(row, j):
        return row['actual'][j]-row['target'][j]
    constant = [mean(residual(r,j) for r in train) for j in range(2)]
    directional, edges = {}, {}
    for direction in (-1,1):
        group = [r for r in train if (1 if r['goal_delta'][0]>0 else -1)==direction]
        clear = [r for r in group if all(abs(a-b)>=2 for a,b in zip(r['actual'],r['before']))]
        if not group or not clear:
            raise ValueError('Both directions need clearly moving training evidence')
        directional[direction] = [mean(residual(r,j) for r in group) for j in range(2)]
        edges[direction] = [mean(residual(r,j) for r in clear) for j in range(2)]
    bands = [[min(edges[-1][j],edges[1][j]),max(edges[-1][j],edges[1][j])] for j in range(2)]
    predictions=[]
    for row in rows:
        direction=1 if row['goal_delta'][0]>0 else -1
        models = dict(constant=[g+b for g,b in zip(row['target'],constant)],
            directional=[g+b for g,b in zip(row['target'],directional[direction])],
            stateful_band=[max(g+lo,min(p,g+hi)) for g,p,(lo,hi) in
                           zip(row['target'],row['before'],bands)])
        predictions.append(dict(leg=row['leg'],split='train' if row['leg']<training_count else 'held_out',
            models={name:dict(predicted=values,signed_error=[a-p for a,p in zip(row['actual'],values)])
                    for name,values in models.items()}))
    metrics={}
    for name in ('constant','directional','stateful_band'):
        errors=[abs(v) for p in predictions[training_count:] for v in p['models'][name]['signed_error']]
        metrics[name]=dict(mean_absolute_error_counts=mean(errors),maximum_absolute_error_counts=max(errors))
    return dict(schema='rocell.matrix_model_review.v1',training_legs=[r['leg'] for r in train],
        held_out_legs=[r['leg'] for r in held],constant_residual=constant,
        directional_residual=directional,clear_response_band_edges=edges,bands=bands,
        predictions=predictions,held_out_metrics=metrics,rows=rows,
        evaluation_basis='one_step_from_measured_start',
        held_out_contains_clear_motion=any(all(abs(a-b)>=2 for a,b in zip(r['actual'],r['before'])) for r in held),
        compensation_authorized=False,hardware_access=False,physical_accuracy_verified=False)
