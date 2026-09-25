"""Offline public-source staging only. No device, filesystem provisioning or upload."""
import hashlib
import re
from pathlib import Path
from rocell.application.product_ghost_export_review import _read
from rocell.application.first_motion_contract import canonical
from rocell.application.wizard_diagnostic_export import WizardDiagnosticExporter, verify_export


def main():
    root=Path(__file__).resolve().parents[1]
    source=root/'.firmware-tools/configured-diagnostic-candidate-r22/RoArm-M3_example'
    target=root/'.firmware-tools/configured-diagnostic-candidate-r23/RoArm-M3_example'
    report,receipt=_read(root/'runs/wizard-exports',
        'wizard-20260919T172412279738Z-60d710244bc94554994cea79527eb2a3', 'attachment-compile-review.json')
    sha=lambda b:hashlib.sha256(b).hexdigest()
    prefix='.firmware-tools/configured-diagnostic-candidate-r22/RoArm-M3_example/'
    expected={Path(p).name:h for p,h in report['source_hashes'].items() if p.replace('\\','/').startswith(prefix)}
    files={p.name:p.read_bytes() for p in source.iterdir() if p.is_file()}
    if report['status']!='COMPILED' or set(files)!=set(expected) or any(sha(b)!=expected[n] for n,b in files.items()):
        raise ValueError('Pinned predecessor inventory mismatch')
    original=dict(files)
    pending=['shoulder_board_session.h']
    while pending:
        name=pending.pop()
        if name in files:continue
        raw=(root/'firmware/diagnostics'/name).read_bytes();files[name]=raw
        for dep in re.findall(rb'#include "([^"/]+\.h)"',raw):
            if (root/'firmware/diagnostics'/dep.decode()).is_file():pending.append(dep.decode())
    def patch(name,old,new):
        raw=files[name]
        if raw.count(old)!=1:raise ValueError('Ambiguous patch: '+name)
        files[name]=raw.replace(old,new,1)
    guard=b'  if(rocellShoulderReserved)return false;\n'
    patch('configured_native_owner.h',b'#include "pose_observation_reservation.h"',
          b'#include "pose_observation_reservation.h"\nbool rocellShoulderReserved=false;')
    patch('diagnostic_http.h',b'bool rocellPrepareHoldChallenge(){',b'bool rocellPrepareHoldChallenge(){\n'+guard)
    patch('configured_pair_board_routes.h',b'  bool operator()(){',b'  bool operator()(){\n'+guard)
    patch('configured_pair_board_routes.h',b'bool rocellConfigurationBusInactive(void*){',b'bool rocellConfigurationBusInactive(void*){\n'+guard)
    patch('configured_recovery_board_routes.h',b'  bool operator()(char* out,size_t capacity){',b'  bool operator()(char* out,size_t capacity){\n'+guard)
    patch('pose_observation_board.h',b'bool rocellReservePose(void*){',b'bool rocellReservePose(void*){\n'+guard)
    patch('configured_pair_board_routes.h',b'void registerDiagnosticRoutes(){',
          b'#include "shoulder_board_session.h"\nvoid registerDiagnosticRoutes(){\n  registerShoulderSessionRoutes();')
    patch('diagnostic_boot.h',b'void loop(){',b'void loop(){\n  if(rocellDiagnosticBootReady&&rocellShoulderReserved){pollShoulderSession();delay(1);return;}')
    target.mkdir(parents=True,exist_ok=False)
    for name,raw in files.items():
        with (target/name).open('xb') as stream:stream.write(raw)
        if (target/name).read_bytes()!=raw:raise ValueError('Stage readback mismatch')
    review=dict(schema='rocell.shoulder_session_stage.v1',revision=23,predecessor_receipt=receipt,
        changed_files={n:dict(before=sha(original[n]) if n in original else None,after=sha(b))
                       for n,b in files.items() if original.get(n)!=b},hardware_access=False,uploaded=False)
    exporter=WizardDiagnosticExporter(root/'runs/wizard-exports');exporter.prepare(create=True)
    saved=exporter.export({'mode':'r23-public-stage'},[],attachments={'shoulder-session-stage.json':canonical(review)})
    if not verify_export(Path(saved['path']))['valid']:raise ValueError('Export failed')
    print(saved['path'])


if __name__=='__main__':main()
