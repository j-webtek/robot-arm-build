"""Actual Windows file-sharing checks on temporary evidence; no child or arm."""

import os
import time
import pytest
from test_endpoint_native_registration import registration


@pytest.mark.skipif(os.name!='nt',reason='Windows file sharing and handle ownership')
def test_owned_backend_blocks_evidence_write_delete_and_rename(tmp_path):
    from rocell.providers.windows._owned_worker_win32 import WindowsOwnedProcess
    reg,_ = registration(tmp_path)
    evidence = reg.package_files[2].path
    original = evidence.read_bytes()
    owner = WindowsOwnedProcess()
    try:
        owner.pin(reg)
        with pytest.raises(OSError):
            with evidence.open('wb') as stream: stream.write(b'changed')
        with pytest.raises(OSError): evidence.unlink()
        with pytest.raises(OSError): evidence.rename(evidence.with_name('replacement.json'))
        assert evidence.read_bytes()==original
        assert owner.created is False
    finally:
        errors = owner.cleanup(time.monotonic_ns()+2_000_000_000)
    assert errors==() and owner.pins==[] and owner.handles=={}
    # Reopening for append without writing verifies release without changing data.
    with evidence.open('ab'): pass
    assert evidence.read_bytes()==original
