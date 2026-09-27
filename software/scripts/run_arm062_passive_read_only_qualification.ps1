param(
    [Parameter(Mandatory = $true)]
    [string]$IntakePath,

    [Parameter(Mandatory = $true)]
    [ValidatePattern('^[0-9a-f]{64}$')]
    [string]$AuthorizedIntakeSha256,

    [string]$OutputPath,

    [switch]$PreflightOnly
)

$ErrorActionPreference = 'Stop'
Set-StrictMode -Version Latest

function Require-Equal {
    param($Actual, $Expected, [string]$Label)
    if ($Actual -cne $Expected) {
        throw "$Label differs from the authorized intake"
    }
}

function Get-HostBinding {
    $hostName = [System.Net.Dns]::GetHostName().ToUpperInvariant()
    $bytes = [System.Text.Encoding]::UTF8.GetBytes($hostName)
    $sha = [System.Security.Cryptography.SHA256]::Create()
    try {
        $digest = $sha.ComputeHash($bytes)
    } finally {
        $sha.Dispose()
    }
    return 'windows-host-sha256-' + (
        [System.BitConverter]::ToString($digest).Replace('-', '').ToLowerInvariant()
    )
}

function Get-ExactEndpointIdentity {
    param($Endpoint)
    $expectedInstance = 'USB\VID_{0}&PID_{1}\{2}' -f (
        $Endpoint.usb_vid, $Endpoint.usb_pid, $Endpoint.usb_serial_number
    )
    $matches = @(
        Get-PnpDevice -Class Ports -PresentOnly |
            Where-Object {
                $_.InstanceId -ceq $expectedInstance -and
                $_.FriendlyName -match ('\(' + [regex]::Escape($Endpoint.port_name) + '\)$')
            }
    )
    if ($matches.Count -ne 1 -or $matches[0].Status -cne 'OK') {
        throw 'Exact pinned PnP endpoint is not uniquely present and healthy'
    }
    return [ordered]@{
        status = $matches[0].Status
        friendly_name = $matches[0].FriendlyName
        instance_id = $matches[0].InstanceId
    }
}

function Get-BytesSha256 {
    param([byte[]]$Bytes)
    $sha = [System.Security.Cryptography.SHA256]::Create()
    try {
        $digest = $sha.ComputeHash($Bytes)
    } finally {
        $sha.Dispose()
    }
    return [System.BitConverter]::ToString($digest).Replace('-', '').ToLowerInvariant()
}

$resolvedIntake = (Resolve-Path -LiteralPath $IntakePath).Path
$document = Get-Content -LiteralPath $resolvedIntake -Raw -Encoding UTF8 |
    ConvertFrom-Json

Require-Equal $document.schema 'rocell.native_t102_read_only_endpoint_intake.v1' 'schema'
Require-Equal $document.status 'READY_FOR_SEPARATE_READ_ONLY_AUTHORIZATION' 'status'
Require-Equal $document.intake_sha256 $AuthorizedIntakeSha256 'intake SHA-256'
Require-Equal $document.host_id (Get-HostBinding) 'host identity'
Require-Equal $document.endpoint.port_name 'COM7' 'COM endpoint'
Require-Equal $document.endpoint.usb_vid '10C4' 'USB VID'
Require-Equal $document.endpoint.usb_pid 'EA60' 'USB PID'
Require-Equal $document.endpoint.usb_serial_number '52E4E1E8337FEF119E92181CEDD322A4' 'USB serial'
Require-Equal ([int]$document.endpoint.baud_rate) 115200 'baud rate'
Require-Equal ([int]$document.endpoint.data_bits) 8 'data bits'
Require-Equal $document.endpoint.parity 'NONE' 'parity'
Require-Equal ([int]$document.endpoint.stop_bits) 1 'stop bits'
Require-Equal $document.endpoint.flow_control 'NONE' 'flow control'
Require-Equal ([double]$document.passive_read_timeout_s) 1.0 'read timeout'
Require-Equal ([int]$document.maximum_passive_lines) 4 'line limit'
Require-Equal ([int]$document.maximum_line_bytes) 2048 'line byte limit'
Require-Equal ([int]$document.open_count_limit) 1 'open limit'
Require-Equal ([int]$document.close_count_limit) 1 'close limit'
Require-Equal ([int]$document.transport_write_count_limit) 0 'write limit'
Require-Equal ([int]$document.active_request_count_limit) 0 'request limit'
Require-Equal ([int]$document.movement_command_count_limit) 0 'movement limit'
Require-Equal ([int]$document.torque_command_count_limit) 0 'torque limit'
foreach ($name in @(
    'buffer_purge_allowed', 'fallback_endpoint_allowed',
    'automatic_retry_allowed', 'dtr_assertion_allowed',
    'rts_assertion_allowed', 'read_only_endpoint_authorized',
    'endpoint_open_authorized', 'controller_start_authorized',
    'transport_write_authorized', 'execution_authorized',
    'hardware_access', 'physical_authority'
)) {
    Require-Equal ([bool]$document.$name) $false $name
}

