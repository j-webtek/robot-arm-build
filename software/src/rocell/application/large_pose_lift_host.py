"""Authenticated one-shot P0 -> T1 coordinator with durable export."""
from __future__ import annotations
import hashlib
from pathlib import Path
import time

from .first_motion_contract import canonical
from .large_pose_lift_record import (RECORD_BYTES, assess_large_pose_lift_record)
from .wizard_diagnostic_export import WizardDiagnosticExporter, verify_export


class LargePoseLiftHost:
    def __init__(self, transport, *, export_root, boot):
        self.transport=transport;self.export_root=Path(export_root).resolve()
        self.boot=boot;self.used=False

    def run_once(self, *, deadline_seconds=14, clock=time.monotonic, pause=time.sleep):
        if self.used or type(deadline_seconds) not in (int, float) or not 0 < deadline_seconds <= 15:
            raise ValueError("One bounded T1 run only")
        self.used=True;end=clock()+deadline_seconds
        if self.transport("POST", "/rocell/large-pose-lift/start", b"T1") != b"CAPTURING_START":
            raise ValueError("T1 start not accepted")
        while True:
            if clock() >= end: raise TimeoutError("T1 outcome uncertain; no retry")
            status=self.transport("GET", "/rocell/large-pose-lift/status")
            if status==b"AWAITING_DURABLE_EXPORT|1":break
            if status not in (b"CAPTURING_START|0",b"PREWRITE|0",b"CAPTURING_ENDPOINT|1"):
                exporter=WizardDiagnosticExporter(self.export_root);exporter.prepare(create=True)
                saved=exporter.export({"mode":"large-pose-lift-terminal-fault"},[],attachments={
                    "large-pose-lift-terminal-status.txt":status,
                    "large-pose-lift-terminal-context.json":canonical({
                        "schema":"rocell.large_pose_lift_terminal_fault.v1","boot":self.boot,
                        "retry_allowed":False,"movement_may_have_occurred":status.endswith(b"|1")})})
                if not verify_export(Path(saved["path"]))["valid"]:
                    raise ValueError("T1 fault export failed; no retry")
                raise ValueError("T1 terminal fault exported: "+str(saved["path"]))
            pause(min(0.1,max(0,end-clock())))
        encoded=self.transport("GET", "/rocell/large-pose-lift/record")
        if type(encoded) is not bytes or len(encoded)!=2*RECORD_BYTES or encoded.lower()!=encoded:
            raise ValueError("Invalid T1 record framing")
        try:raw=bytes.fromhex(encoded.decode("ascii"))
        except (UnicodeError,ValueError) as error:raise ValueError("Invalid T1 record hex") from error
        assessment=assess_large_pose_lift_record(raw,expected_boot=self.boot)
        exporter=WizardDiagnosticExporter(self.export_root);exporter.prepare(create=True)
        saved=exporter.export({"mode":"large-pose-lift-live-result"},[],attachments={
            "large-pose-lift.hex.txt":encoded,
            "large-pose-lift-assessment.json":canonical(assessment)})
        folder=Path(saved["path"])
        if not verify_export(folder)["valid"]:raise ValueError("T1 export verification failed")
        receipt=self.transport("POST","/rocell/large-pose-lift/receipt",
                               hashlib.sha256(raw).hexdigest().encode("ascii"))
        if receipt!=b"LARGE_POSE_T1_RECORDED":
            raise ValueError("T1 receipt uncertain; do not continue")
        return {"export":str(folder),"assessment":assessment,"continuation_authorized":False}
