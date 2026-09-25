[CmdletBinding()]
param(
    [ValidateSet('runtime', 'hardware', 'development')]
    [string] $Profile = 'hardware',

    [switch] $SkipVerification
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

$RocellWorkspace = Split-Path -Parent $MyInvocation.MyCommand.Path
$RocellSoftware = Join-Path $RocellWorkspace 'software'
$RocellVenv = Join-Path $RocellWorkspace '.venv'
$RocellVenvPython = Join-Path $RocellVenv 'Scripts\python.exe'
$RocellLauncher = Join-Path $RocellWorkspace 'rocell.ps1'

$RocellHadPythonNoUserSite = Test-Path -LiteralPath Env:PYTHONNOUSERSITE
$RocellPreviousPythonNoUserSite = [Environment]::GetEnvironmentVariable(
    'PYTHONNOUSERSITE',
    'Process'
)
$RocellHadPythonPath = Test-Path -LiteralPath Env:PYTHONPATH
$RocellPreviousPythonPath = [Environment]::GetEnvironmentVariable(
    'PYTHONPATH',
    'Process'
)

try {
    # Ignore caller-controlled Python import paths throughout environment
    # creation and installation, then restore them in the finally block.
    $env:PYTHONNOUSERSITE = '1'
    $env:PYTHONPATH = $null

    if (-not (Test-Path -LiteralPath (Join-Path $RocellSoftware 'pyproject.toml') -PathType Leaf)) {
        throw "RoCell pyproject.toml is missing from $RocellSoftware"
    }

    Assert-RocellNonReparseItem -LiteralPath $MyInvocation.MyCommand.Path -Label 'RoCell setup script' -ExpectedType Leaf
    Assert-RocellNonReparseItem -LiteralPath $RocellWorkspace -Label 'RoCell workspace' -ExpectedType Container
    Assert-RocellNonReparseItem -LiteralPath $RocellSoftware -Label 'RoCell software directory' -ExpectedType Container
    Assert-RocellNonReparseItem -LiteralPath (Join-Path $RocellSoftware 'pyproject.toml') -Label 'RoCell pyproject' -ExpectedType Leaf
    Assert-RocellNonReparseItem -LiteralPath $RocellLauncher -Label 'RoCell launcher' -ExpectedType Leaf

    $RocellExistingVenv = Get-Item -LiteralPath $RocellVenv -Force -ErrorAction SilentlyContinue
    if ($null -ne $RocellExistingVenv) {
        Assert-RocellNonReparseItem -LiteralPath $RocellVenv -Label 'Workspace virtual environment' -ExpectedType Container
        $RocellNestedReparsePoint = Get-ChildItem -LiteralPath $RocellVenv -Force -Recurse -ErrorAction Stop |
            Where-Object { $_.Attributes -band [IO.FileAttributes]::ReparsePoint } |
            Select-Object -First 1
        if ($null -ne $RocellNestedReparsePoint) {
            throw "The workspace .venv contains a reparse point: $($RocellNestedReparsePoint.FullName)"
        }
    }

    if (-not (Test-Path -LiteralPath $RocellVenvPython -PathType Leaf)) {
        $RocellBootstrapPython = (Get-Command python -ErrorAction Stop).Source
        & $RocellBootstrapPython -I -m venv $RocellVenv
        if ($LASTEXITCODE -ne 0) {
            throw "Python virtual-environment creation failed with exit code $LASTEXITCODE"
        }
    }
    Assert-RocellNonReparseItem -LiteralPath $RocellVenv -Label 'Workspace virtual environment' -ExpectedType Container
    Assert-RocellNonReparseItem -LiteralPath (Join-Path $RocellVenv 'Scripts') -Label 'Workspace virtual-environment Scripts directory' -ExpectedType Container
    Assert-RocellNonReparseItem -LiteralPath $RocellVenvPython -Label 'Workspace virtual-environment interpreter' -ExpectedType Leaf

    $RocellInstallTarget = switch ($Profile) {
        'runtime' { $RocellSoftware }
        'hardware' { "$RocellSoftware[serial,vision]" }
        'development' { "$RocellSoftware[serial,vision,test]" }
    }

    & $RocellVenvPython -I -m pip install --editable $RocellInstallTarget
    if ($LASTEXITCODE -ne 0) {
        throw "RoCell installation failed with exit code $LASTEXITCODE"
    }

    # Reject an environment whose installed dependency constraints conflict
    # before any physical-onboarding command is allowed to use it.
    & $RocellVenvPython -I -m pip check
    if ($LASTEXITCODE -ne 0) {
        throw "RoCell dependency consistency check failed with exit code $LASTEXITCODE"
    }

    # This source/interpreter binding check is mandatory even when the caller
    # skips the extended rehearsal suite. It detects copied/stale editable
    # environments and is a prerequisite for describing installation as done.
    & $RocellLauncher --version | Out-Null
    if ($LASTEXITCODE -ne 0) {
        throw "RoCell checkout/source binding verification failed with exit code $LASTEXITCODE"
    }

    if (-not $SkipVerification) {
        # These checks are deliberately hardware-free. They validate the selected
        # checkout, optional dependencies, and synthetic B0477 stack only.
        & $RocellLauncher status --json
        if ($LASTEXITCODE -ne 0) { throw 'RoCell status verification failed' }

        # Validate the additive v2 contract graph. This performs bounded local
        # file reads only; runtime activation and all physical authorities must
        # remain false for the command to succeed.
        & $RocellLauncher physical-onboard verify-foundation --json
        if ($LASTEXITCODE -ne 0) { throw 'RoCell onboarding foundation validation failed' }

        & $RocellLauncher host-doctor --profile $Profile --require-pass --json
        if ($LASTEXITCODE -ne 0) { throw 'RoCell host environment verification failed' }

        & $RocellLauncher doctor --mode sim --json
        if ($LASTEXITCODE -ne 0) { throw 'RoCell simulation doctor failed' }

        # The connection rehearsal uses only incapable deterministic providers. It
        # proves lifecycle, exact-mode, freshness, close/reopen, and one-shot T=105
        # logic without enumerating or opening a physical device.
        & $RocellLauncher rehearse-physical-connections --require-expected --json
        if ($LASTEXITCODE -ne 0) { throw 'RoCell connection-contract rehearsal failed' }

        if ($Profile -ne 'runtime') {
            & $RocellLauncher rehearse-b0477-stack --require-pass --json
            if ($LASTEXITCODE -ne 0) { throw 'RoCell B0477 rehearsal failed' }
        }

        Write-Host "RoCell $Profile environment is verified and ready. Use: .\rocell.ps1 <command>"
    }
    else {
        Write-Warning (
            "RoCell $Profile dependencies, dependency consistency, and checkout " +
            "binding were verified. The extended hardware-free diagnostics and " +
            "rehearsals were skipped. Run .\setup-rocell.ps1 -Profile $Profile " +
            "without -SkipVerification before starting onboarding; device-access " +
            "commands remain subject to their own fail-closed host gates."
        )
    }
}
finally {
    if ($RocellHadPythonNoUserSite) {
        [Environment]::SetEnvironmentVariable(
            'PYTHONNOUSERSITE',
            $RocellPreviousPythonNoUserSite,
            'Process'
        )
    }
    else {
        Remove-Item -LiteralPath Env:PYTHONNOUSERSITE -ErrorAction SilentlyContinue
    }
    if ($RocellHadPythonPath) {
        [Environment]::SetEnvironmentVariable(
            'PYTHONPATH',
            $RocellPreviousPythonPath,
            'Process'
        )
    }
    else {
        Remove-Item -LiteralPath Env:PYTHONPATH -ErrorAction SilentlyContinue
    }
}
