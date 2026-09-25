"""Trusted host binding for the finite pair wizard action; never browser input."""
from dataclasses import dataclass, field
import time
from pathlib import Path

from .first_motion_contract import canonical
from .held_pair_preparation import replay_held_pair_preparation
from .held_pair_trial import run_admitted_pair
from .product_ghost_export_review import _read
from .wizard_diagnostic_export import WizardDiagnosticExporter

R10_APP_SHA256='b07fd9a442bfeb58a9b846828a5b6cedf25441fd9ce322be9f8f72f32ef9389d'


@dataclass(frozen=True)
class HeldPairWizardBinding:
    preparation_id: str
    preparation_sha256: str
    address: str
    admission_reader: object = field(repr=False)
    key_loader: object = field(repr=False)
    app_sha256: str = R10_APP_SHA256

    def __post_init__(self):
        from .servo_diagnostic_http import DiagnosticHTTPReader
        from .servo_start_authorization import _hex
        from .held_pair_installation_evidence import _profile
        _hex(self.preparation_sha256,32)
        if self.app_sha256 not in {_profile(revision)[0] for revision in (10,11,12,13)}:
            raise ValueError('Reviewed application identity required')
        DiagnosticHTTPReader(self.address,80)
        if not all(callable(value) for value in (self.admission_reader,self.key_loader)):
            raise ValueError('Trusted admission reader and key loader required')

    def preview(self, root):
        source=replay_held_pair_preparation(root,self.preparation_id)
        if source['preparation_sha256']!=self.preparation_sha256:
            raise ValueError('Host-bound preparation changed')
        prep=source['preparation'];plan=prep['pair_plan']
        return dict(preparation_id=self.preparation_id,preparation_sha256=self.preparation_sha256,
            boot_id=plan['boot_id'],address=self.address,servo_id=14,
            forward_target_count=prep['historical_anchor']+plan['offset_counts'],
            return_target_count=prep['historical_anchor'],tolerance_counts=plan['tolerance_counts'],
            app_sha256=self.app_sha256,retry_allowed=False)


def run_wizard_held_pair(binding,root,*,cancelled,deadline_ns):
    """Require fresh host-reviewed admission before loading a key or networking.

    The trusted reader must actually check installation, pair configuration,
    powered-trial approval and current workspace conditions. This function
    validates its exact-subject receipt; it cannot establish those facts itself.
    No default approving reader or browser-based binding constructor exists.
    """
    if type(binding) is not HeldPairWizardBinding:
        raise ValueError('Trusted typed pair binding required')
    def stopped():return cancelled() or time.monotonic_ns()>=deadline_ns
    if stopped():raise ValueError('Pair action cancelled or expired')
    preview=binding.preview(root)
    receipt=binding.admission_reader(dict(preview))
    checks=('installed_image_verified','pair_configuration_verified','powered_trial_approved',
            'supported_and_clear','exclusive_controller')
    if (type(receipt) is not dict or set(receipt)!={'schema','subject','approval_reference','expires_ns',*checks}
            or receipt['schema']!='rocell.held_pair_admission.v1' or receipt['subject']!=preview
            or any(receipt[name] is not True for name in checks)
            or type(receipt['approval_reference']) is not str or not 1<=len(receipt['approval_reference'])<=128
            or type(receipt['expires_ns']) is not int
            or not time.monotonic_ns()<receipt['expires_ns']<=deadline_ns):
        raise ValueError('Fresh exact-subject host admission required')
    exporter=WizardDiagnosticExporter(Path(root));exporter.prepare(create=True)
    saved=exporter.export({'mode':'held-pair-admission'},[],
        attachments={'held-pair-admission.json':canonical(receipt)})
    retained,_=_read(Path(root),Path(saved['path']).name,'attachment-held-pair-admission.json')
    if canonical(retained)!=canonical(receipt):raise ValueError('Admission export changed')
    def expired():return stopped() or time.monotonic_ns()>=receipt['expires_ns']
    if expired():raise ValueError('Admission expired before key access')
    key=binding.key_loader()
    try:
        if expired():raise ValueError('Admission expired before execution')
        result=run_admitted_pair(root,binding.preparation_id,address=binding.address,
            key=key,approved=True,cancelled=expired)
    finally:
        key=None  # Do not retain key in the wizard; Python bytes cannot be securely wiped.
    return dict(admission_export_id=Path(saved['path']).name,**result)
