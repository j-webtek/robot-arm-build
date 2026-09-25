import importlib.util
import json
from pathlib import Path

import pytest


def load():
    root = Path(__file__).resolve().parents[2]
    spec = importlib.util.spec_from_file_location('bound_validator',
        root / 'scripts/build_bound_policy_validator.py')
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    report = json.loads((root / 'runs/wizard-exports' / module.BUILD_EXPORT /
                         'attachment-compile-review.json').read_bytes())
    return root, module, report


def test_current_source_matches_installed_build():
    root, module, report = load()
    assert 'controller_diagnostic_config.h' in module.verify_sources(root, report)


def test_different_application_rejected():
    root, module, report = load()
    report['artifact_hashes']['RoArm-M3_example.ino.bin'] = '0' * 64
    with pytest.raises(ValueError, match='Wrong application'):
        module.verify_sources(root, report)


def test_missing_header_evidence_rejected():
    root, module, report = load()
    key = str(Path('firmware/diagnostics/controller_diagnostic_config.h'))
    report['source_hashes'][key] = '0' * 64
    with pytest.raises(ValueError, match='differs from approved'):
        module.verify_sources(root, report)


def test_changed_source_rejected(monkeypatch):
    root, module, report = load()
    original = module.digest
    monkeypatch.setattr(module, 'digest', lambda path:
                        '0' * 64 if path.name == 'controller_diagnostic_config.h'
                        else original(path))
    with pytest.raises(ValueError, match='differs from approved'):
        module.verify_sources(root, report)


def test_r6_candidate_binding_and_missing_inventory():
    root,module,_=load()
    report=json.loads((root/'runs/wizard-exports'/module.R6_BUILD_EXPORT/'attachment-compile-review.json').read_bytes())
    assert 'controller_startup_config.h' in module.verify_sources(root,report,6)
    key=str(Path('.firmware-tools/configured-diagnostic-candidate-r6/RoArm-M3_example/controller_startup_config.h'))
    del report['source_hashes'][key]
    with pytest.raises(ValueError,match='inventory'):module.verify_sources(root,report,6)
