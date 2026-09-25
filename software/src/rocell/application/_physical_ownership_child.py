"""Fixed hardware-incapable ownership experiment child.

Only two hash-checked, stdlib-only production modules are loaded. Namespace
initializers, site packages, device providers and arbitrary imports/commands are
not accepted. The owned parent bounds pipes, lifetime, memory and descendants.
"""

from __future__ import annotations

import hashlib
import importlib.util
import json
import os
from pathlib import Path
import sys
import time
import types


def canonical(value: object) -> bytes:
    return json.dumps(
        value, sort_keys=True, separators=(",", ":"), ensure_ascii=True
    ).encode("ascii")


def require(value: bool) -> None:
    if not value:
        raise ValueError("FIXED_OWNERSHIP_CHILD_CONTRACT")


def main() -> None:
    require(os.name == "nt" and len(sys.argv) == 1)
    raw = sys.stdin.buffer.readline(16385)
    request = json.loads(raw)
    require(raw == canonical(request) + b"\n")
    require(
        set(request)
        == {
            "schema",
            "source_sha256",
            "module_sha256s",
            "qualification",
            "phase",
            "deadline_ns",
            "directory",
        }
    )
    require(request["schema"] == "rocell.ownership_child_request.v1")
    require(request["phase"] in ("clean", "crash"))
    require(
        type(request["deadline_ns"]) is int
        and time.monotonic_ns()
        < request["deadline_ns"]
        <= time.monotonic_ns() + 30_000_000_000
    )
    names = ("physical_onboarding_durability", "physical_onboarding_leases")
    require(set(request["module_sha256s"]) == set(names))
    for namespace in ("rocell", "rocell.application"):
        module = types.ModuleType(namespace)
        module.__path__ = []
        sys.modules[namespace] = module
    for name in names:
        path = Path(__file__).parent / (name + ".py")
        require(0 < path.stat().st_size <= 512 * 1024)
        payload = path.read_bytes()
        require(hashlib.sha256(payload).hexdigest() == request["module_sha256s"][name])
        qualified = "rocell.application." + name
        spec = importlib.util.spec_from_file_location(qualified, path)
        if spec is None:
            raise ValueError("FIXED_MODULE_SPEC")
        module = importlib.util.module_from_spec(spec)
        sys.modules[qualified] = module
        exec(compile(payload, str(path), "exec"), module.__dict__)
    from rocell.application.physical_onboarding_durability import (
        DurabilityQualificationReport,
    )
    from rocell.application.physical_onboarding_leases import (
        LeaseLevel,
        LeaseSpec,
        OnboardingLeaseManager,
    )

    report = DurabilityQualificationReport.from_dict(request["qualification"])
    manager = OnboardingLeaseManager(
        Path(request["directory"]),
        request["source_sha256"],
        OnboardingLeaseManager.new_launch_nonce(),
        report,
    )
    specs = tuple(
        LeaseSpec(level, request["phase"] + "-" + level.name.lower())
        for level in LeaseLevel
    )
    held = manager.acquire(
        specs,
        operation="OWNERSHIP_" + request["phase"].upper(),
        expected_challenge_sha256=request["source_sha256"],
        challenge_callback=lambda: request["source_sha256"],
        effectful=True,
    )
    ready = {
        "schema": "rocell.ownership_child_ready.v1",
        "request_sha256": hashlib.sha256(raw[:-1]).hexdigest(),
        "pid": os.getpid(),
        "owners": [owner.to_dict() for owner in held.owners],
    }
    sys.stdout.buffer.write(canonical(ready) + b"\n")
    sys.stdout.buffer.flush()
    command = sys.stdin.buffer.readline(65)
    require(
        command
        == (b"CLEAN_RELEASE\n" if request["phase"] == "clean" else b"EXIT_HELD\n")
    )
    require(
        sys.stdin.buffer.read(1) == b"" and time.monotonic_ns() < request["deadline_ns"]
    )
    if request["phase"] == "crash":
        # Deliberate process exit, not an in-process unlock mock. ACTIVE owner
        # records survive while the kernel releases all owned process handles.
        os._exit(73)
    held.close()
    released = [manager.prior_owner(spec) for spec in specs]
    require(all(owner is not None for owner in released))
    sys.stdout.buffer.write(
        canonical(
            {
                "schema": "rocell.ownership_child_released.v1",
                "owners": [owner.to_dict() for owner in released if owner is not None],
            }
        )
        + b"\n"
    )
    sys.stdout.buffer.flush()


if __name__ == "__main__":
    try:
        main()
    except BaseException as error:
        sys.stderr.write(type(error).__name__ + ": " + str(error)[:512] + "\n")
        raise SystemExit(2)
