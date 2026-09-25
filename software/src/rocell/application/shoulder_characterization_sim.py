"""Finite built-in simulation, not an injectable hardware runner.

All servo state and faults are synthetic. Only diagnostic export writes occur.
Each next baseline is reacquired from the simulated final state, never the target.
"""
from dataclasses import asdict, replace
from pathlib import Path
from .compensated_shoulder_contract import Pose, REFERENCE, GOALS
from .first_motion_contract import canonical
from .shoulder_characterization import draft_manifest, assess_leg
from .wizard_diagnostic_export import WizardDiagnosticExporter, verify_export

FAULTS=('NONE','NEIGHBOR','REVERSE','WRONG_GOAL','TORQUE','NO_RESPONSE','UNSETTLED',
        'FEEDBACK_GAP','DELIVERY','EXPORT','BASELINE_DRIFT','CANCELLED')


def run_characterization_sim(exports, *, residual=(9,-7), fault='NONE', fault_leg=4,
                             pattern='legacy', reverse_residual=None):
    if (type(residual) not in (tuple,list) or len(residual)!=2 or
        any(type(v) is not int or abs(v)>12 for v in residual) or fault not in FAULTS or
        type(fault_leg) is not int or not 1<=fault_leg<=12):
        raise ValueError('Bounded synthetic scenario required')
    if reverse_residual is not None and (
        type(reverse_residual) not in (tuple,list) or len(reverse_residual)!=2 or
        any(type(v) is not int or abs(v)>12 for v in reverse_residual)):
        raise ValueError('Bounded reverse residual required')
    manifest=draft_manifest(GOALS[1:3], pattern=pattern)
    exporter=WizardDiagnosticExporter(Path(exports).resolve());exporter.prepare(create=True)
    bounds=[(max(0,p-32),min(4095,p+32)) for p in REFERENCE]
    position=list(REFERENCE);position[1:3]=[g+r for g,r in zip(GOALS[1:3],residual)]
    state=Pose(position,GOALS,(1,)*7,(False,)*7,1,1000)
    anchor=state;clock=1000
    report=dict(schema='rocell.shoulder_characterization_sim.v1',basis='SYNTHETIC_ONLY',
        manifest=manifest,bounds=bounds,fault=fault,fault_leg=fault_leg,residual=list(residual),pattern=pattern,
        state='RUNNING',legs=[],simulated_packets=0,physical_packets=0,
        movement_authorized=False,exports=[])
    report['reverse_residual']=None if reverse_residual is None else list(reverse_residual)

    def save(kind,document,*,track=True):
        saved=exporter.export({'mode':'shoulder-characterization-simulation'},[],
            attachments={kind+'.json':canonical(document)})
        path=Path(saved['path'])
        if not verify_export(path)['valid']:raise OSError('Export verification failed')
        if track:report['exports'].append(str(path))
        return str(path)

    save('campaign-manifest',manifest)
    for leg in manifest['legs']:
        active=fault if leg['leg_id']==fault_leg else 'NONE'
        row=dict(leg_id=leg['leg_id'],command=leg,predecessor_export=report['exports'][-1],packet_sent=False)
        report['legs'].append(row)
        try:
            if clock-anchor.finished_us>=60000000:raise ValueError('CAMPAIGN_DEADLINE')
            if active=='CANCELLED':raise ValueError('CANCELLED')
            # Explicit new acquisition time, retaining actual state and goals.
            clock+=200000
            before=replace(state,started_us=clock,finished_us=clock+1000)
            if active=='BASELINE_DRIFT':before=replace(before,positions=(before.positions[0]+3,)+before.positions[1:])
            before.validate(before.finished_us)
            goals=tuple(leg['command_goals'])
            if (any(before.moving) or sum(goals)!=4114 or
                any(abs(g-p)>32 for g,p in zip(goals,before.positions[1:3])) or
                any(not lo<=p<=hi for p,(lo,hi) in zip(before.positions,bounds)) or
                any(not bounds[i][0]<=goals[i-1]<=bounds[i][1] for i in (1,2)) or
                any(abs(before.positions[i]-state.positions[i])>1 for i in range(7)) or
                before.goals!=state.goals or
                any(abs(before.positions[i]-anchor.positions[i])>2 for i in (0,3,4,5,6))):
                raise ValueError('BASELINE_REJECTED')
            delta=[g-old for g,old in zip(goals,before.goals[1:3])]
            if not delta[0] or delta[0]!=-delta[1] or max(map(abs,delta))>24:
                raise ValueError('COMMAND_REJECTED')
            row['baseline']=asdict(before)
            row['intent_export']=save('leg-intent',row)
            # This is the only simulated dispatch site; there is no transport.
            report['simulated_packets']+=1;row['packet_sent']=True
            # Deliberately synthetic alternatives: constant bias versus bias that
            # changes with approach direction. Neither is a fitted hardware model.
            active_residual=reverse_residual if delta[0]>0 and reverse_residual is not None else residual
            row['target_minus_measured']=[g-p for g,p in zip(goals,before.positions[1:3])]
            positions=list(before.positions);positions[1:3]=[g+r for g,r in zip(goals,active_residual)]
            goal_rows=list(before.goals);goal_rows[1:3]=goals
            if active=='NEIGHBOR':positions[4]+=3
            if active=='REVERSE':positions[1]=before.positions[1]-(2 if delta[0]>0 else -2)
            if active=='WRONG_GOAL':goal_rows[1]+=1
            if active=='NO_RESPONSE':positions=list(before.positions)
            samples=[]
            for index in range(3):
                clock=before.finished_us+(index+1)*200000
                if active=='FEEDBACK_GAP':clock+=2000000
                samples.append(Pose(positions,goal_rows,(1,0,1,1,1,1,1) if active=='TORQUE' else (1,)*7,
                    (False,True,False,False,False,False,False) if active=='UNSETTLED' else (False,)*7,clock,clock+1000))
            state=samples[-1];clock=state.finished_us
            row['samples']=[asdict(p) for p in samples]
            row['raw_export']=save('leg-observations',row)
            row['assessment']=assess_leg(before,goals,samples,bounds=bounds,
                                         delivery_confirmed=active!='DELIVERY',export_verified=True)
            if active=='EXPORT':raise OSError('INJECTED_RESULT_EXPORT_FAILURE')
            row['result_export']=save('leg-result',row)
            if row['assessment']['status']=='STOP':
                report.update(state='STOPPED',reason=row['assessment']['reason']);break
        except (OSError,ValueError) as error:
            row['progression_stopped']=True
            report.update(state='STOPPED',reason=str(error));break
    else:report['state']='COMPLETED'
    report['completed_measurements']=sum('result_export' in row and row['assessment']['status']!='STOP' for row in report['legs'])
    saved=save('campaign-result',report,track=False)
    return dict(report=report,export_path=saved)
