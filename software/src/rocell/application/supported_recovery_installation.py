"""Read-only binding of retained r16 installation and exact startup responses."""
import base64
import hashlib
from pathlib import Path
from .first_motion_contract import canonical
from .held_pair_installation_evidence import review_pair_installation
from .held_pair_capabilities import PATH, validate_pair_capabilities
from .hold_transport_snapshot import STATUS
from .product_ghost_export_review import _read
from .servo_start_authorization import _hex
from .wizard_diagnostic_coordinator import decode_diagnostic_json


def review_recovery_startup(software_root, export_id, *, revision=16):
    if type(revision) is not int or revision not in (16, 17, 19, 20, 21, 22, 23, 24, 25, 26, 27, 28, 29, 31, 33, 34, 35, 36, 37, 38, 39, 40, 41, 42, 43, 44, 45, 46, 47, 48, 49, 50, 51, 52, 53, 54, 55, 56, 57, 58, 60, 61, 62, 63, 64, 65, 66, 67, 68, 69, 70, 71, 72,73,74,75,76,77,78,79,81,82,83,84):
        raise ValueError('Reviewed recovery diagnostic revision required')
    root = Path(software_root)
    installation = review_pair_installation(root, revision=revision)
    exports = root / 'runs/wizard-exports'
    startup, digest = _read(exports, export_id, f'attachment-r{revision}-startup-observation.json')
    if (startup.get('schema') != f'rocell.r{revision}_startup_observation.v1' or
            startup.get('status') != 'IDLE_AND_PAIR_PROTOCOL_OBSERVED' or
            startup.get('address') != '192.168.0.225' or
            any(startup.get(k) is not False for k in ('challenge_requested', 'servo_commands_sent',
                'provisioning_performed', 'reset_performed', 'retry_allowed'))):
        raise ValueError('Reviewed selected-revision startup required')
    retained, _ = _read(exports, startup['installation_export_id'],
                         'attachment-held-pair-installation-evidence.json')
    if canonical(retained) != canonical(installation):
        raise ValueError('Startup installation differs')
    responses = startup['responses']
    if type(responses) is not list or len(responses) != 3:
        raise ValueError('Exact startup response sequence required')
    decoded, raw_values = [], []
    for row, path, maximum in zip(responses, (STATUS, PATH, STATUS), (512, 768, 512)):
        if set(row) != {'path', 'raw_base64', 'sha256'} or row['path'] != path:
            raise ValueError('Startup response identity')
        if type(row['raw_base64']) is not str or len(row['raw_base64']) > 1024:
            raise ValueError('Startup response budget')
        raw = base64.b64decode(row['raw_base64'], validate=True)
        if (len(raw) > maximum or base64.b64encode(raw).decode() != row['raw_base64'] or
                hashlib.sha256(raw).hexdigest() != row['sha256']):
            raise ValueError('Startup response bytes changed')
        raw_values.append(raw);decoded.append(decode_diagnostic_json(raw, maximum=maximum))
    first, _, last = decoded
    boot = first['instance_id'];_hex(boot, 16)
    expected = dict(schema='rocell.hold_transport.v1', instance_id=boot, state='IDLE',
        reason='NOT_CONFIGURED', records=0, record_bytes=4096, storage_fault=False,
        durable_export_verified=False)
    if any(canonical(item) != canonical(expected) for item in (first, last, startup['hold_status'])):
        raise ValueError('Startup is not a stable idle boot')
    observed = validate_pair_capabilities(raw_values[1], expected_boot=boot)
    if canonical(observed) != canonical(startup['capability_observation']):
        raise ValueError('Startup capabilities changed')
    return dict(address=startup['address'], expected_boot=boot, startup_export_id=export_id,
        startup_sha256=digest, installation=installation, motion_authorized=False,
        current_device_bytes_verified=False)
