param(
    [Parameter(Mandatory = $true)]
    [string]$OutputDirectory
)

$ErrorActionPreference = 'Stop'
Add-Type -AssemblyName System.Speech
New-Item -ItemType Directory -Force -Path $OutputDirectory | Out-Null

$manifestPath = Join-Path $PSScriptRoot 'storyboard_v21_shots.json'
$manifest = Get-Content -LiteralPath $manifestPath -Raw | ConvertFrom-Json
$synth = [System.Speech.Synthesis.SpeechSynthesizer]::new()
$preferredVoices = @('Microsoft Mark', 'Microsoft David Desktop', 'Microsoft David')
$installed = @($synth.GetInstalledVoices() | ForEach-Object { $_.VoiceInfo.Name })
foreach ($voice in $preferredVoices) {
    if ($installed -contains $voice) {
        $synth.SelectVoice($voice)
        break
    }
}
$synth.Volume = 100

foreach ($cue in $manifest.narration) {
    $filename = 'voice_{0:d2}.wav' -f [int]$cue.id
    $destination = Join-Path $OutputDirectory $filename
    $window = [double]$cue.end - [double]$cue.start
    $wordCount = (($cue.text -split '\s+') | Where-Object { $_ }).Count
    $wordsPerMinute = 60.0 * $wordCount / [Math]::Max(1.0, $window - 0.25)
    $synth.Rate = if ($wordsPerMinute -gt 190) { 2 } elseif ($wordsPerMinute -gt 165) { 1 } else { 0 }
    $synth.SetOutputToWaveFile($destination)
    $synth.Speak([string]$cue.text)
    $synth.SetOutputToNull()
}

$synth.Dispose()
Write-Output "TACTEVRA_STORYBOARD_VOICEOVER=$OutputDirectory"
