"""Offline adapter to the pinned native firmware policy parser executable."""
import hashlib
from pathlib import Path
import subprocess


class NativeProvisioningValidator:
    def __init__(self, executable, expected_sha256):
        self.executable = Path(executable).resolve(strict=True)
        self.expected_sha256 = expected_sha256

    def __call__(self, policy):
        if type(policy) is not bytes or not 0 < len(policy) <= 4096:
            return False
        if hashlib.sha256(self.executable.read_bytes()).hexdigest() != self.expected_sha256:
            raise ValueError('Native policy validator identity changed')
        # Input is piped, not placed in shell arguments or a temporary file.
        # No retry and no forwarding of potentially sensitive child output.
        result = subprocess.run([str(self.executable)], input=policy,
                                capture_output=True, timeout=5, check=False)
        if result.returncode == 2 and not result.stdout and not result.stderr:
            return False
        if result.returncode != 0 or result.stdout != b'POLICY_ACCEPTED\n' or result.stderr:
            raise ValueError('Native policy validator failed')
        return True