$expectedOperations = @(
    'VERIFY_PINNED_IDENTITY_BEFORE_OPEN',
    'OPEN_EXACT_ENDPOINT_ONCE',
    'VERIFY_PINNED_IDENTITY_AFTER_OPEN',
    'PASSIVE_READ_BOUNDED_LINES',
    'CLOSE_EXACT_ENDPOINT_ONCE'
)
Require-Equal (($document.operations -join '|')) (($expectedOperations -join '|')) 'operations'
$identityBefore = Get-ExactEndpointIdentity $document.endpoint

if ($PreflightOnly) {
    [ordered]@{
        schema = 'rocell.arm062_passive_read_only_preflight.v1'
        status = 'READY_NOT_OPENED'
        intake_sha256 = $AuthorizedIntakeSha256
        endpoint_sha256 = $document.endpoint_sha256
        identity = $identityBefore
        open_attempts = 0
        close_attempts = 0
        outbound_bytes = 0
        hardware_access = $false
        physical_authority = $false
    } | ConvertTo-Json -Depth 8
    exit 0
}

if ([string]::IsNullOrWhiteSpace($OutputPath)) {
    throw 'OutputPath is required for the authorized live qualification'
}
$resolvedOutputParent = (Resolve-Path -LiteralPath (Split-Path -Parent $OutputPath)).Path
$resolvedOutput = Join-Path $resolvedOutputParent (Split-Path -Leaf $OutputPath)
if (Test-Path -LiteralPath $resolvedOutput) {
    throw 'Qualification output already exists'
}

$serialPort = [System.IO.Ports.SerialPort]::new()
$serialPort.PortName = $document.endpoint.port_name
$serialPort.BaudRate = 115200
$serialPort.DataBits = 8
$serialPort.Parity = [System.IO.Ports.Parity]::None
$serialPort.StopBits = [System.IO.Ports.StopBits]::One
$serialPort.Handshake = [System.IO.Ports.Handshake]::None
$serialPort.DtrEnable = $false
$serialPort.RtsEnable = $false
$serialPort.NewLine = "`n"
$serialPort.ReadTimeout = 1000

$startedUtc = [DateTime]::UtcNow.ToString('yyyy-MM-ddTHH:mm:ss.fffZ')
$stopwatch = [System.Diagnostics.Stopwatch]::StartNew()
$openAttempts = 0
$closeAttempts = 0
$openSucceeded = $false
$closeConfirmed = $false
$identityAfter = $null
$lines = [System.Collections.Generic.List[object]]::new()
$partial = [System.Collections.Generic.List[byte]]::new()
$captureStatus = 'PASSIVE_CAPTURE_COMPLETED'
$failure = $null

