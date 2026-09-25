"""Exclusive flushed nonsecret operation record; never resumes an old attempt."""
import os
from pathlib import Path

from .first_motion_contract import canonical


class StartupProvisioningJournal:
    NAME = 'startup-r6-provisioning-events.jsonl'

    def __init__(self, private_root):
        self.path = Path(private_root).resolve() / self.NAME
        self.stream = None
        self.attempted = False

    def reserve(self, record):
        if self.attempted:
            raise ValueError('Reservation already attempted')
        self.attempted = True
        # Parent is an already-established private directory; never create or
        # silently select another directory to evade an existing reservation.
        self.stream = self.path.open('xb')
        return self.event(dict(stage='RESERVED', **record))

    def event(self, record):
        if self.stream is None or self.stream.closed:
            raise ValueError('No active provisioning journal')
        data = canonical(record) + b'\n'
        if len(data) > 4096:
            raise ValueError('Oversized provisioning event')
        try:
            if self.stream.write(data) != len(data):
                raise OSError('Incomplete provisioning event')
            self.stream.flush()
            os.fsync(self.stream.fileno())
            return True
        except BaseException:
            self.close()
            raise

    def close(self):
        if self.stream is not None:
            self.stream.close()
