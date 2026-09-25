# Offline compile-only probe using the retained r7 ESP32 flags. No device tools.
$ErrorActionPreference = 'Stop'
$softwareRoot = Split-Path $PSScriptRoot -Parent
$database = Join-Path $softwareRoot '.firmware-tools/build-configured-diagnostic-candidate-r7--default-4mb-no-psram/compile_commands.json'
$entries = Get-Content -LiteralPath $database -Raw | ConvertFrom-Json
$entry = $entries | Where-Object { $_.file -like '*RoArm-M3_example.ino.cpp' } | Select-Object -First 1
if (-not $entry -or -not ($entry.arguments -contains '-c')) { throw 'Retained compile-only command missing' }
$source = Join-Path $softwareRoot 'firmware/diagnostics/held_pair_memory_probe.cpp'
$outputDirectory = Join-Path $softwareRoot ('.firmware-tools/pair-memory-probe-' + [guid]::NewGuid().ToString('N'))
New-Item -ItemType Directory -Path $outputDirectory | Out-Null
$object = Join-Path $outputDirectory 'held_pair_memory_probe.o'
$compiler = $entry.arguments[0]
$compileArgs = @()
for ($i=1; $i -lt $entry.arguments.Count; $i++) {
    $argument = $entry.arguments[$i]
    if ($argument -eq '-o') { $compileArgs += @('-o', $object); $i++; continue }
    if ($argument -eq $entry.file) { $compileArgs += $source; continue }
    $compileArgs += $argument
}
& $compiler @compileArgs
if ($LASTEXITCODE -ne 0) { throw 'ESP32 memory probe compilation failed' }
$nm = Join-Path (Split-Path $compiler -Parent) 'xtensa-esp32-elf-nm.exe'
$symbols = & $nm '-S' '--radix=d' $object
if ($LASTEXITCODE -ne 0) { throw 'ESP32 object inspection failed' }
$sizes = [ordered]@{}
foreach ($line in $symbols) {
    if ($line -match '^\s*\d+\s+(\d+)\s+\w\s+(rocell_size_\w+)\s*$') {
        $sizes[$Matches[2]] = [int]$Matches[1]
    }
}
if ($sizes.Count -ne 17) { throw 'Expected seventeen target size symbols' }
$headerHashes = [ordered]@{}
Get-ChildItem -LiteralPath (Split-Path $source -Parent) -Filter '*.h' -File |
    Sort-Object Name | ForEach-Object {
        $headerHashes[$_.Name] = (Get-FileHash -LiteralPath $_.FullName -Algorithm SHA256).Hash.ToLowerInvariant()
    }
[ordered]@{
    schema='rocell.held_pair_target_memory_probe.v1'
    target='esp32:esp32:esp32:PartitionScheme=default,PSRAM=disabled'
    compile_only=$true
    runtime_heap_measured=$false
    source_sha256=(Get-FileHash -LiteralPath $source -Algorithm SHA256).Hash.ToLowerInvariant()
    compile_database_sha256=(Get-FileHash -LiteralPath $database -Algorithm SHA256).Hash.ToLowerInvariant()
    header_sha256=$headerHashes
    compiler_sha256=(Get-FileHash -LiteralPath ($compiler + '.exe') -Algorithm SHA256).Hash.ToLowerInvariant()
    object_path=$object
    sizes=$sizes
} | ConvertTo-Json -Depth 4
