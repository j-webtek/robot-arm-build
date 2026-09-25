"""Win32 creation-policy inspection; CreateProcess is replaced with a refusal."""

import os

import pytest

pytestmark = pytest.mark.skipif(os.name != "nt", reason="Windows process transport")


@pytest.mark.parametrize("kind", ["activation", "legacy", "derived-activation"])
def test_detached_camera_pipe_policy_is_exact_type_and_remains_job_contained(
    tmp_path, monkeypatch, kind
):
    from rocell.providers.windows import _owned_worker_win32 as backend
    from test_native_camera_activation_registration import preparation

    class Derived(backend.WindowsOwnedCameraActivationPipeProcess):
        pass

    owner_type = {
        "activation": backend.WindowsOwnedCameraActivationPipeProcess,
        "legacy": backend.WindowsOwnedProcess,
        "derived-activation": Derived,
    }[kind]
    owner = owner_type()
    recorded = []

    def refuse_create(*args):
        recorded.append(args[5])
        return False

    monkeypatch.setattr(owner.k, "CreateProcessW", refuse_create)
    prepared = preparation(tmp_path)
    try:
        with pytest.raises(OSError):
            owner.start(
                prepared.registration,
                prepared.admission_request.wire(),
                check=lambda: None,
                keep_stdin_open=True,
            )
        assert len(recorded) == 1
        flags = recorded[0]
        assert bool(flags & 0x8) is (kind == "activation")
        assert bool(flags & 0x8000000) is (kind != "activation")
        assert flags & 0x4 and flags & 0x80000  # Suspended + extended Job/handle list.
        assert not flags & 0x01000000  # No Job breakaway.
        assert not owner.created and not owner.resumed
    finally:
        import time

        assert owner.cleanup(time.monotonic_ns() + 2_000_000_000) == ()
        assert (
            not owner.pending
            and not owner.handles
            and not owner.unclosed_handles
            and not owner.pins
        )
