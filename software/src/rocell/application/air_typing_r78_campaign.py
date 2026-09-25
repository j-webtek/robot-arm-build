"""Four-leg A-side continuation: independent raw verifier and export-gated host."""
from __future__ import annotations

import hashlib
import time
from pathlib import Path

from .air_typing_r76_endpoint_rule import endpoint_joint_verified
from .air_typing_r78_source_rule import source_joint_verified
from .first_motion_contract import canonical
from .large_pose_relief_record import decode_large_pose_relief_record,_stable,_valid
from .wizard_diagnostic_coordinator import decode_diagnostic_json
from .wizard_diagnostic_export import WizardDiagnosticExporter,verify_export


SOURCE_GOALS=(1994,2076,2038,2598,2234,2040,2047)
SOURCE_POSITIONS=(1987,2082,2031,2600,2235,2041,2047)
TARGETS=(
    (2047,2075,2039,2600,2233,2040,2047),
    (2047,2093,2021,2618,2197,2040,2047),
    (2047,2105,2009,2630,2173,2040,2047),
    (2047,2075,2039,2600,2233,2040,2047),
)
PHASES=("A_return_travel","A_return_hover","A_virtual_downstroke","A_retract")


def assess_leg(raw:bytes,*,boot:str,leg:int,previous=None)->dict:
    if type(leg) is not int or not 1<=leg<=4 or type(raw) is not bytes or len(raw)!=1130:
        raise ValueError("Invalid A-side record")
    if raw[:10]!=b"RCAIRAB401" or raw[26]!=leg:
        raise ValueError("Wrong A-side domain or ordinal")
    target=TARGETS[leg-1]
    if int.from_bytes(raw[27:29],"big")!=target[4]:
        raise ValueError("Wrong wrist target")
    framed=b"RCP4WRST01"+raw[10:26]+(1980).to_bytes(2,"big")+raw[29:]
    record=decode_large_pose_relief_record(framed,profile="P4")
    if record["boot"]!=boot:raise ValueError("Wrong boot")
    before,pre,after=record["start"],record["prewrite"],record["endpoint"]
    _stable(before);_valid(pre);_stable(after,record["sent_us"])
    if not before[-1]["finished_us"]<pre["started_us"]<=pre["finished_us"]<=record["sent_us"]:
        raise ValueError("Prewrite chronology invalid")
    if record["sent_us"]-pre["finished_us"]>100000:raise ValueError("Prewrite expired")
    if leg==1:
        if previous is not None:raise ValueError("Unexpected prior leg")
        positions,goals=SOURCE_POSITIONS,SOURCE_GOALS
    else:
        if previous is None or previous.get("boot")!=boot or previous.get("leg")!=leg-1:
            raise ValueError("Missing verified previous leg")
        positions,goals=previous["final_positions"],previous["final_goals"]
        if before[0]["started_us"]<=previous["finished_us"]:
            raise ValueError("Replayed source samples")
    initial=before[-1]["joints"]
    for i,joint in enumerate(initial):
        if not source_joint_verified(previous_position=positions[i],expected_goal=goals[i],
                                     current_position=joint["position"],current_goal=joint["goal"]):
            raise ValueError("Source changed")
        if joint["torque"]!=1 or pre["joints"][i]["torque"]!=1:
            raise ValueError("Torque changed")
        if (pre["joints"][i]["goal"]!=joint["goal"] or
                abs(pre["joints"][i]["position"]-joint["position"])>1):
            raise ValueError("Prewrite changed")
    selected=[i for i in range(7) if target[i]!=initial[i]["goal"]]
    if not selected or max(abs(target[i]-initial[i]["goal"]) for i in selected)>80:
        raise ValueError("Unreviewed target step")
    for sample in after:
        for i,joint in enumerate(sample["joints"]):
            if joint["goal"]!=target[i] or joint["torque"]!=1:
                raise ValueError("Endpoint control differs")
            travel=joint["position"]-initial[i]["position"]
            if i in selected:
                direction=1 if target[i]>initial[i]["goal"] else -1
                if travel*direction<-1 or abs(travel)>92:
                    raise ValueError("Selected direction or travel invalid")
            elif abs(travel)>2:
                raise ValueError("Passive drift")
    final=after[-1]["joints"]
    for i in selected:
        if not endpoint_joint_verified(initial_goal=initial[i]["goal"],
                initial_position=initial[i]["position"],target_goal=target[i],
                final_position=final[i]["position"]):
            raise ValueError("Selected endpoint not verified")
    return dict(status="A_SIDE_LEG_ENDPOINT_VERIFIED",boot=boot,leg=leg,
                phase=PHASES[leg-1],target_goals=list(target),selected_joints=selected,
                final_positions=[joint["position"] for joint in final],
                final_goals=[joint["goal"] for joint in final],
                target_errors_counts=[final[i]["position"]-target[i] for i in range(7)],
                finished_us=after[-1]["finished_us"],record_sha256=hashlib.sha256(raw).hexdigest(),
                physical_clearance_verified=False,physical_accuracy_verified=False)


