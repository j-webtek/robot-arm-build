[CmdletBinding()]
param(
    [Parameter(Position = 0)]
    [ValidateSet('verify', 'sync-readiness', 'report')]
    [string]$Command = 'verify',
    [switch]$Full,
    [switch]$ApplyGitHub,
    [string]$OutputDir = '.repository-operations'
)

$Arguments = @('scripts/maintain_repository.py', $Command)
if ($Full) { $Arguments += '--full' }
if ($ApplyGitHub) { $Arguments += '--apply-github' }
if ($Command -eq 'report') { $Arguments += @('--output-dir', $OutputDir) }
& python @Arguments
exit $LASTEXITCODE
