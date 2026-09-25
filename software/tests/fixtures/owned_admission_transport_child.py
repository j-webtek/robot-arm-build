"""Fixed incapable pipe child: no camera, serial, network, files or descendants.

This file is used only by direct transport tests, not registered as an
application worker. Blocking reads are bounded externally by the owned Job.
"""

import json
import sys


def main():
    if len(sys.argv) != 1:
        return 2
    first = sys.stdin.buffer.readline(65)
    if first != b"request\n":
        return 3
    sys.stdout.buffer.write(b"READY\n")
    sys.stdout.buffer.flush()
    final = sys.stdin.buffer.readline(65)
    if final != b"release\n" or sys.stdin.buffer.read(1) != b"":
        return 4
    sys.stdout.write(
        json.dumps({"request_bytes": len(first), "release_bytes": len(final)})
    )
    sys.stdout.flush()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
