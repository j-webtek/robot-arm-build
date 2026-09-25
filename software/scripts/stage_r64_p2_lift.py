"""Offline exact P1 -> P2L specialization of the retained r63 workflow."""
import hashlib
from pathlib import Path

from rocell.application.first_motion_contract import canonical
from rocell.application.product_ghost_export_review import _read
from rocell.application.p2_path_review import review_p2_path
from rocell.application.wizard_diagnostic_export import WizardDiagnosticExporter, verify_export

COMPILE = 'wizard-20260923T015145565967Z-a39d76aa5967494f9e831e9fee455f48'
RESULT = 'wizard-20260923T024713112793Z-299f2bdab3454e0fb68cc1cdc7cd44f0'
BOOT = 'f7b522422be6edcb9ab740a776e32ae5'


def specialize(files):
    files = dict(files)
    changes = {
        'large_pose_relief_policy.h': [
            ('T1 -> P1 elbow-relief', 'P1 -> P2L shoulder-lift'),
            ('source_goals[7]={2047,2348,1766,2907,1654,2040,2047}', 'source_goals[7]={2047,2348,1766,2842,1719,2040,2047}'),
            ('source_positions[7]={2047,2357,1759,2904,1652,2041,2047}', 'source_positions[7]={2047,2356,1759,2844,1720,2041,2047}'),
            ('target_goals[7]={2047,2348,1766,2842,1719,2040,2047}', 'target_goals[7]={2047,2283,1831,2842,1719,2040,2047}'),
            ('selected[2]={3,4}', 'selected[2]={1,2}'),
            ('joint==3||joint==4', 'joint==1||joint==2')],
        'large_pose_relief_owner.h': [
            ('T1 -> P1 relief', 'P1 -> P2L lift'),
            ('LARGE_POSE_P1_INTENT', 'LARGE_POSE_P2L_INTENT'),
            ('LARGE_POSE_P1_RECORDED', 'LARGE_POSE_P2L_RECORDED'),
            ('uint8_t(14),uint8_t(15),uint16_t(2842)', 'uint8_t(12),uint8_t(13),uint16_t(2283)'),
            ('uint16_t(1719),uint16_t(20)', 'uint16_t(1831),uint16_t(20)'),
            ('RCRELIEF01', 'RCP2LIFT01'),
            ('put(2842,2);put(1719,2)', 'put(2283,2);put(1831,2)')],
        'large_pose_relief_routes.h': [
            ('T1 -> P1 route', 'P1 -> P2L route'),
            ('body "P1"', 'body "P2L"'),
            ('body!="P1"', 'body!="P2L"'),
            ('LARGE_POSE_P1_RECORDED', 'LARGE_POSE_P2L_RECORDED')],
        'characterization_board_services.h': [
            ('first!=14||second!=15||a!=2842||b!=1719', 'first!=12||second!=13||a!=2283||b!=1831')],
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
    path_review = review_p2_path(raw, expected_boot=BOOT,
        model_path=root/'models/roarm_m3/roarm_m3_kinematic_40dbd84.urdf')
    if path_review['source_positions'] != [2047,2356,1759,2844,1720,2041,2047]:
        raise ValueError('Pinned P1 endpoint differs')
    prefix = '.firmware-tools/configured-diagnostic-candidate-r63/RoArm-M3_example/'
    files = {p.name:p.read_bytes() for p in (root/prefix).iterdir() if p.is_file()}
    sha = lambda value: hashlib.sha256(value).hexdigest()
    expected = {Path(p).name:h for p,h in compiled['source_hashes'].items()
                if p.replace('\\','/').startswith(prefix)}
    if (compiled['status'] != 'COMPILED' or compiled['target'] != 'configured-diagnostic-candidate-r63'
            or set(files) != set(expected) or any(sha(v) != expected[k] for k,v in files.items())):
        raise ValueError('Pinned r63 source differs')
    candidate = specialize(files)
    changed = {k:dict(before=sha(files[k]), after=sha(v)) for k,v in candidate.items() if v != files[k]}
    target = root/'.firmware-tools/configured-diagnostic-candidate-r64/RoArm-M3_example'
    target.mkdir(parents=True, exist_ok=False)
    for name, value in candidate.items():
        with (target/name).open('xb') as stream:
            stream.write(value)
        if (target/name).read_bytes() != value:
            raise ValueError('Staged readback differs')
    exporter = WizardDiagnosticExporter(exports)
    exporter.prepare(create=True)
    saved = exporter.export({'mode':'r64-p2-lift-stage'}, [], attachments={
        'r64-p2-lift-stage.json':canonical(dict(revision=64, predecessor_compile_receipt=receipt,
            source_export=RESULT, changed_files=changed, path_review=path_review,
            selector='P2L', maximum_writes=1, retry_allowed=False, return_allowed=False,
            hardware_access=False, uploaded=False, deployable=False))})
    if not verify_export(Path(saved['path']))['valid']:
        raise ValueError('Stage export invalid')
    return saved['path']


if __name__ == '__main__':
    print(stage(Path(__file__).resolve().parents[1]))
