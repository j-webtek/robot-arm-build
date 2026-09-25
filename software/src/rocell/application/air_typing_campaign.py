"""Independent raw-record verifier and export-gated host for fixed air typing."""
from __future__ import annotations

import hashlib
import time
from pathlib import Path

from .first_motion_contract import canonical
from .large_pose_relief_record import decode_large_pose_relief_record, _stable, _valid
from .local_air_typing_recipe import SOURCE_GOALS, SOURCE_POSITIONS
from .wizard_diagnostic_export import WizardDiagnosticExporter, verify_export


# Must match the separately reviewed native recipe, not caller-supplied coordinates.
TARGETS = (
    (2047,2176,1938,2686,2046,2040,2047),
    (2047,2139,1975,2658,2110,2040,2047),
    (2047,2105,2009,2630,2173,2040,2047),
    (2047,2075,2039,2600,2233,2040,2047),
    (2047,2093,2021,2618,2197,2040,2047),
    (2047,2105,2009,2630,2173,2040,2047),
    (2047,2075,2039,2600,2233,2040,2047),
    (1994,2076,2038,2598,2234,2040,2047),
    (1941,2080,2034,2591,2236,2040,2047),
    (1941,2098,2016,2609,2201,2040,2047),
    (1941,2111,2003,2621,2176,2040,2047),
    (1941,2080,2034,2591,2236,2040,2047),
    (1994,2076,2038,2598,2234,2040,2047),
    (2047,2075,2039,2600,2233,2040,2047),
    (2047,2093,2021,2618,2197,2040,2047),
    (2047,2105,2009,2630,2173,2040,2047),
    (2047,2075,2039,2600,2233,2040,2047),
)
PHASES = (
    "approach", "approach", "approach", "travel", "hover",
    "virtual_downstroke", "retract", "lateral_travel", "travel", "hover",
    "virtual_downstroke", "retract", "lateral_travel", "travel", "hover",
    "virtual_downstroke", "retract",
)
KEYS = (None,None,None,"A","A","A","A",None,"B","B","B","B",None,"A","A","A","A")


def assess_leg(raw, *, boot, leg, previous=None):
    if type(leg) is not int or not 1 <= leg <= len(TARGETS):
        raise ValueError("Invalid leg ordinal")
    if type(raw) is not bytes or len(raw) != 1130 or raw[:10] != b"RCAIRABA01" or raw[26] != leg:
        raise ValueError("Wrong campaign record or leg")
    target = TARGETS[leg - 1]
    if int.from_bytes(raw[27:29], "big") != target[4]:
        raise ValueError("Wrong fixed wrist target in record")
    framed = b"RCP4WRST01" + raw[10:26] + (1980).to_bytes(2, "big") + raw[29:]
    record = decode_large_pose_relief_record(framed, profile="P4")
    if record["boot"] != boot:
        raise ValueError("Wrong boot")
    before, pre, after = record["start"], record["prewrite"], record["endpoint"]
    _stable(before)
    _valid(pre)
    _stable(after, record["sent_us"])
    if not before[-1]["finished_us"] < pre["started_us"] <= pre["finished_us"] <= record["sent_us"]:
        raise ValueError("Prewrite chronology invalid")
    if record["sent_us"] - pre["finished_us"] > 100000:
        raise ValueError("Prewrite expired")
    if leg == 1:
        if previous is not None:
            raise ValueError("Unexpected preceding result")
        expected_positions, expected_goals, tolerance = SOURCE_POSITIONS, SOURCE_GOALS, 3
    else:
        if previous is None or previous.get("boot") != boot or previous.get("leg") != leg - 1:
            raise ValueError("Missing preceding verified leg")
        expected_positions, expected_goals, tolerance = previous["final_positions"], previous["final_goals"], 1
        if before[0]["started_us"] <= previous["finished_us"]:
            raise ValueError("Replayed preceding samples")
    initial = before[-1]["joints"]
    for i, joint in enumerate(initial):
        if joint["goal"] != expected_goals[i] or abs(joint["position"] - expected_positions[i]) > tolerance:
            raise ValueError("Source changed")
        if pre["joints"][i]["goal"] != joint["goal"] or abs(pre["joints"][i]["position"] - joint["position"]) > 1:
            raise ValueError("Prewrite changed")
    selected = [i for i in range(7) if target[i] != initial[i]["goal"]]
    if not selected or max(abs(target[i] - initial[i]["goal"]) for i in selected) > 80:
        raise ValueError("Target step outside fixed bounds")
    for sample in after:
        for i, joint in enumerate(sample["joints"]):
            if joint["goal"] != target[i]:
                raise ValueError("Reported goal differs from fixed target")
            travel = joint["position"] - initial[i]["position"]
            if i in selected:
                direction = 1 if target[i] > initial[i]["goal"] else -1
                if travel * direction < -1 or abs(travel) > 92:
                    raise ValueError("Selected joint direction or travel invalid")
            elif abs(travel) > 2:
                raise ValueError("Unselected joint drift")
    final = after[-1]["joints"]
    for i in selected:
        command = target[i] - initial[i]["goal"]
        travel = final[i]["position"] - initial[i]["position"]
        if (abs(command) >= 4 and travel * (1 if command > 0 else -1) < 2) or abs(final[i]["position"] - target[i]) > 12:
            raise ValueError("Selected endpoint not verified")
    return dict(status="LEG_ENDPOINT_VERIFIED", boot=boot, leg=leg,
                key=KEYS[leg - 1], phase=PHASES[leg - 1],
                target_goals=list(target), selected_joints=selected,
                final_positions=[joint["position"] for joint in final],
                final_goals=[joint["goal"] for joint in final],
                target_errors_counts=[final[i]["position"] - target[i] for i in range(7)],
                finished_us=after[-1]["finished_us"],
                record_sha256=hashlib.sha256(raw).hexdigest(),
                physical_clearance_verified=False, physical_accuracy_verified=False)


