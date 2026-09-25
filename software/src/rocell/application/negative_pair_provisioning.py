"""Pinned r16 filesystem-only direction-change execution profile."""
from .startup_provisioning_execution import StartupProvisioningExecution
from .startup_provisioning_journal import StartupProvisioningJournal
APP_SIZE=1120240
APP_SHA256='dc8b6f0016d29495ef6403d6a04adcbc192ec45ccd1ede7c390c3d1b4b3ea05e'

class NegativePairExecution(StartupProvisioningExecution):
    def _profile(self):
        return APP_SIZE, APP_SHA256, 'negative-pair'

class NegativePairJournal(StartupProvisioningJournal):
    NAME='pair-negative6-provisioning-events.jsonl'


def review_negative_installation(root, export_id):
    """Replay the completed direction-only installation chain, never device I/O."""
    import json
    from pathlib import Path
    from .first_motion_contract import canonical
    from .product_ghost_export_review import _read
    from .physical_onboarding_durability import read_bounded_regular_file
    from .r10_provisioned_evidence import CANDIDATE, POLICY
    root=Path(root).resolve();exports=root/'runs/wizard-exports'
    final,digest=_read(exports,export_id,'attachment-provisioning-run.json')
    expected=dict(schema='rocell.negative-pair_provisioning_result.v1',
        status='FLASH_READBACK_VERIFIED',
        candidate_sha256='d1c041bcb4e90082685babc16698bcef3c639d87464932d6534d8056b71ce3aa',
        source_sha256=CANDIDATE,protected_regions_unchanged=True,recovery_preserved=True,
        retry_allowed=False,startup_attempted=True,configuration_loaded=False,
        motion_authorized=False,application_health_verified=False)
    if set(final)!=set(expected)|{'plan_export_id','verified_write_export_id'} or any(
        canonical(final[k])!=canonical(v) for k,v in expected.items()):
        raise ValueError('Completed negative settings installation required')
    plan,_=_read(exports,final['plan_export_id'],'attachment-provisioning-review.json')
    if (plan['schema']!='rocell.negative-pair_provisioning_review.v1' or
        plan['settings_sha256']!='471898fe914f0843bdd88556b98aa1277c29d672c628df5892bd5bd849a8f314' or
        plan['hold_policy_sha256']!=POLICY or plan['candidate_sha256']!=expected['candidate_sha256'] or
        plan['source_sha256']!=CANDIDATE or plan['remount_verified'] is not True or
        plan['existing_key_preserved'] is not True):
        raise ValueError('Direction change plan differs')
    written,_=_read(exports,final['verified_write_export_id'],'attachment-provisioning-result.json')
    before=dict(final);before.pop('application_health_verified');before.pop('verified_write_export_id')
    before['startup_attempted']=False
    if canonical(written)!=canonical(before): raise ValueError('Write/run receipts differ')
    raw=read_bounded_regular_file(root/'private-backups/controller-20260918-session1'/NegativePairJournal.NAME,maximum_bytes=16384)
    rows=[json.loads(line) for line in raw.splitlines()]
    if [r['stage'] for r in rows]!=['RESERVED','PREWRITE_VERIFIED','WRITE_ATTEMPT_STARTED',
        'FLASH_READBACK_VERIFIED','RESULT_EXPORTED','ONE_STARTUP_ATTEMPT','STARTUP_RESET_SENT']:
        raise ValueError('Installation journal incomplete or repeated')
    if (rows[0]['app_sha256']!=APP_SHA256 or rows[0]['candidate_sha256']!=expected['candidate_sha256'] or
        rows[0]['plan_export_id']!=final['plan_export_id'] or
        rows[4]['export_id']!=final['verified_write_export_id']):
        raise ValueError('Installation journal linkage differs')
    return dict(export_id=export_id,export_sha256=digest,offset_counts=-6,
                current_device_bytes_verified=False)
