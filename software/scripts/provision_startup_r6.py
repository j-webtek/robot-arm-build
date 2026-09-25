"""Explicit r6 provisioning stages; preflight is local-only and creates no key."""
import argparse
import hashlib
import json
from pathlib import Path
import secrets
import subprocess
import sys

from rocell.application.first_motion_contract import canonical
from rocell.application.native_provisioning_validator import NativeProvisioningValidator
from rocell.application.diagnostic_provisioning_image import stage_startup_image
from rocell.application.startup_provisioning_execution import APP_SHA256, FS_START, FS_END
from rocell.application.startup_provisioning_run import run_provisioning
from rocell.application.wizard_diagnostic_export import WizardDiagnosticExporter, verify_export
from rocell.providers.windows.diagnostic_image_store import save_image, load_image

BACKUP = 'd9e3de5cf3738b18144697095534ec9a33e531a6cd5062f68b85b5a29f6df2b9'
POLICY = '75047d49f29468cf69374198321be3f19d56b35a8f98340781458cae56b0a216'
VALIDATOR = '3a6c5647f80891237942639ed497441ccc105b5f455addf0119c16519ba44fe5'
STAGED = 'startup-r6-reviewed-candidate.dpapi'


def digest(data):
    return hashlib.sha256(data).hexdigest()


def check_private_acl(path):
    if sys.platform != 'win32' or path.is_symlink():
        raise ValueError('Reviewed Windows private directory required')
    literal = str(path).replace("'", "''")
    script = (f"$ErrorActionPreference='Stop'; $taskAcl=Get-Acl -LiteralPath '{literal}'; "
        "[pscustomobject]@{Protected=$taskAcl.AreAccessRulesProtected;"
        "CurrentSid=[System.Security.Principal.WindowsIdentity]::GetCurrent().User.Value;"
        "Rules=@($taskAcl.Access | ForEach-Object {[pscustomobject]@{"
        "Sid=$_.IdentityReference.Translate([System.Security.Principal.SecurityIdentifier]).Value;"
        "Type=$_.AccessControlType.ToString();Rights=[int]$_.FileSystemRights;Inherited=$_.IsInherited}})}"
        " | ConvertTo-Json -Depth 4")
    result = subprocess.run(['pwsh', '-NoProfile', '-NonInteractive', '-Command', script],
        capture_output=True, text=True, timeout=10, check=True)
    acl = json.loads(result.stdout)
    if (acl['Protected'] is not True or len(acl['Rules']) != 1 or
            acl['Rules'][0] != dict(Sid=acl['CurrentSid'], Type='Allow', Rights=2032127, Inherited=False)):
        raise ValueError('Private directory must grant only current-user full control')


def preflight(root):
    private = root / 'private-backups/controller-20260918-session1'
    check_private_acl(private)
    backup = (private / 'flash-pair-a.bin').read_bytes()
    if len(backup) != 0x400000 or digest(backup) != BACKUP:
        raise ValueError('Retained source backup mismatch')
    if digest((private / 'flash-pair-b.bin').read_bytes()) != BACKUP:
        raise ValueError('Retained second backup mismatch')
    app = (root / '.firmware-tools/build-configured-diagnostic-candidate-r6--default-4mb-no-psram/RoArm-M3_example.ino.bin').read_bytes()
    if len(app) != 1081872 or digest(app) != APP_SHA256:
        raise ValueError('Reviewed r6 app mismatch')
    policy = canonical(json.loads((root / 'docs/startup-r6-policy-draft.json').read_bytes()))
    if digest(policy) != POLICY:
        raise ValueError('Policy changed since review')
    validator = NativeProvisioningValidator(root / '.firmware-tools/bound-policy-validator-5juihe6t/validate.exe', VALIDATOR)
    if not validator(policy):
        raise ValueError('Native policy rejected')
    if (private / 'startup-r6-provisioning-events.jsonl').exists():
        raise ValueError('Provisioning already reserved; no resume')
    return private, backup[FS_START:FS_END], policy, validator


def read_staged_key(candidate, littlefs):
    fs = littlefs.LittleFS(context=littlefs.UserContext(buffer=bytearray(candidate)),
        mount=False, block_size=4096, block_count=352, read_size=256, prog_size=256)
    fs.mount()  # No formatting or repair.
    try:
        with fs.open('/rocell-startup.key', 'rb') as stream:
            key = stream.read(33)
        if len(key) != 32:
            raise ValueError('Staged key length mismatch')
        return key
    finally:
        fs.unmount()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    modes = parser.add_mutually_exclusive_group(required=True)
    modes.add_argument('--preflight-only', action='store_true')
    modes.add_argument('--authorized-stage-private', action='store_true')
    modes.add_argument('--authorized-provision-and-startup', action='store_true')
    parser.add_argument('--candidate-sha256')
    options = parser.parse_args()
    if options.authorized_provision_and_startup != bool(options.candidate_sha256):
        parser.error('Only provisioning requires the separately approved candidate SHA-256')
    root = Path(__file__).resolve().parents[1]
    private, source, policy, validator = preflight(root)
    if options.preflight_only:
        print(json.dumps(dict(status='LOCAL_PREFLIGHT_VERIFIED', policy_sha256=POLICY,
            source_sha256=digest(source), hardware_access=False, key_created=False)))
        return
    sys.path.insert(0, str(root / '.firmware-tools/littlefs-review'))
    import littlefs
    if littlefs.__version__ != '0.19.0':
        raise ValueError('Unreviewed LittleFS version')
    exports = root / 'runs/wizard-exports'
    if options.authorized_stage_private:
        if (private / STAGED).exists():
            raise ValueError('Staged candidate already exists; no regeneration')
        key = secrets.token_bytes(32)
        candidate, review = stage_startup_image(source, digest(source), policy, key,
            littlefs=littlefs, validate_policy=validator)
        save_image(private, STAGED, candidate)
        exporter = WizardDiagnosticExporter(exports.resolve())
        exporter.prepare(create=True)
        receipt = exporter.export({'mode': 'offline-startup-staging'}, [],
            attachments={'startup-staging-review.json': canonical(review)})
        if not verify_export(Path(receipt['path']))['valid']:
            raise ValueError('Staging export failed; do not restage')
        print(json.dumps(dict(status='PRIVATELY_STAGED_NOT_PROVISIONED',
            candidate_sha256=digest(candidate), export_id=Path(receipt['path']).name,
            hardware_access=False)))
        return
    candidate = load_image(private / STAGED)
    if digest(candidate) != options.candidate_sha256:
        raise ValueError('Approved staged image mismatch')
    key = read_staged_key(candidate, littlefs)
    # No serial/esptool import before explicit provisioning selection and all
    # local checks. Device construction is inert; the core reserves before open.
    sys.path.insert(0, str(root / '.firmware-tools/esptool-api-4.6'))
    import esptool
    from esptool import cmds, loader
    import serial
    if not Path(esptool.__file__).resolve().is_relative_to((root / '.firmware-tools/esptool-api-4.6').resolve()):
        raise ValueError('Unexpected esptool import location')
    from rocell.providers.windows.startup_provisioning_device import StartupProvisioningDevice
    device = StartupProvisioningDevice(esptool=esptool, cmds=cmds, loader=loader, serial=serial)
    result = run_provisioning(source=source, source_sha256=digest(source), candidate=candidate,
        candidate_sha256=options.candidate_sha256, policy=policy, key=key, littlefs=littlefs,
        validate_policy=validator, private_root=private, export_root=exports, device=device,
        save_private_image=save_image, startup_authorized=True)
    print(json.dumps(result))


if __name__ == '__main__':
    main()
