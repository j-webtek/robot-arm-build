"""Cross-session plateau navigation policy; no transport or movement authority."""
from __future__ import annotations

from copy import deepcopy


R49_PRIMARY=(2389,2377,2385,2389,2383,2377,2388,2377,2381,2389,2377,2387)
R48_PRIMARY=(2377,2389,2379,2387,2381)


def _validate(rows, expected):
    if len(rows)!=len(expected) or [row.get('target',[None])[0] for row in rows]!=list(expected):
        raise ValueError('Exact retained mapping sequence required')
    for index,row in enumerate(rows):
        if row.get('leg')!=index or len(row.get('actual',[]))!=2:
            raise ValueError('Contiguous measured mapping rows required')


def derive_plateau_policy(r49_rows, r48_rows, *, r49_export, r48_export):
    """Train on r49 and score two matching transitions against untouched r48."""
    _validate(r49_rows,R49_PRIMARY);_validate(r48_rows,R48_PRIMARY)
    lower_train=[row for row in r49_rows
                 if row['target'][0]==2377 and row['approach_direction']==-1]
    upper_train=[row for row in r49_rows
                 if row['target'][0]==2389 and row['approach_direction']==1
                 and row['baseline_positions'][0] in (2385,2386)]
    if len(lower_train)!=4 or len(upper_train)!=1:
        raise ValueError('Expected r49 anchor evidence missing')
    lower_primary=[row['actual'][0] for row in lower_train]
    lower_second=[row['actual'][1] for row in lower_train]
    upper_primary=[row['actual'][0] for row in upper_train]
    upper_second=[row['actual'][1] for row in upper_train]

    lower_holdout=r48_rows[0];upper_holdout=r48_rows[1]
    if (lower_holdout['target']!=[2377,1737] or
            upper_holdout['target']!=[2389,1725]):
        raise ValueError('Exact r48 held-out anchor transitions required')
    lower_error=[max(0,min(lower_primary)-lower_holdout['actual'][0],
                     lower_holdout['actual'][0]-max(lower_primary)),
                 max(0,min(lower_second)-lower_holdout['actual'][1],
                     lower_holdout['actual'][1]-max(lower_second))]
    upper_error=[max(0,min(upper_primary)-upper_holdout['actual'][0],
                     upper_holdout['actual'][0]-max(upper_primary)),
                 max(0,min(upper_second)-upper_holdout['actual'][1],
                     upper_holdout['actual'][1]-max(upper_second))]
    heldout_pass=max(lower_error+upper_error)<=1
    if not heldout_pass:
        raise ValueError('Cross-session plateau prediction exceeded one count')
    return {'schema':'rocell.local_pair_plateau_policy.v1','scope':'ANCHOR_NAVIGATION_ONLY',
        'training_export':r49_export,'heldout_export':r48_export,
        'rules':{
            'lower':{'required_current_goals':[2389,1725],
                     'required_current_positions':{'minimum':[2390,1723],'maximum':[2392,1725]},
                     'command_goals':[2377,1737],
                     'expected_positions':{'minimum':[min(lower_primary),min(lower_second)],
                                           'maximum':[max(lower_primary),max(lower_second)]}},
            'upper':{'required_current_goals':[2377,1737],
                     'required_current_positions':{'minimum':[2384,1729],'maximum':[2387,1732]},
                     'command_goals':[2389,1725],
                     'expected_positions':{'minimum':[min(upper_primary),min(upper_second)],
                                           'maximum':[max(upper_primary),max(upper_second)]}},
        },
        'heldout':{'lower_actual':deepcopy(lower_holdout['actual']),
                   'upper_actual':deepcopy(upper_holdout['actual']),
                   'lower_out_of_training_range_counts':lower_error,
                   'upper_out_of_training_range_counts':upper_error,
                   'maximum_error_counts':max(lower_error+upper_error),'passed':True},
        'experimental_fine_endpoint_candidates':[
            {'conditioning_plateau':'lower','command_goals':[2385,1729],
             'observed_positions':[2387,1727],'heldout_validated':False},
            {'conditioning_plateau':'lower','command_goals':[2388,1726],
             'observed_positions':[2389,1725],'heldout_validated':False}],
        'encoder_anchor_navigation_validated':True,'fine_endpoint_lookup_validated':False,
        'general_compensation_validated':False,'cartesian_accuracy_validated':False,
        'stylus_accuracy_validated':False,'automatic_retry':False,'automatic_return':False,
        'movement_authorized':False,'hardware_access':False}


def resolve_plateau(policy, *, current_goals, current_positions, desired_plateau):
    """Resolve only a cross-session-validated conditioning transition."""
    if (policy.get('schema')!='rocell.local_pair_plateau_policy.v1' or
            policy.get('encoder_anchor_navigation_validated') is not True or
            policy.get('fine_endpoint_lookup_validated') is not False or
            policy.get('heldout',{}).get('passed') is not True):
        raise ValueError('Validated plateau policy required')
    if desired_plateau not in ('lower','upper'):
        raise ValueError('Only validated anchor plateaus may be resolved')
    rule=policy['rules'][desired_plateau]
    if list(current_goals)!=rule['required_current_goals']:
        raise ValueError('Current goals differ from validated transition')
    if len(current_positions)!=2 or any(not lo<=value<=hi for value,lo,hi in zip(
            current_positions,rule['required_current_positions']['minimum'],
            rule['required_current_positions']['maximum'])):
        raise ValueError('Fresh position is outside validated start plateau')
    return {'schema':'rocell.local_pair_plateau_resolution.v1',
        'desired_plateau':desired_plateau,'command_goals':deepcopy(rule['command_goals']),
        'expected_positions':deepcopy(rule['expected_positions']),
        'fine_endpoint_lookup':False,'movement_authorized':False,
        'fresh_feedback_required':True,'automatic_retry':False,'automatic_return':False}
