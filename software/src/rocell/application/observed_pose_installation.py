"""Offline chain verification for the exact observed-pose filesystem install."""
import hashlib
import json
from pathlib import Path

from .first_motion_contract import canonical
from .held_pair_installation_evidence import review_pair_installation
from .observed_pose_candidate import replay_candidate
from .observed_pose_provisioning import APP_SHA256, ObservedPoseJournal
from .observed_pose_recovery import HOLD_SHA, PAIR_SHA
from .physical_onboarding_durability import read_bounded_regular_file
from .product_ghost_export_review import _read

SOURCE_SHA = 'd1c041bcb4e90082685babc16698bcef3c639d87464932d6534d8056b71ce3aa'


def _require(value, expected):
    if type(value) is not dict or any(canonical(value.get(k)) != canonical(v) for k,v in expected.items()):
        raise ValueError('Observed-pose installation evidence differs')


def validate_installation_chain(stage, final, plan, written, rows):
    """Require completed write/startup evidence; never infer current device state."""
    candidate = stage['review']['candidate_sha256']
    if (type(candidate) is not str or len(candidate)!=64 or
            any(c not in '0123456789abcdef' for c in candidate) or candidate == SOURCE_SHA):
        raise ValueError('Distinct candidate digest required')
    _require(stage['review'], dict(source_sha256=SOURCE_SHA, hold_sha256=HOLD_SHA,
        pair_sha256=PAIR_SHA, changed_paths=['/rocell-hold.json','/rocell-pair.json'],
        unrelated_entries_preserved=True, existing_key_preserved=True, remount_verified=True,
        device_modified=False, provisioning_performed=False, physical_authority='NONE'))
    expected = dict(schema='rocell.observed-pose_provisioning_result.v1',
        status='FLASH_READBACK_VERIFIED', candidate_sha256=candidate, source_sha256=SOURCE_SHA,
        protected_regions_unchanged=True, recovery_preserved=True, retry_allowed=False,
        startup_attempted=True, configuration_loaded=False, motion_authorized=False,
        application_health_verified=False)
    _require(final, expected)
    if set(final) != set(expected)|{'plan_export_id','verified_write_export_id'}:
        raise ValueError('Unexpected provisioning result fields')
    _require(plan, dict(schema='rocell.observed-pose_provisioning_review.v1',
        source_sha256=SOURCE_SHA, candidate_sha256=candidate,
        policy_sha256=hashlib.sha256(canonical(dict(hold_sha256=HOLD_SHA,pair_sha256=PAIR_SHA))).hexdigest(),
        settings_sha256=PAIR_SHA, hold_policy_sha256=HOLD_SHA, remount_verified=True,
        startup_authorized=True, motion_authorized=False, existing_key_preserved=True,
        key_generated=False, device_paths=['/rocell-hold.json','/rocell-pair.json']))
    before = dict(final); before.pop('application_health_verified'); before.pop('verified_write_export_id')
    before['startup_attempted'] = False
    if canonical(written) != canonical(before): raise ValueError('Write/startup receipts differ')
    if [r.get('stage') for r in rows] != ['RESERVED','PREWRITE_VERIFIED','WRITE_ATTEMPT_STARTED',
            'FLASH_READBACK_VERIFIED','RESULT_EXPORTED','ONE_STARTUP_ATTEMPT','STARTUP_RESET_SENT']:
        raise ValueError('Incomplete or repeated installation journal')
    _require(rows[0], dict(app_sha256=APP_SHA256, source_sha256=SOURCE_SHA,
        candidate_sha256=candidate, plan_export_id=final['plan_export_id'],
        offset=0x290000,length=0x160000,retry_allowed=False,motion_authorized=False))
    _require(rows[1], dict(source_sha256=SOURCE_SHA, app_sha256=APP_SHA256))
    _require(rows[2], dict(offset=0x290000,length=0x160000))
    native_written = dict(written); native_written.pop('plan_export_id')
    _require(rows[3], native_written)
    _require(rows[4], dict(export_id=final['verified_write_export_id']))
    _require(rows[6], dict(application_health_verified=False))
    return candidate


def review_observed_installation(software_root, *, stage_export, installation_export):
    root = Path(software_root).resolve(); exports = root/'runs/wizard-exports'
    stage, stage_sha = _read(exports, stage_export, 'attachment-observed-pose-staging.json')
    _require(stage, dict(schema='rocell.observed_pose_private_stage.v1', hardware_access=False,
        installation_authorized=False,startup_authorized=False,motion_authorized=False))
    public = replay_candidate(root, stage['public_candidate_export'])
    if (stage['public_candidate_sha256'] != public['candidate_report_sha256'] or
            canonical(stage['installation']) != canonical(review_pair_installation(root, revision=21))):
        raise ValueError('Stage public candidate/application linkage differs')
    final, final_sha = _read(exports, installation_export, 'attachment-provisioning-run.json')
    plan, _ = _read(exports, final['plan_export_id'], 'attachment-provisioning-review.json')
    written, _ = _read(exports, final['verified_write_export_id'], 'attachment-provisioning-result.json')
    raw = read_bounded_regular_file(root/'private-backups/controller-20260918-session1'/
                                   ObservedPoseJournal.NAME, maximum_bytes=16384)
    rows = [json.loads(line) for line in raw.splitlines()]
    candidate = validate_installation_chain(stage, final, plan, written, rows)
    return dict(stage_export=stage_export, stage_sha256=stage_sha,
        installation_export=installation_export, installation_sha256=final_sha,
        candidate_sha256=candidate, public_candidate_export=stage['public_candidate_export'],
        current_device_bytes_verified=False, startup_health_verified=False, motion_authorized=False)


def review_observed_startup(software_root, *, startup_export, stage_export, installation_export):
    """Join independent settings-install and idle startup evidence; no device I/O."""
    from .supported_recovery_installation import review_recovery_startup
    root = Path(software_root).resolve()
    settings = review_observed_installation(root, stage_export=stage_export,
                                           installation_export=installation_export)
    startup = review_recovery_startup(root, startup_export, revision=21)
    retained, _ = _read(root/'runs/wizard-exports', startup_export,
                         'attachment-r21-startup-observation.json')
    if canonical(retained.get('observed_pose_installation')) != canonical(settings):
        raise ValueError('Startup is not linked to the observed-pose installation')
    return dict(startup, observed_pose_installation=settings,
                current_pose_verified=False, recovery_authorized=False)
