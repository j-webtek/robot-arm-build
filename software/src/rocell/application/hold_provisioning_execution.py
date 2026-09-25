"""Explicit r7-only provisioning profile; no arbitrary application override.

Reuses the tested one-write/readback core. Construction is inert; executing it
requires separately approved candidate bytes and an authorized device adapter.
No reset, key generation, servo command or automatic recovery is provided.
"""
from .startup_provisioning_execution import StartupProvisioningExecution
from .startup_provisioning_journal import StartupProvisioningJournal

APP_SIZE = 1070912
APP_SHA256 = '380d7a69e0b456b25b4ae50e34f8d947724ca5c22db42d75958df509e2618c33'


class HoldProvisioningExecution(StartupProvisioningExecution):
    def _profile(self):
        return APP_SIZE, APP_SHA256, 'hold'


class HoldProvisioningJournal(StartupProvisioningJournal):
    # Never reuse the consumed r6 provisioning or r7 application journal.
    NAME = 'hold-r7-provisioning-events.jsonl'


class HoldReplacementJournal(StartupProvisioningJournal):
    NAME = 'hold-r7-supported-replacement-provisioning-events.jsonl'
