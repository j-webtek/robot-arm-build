"""Rebuild the four-trial roll repeat screen. Read-only; no hardware imports or writes.

Run from the workspace root. This fixed evidence report intentionally refuses
missing, substituted, incomplete or unmatched exports rather than selecting
only favorable trials. It is not a compensation fitter or movement launcher.
"""
import base64
import json
import math
from pathlib import Path

from rocell.application.positional_campaign_native_export import verify_native_retained_export
from rocell.providers.windows.positional_campaign_native_protocol import decode_request
from rocell.arm.campaign_stream_sync import campaign_window

PINS = (
    ('campaign-24dd1038334743dfb570705d0707069d', 'd86062f2b0e8b07fb9b2efabef9bdfddd5e0a2e0ff9b29d331f331e393ff6e25'),
    ('campaign-ebf4113d3221479ab8db7c1a4e290414', 'a1baa51afe16ff961324aab0f644610bc71d6adbb4d644bbd7f4ae2b8440cadc'),
    ('campaign-d1cc3f8a7eb24cb1ac779e74f494e6ce', '75e5008bd3a597de2a25d4dffcf09f8fcaaae75f904f83b053493d8cda4f830f'),
    ('campaign-3f8bd7e08cbe4d54ab8a7291c536431f', '71ea2ce907cdafb3e060e100987a7dfa72ea653625789478507cbc02b742da3a'),
)


def require(condition, message):
    if not condition:
        raise ValueError(message)


def read_trial(cid, expected_hash):
    root=Path('software/runs/wizard-exports')/cid
    v=verify_native_retained_export(root,cid+'-parent-report.json')
    require(v['valid'] and v['reconstruction_consistent'] and v['endpoint_completion_consistent'], 'Export did not reconstruct completely')
    require(v['report_sha256'] == expected_hash, 'Pinned report changed')
    def original(name):
     return base64.b64decode(json.loads((root/(cid+'-parent-'+name+'.original.json')).read_bytes())['base64'])
    b=decode_request(original('request'))['payload']['campaign_intent']
    t=json.loads(original('trial'));leg=t['legs'][0]
    windows={}
    for phase in ('baseline','post'):
     c=leg[phase]
     raw=b''.join(base64.b64decode(x) for x in c['raw']['base64_chunks'])
     rows,issues,_=campaign_window(b,phase,raw,c['read_windows'],c['started_ns'],c['finished_ns'],maximum_bytes=98304)
     require(not issues, 'Malformed retained telemetry')
     windows[phase]=rows
    before=windows['baseline'];after=windows['post']
    return dict(campaign_id=cid,report_sha256=v['report_sha256'],schema=b['schema'],start=before[-1][2],final=after[-1][2],command=leg['command'] if 'command' in leg else b['legs'][0]['command'],other_joint_drift=[max(abs(r[2][i]-before[-1][2][i]) for r in after) for i in (0,1,2,3,5)],write=leg['write'],cleanup=t['cleanup'],attempts=t['native_submission_attempts'],endpoint=v['endpoint_diagnostics'][0],references=b['references'],selected_sample_age_ns=leg['write']['started_ns']-before[-1][1])
    


def compare_pair(left, right):
    """Match actual six-joint starts and all relevant fixed experimental context."""
    require(left['campaign_id'] != right['campaign_id'], 'Duplicate trial')
    for key in ('schema', 'start', 'command'):
        require(left[key] == right[key], 'Mismatched ' + key)
    require(left['schema'] == 'rocell.attended_positional_intent.v17', 'Not fixed roll')
    for key in ('configuration_sha256', 'native_controller_review_sha256',
                'protocol_review_sha256', 'tool_payload_sha256', 'workcell_sha256',
                'bounded_motion_risk_sha256', 'source_sha256'):
        require(left['references'][key] == right['references'][key], 'Mismatched ' + key)
    # Runtime registration hashes include each campaign's unique staging paths;
    # retain them per trial rather than demanding byte-identical registrations.
    # Each original registration is checked by the native export verifier.
    errors = [math.degrees(r['final'][4] - r['command']['rad']) for r in (left, right)]
    return dict(direction=left['endpoint']['direction'], sample_count=2,
                campaign_ids=[left['campaign_id'], right['campaign_id']],
                target_deg=math.degrees(left['command']['rad']),
                final_deg=[math.degrees(r['final'][4]) for r in (left, right)],
                signed_errors_deg=errors,
                reported_spread_deg=abs(math.degrees(left['final'][4] - right['final'][4])))


def main():
    rows = [read_trial(cid, digest) for cid, digest in PINS]
    require(len({r['campaign_id'] for r in rows}) == 4, 'Distinct trials required')
    for row in rows:
        require(row['attempts'] == 1 and not row['write']['uncertain'], 'Write accounting')
        require(row['cleanup']['all_handles_closed'] and
                row['cleanup']['within_budget'] and
                row['cleanup']['pending_io_count'] == 0, 'Cleanup')
        require(not any(row['other_joint_drift']), 'Other-joint movement')
    for previous, following in zip(rows, rows[1:]):
        require(previous['final'] == following['start'], 'Measured handoff changed')
    print(json.dumps(dict(schema='rocell.roll_fixed_repeat_screen.v1', rows=rows,
        pairs=[compare_pair(rows[0], rows[2]), compare_pair(rows[1], rows[3])],
        physical_accuracy_verified=False, physical_timing_verified=False,
        compensation_applied=False, motion_authorized=False), indent=2))


if __name__ == '__main__':
    main()
