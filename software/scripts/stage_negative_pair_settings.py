"""Explicitly approved offline private staging only; cannot deploy or restart."""
import argparse
import hashlib
import json
from pathlib import Path
import subprocess
import sys
import tempfile
from provision_startup_r6 import check_private_acl
from rocell.application.first_motion_contract import canonical
from rocell.application.held_pair_installation_evidence import review_pair_installation
from rocell.application.held_pair_settings import encode_pair_settings
from rocell.application.r10_provisioned_evidence import CANDIDATE, POLICY, SETTINGS
from rocell.application.native_provisioning_validator import NativeProvisioningValidator
from rocell.application.diagnostic_provisioning_image import replace_pair_direction_image
from rocell.application.wizard_diagnostic_export import WizardDiagnosticExporter
from rocell.application.product_ghost_export_review import _read
from rocell.providers.windows.diagnostic_image_store import load_image, save_image

PROPOSED='471898fe914f0843bdd88556b98aa1277c29d672c628df5892bd5bd849a8f314'
DESTINATION='pair-negative6-candidate.dpapi'


def digest(data):
    return hashlib.sha256(data).hexdigest()


def main(argv=None):
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--authorized-offline-private-staging',action='store_true',required=True)
    parser.parse_args(argv)
    root=Path(__file__).resolve().parents[1]
    private=root/'private-backups/controller-20260918-session1'
    check_private_acl(private)
    if (private/DESTINATION).exists(): raise ValueError('Candidate already exists; never overwrite')
    installation=review_pair_installation(root,revision=16)
    hold=canonical(json.loads((root/'docs/hold-r7-supported-pose-draft.json').read_bytes()))
    previous=encode_pair_settings(forward_command_id='r10-elbow-forward',return_command_id='r10-elbow-return')
    proposed=encode_pair_settings(forward_command_id='r10-elbow-forward',return_command_id='r10-elbow-return',offset_counts=-6)
    if (digest(hold),digest(previous),digest(proposed))!=(POLICY,SETTINGS,PROPOSED):
        raise ValueError('Public policy identities changed')
    sketch=root/'.firmware-tools/configured-diagnostic-candidate-r16/RoArm-M3_example'
    pinned={'controller_pair_config.h':'5f20891b2ae10090af19ce785273313a6f297c98d976edece741537284f874aa',
            'controller_hold_config.h':'fa6aab90805c54f719be1cdfc8553584afe2a886d51065d772bea8ee3f1917dd'}
    for name,expected in pinned.items():
        if digest((sketch/name).read_bytes())!=expected: raise ValueError('Candidate parser changed')
    build=Path(tempfile.mkdtemp(prefix='negative-pair-validators-',dir=root/'.firmware-tools'))
    def validator(name,adapter):
        exe=build/(name+'.exe')
        subprocess.run(['clang++','-std=c++17','-I'+str(sketch),
            '-I'+str(root/'.firmware-tools/user/libraries/ArduinoJson/src'),str(root/adapter),
            '-o',str(exe)],check=True,capture_output=True,timeout=60)
        return NativeProvisioningValidator(exe,digest(exe.read_bytes()))
    pair_validator=validator('pair','firmware/validators/validate_pair_provisioning.cpp')
    hold_validator=validator('hold','firmware/diagnostics/validate_hold_provisioning.cpp')
    sys.path.insert(0,str(root/'.firmware-tools/littlefs-review'))
    import littlefs
    if not Path(littlefs.__file__).resolve().is_relative_to((root/'.firmware-tools/littlefs-review').resolve()):
        raise ValueError('Unexpected LittleFS implementation')
    source=load_image(private/'pair-r10-settings-candidate.dpapi')
    candidate,review=replace_pair_direction_image(source,CANDIDATE,previous,proposed,hold,
        littlefs=littlefs,validate_settings=pair_validator,validate_hold_policy=hold_validator)
    stored=save_image(private,DESTINATION,candidate)
    report=dict(schema='rocell.negative_pair_private_stage.v1',review=review,storage=stored,
        installation=installation,settings_sha256=PROPOSED,previous_settings_sha256=SETTINGS,
        previous_image_sha256=CANDIDATE,hardware_access=False,installation_authorized=False,
        startup_authorized=False,motion_authorized=False)
    exports=root/'runs/wizard-exports';exporter=WizardDiagnosticExporter(exports)
    exporter.prepare(create=True)
    saved=exporter.export({'mode':'offline-negative-pair-staging'},[],
        attachments={'negative-pair-staging.json':canonical(report)})
    retained,_=_read(exports,Path(saved['path']).name,'attachment-negative-pair-staging.json')
    if canonical(retained)!=canonical(report): raise ValueError('Staging export changed; retain candidate, do not retry')
    print(json.dumps(dict(export_path=saved['path'],**report)))


if __name__=='__main__': main()
