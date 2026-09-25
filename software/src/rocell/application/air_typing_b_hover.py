"""Independent one-leg r76 B-hover verifier and export-gated host."""
from __future__ import annotations

import hashlib
import time
from pathlib import Path

from .air_typing_continuation_preview import CAPTURED_SOURCE_GOALS, CAPTURED_SOURCE_POSITIONS
from .air_typing_r76_endpoint_rule import endpoint_joint_verified
from .first_motion_contract import canonical
from .large_pose_relief_record import decode_large_pose_relief_record, _stable, _valid
from .wizard_diagnostic_export import WizardDiagnosticExporter, verify_export


TARGET = (1941, 2098, 2016, 2609, 2201, 2040, 2047)
DOMAIN = b"RCAIRAB201"


def assess_record(raw: bytes, *, boot: str) -> dict:
    if type(raw) is not bytes or len(raw) != 1130 or raw[:10] != DOMAIN or raw[26] != 1:
        raise ValueError("Wrong B-hover record")
    if int.from_bytes(raw[27:29], "big") != TARGET[4]:
        raise ValueError("Wrong wrist target")
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
    initial = before[-1]["joints"]
    for i, joint in enumerate(initial):
        if (joint["goal"] != CAPTURED_SOURCE_GOALS[i]
                or abs(joint["position"] - CAPTURED_SOURCE_POSITIONS[i]) > 3):
            raise ValueError("Fresh source differs from captured leg-nine pose")
        if (pre["joints"][i]["goal"] != joint["goal"]
                or abs(pre["joints"][i]["position"] - joint["position"]) > 1):
            raise ValueError("Prewrite changed")
    selected = [i for i in range(7) if TARGET[i] != initial[i]["goal"]]
    if selected != [1, 2, 3, 4]:
        raise ValueError("Unexpected selected joints")
    for sample in after:
        for i, joint in enumerate(sample["joints"]):
            if joint["goal"] != TARGET[i]:
                raise ValueError("Goal readback differs")
            travel = joint["position"] - initial[i]["position"]
            if i in selected:
                direction = 1 if TARGET[i] > initial[i]["goal"] else -1
                if travel * direction < -1 or abs(travel) > 92:
                    raise ValueError("Direction or travel invalid")
            elif abs(travel) > 2:
                raise ValueError("Passive joint drift")
    final = after[-1]["joints"]
    for i in selected:
        if not endpoint_joint_verified(initial_goal=initial[i]["goal"],
                initial_position=initial[i]["position"], target_goal=TARGET[i],
                final_position=final[i]["position"]):
            raise ValueError("Selected endpoint not verified")
    return dict(status="B_HOVER_JOINT_ENDPOINT_VERIFIED", boot=boot,
                target_goals=list(TARGET), selected_joints=selected,
                final_positions=[joint["position"] for joint in final],
                final_goals=[joint["goal"] for joint in final],
                target_errors_counts=[final[i]["position"]-TARGET[i] for i in range(7)],
                finished_us=after[-1]["finished_us"],
                record_sha256=hashlib.sha256(raw).hexdigest(),
                physical_clearance_verified=False, physical_accuracy_verified=False)


class BHoverHost:
    def __init__(self, transport, *, boot: str, export_root: Path, source_kind="unverified"):
        if source_kind not in ("simulation", "controller_feedback", "unverified"):
            raise ValueError("Unknown source kind")
        self.transport = transport
        self.boot = boot
        self.root = Path(export_root).resolve()
        self.source_kind = source_kind
        self.used = False

    def run_once(self, *, clock=time.monotonic, pause=time.sleep):
        if self.used:
            raise ValueError("One-use B-hover host consumed")
        self.used = True
        exporter = WizardDiagnosticExporter(self.root)
        exporter.prepare(create=True)
        raw = b""
        def call(method, suffix, body=b""):
            return self.transport(method, "/rocell/air-type-b-hover/" + suffix, body)
        try:
            if call("POST", "start", b"AIRB1") != b"CAPTURING_START":
                raise ValueError("Start uncertain; no retry")
            deadline = clock() + 14
            while True:
                if clock() >= deadline:
                    raise TimeoutError("B-hover deadline")
                status = call("GET", "status")
                if status == b"AWAITING_EXPORT|1":
                    break
                if status not in (b"CAPTURING_START|1", b"PREWRITE|1",
                                  b"CAPTURING_ENDPOINT|1"):
                    raise ValueError("Unexpected B-hover status")
                pause(0.1)
            encoded = call("GET", "record")
            if type(encoded) is not bytes or len(encoded) != 2260:
                raise ValueError("Record framing invalid")
            raw = bytes.fromhex(encoded.decode("ascii"))
            row = assess_record(raw, boot=self.boot)
            row["source_kind"] = self.source_kind
            saved = exporter.export({"mode": "r76-b-hover-endpoint"}, [], attachments={
                "b-hover-record.hex.txt": raw.hex().encode(),
                "b-hover-assessment.json": canonical(row)})
            if not verify_export(Path(saved["path"]))["valid"]:
                raise ValueError("Endpoint export invalid")
            receipt = f'1:{row["record_sha256"]}'.encode()
            if call("POST", "receipt", receipt) != b"COMPLETE":
                raise ValueError("Receipt uncertain; no retry")
            return dict(status="B_HOVER_COMPLETE", row=row, export=saved["path"],
                        follow_on_movement_authorized=False)
        except Exception as error:
            saved = exporter.export({"mode": "r76-b-hover-fault"}, [], attachments={
                "b-hover-fault.json": canonical(dict(boot=self.boot,
                    error_type=type(error).__name__, source_kind=self.source_kind,
                    retry_allowed=False, movement_outcome_uncertain=True)),
                "b-hover-fault-record.hex.txt": raw.hex().encode()})
            if not verify_export(Path(saved["path"]))["valid"]:
                raise ValueError("Fault export failed") from error
            raise ValueError("B-hover stopped; evidence: " + saved["path"]) from error
