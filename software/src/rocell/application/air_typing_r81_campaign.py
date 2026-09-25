"""Eight-leg, one-use isolated-elbow direction comparison."""
from __future__ import annotations

import hashlib
import time
from pathlib import Path

from .air_typing_elbow_direction_recipe import PHASES, SOURCE_GOALS, SOURCE_POSITIONS, TARGETS
from .air_typing_r76_endpoint_rule import endpoint_joint_verified
from .air_typing_r78_campaign import assess_source_fault
from .air_typing_r78_source_rule import source_joint_verified
from .first_motion_contract import canonical
from .large_pose_relief_record import _stable, _valid, decode_large_pose_relief_record
from .wizard_diagnostic_export import WizardDiagnosticExporter, verify_export


def _assess_leg(raw: bytes, *, boot: str, leg: int, previous,
                targets, phases, source_positions, source_goals, domain, status,
                max_step=30,max_travel=42) -> dict:
    if type(leg) is not int or not 1 <= leg <= len(targets) or type(raw) is not bytes or len(raw) != 1130:
        raise ValueError("Invalid elbow-direction record")
    if raw[:10] != domain or raw[26] != leg:
        raise ValueError("Wrong elbow-direction domain or ordinal")
    target = targets[leg-1]
    if int.from_bytes(raw[27:29], "big") != target[4]:
        raise ValueError("Wrong elbow-direction target")
    framed = b"RCP4WRST01" + raw[10:26] + (1980).to_bytes(2, "big") + raw[29:]
    record = decode_large_pose_relief_record(framed, profile="P4")
    if record["boot"] != boot:
        raise ValueError("Wrong boot")
    before, pre, after = record["start"], record["prewrite"], record["endpoint"]
    _stable(before); _valid(pre); _stable(after, record["sent_us"])
    if not before[-1]["finished_us"] < pre["started_us"] <= pre["finished_us"] <= record["sent_us"]:
        raise ValueError("Prewrite chronology invalid")
    if record["sent_us"] - pre["finished_us"] > 100000:
        raise ValueError("Prewrite expired")
    if leg == 1:
        if previous is not None:
            raise ValueError("Unexpected prior leg")
        positions, goals = source_positions, source_goals
    else:
        if previous is None or previous.get("boot") != boot or previous.get("leg") != leg-1:
            raise ValueError("Missing verified previous leg")
        positions, goals = previous["final_positions"], previous["final_goals"]
        if before[0]["started_us"] <= previous["finished_us"]:
            raise ValueError("Replayed source samples")
    initial = before[-1]["joints"]
    for i, joint in enumerate(initial):
        if (not source_joint_verified(previous_position=positions[i], expected_goal=goals[i],
                                      current_position=joint["position"], current_goal=joint["goal"])
                or joint["torque"] != 1 or pre["joints"][i]["torque"] != 1):
            raise ValueError("Source changed")
        if (pre["joints"][i]["goal"] != joint["goal"] or
                abs(pre["joints"][i]["position"] - joint["position"]) > 1):
            raise ValueError("Prewrite changed")
    selected = [i for i in range(7) if target[i] != initial[i]["goal"]]
    if selected != [3] or not 1 <= abs(target[3]-initial[3]["goal"]) <= max_step:
        raise ValueError("Unreviewed isolated-elbow step")
    for sample in after:
        for i, joint in enumerate(sample["joints"]):
            if joint["goal"] != target[i] or joint["torque"] != 1:
                raise ValueError("Endpoint control differs")
            travel = joint["position"] - initial[i]["position"]
            if i == 3:
                direction = 1 if target[3] > initial[3]["goal"] else -1
                if travel*direction < -1 or abs(travel) > max_travel:
                    raise ValueError("Elbow direction or travel invalid")
            elif abs(travel) > 2:
                raise ValueError("Passive drift")
    final = after[-1]["joints"]
    if not endpoint_joint_verified(initial_goal=initial[3]["goal"],
            initial_position=initial[3]["position"], target_goal=target[3],
            final_position=final[3]["position"]):
        raise ValueError("Elbow endpoint not verified")
    return dict(status=status, boot=boot, leg=leg,
                phase=phases[leg-1], target_goals=list(target), selected_joints=selected,
                final_positions=[joint["position"] for joint in final],
                final_goals=[joint["goal"] for joint in final],
                target_errors_counts=[final[i]["position"]-target[i] for i in range(7)],
                finished_us=after[-1]["finished_us"], record_sha256=hashlib.sha256(raw).hexdigest(),
                physical_clearance_verified=False, physical_accuracy_verified=False)


