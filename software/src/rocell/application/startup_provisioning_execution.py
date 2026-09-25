"""One-shot write/verification core for an explicitly approved staged image.

No ports, keys, reset or network are created here. The caller must independently
validate/preserve the staged filesystem and obtain approval for its exact digest.
The injected device's write method must itself disable transport write retries.
"""
import hashlib

from .diagnostic_provisioning_image import IMAGE_SIZE

FLASH_SIZE = 0x400000
FS_START = 0x290000
FS_END = FS_START + IMAGE_SIZE
APP_START = 0x10000
APP_SIZE = 1081872
APP_SHA256 = '71447b72f1488954ece0f6e9d95ca6ec3fc14b45982a10d65a96d3caa3691526'
PARTITION_SHA256 = '148b959cbff1c38aa8e1d5c0ba9d612c54997b945e56a63f41223eef650653a1'
MAC = 'fc:e8:c0:f8:d5:38'


def digest(data):
    return hashlib.sha256(data).hexdigest()


def _hash(value):
    if type(value) is not str or len(value) != 64 or any(c not in '0123456789abcdef' for c in value):
        raise ValueError('Exact lowercase SHA-256 required')


class StartupProvisioningExecution:
    """Consumes one invocation even on failure; never retries, resets or restores.

    reserve(record) must durably reserve a unique operation before any device I/O.
    preserve_source(bytes) must privately retain and readback-verify the original
    filesystem before writing. event(record) must flush nonsecret evidence.
    These callbacks return literal True only after durability succeeds. A caller
    must retain the reservation across process restarts; recreating this Python
    object is not recovery or permission for another attempt.
    """
    def __init__(self):
        self.consumed = False

    def _profile(self):
        return APP_SIZE, APP_SHA256, 'startup'

    def execute(self, device, candidate, *, source_sha256, candidate_sha256,
                reserve, preserve_source, event):
        if self.consumed:
            raise ValueError('Provisioning attempt already consumed')
        self.consumed = True
        app_size, app_sha256, mode = self._profile()
        _hash(source_sha256)
        _hash(candidate_sha256)
        if (type(candidate) is not bytes or len(candidate) != IMAGE_SIZE or
                digest(candidate) != candidate_sha256 or candidate_sha256 == source_sha256):
            raise ValueError('Reviewed candidate identity mismatch')
        reservation = dict(schema=f'rocell.{mode}_provisioning_attempt.v1',
            source_sha256=source_sha256, candidate_sha256=candidate_sha256,
            app_sha256=app_sha256, offset=FS_START, length=IMAGE_SIZE,
            retry_allowed=False, motion_authorized=False)
        if reserve(reservation) is not True:
            raise ValueError('Durable provisioning reservation failed')

        def record(stage, **fields):
            if event(dict(stage=stage, **fields)) is not True:
                raise ValueError('Provisioning evidence publication failed')

        # Opening/resetting a real device belongs to the authorized adapter.
        # This core checks identity again before trusting its memory readback.
        expected = dict(mac=MAC, flash_id=0x164020, secure_boot=False,
                        flash_encryption=False, secure_download_mode=False)
        identity = device.identity()
        if (type(identity) is not dict or set(identity) != set(expected) or
                any(type(identity[k]) is not type(v) or identity[k] != v for k, v in expected.items())):
            raise ValueError('Controller compatibility mismatch')
        before = device.read_flash(0, FLASH_SIZE)
        if type(before) is not bytes or len(before) != FLASH_SIZE:
            raise ValueError('Incomplete prewrite flash acquisition')
        source = before[FS_START:FS_END]
        if (digest(source) != source_sha256 or
                digest(before[APP_START:APP_START+app_size]) != app_sha256 or
                digest(before[0x8000:0x8c00]) != PARTITION_SHA256):
            raise ValueError('Installed source/application/partition mismatch')
        if preserve_source(source) is not True:
            raise ValueError('Private recovery preservation failed')
        record('PREWRITE_VERIFIED', source_sha256=source_sha256, app_sha256=app_sha256)
        record('WRITE_ATTEMPT_STARTED', offset=FS_START, length=IMAGE_SIZE)
        # Exceptions and uncertain returns stop here; never invoke write again.
        if device.write_flash_once(FS_START, candidate) is not True:
            raise ValueError('Provisioning delivery uncertain')
        after = device.read_flash(0, FLASH_SIZE)
        if type(after) is not bytes or len(after) != FLASH_SIZE:
            raise ValueError('Incomplete postwrite flash acquisition')
        if after[FS_START:FS_END] != candidate:
            raise ValueError('Provisioning readback mismatch')
        if before[:FS_START] != after[:FS_START] or before[FS_END:] != after[FS_END:]:
            raise ValueError('Protected flash region changed')
        result = dict(schema=f'rocell.{mode}_provisioning_result.v1',
            status='FLASH_READBACK_VERIFIED', candidate_sha256=candidate_sha256,
            source_sha256=source_sha256, protected_regions_unchanged=True,
            recovery_preserved=True, retry_allowed=False, startup_attempted=False,
            configuration_loaded=False, motion_authorized=False)
        record('FLASH_READBACK_VERIFIED', **result)
        return result
