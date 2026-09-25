from pathlib import Path


def test_r37_is_only_matrix_policy_and_selection_change():
    root = Path(__file__).resolve().parents[2]/'.firmware-tools'
    def files(revision):
        path = root/f'configured-diagnostic-candidate-r{revision}/RoArm-M3_example'
        return {p.name: p.read_bytes() for p in path.iterdir() if p.is_file()}
    old, new = files(36), files(37)
    assert old.keys() == new.keys()
    assert {n for n in old if old[n] != new[n]} == {
        'characterization_prepare.h', 'characterization_controller.h',
        'shoulder_characterization_policy.h', 'shoulder_characterization_owner.h',
        'characterization_smoke_board.h'}
    board = 'characterization_smoke_board.h'
    assert new[board] == old[board].replace(b'CharacterizationPattern::Matched',
                                          b'CharacterizationPattern::Matrix')
    owner = new['shoulder_characterization_owner.h']
    assert b'consecutive_small_==0' in owner
    assert b'pose.finished_us-(matrix_?samples_[0].started_us:sent_)<2000000' in owner
    assert b'CharacterizationOutcome::SettledSmall?4' in owner
    # Frozen r37 is tied to its compile evidence, not mutable next-candidate source.
    import hashlib
    from rocell.application.product_ghost_export_review import _read
    report, _ = _read(root.parent/'runs/wizard-exports',
        'wizard-20260920T165204433480Z-9ee192ff5bd24979a284023834ad2400',
        'attachment-compile-review.json')
    hashes = {Path(p).name: digest for p,digest in report['source_hashes'].items()
              if 'configured-diagnostic-candidate-r37' in p}
    for name in ('characterization_prepare.h', 'characterization_controller.h',
                 'shoulder_characterization_policy.h', 'shoulder_characterization_owner.h'):
        assert hashlib.sha256(new[name]).hexdigest() == hashes[name]
