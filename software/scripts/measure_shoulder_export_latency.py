"""Offline lower-bound timing probe: synthetic replies, real workspace exports.

Uses the explicitly synthetic unit-test transport, no sockets/serial/private keys.
This measures host persistence overhead, NOT controller, Wi-Fi or servo latency.
"""
import importlib.util
from pathlib import Path
import tempfile
import time
from rocell.application.first_motion_contract import canonical
from rocell.application.shoulder_session_runner import run_shoulder_session
from rocell.application.wizard_diagnostic_export import WizardDiagnosticExporter, verify_export


def main():
    root=Path(__file__).resolve().parents[1]
    spec=importlib.util.spec_from_file_location('synthetic_shoulder_fixture',
        root/'tests/unit/test_shoulder_session_runner.py')
    fixture=importlib.util.module_from_spec(spec);spec.loader.exec_module(fixture)
    exports=root/'runs/wizard-exports'
    run_root=Path(tempfile.mkdtemp(prefix='shoulder-latency-',dir=exports))
    transport=fixture.Transport();receipts=[];began=time.perf_counter()

    def measured(method,path,body,timeout):
        if path.endswith('/receipt'):
            receipts.append(dict(sequence=transport.sequence,at_s=time.perf_counter()-began))
        return transport(method,path,body,timeout)

    result=run_shoulder_session(run_root,expected_boot='11'*16,key=bytes(range(32)),
        exchange=measured,authorized=True)
    gaps=[dict(sequence=b['sequence'],gap_ms=1000*(b['at_s']-a['at_s']))
          for a,b in zip(receipts,receipts[1:]) if b['sequence']>=8]
    post_enable_s=(receipts[-1]['at_s']-receipts[7]['at_s']) if len(receipts)>8 else None
    report=dict(schema='rocell.shoulder_host_latency.v1',origin='SIMULATION',hardware_access=False,
        transport='instantaneous synthetic unit fixture',controller_clock='not modeled',
        host_elapsed_s=time.perf_counter()-began,run_state=result['report']['state'],
        runner_export=result['export_path'],receipt_gaps=gaps,post_enable_host_s=post_enable_s,
        max_receipt_gap_ms=max((v['gap_ms'] for v in gaps),default=None),
        candidate_max_gap_ms=500,candidate_total_observation_ms=3000,
        live_timing_verified=False)
    exporter=WizardDiagnosticExporter(exports);exporter.prepare(create=True)
    saved=exporter.export({'mode':'offline-host-export-latency'},[],
        attachments={'shoulder-latency.json':canonical(report)})
    if not verify_export(Path(saved['path']))['valid']:raise ValueError('Timing export verification failed')
    print(canonical(dict(report,export_path=saved['path'])).decode())


if __name__=='__main__':main()
