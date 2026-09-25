"""Explicit hold-only orchestration; no credential generation or implicit I/O.

Call only with separately approved candidate bytes. A real device adapter is
inert until the durably reserved execution begins. Reset remains opt-in and
cannot occur until the filesystem readback result is exported and verified.
"""
from .startup_provisioning_run import _run_provisioning


def run_hold_provisioning(*, source, source_sha256, candidate, candidate_sha256,
                         policy, key, littlefs, validate_policy, private_root,
                         export_root, device, save_private_image, startup_authorized=False):
    return _run_provisioning('hold', **locals())


def run_hold_policy_replacement(*, source, source_sha256, candidate, candidate_sha256,
                                previous_policy, policy, littlefs, validate_policy,
                                private_root, export_root, device, save_private_image,
                                startup_authorized=False):
    """Separate one-use replacement journal; no new key or implicit reset."""
    return _run_provisioning('hold-replacement', key=None, **locals())
