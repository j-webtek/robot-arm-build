[CmdletBinding(PositionalBinding = $false)]
param(
    [Parameter(ValueFromRemainingArguments = $true)]
    [string[]] $RocellArguments
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

# Keep the launcher anchored to this checkout so it cannot accidentally load a
# different installed copy of RoCell when commissioning evidence is collected.
$RocellWorkspace = Split-Path -Parent $MyInvocation.MyCommand.Path
$RocellSource = Join-Path $RocellWorkspace 'software\src'
$RocellManifest = Join-Path $RocellWorkspace 'software\config\system_manifest.json'
$RocellVenvPython = Join-Path $RocellWorkspace '.venv\Scripts\python.exe'
$RocellPhysicalCommand = (
    ($RocellArguments -contains 'physical-onboard') -or
    ($RocellArguments -contains 'arm-feedback')
)

# The launcher is the checkout-anchoring boundary. Accepting another workspace
# or manifest later on the command line would let argparse override the values
# this script is meant to fix. Reject their long-option abbreviations here too,
# so this boundary stays safe even if a future parser accidentally re-enables
# abbreviation. Advanced overrides must use python -m rocell directly.
$RocellForbiddenOverride = $RocellArguments | Where-Object {
    $RocellOptionName = ([string] $_ -split '=', 2)[0]
    $RocellOptionName.Length -gt 2 -and (
        '--workspace'.StartsWith(
            $RocellOptionName,
            [StringComparison]::OrdinalIgnoreCase
        ) -or
        '--manifest'.StartsWith(
            $RocellOptionName,
            [StringComparison]::OrdinalIgnoreCase
        )
    )
} | Select-Object -First 1
if ($null -ne $RocellForbiddenOverride) {
    throw "The workspace launcher does not accept $RocellForbiddenOverride overrides."
}

if (-not (Test-Path -LiteralPath $RocellManifest -PathType Leaf)) {
    throw "RoCell system manifest is missing from $RocellWorkspace"
}

# Check every security-relevant component explicitly. Checking only the final
# file is insufficient on Windows because an intermediate Scripts/source/config
# directory can itself be a junction while the final item looks ordinary.
Assert-RocellNonReparseItem -LiteralPath $MyInvocation.MyCommand.Path -Label 'RoCell launcher' -ExpectedType Leaf
Assert-RocellNonReparseItem -LiteralPath $RocellWorkspace -Label 'RoCell workspace' -ExpectedType Container
Assert-RocellNonReparseItem -LiteralPath (Join-Path $RocellWorkspace 'software') -Label 'RoCell software directory' -ExpectedType Container
Assert-RocellNonReparseItem -LiteralPath (Join-Path $RocellWorkspace 'software\config') -Label 'RoCell config directory' -ExpectedType Container
Assert-RocellNonReparseItem -LiteralPath $RocellManifest -Label 'RoCell system manifest' -ExpectedType Leaf
Assert-RocellNonReparseItem -LiteralPath $RocellSource -Label 'RoCell source directory' -ExpectedType Container
Assert-RocellNonReparseItem -LiteralPath (Join-Path $RocellSource 'rocell') -Label 'RoCell package directory' -ExpectedType Container
Assert-RocellNonReparseItem -LiteralPath (Join-Path $RocellSource 'rocell\__init__.py') -Label 'RoCell package initializer' -ExpectedType Leaf
Assert-RocellNonReparseItem -LiteralPath (Join-Path $RocellSource 'rocell\cli.py') -Label 'RoCell CLI module' -ExpectedType Leaf
Assert-RocellNonReparseItem -LiteralPath (Join-Path $RocellSource 'rocell\__main__.py') -Label 'RoCell main module' -ExpectedType Leaf

if (Test-Path -LiteralPath $RocellVenvPython -PathType Leaf) {
    Assert-RocellNonReparseItem -LiteralPath (Join-Path $RocellWorkspace '.venv') -Label 'Workspace virtual environment' -ExpectedType Container
    Assert-RocellNonReparseItem -LiteralPath (Join-Path $RocellWorkspace '.venv\Scripts') -Label 'Workspace virtual-environment Scripts directory' -ExpectedType Container
    Assert-RocellNonReparseItem -LiteralPath $RocellVenvPython -Label 'Workspace virtual-environment interpreter' -ExpectedType Leaf
    $RocellPython = $RocellVenvPython
    $RocellIsControlledVenv = $true
}
else {
    if ($RocellPhysicalCommand) {
        throw 'Physical device access requires the workspace .venv. Run .\setup-rocell.ps1 -Profile hardware first.'
    }
    $RocellPythonCommand = Get-Command python -ErrorAction Stop
    $RocellPython = $RocellPythonCommand.Source
    $RocellIsControlledVenv = $false
}

# A prepared workspace can run isolated from user-site packages and a poisoned
# external PYTHONPATH. Preserve the caller's process environment exactly: a
# launcher must not change how unrelated Python commands behave after it exits.
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
$RocellExitCode = 1

try {
    $env:PYTHONNOUSERSITE = '1'
    if ($RocellIsControlledVenv) {
        $env:PYTHONPATH = $null

        # Editable environments are relocatable only when their import mapping
        # still names this checkout. First inspect the package spec without
        # importing RoCell; only an exact initializer match permits imports.
        # This prevents a stale editable package from executing before its
        # origin has been proven.
        $RocellObservedBootstrap = @(
            & $RocellPython -I -c 'import importlib.util, pathlib, sys; spec=importlib.util.find_spec("rocell"); origin=getattr(spec, "origin", None); assert origin is not None; print(pathlib.Path(sys.executable).resolve()); print(pathlib.Path(sys.prefix).resolve()); print(pathlib.Path(origin).resolve())'
        )
        $RocellBootstrapProbeExitCode = $LASTEXITCODE
        if ($RocellBootstrapProbeExitCode -ne 0) {
            throw "Could not verify the installed RoCell package spec (exit $RocellBootstrapProbeExitCode)."
        }
        $RocellExpectedBootstrap = @(
            (Resolve-Path -LiteralPath $RocellVenvPython).Path,
            (Resolve-Path -LiteralPath (Join-Path $RocellWorkspace '.venv')).Path,
            (Resolve-Path -LiteralPath (Join-Path $RocellSource 'rocell\__init__.py')).Path
        )
        if ($RocellObservedBootstrap.Count -ne $RocellExpectedBootstrap.Count) {
            throw 'The controlled environment returned an unexpected interpreter/package-spec set.'
        }
        for ($RocellOriginIndex = 0; $RocellOriginIndex -lt $RocellExpectedBootstrap.Count; $RocellOriginIndex++) {
            if (-not [string]::Equals(
                [IO.Path]::GetFullPath([string] $RocellObservedBootstrap[$RocellOriginIndex]),
                [IO.Path]::GetFullPath([string] $RocellExpectedBootstrap[$RocellOriginIndex]),
                [StringComparison]::OrdinalIgnoreCase
            )) {
                throw "The workspace .venv interpreter/package binding is stale or outside this checkout: $($RocellObservedBootstrap[$RocellOriginIndex])"
            }
        }

        # The package initializer is now proven local. Import the two CLI entry
        # modules and independently verify their exact source locations.
        $RocellObservedEntryPoints = @(
            & $RocellPython -I -c 'import pathlib, rocell.cli, rocell.__main__; print(pathlib.Path(rocell.cli.__file__).resolve()); print(pathlib.Path(rocell.__main__.__file__).resolve())'
        )
        $RocellEntryPointProbeExitCode = $LASTEXITCODE
        if ($RocellEntryPointProbeExitCode -ne 0) {
            throw "Could not verify the installed RoCell entry points (exit $RocellEntryPointProbeExitCode)."
        }
        $RocellExpectedEntryPoints = @(
            (Resolve-Path -LiteralPath (Join-Path $RocellSource 'rocell\cli.py')).Path,
            (Resolve-Path -LiteralPath (Join-Path $RocellSource 'rocell\__main__.py')).Path
        )
        if ($RocellObservedEntryPoints.Count -ne $RocellExpectedEntryPoints.Count) {
            throw 'The controlled environment returned an unexpected RoCell entry-point origin set.'
        }
        for ($RocellOriginIndex = 0; $RocellOriginIndex -lt $RocellExpectedEntryPoints.Count; $RocellOriginIndex++) {
            if (-not [string]::Equals(
                [IO.Path]::GetFullPath([string] $RocellObservedEntryPoints[$RocellOriginIndex]),
                [IO.Path]::GetFullPath([string] $RocellExpectedEntryPoints[$RocellOriginIndex]),
                [StringComparison]::OrdinalIgnoreCase
            )) {
                throw "The workspace .venv RoCell entry-point binding is stale or outside this checkout: $($RocellObservedEntryPoints[$RocellOriginIndex])"
            }
        }

        & $RocellPython -I -m rocell --workspace $RocellWorkspace @RocellArguments
    }
    else {
        # The global-Python fallback remains available only for hardware-free
        # development commands before setup has been run.
        $env:PYTHONPATH = $RocellSource
        & $RocellPython -m rocell --workspace $RocellWorkspace @RocellArguments
    }
    $RocellExitCode = $LASTEXITCODE
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

exit $RocellExitCode
