"""Replay pinned originals offline; emit diagnostics without serial access/writes."""
import base64
import hashlib
import json
from pathlib import Path

from rocell.application.first_motion_contract import canonical
from rocell.application.positional_campaign_capture import validate_campaign_capture
from rocell.application.positional_campaign_native_export import verify_native_retained_export
from rocell.arm.campaign_stream_sync import campaign_window
from rocell.arm.cross_window_framing import analyze_cross_command_post
from rocell.arm.endpoint_persistence import analyze_endpoint_persistence
from rocell.providers.windows.positional_campaign_native_protocol import decode_request
from rocell.safety.positional_campaign_authority import PositionalCampaignIntent

CID = 'campaign-ddd0578c2a554851bca029b2f496a2f7'
REPORT_SHA = '06afb04e693e352d320dd57177bbe3555d5c31f7cc8633ab33cf3bea70d0f3dd'


def require(condition, message):
    if not condition:
        raise ValueError(message)


def review():
    root = Path(__file__).resolve().parents[1] / 'runs' / 'wizard-exports' / CID
    verified = verify_native_retained_export(root, CID + '-parent-report.json')
    require(verified['valid'] and verified['report_sha256'] == REPORT_SHA,
            'Original export integrity or pinned report mismatch')
    require(not verified['reconstruction_consistent'] and
            not verified['endpoint_completion_consistent'], 'Historical verdict changed')

    def original(name):
        envelope = json.loads((root / (CID + '-parent-' + name + '.original.json')).read_bytes())
        return base64.b64decode(envelope['base64'], validate=True)

    body = decode_request(original('request'))['payload']['campaign_intent']
    request = PositionalCampaignIntent(canonical(body))
    trial = json.loads(original('trial'))
    require(len(trial['legs']) == 1 and trial['native_submission_attempts'] == 1,
            'Unexpected trial shape')
    leg = trial['legs'][0]
    baseline, post, write = leg['baseline'], leg['post'], leg['write']
    require(not write['uncertain'], 'Uncertain original write')
    raw_before = validate_campaign_capture(request, baseline, phase='baseline')
    raw_after = validate_campaign_capture(request, post, phase='post',
                                         command_completed_ns=write['finished_ns'])
    before, issues, _ = campaign_window(body, 'baseline', raw_before,
        baseline['read_windows'], baseline['started_ns'], baseline['finished_ns'],
        maximum_bytes=body['limits']['maximum_raw_bytes_per_leg'])
    require(before and not issues, 'Baseline not usable')
    rows, issues, proof = analyze_cross_command_post(raw_before, baseline['read_windows'],
        raw_after, post['read_windows'], post_started_ns=post['started_ns'],
        post_finished_ns=post['finished_ns'],
        baseline_sha256=hashlib.sha256(raw_before).hexdigest(),
        post_sha256=hashlib.sha256(raw_after).hexdigest(),
        write_started_ns=write['started_ns'], write_finished_ns=write['finished_ns'])
    persistence = analyze_endpoint_persistence(rows, joint='r', start=before[-1][2],
        target=body['legs'][0]['command']['rad'], write_finished_ns=write['finished_ns'],
        capture_finished_ns=post['finished_ns'], capture_issues=issues)
    require(not issues and proof['post_excluded_range'] == [0, 4], 'Unexpected framing result')
    require(persistence['status'] == 'REPORTED_ENDPOINT_CHANGED', 'Late change not detected')
    return dict(schema='rocell.roll_cross_window_replay.v1', campaign_id=CID,
        report_sha256=REPORT_SHA, original_integrity_verified=True,
        historical_reconstruction_consistent=False, historical_endpoint_completion=False,
        framing=proof, persistence=persistence, historical_verdict='HELD_UNCHANGED',
        native_integration_enabled=False, new_commands_sent=0, motion_authorized=False)


if __name__ == '__main__':
    print(json.dumps(review(), indent=2))
