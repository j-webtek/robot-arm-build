import importlib.util
import json
from pathlib import Path
import subprocess
import sys
from test_ghost_endpoint_rehearsal import workspace
from rocell.application.wizard_diagnostic_export import verify_export

SCRIPT=Path(__file__).resolve().parents[2]/'scripts/rehearse_ghost_suite.py'


def test_real_suite_exports_readable_summary_and_raw_cases(workspace):
    (workspace/'software/runs').mkdir()
    result=subprocess.run([sys.executable,str(SCRIPT),'--workspace',str(workspace)],
                          capture_output=True,text=True,timeout=30)
    assert result.returncode==0,result.stderr
    summary=json.loads(result.stdout)
    assert summary['status']=='SIMULATION_SUITE_PASS' and summary['cases']==9
    folder=Path(summary['export'])
    assert summary['export_valid'] and verify_export(folder)['valid']
    assert (folder/'attachment-ghost-summary.md').is_file()
    suite=json.loads((folder/'attachment-ghost-suite.json').read_bytes())
    spec=importlib.util.spec_from_file_location('ghost_suite',SCRIPT)
    module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
    for case in suite['cases']:
        case_path=folder.parent/case['case_export']
        assert verify_export(case_path)['valid']
        report=json.loads((case_path/'attachment-ghost-case.json').read_bytes())
        assert module.evaluate(report)['passed']
        # A misleading success label cannot conceal duplicate dispatches.
        report['trial_results'][0]['simulated_wire_writes']*=2
        assert not module.evaluate(report)['passed']