class AirTypingHost:
    def __init__(self, transport, *, boot, export_root, source_kind="unverified"):
        if source_kind not in ("simulation", "unverified", "controller_feedback"):
            raise ValueError("Unknown source kind")
        self.transport = transport
        self.boot = boot
        self.root = Path(export_root).resolve()
        self.source_kind = source_kind
        self.used = False

    def run_once(self, *, clock=time.monotonic, pause=time.sleep, maximum_legs=len(TARGETS)):
        if self.used or type(maximum_legs) is not int or not 1 <= maximum_legs <= len(TARGETS):
            raise ValueError("One fixed finite campaign only")
        self.used = True
        exporter = WizardDiagnosticExporter(self.root)
        exporter.prepare(create=True)
        rows, exports, leg, raw = [], [], 0, b""
        def call(method, suffix, body=b""):
            return self.transport(method, "/rocell/air-type/" + suffix, body)
        try:
            if call("POST", "start", b"AIR17") != b"CAPTURING_START":
                raise ValueError("Start uncertain; no retry")
            for leg in range(1, maximum_legs + 1):
                raw = b""
                deadline = clock() + 14
                while True:
                    if clock() >= deadline:
                        raise TimeoutError("Leg timeout")
                    status = call("GET", "status")
                    if status == f"AWAITING_EXPORT|{leg}".encode():
                        break
                    if status not in [f"{state}|{leg}".encode() for state in
                                      ("CAPTURING_START", "PREWRITE", "CAPTURING_ENDPOINT")]:
                        raise ValueError("Unexpected campaign status")
                    pause(0.1)
                encoded = call("GET", "record")
                if type(encoded) is not bytes or len(encoded) != 2260:
                    raise ValueError("Record framing invalid")
                raw = bytes.fromhex(encoded.decode("ascii"))
                row = assess_leg(raw, boot=self.boot, leg=leg, previous=rows[-1] if rows else None)
                row["source_kind"] = self.source_kind
                saved = exporter.export({"mode": "air-typing-leg"}, [], attachments={
                    "air-typing-record.hex.txt": raw.hex().encode(),
                    "air-typing-assessment.json": canonical(row)})
                if not verify_export(Path(saved["path"]))["valid"]:
                    raise ValueError("Leg export verification failed")
                exports.append(saved["path"])
                receipt = f'{leg}:{row["record_sha256"]}'.encode()
                expected = b"COMPLETE" if leg == len(TARGETS) else f"READY|{leg + 1}".encode()
                if call("POST", "receipt", receipt) != expected:
                    raise ValueError("Receipt uncertain; no retry")
                rows.append(row)
                if leg < maximum_legs and leg < len(TARGETS):
                    if call("POST", "next", str(leg + 1).encode()) != b"CAPTURING_START":
                        raise ValueError("Next-leg admission uncertain; no retry")
            return dict(status="CAMPAIGN_COMPLETE" if maximum_legs == len(TARGETS) else "CAMPAIGN_PAUSED_AFTER_BOUND",
                        rows=rows, exports=exports, continuation_authorized=False)
        except Exception as error:
            saved = exporter.export({"mode": "air-typing-fault"}, [], attachments={
                "air-typing-fault.json": canonical(dict(boot=self.boot, leg=leg,
                    error_type=type(error).__name__, completed_legs=len(rows),
                    prior_exports=exports, source_kind=self.source_kind, retry_allowed=False)),
                "air-typing-fault-record.hex.txt": raw.hex().encode()})
            if not verify_export(Path(saved["path"]))["valid"]:
                raise ValueError("Fault export failed; no continuation") from error
            raise ValueError("Campaign stopped; evidence: " + saved["path"]) from error