def assess_source_fault(raw:bytes,*,leg:int)->dict:
    doc=decode_diagnostic_json(raw,maximum=1200)
    if (type(doc) is not dict or doc.get("schema")!="rocell.air_source_fault.v1"
            or doc.get("leg")!=leg or type(doc.get("samples")) is not list
            or len(doc["samples"])!=3):
        raise ValueError("Invalid source-fault record")
    for sample in doc["samples"]:
        if (type(sample) is not dict or set(sample)!={"started_us","finished_us",
            "positions","goals","torque"} or
            any(type(sample[key]) is not list or len(sample[key])!=7
                for key in ("positions","goals","torque")) or
            any(type(value) is not int or not 0<=value<=4095
                for key in ("positions","goals") for value in sample[key]) or
            any(type(value) is not int or value not in (0,1) for value in sample["torque"]) or
            type(sample["started_us"]) is not int or type(sample["finished_us"]) is not int or
            not 0<sample["started_us"]<=sample["finished_us"]):
            raise ValueError("Invalid source-fault sample")
    return doc


class AirTypingASideHost:
    def __init__(self,transport,*,boot:str,export_root:Path,source_kind="unverified"):
        if source_kind not in ("simulation","controller_feedback","unverified"):
            raise ValueError("Unknown source kind")
        self.transport=transport;self.boot=boot;self.root=Path(export_root).resolve()
        self.source_kind=source_kind;self.used=False

    def run_once(self,*,clock=time.monotonic,pause=time.sleep):
        if self.used:raise ValueError("One-use A-side host consumed")
        self.used=True
        exporter=WizardDiagnosticExporter(self.root);exporter.prepare(create=True)
        rows,exports,leg,raw=[],[],0,b""
        last_status=None;source_fault=None
        def call(method,suffix,body=b""):
            return self.transport(method,"/rocell/air-type-last/"+suffix,body)
        try:
            if call("POST","start",b"AIR4")!=b"CAPTURING_START":
                raise ValueError("Start uncertain; no retry")
            for leg in range(1,5):
                raw=b"";deadline=clock()+14
                while True:
                    if clock()>=deadline:raise TimeoutError("Leg timeout")
                    status=call("GET","status")
                    last_status=status.decode("ascii","replace") if type(status) is bytes else repr(status)
                    if status==f"AWAITING_EXPORT|{leg}".encode():break
                    if status==f"SOURCE_POSE_REJECTED|{leg}".encode():
                        source_fault=assess_source_fault(call("GET","source-fault"),leg=leg)
                        raise ValueError("Source pose rejected before write")
                    if status not in [f"{state}|{leg}".encode() for state in
                                      ("CAPTURING_START","PREWRITE","CAPTURING_ENDPOINT")]:
                        raise ValueError("Unexpected A-side status")
                    pause(0.1)
                encoded=call("GET","record")
                if type(encoded) is not bytes or len(encoded)!=2260:
                    raise ValueError("Record framing invalid")
                raw=bytes.fromhex(encoded.decode("ascii"))
                row=assess_leg(raw,boot=self.boot,leg=leg,previous=rows[-1] if rows else None)
                row["source_kind"]=self.source_kind
                saved=exporter.export({"mode":"r78-air-typing-leg"},[],attachments={
                    "air-typing-last-record.hex.txt":raw.hex().encode(),
                    "air-typing-last-assessment.json":canonical(row)})
                if not verify_export(Path(saved["path"]))["valid"]:
                    raise ValueError("Leg export invalid")
                exports.append(saved["path"])
                if call("POST","receipt",f'{leg}:{row["record_sha256"]}'.encode())!=(
                        b"COMPLETE" if leg==4 else f"READY|{leg+1}".encode()):
                    raise ValueError("Receipt uncertain; no retry")
                rows.append(row)
                if leg<4 and call("POST","next",str(leg+1).encode())!=b"CAPTURING_START":
                    raise ValueError("Next-leg admission uncertain; no retry")
            return dict(status="A_SIDE_COMPLETE",rows=rows,exports=exports,
                        follow_on_movement_authorized=False)
        except Exception as error:
            saved=exporter.export({"mode":"r78-air-typing-fault"},[],attachments={
                "air-typing-last-fault.json":canonical(dict(boot=self.boot,leg=leg,
                    error_type=type(error).__name__,completed_legs=len(rows),
                    prior_exports=exports,source_kind=self.source_kind,
                    last_controller_status=last_status,source_fault=source_fault,
                    retry_allowed=False)),
                "air-typing-last-fault-record.hex.txt":raw.hex().encode()})
            if not verify_export(Path(saved["path"]))["valid"]:
                raise ValueError("Fault export invalid") from error
            raise ValueError("A-side campaign stopped; evidence: "+saved["path"]) from error
