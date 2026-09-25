"""Local readback prediction, not a motion or compensation controller."""
from dataclasses import dataclass
from statistics import mean

from .first_motion_contract import canonical
from .p4_repeat_campaign import assess_leg
from .p4_repeat_campaign_review import GOALS
from .product_ghost_export_review import _read
from .wizard_diagnostic_export import verify_export

TRAIN='wizard-20260924T184928945241Z-a5a64a08eb254bd0bb0a2b7110fdc2da'
TEST='wizard-20260924T185253127570Z-3b13c2395f064910a7cb46aeaf469527'


def load_session(exports, summary_id):
    exports=exports.resolve()
    summary,_=_read(exports,summary_id,'attachment-r72-campaign-summary.json')
    if summary.get('verified_legs')!=12 or len(set(summary['source_exports']))!=12:
        raise ValueError('Complete distinct twelve-leg session required')
    rows=[]
    for leg,source in enumerate(summary['source_exports'],1):
        saved,_=_read(exports,source,'attachment-p4-repeat-assessment.json')
        if not verify_export(exports/source)['valid']:raise ValueError('Source export invalid')
        raw=bytes.fromhex((exports/source/'attachment-p4-repeat-record.hex.txt').read_text('ascii'))
        row=assess_leg(raw,boot=summary['boot'],leg=leg,previous=rows[-1] if rows else None)
        row['source_kind']='controller_feedback'
        if canonical(row)!=canonical(saved):raise ValueError('Assessment differs from raw replay')
        rows.append(row)
    return rows


@dataclass(frozen=True)
class EndpointTable:
    training_boot: str
    # (command goal, approach sign, mean position-minus-goal, sample count, spread)
    cells: tuple

    def predict(self, goal, direction, *, passive_goals=GOALS, speed=20, acceleration=1):
        if (type(goal) is not int or type(direction) is not int or direction not in (-1,1)
                or speed!=20 or acceleration!=1 or len(passive_goals)!=7
                or any(passive_goals[i]!=GOALS[i] for i in range(7) if i!=4)):
            raise ValueError('Outside reviewed scope')
        for target,sign,bias,_,_ in self.cells:
            if (goal,direction)==(target,sign):return goal+bias
        raise ValueError('Unseen goal/direction; no interpolation or extrapolation')


def fit_table(rows):
    if len(rows)!=12 or len({r['boot'] for r in rows})!=1:
        raise ValueError('One complete training session required')
    if [r['leg'] for r in rows]!=list(range(1,13)):
        raise ValueError('Training legs incomplete or reordered')
    cells=[]
    for goal,direction in sorted({(r['target'],r['direction']) for r in rows}):
        selected=[r for r in rows if (r['target'],r['direction'])==(goal,direction)]
        errors=[r['endpoint_error_counts'] for r in selected]
        cells.append((goal,direction,mean(errors),len(errors),max(errors)-min(errors)))
    return EndpointTable(rows[0]['boot'],tuple(cells))


def evaluate(table, rows):
    if len(rows)!=12 or any(r['boot']==table.training_boot for r in rows):
        raise ValueError('Separate complete evaluation session required')
    if len({r['boot'] for r in rows})!=1 or [r['leg'] for r in rows]!=list(range(1,13)):
        raise ValueError('Evaluation session incomplete or reordered')
    residuals=[]
    for row in rows:
        predicted=table.predict(row['target'],row['direction'],passive_goals=row['final_goals'])
        actual=row['final_positions'][4]
        residuals.append(dict(leg=row['leg'],goal=row['target'],direction=row['direction'],
            predicted_position=predicted,measured_position=actual,
            prediction_error_counts=actual-predicted,
            goal_only_prediction_error_counts=actual-row['target']))
    return dict(rows=residuals,
        table_mae_counts=mean(abs(r['prediction_error_counts']) for r in residuals),
        table_max_error_counts=max(abs(r['prediction_error_counts']) for r in residuals),
        goal_only_mae_counts=mean(abs(r['goal_only_prediction_error_counts']) for r in residuals),
        goal_only_max_error_counts=max(abs(r['goal_only_prediction_error_counts']) for r in residuals))
