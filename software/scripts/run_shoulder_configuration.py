"""r22 receipt-bound read-only capture. Never install, restart or move the arm."""
import argparse
import hashlib
import json
from pathlib import Path

from rocell.application.supported_recovery_installation import review_recovery_startup
from rocell.application.hold_transport_export import capture_hold_transport
from rocell.application.hold_transport_snapshot import HoldHTTPReader
from rocell.application.shoulder_configuration_capture import capture_shoulders


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--startup-export', required=True)
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument('--preflight-only', action='store_true')
    mode.add_argument('--authorized-observation', action='store_true')
    args = parser.parse_args(argv)
    root = Path(__file__).resolve().parents[1]
    binding = review_recovery_startup(root, args.startup_export, revision=22)
    exports = root / 'runs/wizard-exports'
    boot = binding['expected_boot']
    # These claims are conservative local exclusions, not proof of live idleness.
    names = ('shoulder-configuration-'+boot, 'pose-observation-'+boot,
             'first-hold-trial-'+boot, 'supported-recovery-trial-'+boot,
             'held-pair-trial-'+hashlib.sha256(boot.encode('ascii')).hexdigest())
    if any((exports/(name+'.json')).exists() for name in names):
        raise ValueError('Boot already reserved for capture or actuation; no retry')
    if args.preflight_only:
        print(json.dumps(dict(status='LOCAL_R22_SHOULDER_PREFLIGHT_VERIFIED',
            expected_boot=boot, hardware_access=False, current_pose_verified=False,
            motion_authorized=False)))
        return
    before = capture_hold_transport(exports, HoldHTTPReader(binding['address']), expected_boot=boot)
    summary = before['summary']
    status = summary.get('status', {})
    if (summary.get('category') != 'TRANSPORT_CAPTURED' or status.get('state') != 'IDLE'
            or status.get('reason') != 'NOT_CONFIGURED' or status.get('records') != 0
            or status.get('storage_fault') is not False):
        raise ValueError('Fresh same-boot idle state required')
    result = capture_shoulders(exports, address=binding['address'], expected_boot=boot,
                               authorized=True)
    print(json.dumps(result))


if __name__ == '__main__':
    main()
