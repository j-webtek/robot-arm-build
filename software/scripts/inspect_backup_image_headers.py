"""Offline, read-only ESP32 image-header inventory; never prints NVS/filesystem data.

Offsets are supplied explicitly from a separately reviewed partition table.
This is metadata inspection, NOT image integrity or deployment qualification.
"""

import argparse
import json
import struct
from pathlib import Path


def inspect_image(data: bytes, offset: int) -> dict:
    if offset < 0 or offset + 288 > len(data):
        raise ValueError("Image header outside backup")
    header = data[offset : offset + 24]
    result = {"offset": hex(offset), "image_magic": header[0]}
    if header[0] != 0xE9:
        result["status"] = "NO_ESP_IMAGE_HEADER"
        return result
    result.update(
        status="HEADER_ONLY_NOT_VALIDATED",
        segments=header[1],
        flash_mode=header[2],
        flash_size_frequency=header[3],
        chip_id=struct.unpack_from("<H", header, 12)[0],
    )
    descriptor = data[offset + 32 : offset + 288]
    if struct.unpack_from("<I", descriptor)[0] == 0xABCD5432:
        fields = {"version": (16, 32), "project_name": (48, 32),
                  "build_time": (80, 16), "build_date": (96, 16),
                  "idf_version": (112, 32)}
        result["build_metadata"] = {
            name: descriptor[start:start + size].split(b"\0")[0].decode(
                "ascii", errors="replace")
            for name, (start, size) in fields.items()
        }
    return result


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("backup", type=Path)
    parser.add_argument("offset", nargs="+", type=lambda value: int(value, 0))
    args = parser.parse_args()
    data = args.backup.read_bytes()
    print(json.dumps([inspect_image(data, offset) for offset in args.offset], indent=2))
