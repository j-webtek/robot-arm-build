"""Offline P3 -> T4L specialization of the reviewed paired-shoulder r64 workflow."""
import hashlib
from pathlib import Path

from rocell.application.first_motion_contract import canonical
from rocell.application.product_ghost_export_review import _read
from rocell.application.t4_lift_review import review_t4_lift
from rocell.application.wizard_diagnostic_export import WizardDiagnosticExporter, verify_export

COMPILE = 'wizard-20260923T094333014308Z-df5a0efd5a874f0ab2de6dd4da1bc575'
RESULT = 'wizard-20260924T000623600641Z-c2103044389a40f4a53461447c9b9ea8'
BOOT = 'f7af4364ee3b87335970ee6052674b12'


def specialize(files):
    files = dict(files)
    changes = {
        'large_pose_relief_policy.h': [
            ('P1 -> P2L shoulder-lift', 'P3 -> T4L shoulder-lift'),
            ('source_goals[7]={2047,2348,1766,2842,1719,2040,2047}', 'source_goals[7]={2047,2283,1831,2777,1850,2040,2047}'),
            ('source_positions[7]={2047,2356,1759,2844,1720,2041,2047}', 'source_positions[7]={2047,2291,1825,2780,1850,2041,2047}'),
            ('target_goals[7]={2047,2283,1831,2842,1719,2040,2047}', 'target_goals[7]={2047,2217,1897,2777,1850,2040,2047}')],
        'large_pose_relief_owner.h': [
            ('P1 -> P2L lift', 'P3 -> T4L lift'),
            ('LARGE_POSE_P2L_INTENT', 'LARGE_POSE_T4L_INTENT'),
            ('LARGE_POSE_P2L_RECORDED', 'LARGE_POSE_T4L_RECORDED'),
            ('uint16_t(2283)', 'uint16_t(2217)'),
            ('uint16_t(1831)', 'uint16_t(1897)'),
            ('RCP2LIFT01', 'RCT4LIFT01'),
            ('put(2283,2);put(1831,2)', 'put(2217,2);put(1897,2)')],
        'large_pose_relief_routes.h': [
            ('P1 -> P2L route', 'P3 -> T4L route'),
            ('body "P2L"', 'body "T4L"'),
            ('body!="P2L"', 'body!="T4L"'),
            ('LARGE_POSE_P2L_RECORDED', 'LARGE_POSE_T4L_RECORDED')],
        'characterization_board_services.h': [
            ('first!=12||second!=13||a!=2283||b!=1831', 'first!=12||second!=13||a!=2217||b!=1897')],
    }
    for name, replacements in changes.items():
        for before, after in replacements:
            before, after = before.encode(), after.encode()
            if files[name].count(before) != 1:
                raise ValueError('Expected unique reviewed source: '+name)
            files[name] = files[name].replace(before, after)
    return files


def stage(root):
    root = Path(root).resolve()
    exports = root/'runs/wizard-exports'
    compiled, receipt = _read(exports, COMPILE, 'attachment-compile-review.json')
    source = exports/RESULT
    if not verify_export(source)['valid']:
        raise ValueError('Invalid source export')
    raw = bytes.fromhex((source/'attachment-large-pose-relief.hex.txt').read_text())
    path_review = review_t4_lift(raw, expected_boot=BOOT,
        model_path=root/'models/roarm_m3/roarm_m3_kinematic_40dbd84.urdf')
    if path_review['source_positions'] != [2047,2291,1825,2780,1850,2041,2047]:
        raise ValueError('Pinned P3 endpoint differs')
    prefix = '.firmware-tools/configured-diagnostic-candidate-r64/RoArm-M3_example/'
    files = {p.name:p.read_bytes() for p in (root/prefix).iterdir() if p.is_file()}
    sha = lambda value: hashlib.sha256(value).hexdigest()
    expected = {Path(p).name:h for p,h in compiled['source_hashes'].items()
                if p.replace('\\','/').startswith(prefix)}
    if (compiled['status'] != 'COMPILED' or compiled['target'] != 'configured-diagnostic-candidate-r64'
            or set(files) != set(expected) or any(sha(v) != expected[k] for k,v in files.items())):
        raise ValueError('Pinned r64 source differs')
    candidate = specialize(files)
    changed = {k:dict(before=sha(files[k]), after=sha(v)) for k,v in candidate.items() if v != files[k]}
    target = root/'.firmware-tools/configured-diagnostic-candidate-r68/RoArm-M3_example'
    target.mkdir(parents=True, exist_ok=False)
    for name, value in candidate.items():
        with (target/name).open('xb') as stream:
            stream.write(value)
        if (target/name).read_bytes() != value:
            raise ValueError('Staged readback differs')
    exporter = WizardDiagnosticExporter(exports)
    exporter.prepare(create=True)
    saved = exporter.export({'mode':'r68-t4-lift-stage'}, [], attachments={
        'r68-t4-lift-stage.json':canonical(dict(revision=68, predecessor_compile_receipt=receipt,
            source_export=RESULT, changed_files=changed, path_review=path_review,
            selector='T4L', maximum_writes=1, retry_allowed=False, return_allowed=False,
            hardware_access=False, uploaded=False, deployable=False))})
    if not verify_export(Path(saved['path']))['valid']:
        raise ValueError('Stage export invalid')
    return saved['path']


if __name__ == '__main__':
    print(stage(Path(__file__).resolve().parents[1]))
