"""Bounded diagnostic of the fixed incapable child and its OWN Job only."""

import ctypes as C
from ctypes import wintypes as W
import json

from test_owned_usb_identity_runner import usb_fixture, run_case
from rocell.providers.windows import owned_usb_identity_runner as runner
from rocell.providers.windows import _owned_worker_win32 as backend


def test_actual_owned_job_accounting(monkeypatch):
    owner = backend.WindowsOwnedUsbPipeProcess()
    query = owner.k.QueryInformationJobObject
    image_name = owner.k.QueryFullProcessImageNameW
    image_name.argtypes = [W.HANDLE, W.DWORD, W.LPWSTR, C.POINTER(W.DWORD)]
    image_name.restype = W.BOOL
    records = []

    def instrumented(job, information_class, buffer, size, needed):
        result = query(job, information_class, buffer, size, needed)
        if result and information_class == 3 and len(records) < 128:
            ids = C.cast(buffer, C.POINTER(backend._Pids)).contents
            limits = backend._Limits()
            assert query(job, 9, C.byref(limits), C.sizeof(limits), None)
            row = {
                "root_pid": owner.pid,
                "assigned": ids.assigned,
                "listed": ids.listed,
                "process_limit": limits.basic.processes,
                "limit_flags": limits.basic.flags,
                "members": [],
            }
            for pid in ids.pids[: min(ids.listed, 4)]:
                # Never enumerate a PID outside this exact owned Job result.
                handle = owner.process
                temporary = pid != owner.pid
                if temporary:
                    handle = owner.k.OpenProcess(0x1000 | 0x100000, False, pid)
                    if handle:
                        owner._own(handle, "usb-test-member-observation")
                member = {"pid": pid, "handle_observed": bool(handle)}
                try:
                    if handle:
                        member["wait_status"] = owner.k.WaitForSingleObject(handle, 0)
                        inside = W.BOOL()
                        member["membership_query_succeeded"] = bool(
                            owner.k.IsProcessInJob(handle, job, C.byref(inside))
                        )
                        member["inside_job"] = bool(inside.value)
                        if member["membership_query_succeeded"] and inside.value:
                            path_buffer = C.create_unicode_buffer(4096)
                            path_length = W.DWORD(4096)
                            member["image_query_succeeded"] = bool(
                                image_name(handle, 0, path_buffer, C.byref(path_length))
                            )
                            if member["image_query_succeeded"]:
                                member["image_name"] = path_buffer.value
                finally:
                    if temporary and handle:
                        owner._close(handle)
                row["members"].append(member)
            records.append(row)
        return result

    monkeypatch.setattr(owner.k, "QueryInformationJobObject", instrumented)
    monkeypatch.setattr(runner, "_new_owner", lambda: owner)
    monkeypatch.setattr(runner, "source_fingerprint", lambda path: "a" * 64)
    _, evidence = run_case(usb_fixture())
    print(
        json.dumps(
            {
                "status": evidence.status,
                "error": evidence.error,
                "process": evidence.to_dict()["process"],
                "queries": records,
            }
        )
    )
    assert records and all(r["process_limit"] == 1 for r in records)
    assert evidence.status == "OBSERVED"
    assert evidence.to_dict()["process"]["peak_processes"] == 1
    assert all(r["assigned"] <= 1 and r["listed"] <= 1 for r in records)
    assert evidence.process_cleanup_confirmed
    assert not owner.errors and not owner.handles and not owner.pins
