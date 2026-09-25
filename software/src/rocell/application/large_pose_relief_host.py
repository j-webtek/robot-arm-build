"""Authenticated one-shot T1 -> P1 coordinator with durable export."""
from __future__ import annotations
import hashlib
from pathlib import Path
import time

from .first_motion_contract import canonical
from .large_pose_relief_record import (record_bytes, assess_large_pose_relief_record, reviewed_profile)
from .wizard_diagnostic_export import WizardDiagnosticExporter, verify_export


class LargePoseReliefHost:
    def __init__(self, transport, *, export_root, boot, profile='P1'):
        reviewed_profile(profile)
        self.profile=profile
        self.transport=transport;self.export_root=Path(export_root).resolve()
        self.boot=boot;self.used=False

    def run_once(self, *, deadline_seconds=14, clock=time.monotonic, pause=time.sleep):
        if self.used or type(deadline_seconds) not in (int, float) or not 0 < deadline_seconds <= 15:
            raise ValueError("One bounded P1 run only")
        self.used=True;end=clock()+deadline_seconds
        if self.transport("POST", "/rocell/large-pose-relief/start", self.profile.encode('ascii')) != b"CAPTURING_START":
            raise ValueError("P1 start not accepted")
        while True:
            if clock() >= end: raise TimeoutError("P1 outcome uncertain; no retry")
            status=self.transport("GET", "/rocell/large-pose-relief/status")
            if status==b"AWAITING_DURABLE_EXPORT|1":break
            if status not in (b"CAPTURING_START|0",b"PREWRITE|0",b"CAPTURING_ENDPOINT|1"):
                exporter=WizardDiagnosticExporter(self.export_root);exporter.prepare(create=True)
                saved=exporter.export({"mode":"large-pose-relief-terminal-fault"},[],attachments={
                    "large-pose-relief-terminal-status.txt":status,
                    "large-pose-relief-terminal-context.json":canonical({
                        "schema":"rocell.large_pose_relief_terminal_fault.v1","boot":self.boot,"profile":self.profile,
                        "retry_allowed":False,"movement_may_have_occurred":status.endswith(b"|1")})})
                if not verify_export(Path(saved["path"]))["valid"]:
                    raise ValueError("P1 fault export failed; no retry")
                raise ValueError("P1 terminal fault exported: "+str(saved["path"]))
            pause(min(0.1,max(0,end-clock())))
        encoded=self.transport("GET", "/rocell/large-pose-relief/record")
        if type(encoded) is not bytes or len(encoded)!=2*record_bytes(self.profile) or encoded.lower()!=encoded:
            raise ValueError("Invalid P1 record framing")
        try:raw=bytes.fromhex(encoded.decode("ascii"))
        except (UnicodeError,ValueError) as error:raise ValueError("Invalid P1 record hex") from error
        assessment=assess_large_pose_relief_record(raw,expected_boot=self.boot,profile=self.profile)
        exporter=WizardDiagnosticExporter(self.export_root);exporter.prepare(create=True)
        saved=exporter.export({"mode":"large-pose-relief-live-result"},[],attachments={
            "large-pose-relief.hex.txt":encoded,
            "large-pose-relief-assessment.json":canonical(assessment)})
        folder=Path(saved["path"])
        if not verify_export(folder)["valid"]:raise ValueError("P1 export verification failed")
        receipt=self.transport("POST","/rocell/large-pose-relief/receipt",
                               hashlib.sha256(raw).hexdigest().encode("ascii"))
        if receipt!=('LARGE_POSE_'+self.profile+'_RECORDED').encode('ascii'):
            raise ValueError("P1 receipt uncertain; do not continue")
        return {"export":str(folder),"assessment":assessment,"continuation_authorized":False}
