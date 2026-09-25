"""Inspect a verified private backup offline; print presence/validity, never secrets."""
import hashlib
import json
from pathlib import Path
import sys


def main():
    root = Path(__file__).resolve().parents[1]
    private = root / 'private-backups/controller-20260918-session1'
    a = (private / 'flash-pair-a.bin').read_bytes()
    b = (private / 'flash-pair-b.bin').read_bytes()
    expected = 'd9e3de5cf3738b18144697095534ec9a33e531a6cd5062f68b85b5a29f6df2b9'
    if len(a) != 4194304 or a != b or hashlib.sha256(a).hexdigest() != expected:
        raise ValueError('Verified backup identity changed')
    sys.path.insert(0, str(root / '.firmware-tools/littlefs-review'))
    import littlefs
    if littlefs.__version__ != '0.19.0':
        raise ValueError('Unexpected offline filesystem reader version')

    class ReadOnlyContext(littlefs.UserContext):
        def prog(self, *args):
            return -5

        def erase(self, *args):
            return -5

    context = ReadOnlyContext(buffer=bytearray(a[0x290000:0x3f0000]))
    # The library's default mount path auto-formats on failure. Never use it.
    fs = littlefs.LittleFS(context=context, mount=False, block_size=4096,
                          block_count=352, read_size=256, prog_size=256)
    fs.mount()
    names = fs.listdir('/')
    report = {'schema': 'rocell.backup_configuration_review.v1',
              'offline': True, 'reader_version': littlefs.__version__,
              'wifi_config_present': 'wifiConfig.json' in names,
              'wifi_config_usable_by_candidate': False,
              'diagnostic_policy_present': 'rocell-diagnostics.json' in names,
              'diagnostic_key_present': 'rocell-diagnostics.key' in names,
              'device_modified': False, 'secrets_included': False}
    if report['wifi_config_present'] and 0 < fs.stat('/wifiConfig.json').size <= 1024:
        try:
            with fs.open('/wifiConfig.json', 'r') as stream:
                config = json.load(stream)
            ssid, password = config.get('sta_ssid'), config.get('sta_password')
            report['wifi_config_usable_by_candidate'] = (
                isinstance(ssid, str) and isinstance(password, str)
                and 1 <= len(ssid.encode()) <= 32 and 8 <= len(password.encode()) <= 63
                and '\0' not in ssid and '\0' not in password)
        except (ValueError, UnicodeError, AttributeError):
            pass
    fs.unmount()
    if bytes(context.buffer) != a[0x290000:0x3f0000]:
        raise ValueError('Offline reader unexpectedly changed its memory buffer')
    print(json.dumps(report))


if __name__ == '__main__':
    main()
