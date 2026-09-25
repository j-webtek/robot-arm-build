"""Compile-only ESP32 size/stack regression; never link/upload or open a port."""
from pathlib import Path
import re
import subprocess
import pytest


def test_esp32_hold_memory_budget(tmp_path):
    root = Path(__file__).resolve().parents[2]
    bin_dir = root / '.firmware-tools/data/packages/esp32/tools/esp-x32/2302/bin'
    compiler = bin_dir / 'xtensa-esp32-elf-g++.exe'
    if not compiler.exists():
        pytest.skip('Pinned ESP32 cross compiler required')
    target = tmp_path / 'hold_memory_probe.o'
    compiled = subprocess.run([str(compiler), '-std=gnu++17', '-Os', '-fstack-usage',
        '-I', str(root / '.firmware-tools/user/libraries/ArduinoJson/src'),
        '-c', str(root / 'firmware/diagnostics/hold_memory_probe.cpp'), '-o', str(target)],
        capture_output=True, text=True, timeout=60)
    assert compiled.returncode == 0, compiled.stderr
    symbols = subprocess.run([str(bin_dir / 'xtensa-esp32-elf-nm.exe'), '-S', '--size-sort', str(target)],
        capture_output=True, text=True, timeout=10)
    assert symbols.returncode == 0, symbols.stderr
    sizes = {name: int(size, 16) for size, name in
             re.findall(r'^[0-9a-f]+ ([0-9a-f]+) B (hold_probe_\w+)$', symbols.stdout, re.MULTILINE)}
    assert sizes['hold_probe_runtime_store'] == sizes['hold_probe_runtime'] + sizes['hold_probe_store']
    # Review thresholds for this object graph, not proof of available live heap.
    assert sizes['hold_probe_runtime_store'] <= 80000
    assert sizes['hold_probe_owner'] <= 16000
    assert sizes['hold_probe_allocated_wrapper'] <= 32
    assert sizes['hold_probe_allocation'] <= 80000
    assert sizes['hold_probe_configured_allocation'] <= 100000
    frames = [int(line.split('\t')[1]) for line in target.with_suffix('.su').read_text().splitlines()]
    assert frames and max(frames) <= 512
