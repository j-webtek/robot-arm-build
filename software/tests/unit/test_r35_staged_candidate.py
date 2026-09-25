from pathlib import Path


def test_staged_change_set_and_limits():
    root=Path(__file__).resolve().parents[2]/'.firmware-tools'
    old=root/'configured-diagnostic-candidate-r34/RoArm-M3_example'
    new=root/'configured-diagnostic-candidate-r35/RoArm-M3_example'
    before={p.name:p.read_bytes() for p in old.iterdir() if p.is_file()}
    after={p.name:p.read_bytes() for p in new.iterdir() if p.is_file()}
    assert before.keys()==after.keys()
    assert {n for n in before if before[n]!=after[n]}=={
        'shoulder_characterization_owner.h','characterization_smoke_board.h'}
    assert b'CharacterizationPattern::Matched' in after['characterization_smoke_board.h']
    assert b'CAMPAIGN_TARGET_EXCURSION' in after['shoulder_characterization_owner.h']
    assert b'anchor_set_' in after['shoulder_characterization_owner.h']
