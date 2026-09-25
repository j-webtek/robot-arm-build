# Compile-only compatibility check. Never upload this no-op probe to the arm.
$ErrorActionPreference = 'Stop'
$softwareRoot = Split-Path -Parent $PSScriptRoot
$toolRoot = Join-Path $softwareRoot '.firmware-tools'
$probePath = Join-Path $softwareRoot 'firmware/build_probes/campaign_probe'
$includePath = (Join-Path $softwareRoot 'firmware/diagnostics').Replace('\', '/')
if ($includePath -match '\s') { throw 'This pinned compile probe requires a workspace path without spaces.' }
$previousData = $env:ARDUINO_DIRECTORIES_DATA
$previousUser = $env:ARDUINO_DIRECTORIES_USER
try {
    $env:ARDUINO_DIRECTORIES_DATA = Join-Path $toolRoot 'data'
    $env:ARDUINO_DIRECTORIES_USER = Join-Path $toolRoot 'user'
    # Preserve ESP32 platform defaults: overriding extra_flags with only -I
    # removes -c and incorrectly attempts linking each C++ translation unit.
    & (Join-Path $toolRoot 'cli-1.5.1/arduino-cli.exe') compile --clean `
        --fqbn 'esp32:esp32:esp32:PartitionScheme=default,PSRAM=disabled' `
        --build-path (Join-Path $toolRoot 'build-characterization-probe') `
        --build-property "compiler.cpp.extra_flags=-MMD -c -I$includePath" `
        $probePath
    if ($LASTEXITCODE -ne 0) { throw "Compile probe failed with exit code $LASTEXITCODE" }
} finally {
    $env:ARDUINO_DIRECTORIES_DATA = $previousData
    $env:ARDUINO_DIRECTORIES_USER = $previousUser
}
