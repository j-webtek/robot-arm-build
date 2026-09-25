"""Simulation-only proposed telemetry contract; not a supported arm command.

No device IO or native admission imports. Firmware must acquire and label each
servo read honestly; passing this checker cannot attest installed firmware.
"""
import math
import re

from rocell.application.wizard_diagnostic_coordinator import decode_diagnostic_json

SCHEMA = 'rocell.proposed_servo_acquisition.v1'
JOINTS = ('b', 's', 'e', 't', 'r', 'g')


def _integer(value):
    return type(value) is int and 0 <= value < 2**63


class SimulatedServoFreshnessMonitor:
    """Bounded, sticky-failure validation of a single proposed command epoch.

    A boot change, missed read, stale sequence or malformed report ends this
    instance. Reconstructing the monitor is not permission to rearm hardware.
    All six joint sequences must advance, even when positions are unchanged.
    """
    def __init__(self, *, boot_id, command_sha256):
        if (type(boot_id) is not str or re.fullmatch(r'[a-f0-9]{32}', boot_id) is None
                or type(command_sha256) is not str
                or re.fullmatch(r'[a-f0-9]{64}', command_sha256) is None):
            raise ValueError('Exact simulated boot and command association required')
        self.boot_id, self.command_sha256 = boot_id, command_sha256
        self.count, self.failed = 0, False
        self.previous = None

    def push(self, raw):
        if self.failed:
            raise ValueError('Freshness monitor held; no automatic rearm')
        try:
            if type(raw) is not bytes or len(raw) > 8192 or self.count >= 512:
                raise ValueError('Finite original report budget exceeded')
            body = decode_diagnostic_json(raw, maximum=8192)
            fields = {'schema', 'boot_id', 'command_sha256', 'command_applied_us',
                      'report_sequence', 'published_us', 'joints'}
            if (type(body) is not dict or set(body) != fields or body['schema'] != SCHEMA
                    or body['boot_id'] != self.boot_id
                    or body['command_sha256'] != self.command_sha256
                    or any(not _integer(body[k]) for k in
                           ('command_applied_us', 'report_sequence', 'published_us'))
                    or body['published_us'] < body['command_applied_us']
                    or type(body['joints']) is not dict or set(body['joints']) != set(JOINTS)):
                raise ValueError('Proposed report context invalid')
            previous = self.previous
            if previous and (body['report_sequence'] <= previous['report_sequence']
                    or body['published_us'] <= previous['published_us']
                    or body['command_applied_us'] != previous['command_applied_us']):
                raise ValueError('Report replay, clock regression or command epoch changed')
            for joint, row in body['joints'].items():
                if (type(row) is not dict or set(row) != {'read_ok', 'sequence', 'acquired_us', 'position_rad'}
                        or row['read_ok'] is not True
                        or not _integer(row['sequence']) or not _integer(row['acquired_us'])
                        or type(row['position_rad']) not in (int, float)
                        or not math.isfinite(row['position_rad']) or abs(row['position_rad']) > 100
                        or not body['command_applied_us'] <= row['acquired_us'] <= body['published_us']
                        or body['published_us']-row['acquired_us'] > 100_000):
                    raise ValueError('Failed, stale or invalid joint acquisition')
                if previous and (row['sequence'] <= previous['joints'][joint]['sequence']
                        or row['acquired_us'] <= previous['joints'][joint]['acquired_us']):
                    raise ValueError('Cached joint acquisition')
            self.previous = body
            self.count += 1
            return self.snapshot()
        except Exception:
            self.failed = True
            raise

    def snapshot(self):
        return dict(schema='rocell.simulated_servo_freshness.v1',
            status='HELD' if self.failed else 'SIMULATED_REPORTS_CONSISTENT' if self.count else 'EMPTY',
            report_count=self.count, basis='SIMULATION_ONLY',
            installed_protocol_supported=False, device_sample_freshness_verified=False,
            native_execution_released=False, motion_authorized=False,
            automatic_next_command_allowed=False)
