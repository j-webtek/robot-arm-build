param(
    [Parameter(Mandatory = $true)]
    [string]$OutputDirectory
)

$ErrorActionPreference = 'Stop'
Add-Type -AssemblyName System.Speech
New-Item -ItemType Directory -Force -Path $OutputDirectory | Out-Null

$segments = @(
    'When AI moves real hardware, a wrong guess becomes real motion.',
    'Tactevra turns one request into one checked physical action.',
    'A fixed camera reads four board markers, placing every target in one shared frame.',
    'The model proposes the action, named target, coordinate frame, and confidence. Never motor commands.',
    'Deterministic gates stop stale or malformed plans before the arm can move.',
    'Units. Frame. Reach. Clearance. Freshness. Every gate must pass.',
    'Measured geometry resolves the H key into exact board coordinates.',
    'The arm carries the stylus and sends one bounded press.',
    'Telemetry confirms the target, while the host confirms the character H.',
    'That closes one shared contract, from intent to verified physical action.',
    'Tactevra. Physical intelligence, checked.'
)

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
$rates = @(1, 1, 1, 1, 1, 2, 1, 1, 1, 1, 1)

for ($index = 0; $index -lt $segments.Count; $index++) {
    $filename = 'voice_{0:d2}.wav' -f ($index + 1)
    $destination = Join-Path $OutputDirectory $filename
    $synth.Rate = $rates[$index]
    $synth.SetOutputToWaveFile($destination)
    $synth.Speak($segments[$index])
    $synth.SetOutputToNull()
}

$synth.Dispose()
Write-Output "TACTEVRA_VOICEOVER=$OutputDirectory"
