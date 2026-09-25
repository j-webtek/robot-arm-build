import importlib.util
from pathlib import Path


def test_frame_review_includes_optimized_mangled_clones():
    path=Path(__file__).resolve().parents[2]/'scripts/review_pair_candidate.py'
    spec=importlib.util.spec_from_file_location('pair_review',path)
    module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
    rows=module.stack_frames('''400e00d0 <_ZN17RocellPreparePairclEv$isra$0>:
400e00d0:  entry a1, 0xee0
400e0100 <rocell_diag::ControllerPairConfigParser::parse(char const*, unsigned int)>:
400e0100:  entry a1, 1328
400e0200 <unrelated()>:
400e0200:  entry a1, 4096
400e0300 <rocell_diag::ShoulderConfigurationSnapshot::acquire()>:
400e0300:  entry a1, 96
400e0400 <rocell_diag::shoulder_configuration_json()>:
400e0400:  entry a1, 144
''')
    assert [row['frame_bytes'] for row in rows]==[3808,1328,96,144]
    assert module.stack_frames('no function entry evidence')==[]
