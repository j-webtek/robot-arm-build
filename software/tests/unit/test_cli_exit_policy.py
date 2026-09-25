from rocell.cli import ExitCode, _target_sweep_exit_code


def test_target_sweep_alignment_block_is_always_nonzero() -> None:
    assert _target_sweep_exit_code(
        alignment_passed=False,
        all_accepted=False,
        require_all=False,
    ) == int(ExitCode.CONFIGURATION_ERROR)


def test_target_sweep_ik_gaps_are_optional_unless_require_all() -> None:
    assert _target_sweep_exit_code(
        alignment_passed=True,
        all_accepted=False,
        require_all=False,
    ) == int(ExitCode.OK)
    assert _target_sweep_exit_code(
        alignment_passed=True,
        all_accepted=False,
        require_all=True,
    ) == int(ExitCode.CONFIGURATION_ERROR)
