"""Replay the exact completed r10 pair provisioning and startup evidence.

Local receipts establish retained installation evidence, not current device state
or movement permission. The live hold runner separately checks the current boot.
"""
import base64
import hashlib
from pathlib import Path

from .first_motion_contract import canonical
from .held_pair_installation_evidence import review_pair_installation
from .held_pair_capabilities import validate_pair_capabilities
from .product_ghost_export_review import _read
from .wizard_diagnostic_coordinator import decode_diagnostic_json

SOURCE = '4524696545583513b283348789b2e1f92ed37e178efcb10edf32dcbd639ec4bf'
CANDIDATE = 'a5ca3cc090277da8952fec21ebc1b84d692819515fb9a9a3550c56539b7a4096'
POLICY = '2ab588877107ebbc067607c29003fb317867123780e40c8e9d41011907d312d1'
SETTINGS = 'b7aa29c516f25c46f8c93faff3bf67b4839b363747edf8a8ddc3c981446c58f9'
PLAN = 'wizard-20260919T020745879558Z-a941c6791dfb47ffaa767ad02ffd49f7'
WRITE = 'wizard-20260919T022043593829Z-2486264d58b2411dac6d1039f6070aa7'
RUN = 'wizard-20260919T022043752542Z-414620623d6147db83e49a2f48894baa'
HEALTH = 'wizard-20260919T022051699398Z-4436c2b821ca405588eace24e4acdf96'
BOOT = '4eaa09b8a66ab0b934de43e587522f4c'
ADDRESS = '192.168.0.225'


def require_fields(value, expected):
    if type(value) is not dict or any(canonical(value.get(k)) != canonical(v) for k,v in expected.items()):
        raise ValueError('Retained r10 evidence differs')


def review_provisioned_r10(software_root, *, revision=10):
    if type(revision) is not int or revision not in (10,11,12,13):
        raise ValueError('Reviewed startup revision required')
    boot = BOOT if revision == 10 else '76c002985bcf308b43c7dbd486ba72aa'
    health_id = HEALTH if revision == 10 else 'wizard-20260919T024912549021Z-39ed12903fe04c10bd0731ed6b19b4f4'
    if revision == 12:
        boot = '39d9f96926e24a3d35d6889d2c9509d3'
        health_id = 'wizard-20260919T030051107264Z-0f89c5116c0d4b09bc3c32524bd6e04f'
    if revision == 13:
        boot = '6bc1df9e5ac164fd009bcb40bf95d1fd'
        health_id = 'wizard-20260919T035748835373Z-133bb218dcdd40018e2b609d220e54b3'
    root = Path(software_root)
    installation = review_pair_installation(root) if revision == 10 else review_pair_installation(root, revision=revision)
    exports = root/'runs/wizard-exports'
    plan, plan_sha = _read(exports, PLAN, 'attachment-provisioning-review.json')
    require_fields(plan, dict(schema='rocell.pair-settings_provisioning_review.v1',
        source_sha256=SOURCE, candidate_sha256=CANDIDATE, policy_sha256=SETTINGS,
        settings_sha256=SETTINGS, hold_policy_sha256=POLICY, existing_entries_preserved=6,
        remount_verified=True, startup_authorized=True, motion_authorized=False,
        existing_key_preserved=True, device_path='/rocell-pair.json', key_generated=False))
    write, write_sha = _read(exports, WRITE, 'attachment-provisioning-result.json')
    expected = dict(schema='rocell.pair-settings_provisioning_result.v1',
        status='FLASH_READBACK_VERIFIED', candidate_sha256=CANDIDATE, source_sha256=SOURCE,
        protected_regions_unchanged=True, recovery_preserved=True, retry_allowed=False,
        startup_attempted=False, configuration_loaded=False, motion_authorized=False,
        plan_export_id=PLAN)
    if canonical(write) != canonical(expected):
        raise ValueError('Exact verified write receipt required')
    run, run_sha = _read(exports, RUN, 'attachment-provisioning-run.json')
    if canonical(run) != canonical(dict(expected, startup_attempted=True,
            application_health_verified=False, verified_write_export_id=WRITE)):
        raise ValueError('Exact single-startup receipt required')
    health, health_sha = _read(exports, health_id, f'attachment-r{revision}-startup-observation.json')
    require_fields(health, dict(schema=f'rocell.r{revision}_startup_observation.v1', address=ADDRESS,
        status='IDLE_AND_PAIR_PROTOCOL_OBSERVED', challenge_requested=False,
        servo_commands_sent=False, provisioning_performed=False, reset_performed=False,
        retry_allowed=False))
    responses = health.get('responses')
    paths = ['/rocell/diagnostics/status','/rocell/held-pair/capabilities','/rocell/diagnostics/status']
    if type(responses) is not list or len(responses) != 3:
        raise ValueError('Bounded startup observations required')
    raw = []
    for row, path, limit in zip(responses, paths, (512,768,512)):
        payload = base64.b64decode(row['raw_base64'], validate=True)
        if row['path'] != path or len(payload)>limit or hashlib.sha256(payload).hexdigest()!=row['sha256']:
            raise ValueError('Startup raw response differs')
        raw.append(payload)
    status = decode_diagnostic_json(raw[0], maximum=512)
    require_fields(status, dict(schema='rocell.hold_transport.v1', instance_id=boot,
        state='IDLE', reason='NOT_CONFIGURED', records=0, storage_fault=False))
    if raw[0] != raw[2] or canonical(status) != canonical(health['hold_status']):
        raise ValueError('Unstable or inconsistent startup status')
    validate_pair_capabilities(raw[1], expected_boot=boot)
    if revision in (11,12,13):
        retained_installation,_ = _read(exports, health['installation_export_id'],
            'attachment-held-pair-installation-evidence.json')
        if canonical(retained_installation) != canonical(installation):
            raise ValueError('Startup installation linkage differs')
    return dict(schema=f'rocell.provisioned_r{revision}_evidence.v1', expected_boot=boot,
        address=ADDRESS, candidate_sha256=CANDIDATE, hold_policy_sha256=POLICY,
        settings_sha256=SETTINGS, installation=installation,
        plan_export_id=PLAN, plan_sha256=plan_sha, write_export_id=WRITE, write_sha256=write_sha,
        run_export_id=RUN, run_sha256=run_sha, health_export_id=health_id, health_sha256=health_sha,
        hardware_access=False, current_boot_verified=False, motion_authorized=False)
