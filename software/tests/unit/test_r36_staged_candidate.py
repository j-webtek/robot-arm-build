from pathlib import Path


def test_only_diagnostic_owner_and_record_access_changed():
    root=Path(__file__).resolve().parents[2]/'.firmware-tools'
    def files(revision):
        path=root/f'configured-diagnostic-candidate-r{revision}/RoArm-M3_example'
        return {p.name:p.read_bytes() for p in path.iterdir() if p.is_file()}
    old,new=files(35),files(36)
    assert old.keys()==new.keys()
    assert {n for n in old if old[n]!=new[n]}=={
        'shoulder_characterization_owner.h','characterization_session.h'}
    assert b'pose.finished_us-sent_<2000000' in new['shoulder_characterization_owner.h']
    assert b'CharacterizationPattern::Matched' in new['characterization_smoke_board.h']
