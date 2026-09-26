"""Explicit hardware-free CI stages; no discovery of live experiment scripts."""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[2]
PYTHON = ROOT / '.venv-ci' / ('Scripts/python.exe' if sys.platform == 'win32' else 'bin/python')
TESTS = (
    'software/tests/unit/test_snapshot_audit.py',
    'software/tests/unit/test_model_motion_ingress_v2.py',
    'software/tests/unit/test_model_motion_planner_gate.py',
    'software/tests/unit/test_model_motion_sequence_coordinator.py',
    'software/tests/unit/test_zero_write_waveshare_adapter_v1.py',
    'software/tests/unit/test_zero_write_sole_writer_v1.py',
    'software/tests/unit/test_installed_controller_qualification_v1.py',
    'software/tests/integration/test_zero_write_waveshare_contract_v1.py',
    'software/tests/integration/test_model_motion_v2_shared_gate.py',
    'software/tests/integration/test_shared_shadow_runner_v2.py',
    'software/ai/tests/test_batch_emitter_v2.py',
    'software/ai/tests/test_capture_binding.py',
    'software/ai/tests/test_precision_binding_v2.py',
    'software/ai/tests/test_confidence_metrics.py',
)


def run(*args: str, capture: bool = False) -> subprocess.CompletedProcess:
    return subprocess.run([str(PYTHON), *args], cwd=ROOT, check=True,
                          text=True, capture_output=capture, timeout=600)


def require(condition: bool, message: str) -> None:
    if not condition:
        raise RuntimeError(message)


def smoke() -> None:
    # -I ignores PYTHONPATH and cwd: this must resolve the installed package.
    run('-I', '-c', "import rocell; from importlib.metadata import version; print('Installed rocell', version('rocell'))")
    results = {}
    for command in ('ground', 'coordinate-preview'):
        results[command] = json.loads(run('software/ai/run_offline.py', command,
            '--request', 'Type "hi" on the keyboard', capture=True).stdout)
    ground = results['ground']
    require(ground['inspection']['status'] == 'accepted', 'Grounded request rejected')
    require(ground['proposal']['text'] == 'hi', 'Literal text changed')
    require([a['key'] for a in ground['inspection']['action_plan']['actions']] == ['H', 'I'],
            'Action order changed')
    preview = results['coordinate-preview']
    require(preview['execution_authorized'] is False, 'Preview claims execution authority')
    require(preview['controller_commands'] == [], 'Preview contains controller commands')
    require(preview['coordinate_source'] == 'SIMULATION_ONLY_NOMINAL_UNMEASURED',
            'Preview no longer declares nominal geometry')
    require([t['target_id'] for t in preview['targets']] == ['H', 'I'], 'Preview order changed')
    print('PASS: installed package, H/I ordering, nominal preview, no execution authority')


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('stage', choices=('install-base', 'install-tests', 'smoke', 'test', 'environment'))
    stage = parser.parse_args().stage
    require(PYTHON.is_file(), 'Create .venv-ci with python -m venv .venv-ci first')
    if stage == 'install-base':
        run('-m', 'pip', 'install', './software')
        run('-m', 'pip', 'check')
    elif stage == 'install-tests':
        run('-m', 'pip', 'install', './software[test]')
        run('-m', 'pip', 'check')
    elif stage == 'smoke':
        smoke()
    elif stage == 'environment':
        run('scripts/ci/environment_report.py')
    else:
        run('-m', 'pytest', '-q', *TESTS)


if __name__ == '__main__':
    main()
