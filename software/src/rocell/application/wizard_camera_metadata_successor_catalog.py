"""Reviewed fixed metadata-only successor; never learn hashes at runtime.

Build/test provenance is retained separately from the old v1 catalog. This
catalog may register inventory/identity only, never camera activation.
"""

CATALOG_ID = "windows-camera-metadata-only-development-v2"
CATALOG_LABEL = "Windows metadata-only camera helper (2026-09-12 successor)"
NATIVE_ROOT = "software/native/windows_camera/"
HELPER_RELATIVE_PATH = (
    NATIVE_ROOT
    + "build-metadata-only-20260912-01/Release/rocell_windows_camera_metadata.exe"
)
NATIVE_HELPER_SHA256 = (
    "14f4a9b0b2e9a2bc332fec2c16c7914a16736a25036e72dca38ae2dd0bd33673"
)
PINS = (
    ("NATIVE_HELPER", HELPER_RELATIVE_PATH, NATIVE_HELPER_SHA256, 219648),
    (
        "HISTORICAL_RECORD",
        NATIVE_ROOT + "integrated_build_manifest.json",
        "435fce4a83f2536cb0c2fa4b02c1aaacfb2a9dda58796d763fff4547095168f5",
        4116,
    ),
    (
        "CURRENT_METADATA_BUILD_RECORD",
        NATIVE_ROOT + "metadata_only_build_record_20260912.json",
        "967f3aa619dca24bdcdcad9743d82c72a2daf9dfab85a83e357610972501103b",
        4085,
    ),
    (
        "NATIVE_BUILD_SOURCE",
        NATIVE_ROOT + "metadata_only/CMakeLists.txt",
        "38e0cd64f4831e1f334a0ca191d093b977f757a4dbfb4d277f4b956ca396abc1",
        2696,
    ),
    (
        "NATIVE_TEST_SOURCE",
        NATIVE_ROOT + "metadata_only/denied_commands_test.py",
        "a9333616d905418577e9a5767bc6f63044b4998a5d566cfe3f228e3391d89d28",
        1392,
    ),
    (
        "NATIVE_SOURCE",
        NATIVE_ROOT + "camera_worker.cpp",
        "19f6dc99b8828c7e5c3553d68788bef4011e2a075a96c1755c326faf773716be",
        38808,
    ),
    (
        "NATIVE_SOURCE",
        NATIVE_ROOT + "identity_metadata.h",
        "e4f39f7156f66b5fe2f2e8f812d9c1a6ab6e3e69d530aad59f50c4166545b3f0",
        5574,
    ),
    (
        "NATIVE_SOURCE",
        NATIVE_ROOT + "identity_metadata.cpp",
        "7c122cd638346a9a4761f504f3560f9d49c1baf7716d7321bdd1538c6e8f2cfd",
        25356,
    ),
    (
        "NATIVE_TEST_SOURCE",
        NATIVE_ROOT + "identity_metadata_tests.cpp",
        "312afee6b801c6eb44c4095c4104f068e5ede6d2703fe135ddf4b5737b8b251e",
        20714,
    ),
    (
        "NATIVE_TEST_SOURCE",
        NATIVE_ROOT + "identity_metadata_wire_test.py",
        "91bfea68b199602bb1693a1862baf6f2b8ef7189fc1700d92b5b3bc36b80ef52",
        3918,
    ),
    (
        "NATIVE_SOURCE",
        NATIVE_ROOT + "admission_protocol.h",
        "2f171649b196c8eb18dbf2f57eeb34787e58b8ca50a8d3f6bb015b0988d95a3f",
        1692,
    ),
    (
        "NATIVE_SOURCE",
        NATIVE_ROOT + "admission_protocol.cpp",
        "54124fbef5eba9e3d3f3484123c280231b9178fd30f5b353dddddc86e876f800",
        8709,
    ),
    (
        "NATIVE_SOURCE",
        NATIVE_ROOT + "admission_entry.h",
        "69cb306c4d3e0b6527091a7ed3ddbfd3bf6627c67ed789e455fbed7530015a39",
        489,
    ),
    (
        "NATIVE_SOURCE",
        NATIVE_ROOT + "admission_entry.cpp",
        "91aa3c41bde8e24b19f6a2d4494896a847583a92ad5e30b2b42c3809604a9643",
        3866,
    ),
    (
        "NATIVE_SOURCE",
        NATIVE_ROOT + "camera_cleanup.h",
        "f6262373862550e64e0822ce089a2cf8314a0b1f24243106b4d6fbf195bde6d9",
        3013,
    ),
    (
        "CURRENT_METADATA_CLIENT",
        "software/src/rocell/providers/windows/camera_worker_client.py",
        "2e7a8f8d330374f0614787e3c75441aab3739c613a5392641396b655541832ba",
        66098,
    ),
    (
        "NATIVE_TEST_ARTIFACT",
        NATIVE_ROOT
        + "build-metadata-only-20260912-01/Release/rocell_identity_metadata_tests.exe",
        "ce9cfc2619a03e4c3f2d80519a842a1c143e9fa4136b92dc27f7c8cfb2115f56",
        139776,
    ),
)
