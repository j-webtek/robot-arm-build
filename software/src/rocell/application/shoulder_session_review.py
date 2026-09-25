"""Independent ordered evidence checks before acknowledging shoulder records."""
import re
from .wizard_diagnostic_coordinator import decode_diagnostic_json


class ShoulderSessionReview:
    def __init__(self, boot, command):
        self.boot, self.command = boot, command
        self.count = 0
        self.baseline = None
        self.last_finished = 0

    def accept(self, raw):
        doc = decode_diagnostic_json(raw, maximum=4095)
        prefix = ['BASELINE', 'PRELOAD_INTENT', 'PRELOAD_RESULT', 'PRELOAD_VERIFIED',
                  'PRELOAD_INTENT', 'PRELOAD_RESULT', 'PRELOAD_VERIFIED',
                  'PAIR_ENABLE_INTENT', 'PAIR_ENABLE_SENT_UNACKNOWLEDGED', 'PAIR_ENABLE_READBACK']
        seq = self.count
        event = prefix[seq] if seq < len(prefix) else 'TIMED_HOLD_SAMPLE'
        if (seq >= 64 or doc.get('schema') != 'rocell.shoulder_hold_event.v1'
                or doc.get('boot_id') != self.boot or doc.get('command_id') != self.command
                or type(doc.get('sequence')) is not int or doc['sequence'] != seq
                or doc.get('event') != event or doc.get('physical_accuracy_verified') is not False):
            raise ValueError('Unexpected shoulder record identity/order')
        start, end = doc.get('scan_started_us'), doc.get('scan_finished_us')
        if (type(start) is not int or type(end) is not int or start <= 0
                or start < self.last_finished or not start <= end <= start + 300_000):
            raise ValueError('Invalid scan timing')
        rows = doc.get('joints')
        if not isinstance(rows, list) or len(rows) != 7:
            raise ValueError('Seven joint rows required')
        for i, row in enumerate(rows):
            if (not isinstance(row, list) or len(row) != 5
                    or any(type(v) is not int for v in row[:4]) or row[0] != 11+i
                    or not 0 <= row[1] <= 4095 or not 0 <= row[2] <= 4095
                    or row[3] not in (0, 1) or not isinstance(row[4], str)
                    or not re.fullmatch('[0-9a-f]{30}', row[4])):
                raise ValueError('Malformed joint evidence')
            feedback = bytes.fromhex(row[4])
            if int.from_bytes(feedback[:2], 'little') != row[1]:
                raise ValueError('Position disagrees with raw feedback')
            if seq >= 9 and (feedback[2] or feedback[3] or feedback[10]):
                raise ValueError('Hold feedback reports motion')
        baseline = self.baseline if self.baseline is not None else rows
        if baseline[1][3] or baseline[2][3]:
            raise ValueError('Shoulders must begin passive')
        if any(r[3] and abs(r[1]-r[2]) > 2 for r in baseline):
            raise ValueError('Existing enabled joint not tracking')
        completed = 0 if seq < 3 else 1 if seq < 6 else 2
        for i, row in enumerate(rows):
            expected_goal = baseline[i][1] if 1 <= i <= completed else baseline[i][2]
            expected_torque = 1 if seq >= 9 and i in (1, 2) else baseline[i][3]
            if (abs(row[1]-baseline[i][1]) > 2 or row[2] != expected_goal
                    or row[3] != expected_torque):
                raise ValueError('Unexpected joint state change')
        sid = 12 if seq in (1, 2, 3) else 13 if seq in (4, 5, 6) else 0
        result = 1 if seq in (2, 3, 5, 6) or seq >= 9 else 0
        role = 'PRE_ACTION' if seq in (2, 5, 8) else 'OBSERVATION'
        if (type(doc.get('servo_id')) is not int or doc['servo_id'] != sid
                or type(doc.get('result')) is not int or doc['result'] != result
                or doc.get('snapshot_role') != role):
            raise ValueError('Unexpected action result/role')
        if seq in (1, 2, 4, 5):
            if (doc.get('requested_target') != baseline[sid-11][1]
                    or doc.get('speed') != 20 or doc.get('acceleration') != 1):
                raise ValueError('Preload target is not baseline position')
        if seq in (2, 5):
            a, b = doc.get('action_started_us'), doc.get('action_finished_us')
            if (type(a) is not int or type(b) is not int or not end <= a <= b
                    or doc.get('device_error') != 0):
                raise ValueError('Invalid preload delivery evidence')
            end = b
        self.baseline = baseline
        self.last_finished = end
        self.count += 1
        return doc
