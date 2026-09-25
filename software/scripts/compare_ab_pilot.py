"""Offline comparison of verified pilot exports. No hardware or model fitting."""
import argparse
from pathlib import Path
from rocell.application.product_ghost_export_review import _read
from rocell.application.compensation_ab_plan import compare_endpoints
from rocell.application.first_motion_contract import canonical
from rocell.application.wizard_diagnostic_export import WizardDiagnosticExporter, verify_export


def load_trial(exports, audit_id, variant):
    audit, digest = _read(exports, audit_id, 'attachment-ab-terminal-review.json')
    if audit['variant'] != variant or audit['terminal_measurement_usable'] is not True:
        raise ValueError('Usable selected-variant terminal audit required')
    def source(path, attachment):
        selected = Path(path)
        if selected.parent.resolve() != exports.resolve():
            raise ValueError('Source outside assigned export folder')
        return _read(exports, selected.name, attachment)[0]
    run = source(audit['source_run'], 'attachment-smoke-run.json')
    record = source(audit['source_result'], 'attachment-characterization-result.json')
    terminal = run.get('failed_leg_export')
    if terminal is None and run.get('legs'):
        terminal = run['legs'][-1]
    if not terminal or terminal['leg'] != 2 or terminal['export_path'] != audit['source_result']:
        raise ValueError('Terminal source is not the run result')
    expected = [[2377,1737],[2389,1725],
                [2387,1727] if variant == 'control' else [2378,1736]]
    if record['leg'] != 2 or record['goals'] != expected:
        raise ValueError('Fixed trial identity differs')
    if run['challenge']['manifest']['goals'] != expected:
        raise ValueError('Run manifest differs')
    # Require both conditioning exports, not merely a terminal summary.
    if len(run['legs']) < 2:
        raise ValueError('Missing conditioning evidence')
    for index in (0,1):
        leg = run['legs'][index]
        conditioning = source(leg['export_path'], 'attachment-characterization-result.json')
        if leg['leg'] != index or conditioning['leg'] != index or conditioning['goals'] != expected:
            raise ValueError('Conditioning identity differs')
        if not leg['assessment']['continuation_eligible']:
            raise ValueError('Conditioning did not pass')
    before = [record['baseline']['joints'][i]['position'] for i in (1,2)]
    end = [record['observations'][-1]['joints'][i]['position'] for i in (1,2)]
    if before != audit['before'] or end != audit['actual'] or audit['desired'] != [2388,1729]:
        raise ValueError('Audit and raw endpoint differ')
    if [record['baseline']['joints'][i]['goal'] for i in (1,2)] != [2389,1725]:
        raise ValueError('Trial starting targets differ')
    predictions = source(run['baseline_review']['prediction_export'], 'attachment-ab-predictions.json')
    if (predictions['variant'] != variant or predictions['targets'] != expected or
            predictions['campaign'] != run['challenge']['campaign'] or
            predictions['reference_sha256'] != run['challenge']['reference']):
        raise ValueError('Frozen prediction provenance differs')
    return audit, digest, predictions['frozen_models']


def compare(exports, control_id, candidate_id):
    a, ah, am = load_trial(exports, control_id, 'control')
    b, bh, bm = load_trial(exports, candidate_id, 'compensated')
    if am != bm:
        raise ValueError('Frozen model differs between trials')
    score = compare_endpoints(control_before=a['before'], compensated_before=b['before'],
        control_end=a['actual'], compensated_end=b['actual'], desired=a['desired'])
    score.update(control_audit_sha256=ah, candidate_audit_sha256=bh,
        control_export=control_id, candidate_export=candidate_id,
        model_refitted=False, hardware_access=False,
        comparison_eligible=score['starts_match_within_one_count'])
    exporter = WizardDiagnosticExporter(exports); exporter.prepare(create=True)
    saved = exporter.export({'mode':'ab-pilot-comparison'}, [], attachments={
        'ab-comparison.json':canonical(score)})
    if not verify_export(Path(saved['path']))['valid']:
        raise ValueError('Comparison export failed')
    return saved['path']


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--control-audit', required=True)
    parser.add_argument('--candidate-audit', required=True)
    args = parser.parse_args()
    print(compare(Path(__file__).resolve().parents[1]/'runs/wizard-exports',
                  args.control_audit, args.candidate_audit))
