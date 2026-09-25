"""Fixed, stdlib-only passive-arm IPC fixture. No serial or device APIs.

Only process execution is real. All device lifecycle fields are synthetic and
must stay labeled as such. This does not qualify the physical serial backend.
"""

import base64
import hashlib
import json
import sys
import time


def canonical(value):
    return json.dumps(
        value, sort_keys=True, separators=(",", ":"), ensure_ascii=True, allow_nan=False
    ).encode("ascii")


def main():
    raw = sys.stdin.buffer.read(64 * 1024 + 1)
    if not raw or len(raw) > 64 * 1024:
        return 3
    outer = json.loads(raw)
    body = {key: value for key, value in outer.items() if key != "request_sha256"}
    if hashlib.sha256(canonical(body)).hexdigest() != outer["request_sha256"]:
        return 4
    payload = outer["payload"]
    request = payload["request"]
    scenario = sys.argv[1]
    if (
        payload["scenario"] != scenario
        or request["mode"] != "rehearsal"
        or scenario
        not in {
            "nominal",
            "open-failed",
            "cleanup-unknown",
            "malformed",
            "wrong-binding",
            "stall",
        }
    ):
        return 5
    if scenario == "stall":
        time.sleep(20)
        return 6
    if scenario == "malformed":
        sys.stdout.write('{"broken":')
        return 0
    now = time.monotonic_ns()
    startup = b"SYNTHETIC passive startup observation\r\n"
    value = {
        "schema": "rocell.arm_passive_bench_result.v1",
        "request_sha256": hashlib.sha256(canonical(request)).hexdigest(),
        "attempt_id": request["attempt_id"],
        "launch_id": request["launch_id"],
        "origin": "SYNTHETIC_REHEARSAL",
        "runtime_sha256": request["references"]["runtime_sha256"],
        "open_state": "SUCCEEDED",
        "close_state": "CONFIRMED",
        "settings_verified": True,
        "observation_complete": True,
        "started_monotonic_ns": now,
        "observation_finished_monotonic_ns": now,
        "finished_monotonic_ns": now,
        "outbound_bytes": 0,
        "startup": {
            "base64": base64.b64encode(startup).decode("ascii"),
            "sha256": hashlib.sha256(startup).hexdigest(),
            "bytes": len(startup),
            "unretained_bytes": 0,
        },
        "errors": [],
    }
    if scenario == "open-failed":
        value.update(
            open_state="FAILED",
            close_state="NOT_REQUIRED",
            settings_verified=False,
            observation_complete=False,
            errors=["OPEN_FAILED"],
        )
        value["startup"] = {
            "base64": "",
            "sha256": hashlib.sha256(b"").hexdigest(),
            "bytes": 0,
            "unretained_bytes": 0,
        }
    if scenario == "cleanup-unknown":
        value.update(close_state="UNKNOWN", errors=["CLOSE_FAILED"])
    result = {
        "schema": "rocell.owned_passive_arm_fixture_result.v1",
        "request_sha256": (
            "f" * 64 if scenario == "wrong-binding" else outer["request_sha256"]
        ),
        "attempt_id": outer["attempt_id"],
        "physical_authority": False,
        "scenario": scenario,
        "passive_result": value,
    }
    sys.stdout.buffer.write(canonical(result))
    sys.stdout.buffer.flush()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
