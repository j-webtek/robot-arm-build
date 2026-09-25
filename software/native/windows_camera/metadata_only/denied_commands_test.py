"""Verify the dedicated metadata build rejects active argv before device I/O."""

from pathlib import Path
import subprocess
import sys


def main() -> None:
    if len(sys.argv) != 2:
        raise RuntimeError("Expected the fixed metadata-only test target")
    executable = Path(sys.argv[1]).resolve(strict=True)
    if executable.name != "rocell_windows_camera_metadata.exe":
        raise RuntimeError("Refusing any other executable")
    cases = (
        (),
        ("probe", "--endpoint", "UNUSED-OFFLINE-FIXTURE", "--max-ms", "5000"),
        ("capture", "--endpoint", "UNUSED-OFFLINE-FIXTURE"),
        ("--owned-probe",),
        ("--owned-capture",),
        ("--owned-probe-v2",),
        ("--owned-capture-v2",),
        ("set-controls",),
        ("unknown",),
    )
    for args in cases:
        result = subprocess.run(
            [str(executable), *args],
            stdin=subprocess.DEVNULL,
            capture_output=True,
            timeout=2,
            check=False,
            creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
        )
        assert result.returncode == 2, (args, result.returncode, result.stderr)
        assert result.stdout == b""
        assert result.stderr.strip() == b"METADATA_ONLY_OPERATION_REQUIRED"
    print("PASS: 9 active/unknown command denials; no metadata or capture request")


if __name__ == "__main__":
    main()