try {
    $openAttempts = 1
    $serialPort.Open()
    $openSucceeded = $serialPort.IsOpen
    if (-not $openSucceeded) {
        throw 'Serial endpoint did not report open'
    }
    $identityAfter = Get-ExactEndpointIdentity $document.endpoint
    while ($stopwatch.Elapsed.TotalSeconds -lt 1.0 -and $lines.Count -lt 4) {
        $remainingMs = [Math]::Max(
            1, [Math]::Ceiling((1.0 - $stopwatch.Elapsed.TotalSeconds) * 1000)
        )
        $serialPort.ReadTimeout = [int]$remainingMs
        try {
            $value = $serialPort.ReadByte()
        } catch [System.TimeoutException] {
            break
        }
        if ($value -lt 0) {
            break
        }
        $partial.Add([byte]$value)
        if ($partial.Count -gt 2048) {
            $captureStatus = 'PASSIVE_LINE_LIMIT_EXCEEDED'
            break
        }
        if ($value -eq 10) {
            $bytes = $partial.ToArray()
            $lines.Add([ordered]@{
                ordinal = $lines.Count
                bytes = $bytes.Length
                base64 = [Convert]::ToBase64String($bytes)
                sha256 = Get-BytesSha256 $bytes
                newline_terminated = $true
            })
            $partial.Clear()
        }
    }
    if ($partial.Count -gt 0 -and $partial.Count -le 2048) {
        $bytes = $partial.ToArray()
        $lines.Add([ordered]@{
            ordinal = $lines.Count
            bytes = $bytes.Length
            base64 = [Convert]::ToBase64String($bytes)
            sha256 = Get-BytesSha256 $bytes
            newline_terminated = $false
        })
    }
} catch {
    $captureStatus = 'PASSIVE_CAPTURE_FAILED'
    $failure = $_.Exception.GetType().FullName + ': ' + $_.Exception.Message
} finally {
    $stopwatch.Stop()
    $closeAttempts = 1
    try {
        $serialPort.Close()
        $closeConfirmed = -not $serialPort.IsOpen
    } catch {
        $closeConfirmed = $false
        if ($null -eq $failure) {
            $failure = $_.Exception.GetType().FullName + ': ' + $_.Exception.Message
            $captureStatus = 'PASSIVE_CAPTURE_FAILED'
        }
    }
    $serialPort.Dispose()
}

$finishedUtc = [DateTime]::UtcNow.ToString('yyyy-MM-ddTHH:mm:ss.fffZ')
$receipt = [ordered]@{
    schema = 'rocell.native_t102_read_only_endpoint_qualification.v1'
    status = $captureStatus
    intake_sha256 = $AuthorizedIntakeSha256
    intake_id = $document.intake_id
    host_id = $document.host_id
    endpoint_sha256 = $document.endpoint_sha256
    started_utc = $startedUtc
    finished_utc = $finishedUtc
    elapsed_ms = [Math]::Round($stopwatch.Elapsed.TotalMilliseconds, 3)
    identity_before = $identityBefore
    identity_after = $identityAfter
    open_attempts = $openAttempts
    open_succeeded = $openSucceeded
    close_attempts = $closeAttempts
    close_confirmed = $closeConfirmed
    maximum_passive_lines = 4
    maximum_line_bytes = 2048
    passive_read_timeout_s = 1.0
    captured_lines = @($lines)
    captured_line_count = $lines.Count
    outbound_bytes = 0
    active_requests = 0
    movement_commands = 0
    torque_commands = 0
    retry_count = 0
    purge_count = 0
    dtr_asserted = $false
    rts_asserted = $false
    failure = $failure
    controller_start_authorized = $false
    transport_write_authorized = $false
    execution_authorized = $false
    physical_authority = $false
}
$json = $receipt | ConvertTo-Json -Depth 12
$utf8 = [System.Text.UTF8Encoding]::new($false)
$stream = [System.IO.File]::Open(
    $resolvedOutput,
    [System.IO.FileMode]::CreateNew,
    [System.IO.FileAccess]::Write,
    [System.IO.FileShare]::None
)
try {
    $bytes = $utf8.GetBytes($json + "`n")
    $stream.Write($bytes, 0, $bytes.Length)
    $stream.Flush($true)
} finally {
    $stream.Dispose()
}
$json
if ($captureStatus -ne 'PASSIVE_CAPTURE_COMPLETED' -or -not $closeConfirmed) {
    exit 1
}
