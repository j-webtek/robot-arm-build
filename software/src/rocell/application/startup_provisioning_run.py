"""Approved provisioning orchestration; inputs must be reviewed before invocation.

This function does not generate keys or infer user approval. A caller supplies the
exact approved candidate digest and explicit startup choice. No CLI/device/key is
constructed implicitly. Tests use synthetic images and injected devices.
"""
from pathlib import Path

from .diagnostic_provisioning_image import stage_startup_image
from .first_motion_contract import canonical
from .startup_provisioning_execution import StartupProvisioningExecution, digest
from .startup_provisioning_journal import StartupProvisioningJournal
from .wizard_diagnostic_export import WizardDiagnosticExporter, verify_export


def run_provisioning(*, source, source_sha256, candidate, candidate_sha256, policy,
                     key, littlefs, validate_policy, private_root, export_root,
                     device, save_private_image, startup_authorized=False):
    """Preserve the r6-only entry point and its existing journal/artifact names."""
    return _run_provisioning('startup', **locals())


def _run_provisioning(profile, *, source, source_sha256, candidate, candidate_sha256, policy,
                     key, littlefs, validate_policy, private_root, export_root,
                     device, save_private_image, startup_authorized=False, previous_policy=None,
                     validate_existing_policy=None):
    """Re-stage exact bytes, preserve privately, execute once, export before reset.

    save_private_image must be the reviewed current-user DPAPI save/readback path
    in live use. The private directory and ACL must already be established.
    No raw images, keys or arbitrary exception text enter public exports.
    """
    if type(startup_authorized) is not bool:
        raise ValueError('Explicit startup choice required')
    if profile == 'startup':
        stage = stage_startup_image
        execution_type, journal_type = StartupProvisioningExecution, StartupProvisioningJournal
        private_prefix = 'startup-r6'
    elif profile == 'hold':
        from .diagnostic_provisioning_image import stage_hold_image
        from .hold_provisioning_execution import HoldProvisioningExecution, HoldProvisioningJournal
        stage = stage_hold_image
        execution_type, journal_type = HoldProvisioningExecution, HoldProvisioningJournal
        private_prefix = 'hold-r7'
    elif profile == 'hold-replacement':
        from .diagnostic_provisioning_image import replace_hold_policy_image
        from .hold_provisioning_execution import HoldProvisioningExecution, HoldReplacementJournal
        def stage(source, source_sha256, policy, key, **kwargs):
            if key is not None:
                raise ValueError('Replacement must preserve the existing credential')
            return replace_hold_policy_image(source, source_sha256, previous_policy, policy, **kwargs)
        execution_type, journal_type = HoldProvisioningExecution, HoldReplacementJournal
        private_prefix = 'hold-r7-supported-replacement'
    elif profile == 'pair-settings':
        from .diagnostic_provisioning_image import stage_pair_settings_image
        from .pair_settings_provisioning import PairSettingsExecution, PairSettingsJournal
        def stage(source, source_sha256, policy, key, **kwargs):
            if key is not None:raise ValueError('Pair settings must preserve the retained key')
            staged, review = stage_pair_settings_image(source,source_sha256,policy,previous_policy,
                littlefs=kwargs['littlefs'],validate_settings=kwargs['validate_policy'],
                validate_hold_policy=validate_existing_policy)
            # The common provisioning plan names its public payload policy_sha256.
            review['policy_sha256']=review['settings_sha256']
            return staged, review
        execution_type, journal_type = PairSettingsExecution, PairSettingsJournal
        private_prefix = 'pair-r10-settings'
    elif profile == 'negative-pair':
        from .diagnostic_provisioning_image import replace_pair_direction_image
        from .negative_pair_provisioning import NegativePairExecution, NegativePairJournal
        def stage(source, source_sha256, policy, key, **kwargs):
            if key is not None: raise ValueError('Direction replacement cannot replace credentials')
            staged, review = replace_pair_direction_image(source, source_sha256,
                previous_policy['settings'], policy, previous_policy['hold'],
                littlefs=kwargs['littlefs'], validate_settings=kwargs['validate_policy'],
                validate_hold_policy=validate_existing_policy)
            review['policy_sha256']=review['settings_sha256']
            return staged, review
        execution_type, journal_type = NegativePairExecution, NegativePairJournal
        private_prefix = 'pair-negative6-install'
    elif profile == 'observed-pose':
        from .diagnostic_provisioning_image import replace_observed_pose_image
        from .observed_pose_provisioning import ObservedPoseExecution, ObservedPoseJournal
        def stage(source, source_sha256, policy, key, **kwargs):
            if key is not None:
                raise ValueError('Observed pose replacement cannot replace credentials')
            staged, review = replace_observed_pose_image(source, source_sha256,
                previous_policy['hold'], previous_policy['pair'], policy['hold'], policy['pair'],
                littlefs=kwargs['littlefs'], validate_hold=validate_existing_policy,
                validate_pair=kwargs['validate_policy'])
            review.update(policy_sha256=digest(canonical({
                              'hold_sha256':review['hold_sha256'],
                              'pair_sha256':review['pair_sha256']})),
                          settings_sha256=review['pair_sha256'],
                          hold_policy_sha256=review['hold_sha256'])
            return staged, review
        execution_type, journal_type = ObservedPoseExecution, ObservedPoseJournal
        private_prefix = 'observed-pose-install'
    else:
        raise ValueError('Unreviewed provisioning profile')
    private_root = Path(private_root).resolve(strict=True)
    if not private_root.is_dir():
        raise ValueError('Existing private directory required')
    exporter = WizardDiagnosticExporter(Path(export_root).resolve())
    exporter.prepare(create=True)
    journal = journal_type(private_root)
    if journal.path.exists():
        raise ValueError('Existing provisioning attempt; no automatic resume')
    # Rebuild from the original source with the pinned filesystem and parser.
    # This prevents a hash-correct but unvalidated arbitrary image from reaching
    # the write core. Existing files and exact policy/key bytes are verified there.
    staged, review = stage(source, source_sha256, policy, key,
        littlefs=littlefs, validate_policy=validate_policy)
    if type(candidate) is not bytes or staged != candidate or digest(candidate) != candidate_sha256:
        raise ValueError('Candidate differs from reviewed preserving stage')
    plan = dict(schema=f'rocell.{profile}_provisioning_review.v1', **{
        k: review[k] for k in ('source_sha256', 'candidate_sha256', 'policy_sha256',
                              'existing_entries_preserved', 'remount_verified')},
        startup_authorized=startup_authorized, motion_authorized=False)
    if profile in ('pair-settings', 'negative-pair', 'observed-pose'):
        plan.update(settings_sha256=review['settings_sha256'],
            hold_policy_sha256=review['hold_policy_sha256'],existing_key_preserved=True,
            device_path='/rocell-pair.json',key_generated=False)
        if profile == 'observed-pose':
            plan.pop('device_path')
            plan['device_paths'] = ['/rocell-hold.json', '/rocell-pair.json']

    def export(name, document):
        receipt = exporter.export({'mode': profile+'-provisioning'}, [],
            attachments={name: canonical(document)})
        if not verify_export(Path(receipt['path']))['valid']:
            raise ValueError('Provisioning export verification failed')
        return Path(receipt['path']).name

    plan_export = export('provisioning-review.json', plan)

    def reserve(record):
        journal.reserve(dict(record, plan_export_id=plan_export))
        saved = save_private_image(private_root, private_prefix+'-candidate.dpapi', candidate)
        if saved['image_sha256'] != candidate_sha256:
            raise ValueError('Private candidate verification failed')
        return True

    def preserve(data):
        saved = save_private_image(private_root, private_prefix+'-prewrite-source.dpapi', data)
        return saved['image_sha256'] == source_sha256

    try:
        result = execution_type().execute(device, candidate,
            source_sha256=source_sha256, candidate_sha256=candidate_sha256,
            reserve=reserve, preserve_source=preserve, event=journal.event)
        verified_export = export('provisioning-result.json', dict(result, plan_export_id=plan_export))
        journal.event(dict(stage='RESULT_EXPORTED', export_id=verified_export))
        if startup_authorized:
            journal.event(dict(stage='ONE_STARTUP_ATTEMPT'))
            device.startup_once()
            journal.event(dict(stage='STARTUP_RESET_SENT', application_health_verified=False))
        final = dict(result, startup_attempted=startup_authorized,
            application_health_verified=False, plan_export_id=plan_export,
            verified_write_export_id=verified_export)
        final_export = export('provisioning-run.json', final)
        return dict(final, export_id=final_export)
    except BaseException:
        # Fixed label only; even exception messages can contain secret bytes.
        # If logging is also broken, retain the existing reserved journal anyway.
        try:
            journal.event(dict(stage='STOPPED', retry_allowed=False, automatic_recovery=False))
        except Exception:
            pass
        raise
    finally:
        device.close()
        journal.close()