def assess_leg(raw: bytes, *, boot: str, leg: int, previous=None) -> dict:
    return _assess_leg(raw,boot=boot,leg=leg,previous=previous,
        targets=TARGETS,phases=PHASES,source_positions=SOURCE_POSITIONS,
        source_goals=SOURCE_GOALS,domain=b"RCAIRAB701",
        status="ELBOW_DIRECTION_LEG_ENDPOINT_VERIFIED")


class AirTypingElbowDirectionHost:
    route="/rocell/air-elbow-direction/"
    selector=b"AIRE8"
    leg_count=8
    mode_prefix="r81-elbow-direction"
    attachment_prefix="elbow-direction"
    completion_status="ELBOW_DIRECTION_COMPLETE"
    assess=staticmethod(assess_leg)
    def __init__(self, transport, *, boot: str, export_root: Path, source_kind="unverified"):
        if source_kind not in ("simulation", "controller_feedback", "unverified"):
            raise ValueError("Unknown source kind")
        self.transport = transport; self.boot = boot; self.root = Path(export_root).resolve()
        self.source_kind = source_kind; self.used = False

    def run_once(self, *, clock=time.monotonic, pause=time.sleep):
        if self.used:
            raise ValueError("One-use elbow-direction host consumed")
        self.used = True
        exporter = WizardDiagnosticExporter(self.root); exporter.prepare(create=True)
        rows, exports, leg, raw = [], [], 0, b""
        last_status = None; source_fault = None
        def call(method, suffix, body=b""):
            return self.transport(method, self.route+suffix, body)
        try:
            if call("POST", "start", self.selector) != b"CAPTURING_START":
                raise ValueError("Start uncertain; no retry")
            for leg in range(1, self.leg_count+1):
                raw = b""; deadline = clock()+14
                while True:
                    if clock() >= deadline:
                        raise TimeoutError("Leg timeout")
                    status = call("GET", "status")
                    last_status = status.decode("ascii", "replace") if type(status) is bytes else repr(status)
                    if status == f"AWAITING_EXPORT|{leg}".encode():
                        break
                    if status == f"SOURCE_POSE_REJECTED|{leg}".encode():
                        source_fault = assess_source_fault(call("GET", "source-fault"), leg=leg)
                        raise ValueError("Source pose rejected before write")
                    if status not in [f"{state}|{leg}".encode() for state in
                                      ("CAPTURING_START", "PREWRITE", "CAPTURING_ENDPOINT")]:
                        raise ValueError("Unexpected elbow-direction status")
                    pause(0.1)
                encoded = call("GET", "record")
                if type(encoded) is not bytes or len(encoded) != 2260:
                    raise ValueError("Record framing invalid")
                raw = bytes.fromhex(encoded.decode("ascii"))
                row = self.assess(raw, boot=self.boot, leg=leg,
                                  previous=rows[-1] if rows else None)
                row["source_kind"] = self.source_kind
                saved = exporter.export({"mode":self.mode_prefix+"-leg"}, [], attachments={
                    self.attachment_prefix+"-record.hex.txt":raw.hex().encode(),
                    self.attachment_prefix+"-assessment.json":canonical(row)})
                if not verify_export(Path(saved["path"]))["valid"]:
                    raise ValueError("Leg export invalid")
                exports.append(saved["path"])
                expected = b"COMPLETE" if leg == self.leg_count else f"READY|{leg+1}".encode()
                if call("POST", "receipt", f'{leg}:{row["record_sha256"]}'.encode()) != expected:
                    raise ValueError("Receipt uncertain; no retry")
                rows.append(row)
                if leg < self.leg_count and call("POST", "next", str(leg+1).encode()) != b"CAPTURING_START":
                    raise ValueError("Next-leg admission uncertain; no retry")
            return dict(status=self.completion_status, rows=rows, exports=exports,
                        follow_on_movement_authorized=False)
        except Exception as error:
            saved = exporter.export({"mode":self.mode_prefix+"-fault"}, [], attachments={
                self.attachment_prefix+"-fault.json":canonical(dict(boot=self.boot, leg=leg,
                    error_type=type(error).__name__, completed_legs=len(rows), prior_exports=exports,
                    source_kind=self.source_kind, last_controller_status=last_status,
                    source_fault=source_fault, retry_allowed=False)),
                self.attachment_prefix+"-fault-record.hex.txt":raw.hex().encode()})
            if not verify_export(Path(saved["path"]))["valid"]:
                raise ValueError("Fault export invalid") from error
            raise ValueError("Elbow-direction campaign stopped; evidence: "+saved["path"]) from error
