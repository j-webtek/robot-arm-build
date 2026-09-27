param(
    [Parameter(Mandatory = $true)]
    [string]$OutputDirectory
)

$ErrorActionPreference = 'Stop'
Add-Type -AssemblyName System.Speech
New-Item -ItemType Directory -Force -Path $OutputDirectory | Out-Null

$segments = @(
    'When AI moves real hardware, usually right isn''t good enough. A wrong guess isn''t a typo. It''s a motion.',
    'Tactevra turns one request into one checked physical action.',
    'First, a fixed camera reads marker tags on the board, so every target is measured in one shared frame.',
    'Next, the model proposes: an action, a named target, a frame, and its confidence. Never raw motor commands.',
    'Then deterministic gates check every proposal. A stale or malformed plan is rejected before anything moves.',
    'Units. Frame. Reach. Clearance. Freshness. Only a plan that passes every gate is admitted.',
    'Measured geometry turns the H key into exact millimeters, through the camera, board, and device frames.',
    'One controller, and only one, sends a single bounded motion.',
    'Telemetry and the camera confirm the result before the next action is allowed.',
    'One shared contract, from user intent to verified physical action.',
    'Tactevra.'
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
$rates = @(4, 1, 1, 2, 1, 4, 1, 1, 1, 1, 1)

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
