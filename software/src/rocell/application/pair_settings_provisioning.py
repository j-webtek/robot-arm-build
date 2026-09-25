"""Exact r10 filesystem-only profile. Inert until separately authorized execution."""
from .startup_provisioning_execution import StartupProvisioningExecution
from .startup_provisioning_journal import StartupProvisioningJournal

APP_SIZE=1103808
APP_SHA256='b07fd9a442bfeb58a9b846828a5b6cedf25441fd9ce322be9f8f72f32ef9389d'


class PairSettingsExecution(StartupProvisioningExecution):
    def _profile(self):return APP_SIZE,APP_SHA256,'pair-settings'


class PairSettingsJournal(StartupProvisioningJournal):
    NAME='pair-r10-settings-provisioning-events.jsonl'


def run_pair_settings_provisioning(*, source, source_sha256, candidate, candidate_sha256,
                                  settings, expected_hold_policy, littlefs, validate_settings,
                                  validate_hold_policy, private_root, export_root, device,
                                  save_private_image, startup_authorized=False):
    """Rebuild and preserve the exact candidate before one filesystem write.

    Caller must obtain separate approval and supply the reviewed native validators
    and current-user private-image storage. No approval is inferred here.
    """
    from .startup_provisioning_run import _run_provisioning
    return _run_provisioning('pair-settings',source=source,source_sha256=source_sha256,
        candidate=candidate,candidate_sha256=candidate_sha256,policy=settings,key=None,
        previous_policy=expected_hold_policy,littlefs=littlefs,validate_policy=validate_settings,
        validate_existing_policy=validate_hold_policy,private_root=private_root,
        export_root=export_root,device=device,save_private_image=save_private_image,
        startup_authorized=startup_authorized)
