[CmdletBinding()]
param(
    [Parameter(Mandatory = $true)]
    [string] $CellId,

    [string] $SessionId,

    [switch] $SkipEnvironmentSetup
)

$ErrorActionPreference = 'Stop'

function Assert-RocellNonReparseItem {
    param(
        [Parameter(Mandatory = $true)]
        [string] $LiteralPath,

        [Parameter(Mandatory = $true)]
        [string] $Label,

        [ValidateSet('Any', 'Container', 'Leaf')]
        [string] $ExpectedType = 'Any'
    )

    $RocellCheckedItem = Get-Item -LiteralPath $LiteralPath -Force -ErrorAction Stop
    if (
        ($ExpectedType -eq 'Container' -and -not $RocellCheckedItem.PSIsContainer) -or
        ($ExpectedType -eq 'Leaf' -and $RocellCheckedItem.PSIsContainer)
    ) {
        throw "$Label has the wrong filesystem type: $LiteralPath"
    }
    if ($RocellCheckedItem.Attributes -band [IO.FileAttributes]::ReparsePoint) {
        throw "$Label must not be a symlink, junction, or other reparse point: $LiteralPath"
    }
}

# This entry point intentionally performs only software preparation. It never
# inventories a device, opens a camera or serial port, applies robot power, or
# sends an arm command. Physical actions remain individual operator-gated steps.
$RocellWorkspace = Split-Path -Parent $MyInvocation.MyCommand.Path
$RocellSetup = Join-Path $RocellWorkspace 'setup-rocell.ps1'
$RocellLauncher = Join-Path $RocellWorkspace 'rocell.ps1'

Assert-RocellNonReparseItem -LiteralPath $MyInvocation.MyCommand.Path -Label 'RoCell onboarding starter' -ExpectedType Leaf
Assert-RocellNonReparseItem -LiteralPath $RocellWorkspace -Label 'RoCell workspace' -ExpectedType Container
Assert-RocellNonReparseItem -LiteralPath $RocellSetup -Label 'RoCell setup script' -ExpectedType Leaf
Assert-RocellNonReparseItem -LiteralPath $RocellLauncher -Label 'RoCell launcher' -ExpectedType Leaf

if ([string]::IsNullOrWhiteSpace($SessionId)) {
    $RocellUtc = [DateTime]::UtcNow.ToString('yyyyMMddTHHmmssZ')
    $RocellSuffix = [Guid]::NewGuid().ToString('N').Substring(0, 8)
    $SessionId = "arrival-$RocellUtc-$RocellSuffix"
}

if (-not $SkipEnvironmentSetup) {
    & $RocellSetup -Profile hardware
    if ($LASTEXITCODE -ne 0) {
        throw "RoCell hardware-profile setup failed with exit code $LASTEXITCODE"
    }
}

# Repeat the side-effect-free gate immediately before the session is bound so
# a changed interpreter or package environment cannot be overlooked.
& $RocellLauncher host-doctor --profile hardware --require-pass --json
if ($LASTEXITCODE -ne 0) {
    throw "RoCell hardware-profile host gate failed with exit code $LASTEXITCODE"
}

# Repeat the source-bound, zero-I/O v2 foundation check immediately before
# session creation. Open implementation gates remain blockers; validation does
# not activate the future coordinator or any device authority.
& $RocellLauncher physical-onboard verify-foundation --json
if ($LASTEXITCODE -ne 0) {
    throw "RoCell onboarding foundation validation failed with exit code $LASTEXITCODE"
}

# Revalidate the exact connection lifecycle immediately before binding a new
# session. This command uses only deterministic incapable providers: it cannot
# enumerate, open, configure, or command a physical camera or arm.
& $RocellLauncher rehearse-physical-connections --require-expected --json
if ($LASTEXITCODE -ne 0) {
    throw "RoCell synthetic camera/arm connection rehearsal failed with exit code $LASTEXITCODE"
}

& $RocellLauncher physical-onboard new `
    --cell-id $CellId `
    --session-id $SessionId `
    --prepare-safe `
    --json
if ($LASTEXITCODE -ne 0) {
    Write-Warning (
        "If the preceding JSON says session_published=true, recover only with: " +
        ".\rocell.ps1 physical-onboard status --session-id $SessionId --json"
    )
    throw "RoCell physical onboarding session creation failed with exit code $LASTEXITCODE"
}

Write-Host "Created diagnostic-only onboarding session $SessionId."
Write-Host "Next: .\rocell.ps1 physical-onboard status --session-id $SessionId --json"
Write-Host 'No device was inventoried or opened and no robot power or command was issued.'
