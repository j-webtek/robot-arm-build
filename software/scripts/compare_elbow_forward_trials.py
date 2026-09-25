"""Offline comparison of independently replayed forward traces; no tuning or I/O to arm."""
import argparse
import json
from pathlib import Path
from review_r13_forward_tracking import analyze_forward
from rocell.application.first_motion_contract import canonical
from rocell.application.product_ghost_export_review import _read
from rocell.application.wizard_diagnostic_export import WizardDiagnosticExporter


def summarize(trace):
    samples = [s for s in trace['samples'] if s['after_ack_us'] >= 0]
    if not samples: raise ValueError('Post-command samples required')
    assessment = trace['assessment']
    final = samples[-1]['position_counts']
    plateau = len(samples)-1
    while plateau > 0 and samples[plateau-1]['position_counts'] == final:
        plateau -= 1
    return dict(source_export=trace['source_export'], source_sha256=trace['source_sha256'],
        assessment=assessment, action=trace['action'], postcommand_samples=len(samples),
        position_range=[min(s['position_counts'] for s in samples),max(s['position_counts'] for s in samples)],
        observed_final_plateau_start_us=samples[plateau]['after_ack_us'],
        last_sample_start_us=samples[-1]['after_ack_us'],
        load_range=[min(s['load_library_units'] for s in samples),max(s['load_library_units'] for s in samples)],
        speed_range=[min(s['speed_library_units'] for s in samples),max(s['speed_library_units'] for s in samples)],
        voltage_raw_range=[min(s['voltage_raw'] for s in samples),max(s['voltage_raw'] for s in samples)],
        moving_values=sorted(set(s['moving_raw'] for s in samples)))


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('exports',nargs=2)
    parser.add_argument('--second-is-return',action='store_true')
    args=parser.parse_args()
    if args.exports[0]==args.exports[1]: raise ValueError('Two distinct trials required')
    root=Path(__file__).resolve().parents[1]
    traces=[analyze_forward(root,source,leg='return' if index==1 and args.second_is_return else 'forward')
            for index,source in enumerate(args.exports)]
    if args.second_is_return and canonical(traces[1]['paired_forward_assessment']) != canonical(traces[0]['assessment']):
        raise ValueError('Return must belong to the compared forward trial')
    summaries=[summarize(trace) for trace in traces]
    for summary,trace in zip(summaries,traces):
        post=[s for s in trace['samples'] if s['after_ack_us']>=0]
        summary['current_library_range']=[min(s['current_library_units'] for s in post),
                                          max(s['current_library_units'] for s in post)]
        summary['temperature_raw_range']=[min(s['temperature_raw'] for s in post),
                                          max(s['temperature_raw'] for s in post)]
    fields=('start_position','requested_target','encoded_target','first_goal_readback',
            'settled_goal_readback','final_position','signed_error_counts','category')
    same_endpoint=all(summaries[0]['assessment'][field]==summaries[1]['assessment'][field] for field in fields)
    report=dict(schema='rocell.forward_trace_comparison.v1',trials=summaries,
        matching_endpoint_fields=same_endpoint, causal_claim=False,
        independent_wire_capture=False, compensation_validated=False,
        hardware_access=False,progression_authority=False)
    exports=root/'runs/wizard-exports'
    exporter=WizardDiagnosticExporter(exports);exporter.prepare(create=True)
    saved=exporter.export({'mode':'offline-forward-comparison'},[],attachments={
        'forward-comparison.json':canonical(report),
        'forward-traces.json':canonical(traces)})
    for name, value in (('forward-comparison',report),('forward-traces',traces)):
        retained,_=_read(exports,Path(saved['path']).name,'attachment-'+name+'.json')
        if canonical(retained)!=canonical(value): raise ValueError('Comparison export changed')
    print(json.dumps(dict(export_path=saved['path'],**report)))


if __name__=='__main__': main()
