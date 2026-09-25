"""Exact r21 filesystem replacement execution profile; inert until invoked."""
from .startup_provisioning_execution import StartupProvisioningExecution
from .startup_provisioning_journal import StartupProvisioningJournal

APP_SIZE = 1127424
APP_SHA256 = '035922452587280362fc1e6fe0120f274647eeb2b0f8ee3c7bc88cb8c3289051'


class ObservedPoseExecution(StartupProvisioningExecution):
    def _profile(self):
        return APP_SIZE, APP_SHA256, 'observed-pose'


class ObservedPoseJournal(StartupProvisioningJournal):
    NAME = 'observed-pose-provisioning-events.jsonl'
