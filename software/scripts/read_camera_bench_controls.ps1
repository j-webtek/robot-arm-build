[CmdletBinding()]
param([Parameter(Mandatory=$true)][string]$DevicePath)
$ErrorActionPreference = 'Stop'
# A separate bench utility; never import its JSON as commissioned evidence.
Add-Type -Path (Join-Path $PSScriptRoot 'CameraBenchControls.cs')
[RoCellBench.CameraBenchControls]::Read('Arducam B0477 (USB3 20MP)', $DevicePath) | ConvertTo-Json -Depth 6
