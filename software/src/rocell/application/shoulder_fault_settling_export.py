"""Validate and export fault-linked observations before signing read progression.

This has no transport, restart or motion API. The parent fault remains a failure.
"""
import hashlib
from .shoulder_export_receipt import export_and_sign
from .wizard_diagnostic_coordinator import decode_diagnostic_json


class FaultSettlingExport:
    def __init__(self, original, *, boot, parent_command):
        doc = decode_diagnostic_json(original, maximum=4095)
        if (type(doc) is not dict or doc.get('schema') != 'rocell.shoulder_hold_event.v1'
                or doc.get('boot_id') != boot or doc.get('command_id') != parent_command
                or doc.get('event') != 'STATE_MISMATCH'
                or type(doc.get('scan_finished_us')) is not int
                or doc['scan_finished_us'] <= 0):
            raise ValueError('Original failing scan required')
        self.boot = boot
        self.parent = parent_command
        self.command = 'settle-' + parent_command
        self.digest = hashlib.sha256(original).hexdigest()
        self.count = 0
        self.finished = doc['scan_finished_us']
        self.reference = None
        self.failed = False
        self.stable_count = 0
        self.anchor = None

    def export(self, root, raw, *, key):
        if self.failed:
            raise ValueError('Capture export already failed')
        try:
            return self._export(root, raw, key=key)
        except (ValueError, TypeError, KeyError, OSError):
            self.failed = True
            raise

    def _export(self, root, raw, *, key):
        doc = decode_diagnostic_json(raw, maximum=4095)
        if (type(doc) is not dict or self.count >= 12 or doc.get('event') != 'FAULT_SETTLING_SAMPLE'
                or doc.get('parent_command_id') != self.parent
                or doc.get('original_fault_sha256') != self.digest
                or doc.get('parent_fault_latched') is not True
                or doc.get('movement_authorized') is not False
                or doc.get('physical_accuracy_verified') is not False):
            raise ValueError('Fault capture binding mismatch')
        start, finish = doc['scan_started_us'], doc['scan_finished_us']
        if (type(start) is not int or type(finish) is not int or start <= self.finished
                or not 0 <= finish-start <= 300_000
                or (self.count and start-self.finished < 500_000)):
            raise ValueError('Capture scan timing invalid')
        rows = doc['joints']
        if type(rows) is not list or len(rows) != 7:
            raise ValueError('Seven joint rows required')
        for sid, row in enumerate(rows, 11):
            if (type(row) is not list or len(row) != 5 or row[0] != sid
                    or any(type(x) is not int for x in row[:4])
                    or not 0 <= row[1] <= 4095 or not 0 <= row[2] <= 4095
                    or row[3] not in (0, 1) or type(row[4]) is not str or len(row[4]) != 30):
                raise ValueError('Invalid joint row')
            feedback = bytes.fromhex(row[4])
            if len(feedback) != 15 or int.from_bytes(feedback[:2], 'little') != row[1]:
                raise ValueError('Raw feedback position mismatch')
        reference = [(r[2], r[3]) for r in rows]
        if self.reference is not None and reference != self.reference:
            raise ValueError('Target or torque changed; retain as failure without receipt')
        result = export_and_sign(root, raw, key=key, boot=self.boot,
                                 command=self.command, sequence=self.count)
        positions = [r[1] for r in rows]
        still = all(not any(bytes.fromhex(r[4])[i] for i in (2, 3, 10)) for r in rows)
        if not still:
            self.stable_count = 0
        elif self.stable_count and all(abs(a-b) <= 1 for a,b in zip(positions,self.anchor)):
            self.stable_count += 1
        else:
            self.stable_count = 1
            self.anchor = positions
        self.count += 1
        self.finished = finish
        self.reference = reference
        return result
