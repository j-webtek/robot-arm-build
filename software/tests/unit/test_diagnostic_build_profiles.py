"""Compile-profile selection is pure and does not touch a controller/toolchain."""
import importlib.util
from pathlib import Path

import pytest


def load_script():
    path = Path(__file__).resolve().parents[2] / 'scripts/compile_diagnostic_reference.py'
    spec = importlib.util.spec_from_file_location('diagnostic_compile_profiles', path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_layout_profile_preserves_earlier_artifacts():
    module = load_script()
    tools = Path('test-tools')
    original, old_fqbn = module.build_settings(tools, 'configured-diagnostic-candidate-r2', 'legacy-huge-app')
    reviewed, fqbn = module.build_settings(tools, 'configured-diagnostic-candidate-r2', 'default-4mb-no-psram')
    assert original.name == 'build-configured-diagnostic-candidate-r2'
    assert reviewed != original
    assert reviewed.name.endswith('--default-4mb-no-psram')
    assert old_fqbn.endswith('PartitionScheme=huge_app,PSRAM=enabled')
    assert fqbn.endswith('PartitionScheme=default,PSRAM=disabled')


def test_unknown_profile_has_no_fallback():
    with pytest.raises(KeyError):
        load_script().build_settings(Path('test-tools'), 'probe', 'guessed-board')
