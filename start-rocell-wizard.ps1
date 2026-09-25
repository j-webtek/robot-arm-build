[CmdletBinding()]
param(
    [ValidateSet('rehearsal', 'physical')]
    [string] $Mode = 'rehearsal',
    [string] $CellId = 'CELL-A',
    [ValidateSet('browser', 'terminal')]
    [string] $Ui = 'browser',
    [string] $ExportDirectory,
    [ValidateRange(0, 65535)]
    [int] $Port = 0,
    [switch] $NoBrowser,
    [switch] $Check
)

$ErrorActionPreference = 'Stop'
$RocellWizardWorkspace = Split-Path -Parent $MyInvocation.MyCommand.Path
$RocellWizardLauncher = Join-Path $RocellWizardWorkspace 'rocell.ps1'

# The existing launcher verifies the interpreter and checkout. This new entry
# point never installs drivers/dependencies or silently changes legacy startup.
# Rehearsal is the default. Startup never opens a device or powers hardware;
# any eligible USB baseline query is a separate, explicitly reviewed action.
$RocellWizardArguments = @(
    'physical-onboard', 'wizard', '--mode', $Mode,
    '--cell-id', $CellId, '--port', [string] $Port, '--ui', $Ui
)
if ($ExportDirectory) {
    $RocellWizardArguments += @('--export-dir', $ExportDirectory)
}
if ($Check) {
    $RocellWizardArguments += @('--check', '--json')
}
elseif (-not $NoBrowser -and $Ui -eq 'browser') {
    $RocellWizardArguments += '--open-browser'
}

& $RocellWizardLauncher @RocellWizardArguments
if ($LASTEXITCODE -ne 0) {
    throw "RoCell wizard exited with code $LASTEXITCODE. Inspect the preceding diagnosis; no automatic retry is attempted."
}
