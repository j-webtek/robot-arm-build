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
    try { $digest = $sha.ComputeHash($bytes) } finally { $sha.Dispose() }
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
    try { $digest = $sha.ComputeHash($Bytes) } finally { $sha.Dispose() }
    return [System.BitConverter]::ToString($digest).Replace('-', '').ToLowerInvariant()
}

$resolvedIntake = (Resolve-Path -LiteralPath $IntakePath).Path
$document = Get-Content -LiteralPath $resolvedIntake -Raw -Encoding UTF8 |
    ConvertFrom-Json

Require-Equal $document.schema 'rocell.native_t105_active_feedback_intake.v1' 'schema'
Require-Equal $document.status 'READY_FOR_SEPARATE_ACTIVE_FEEDBACK_AUTHORIZATION' 'status'
Require-Equal $document.intake_sha256 $AuthorizedIntakeSha256 'intake SHA-256'
Require-Equal $document.host_id (Get-HostBinding) 'host identity'
Require-Equal $document.read_only_intake_sha256 '2d88fa8874088ce47b778343ea0ed07994bafb64267b8cd121765c52536ce1d9' 'read-only intake SHA-256'
Require-Equal $document.passive_qualification_sha256 'ac84722855d43e66e07d512bd60c3d19b2c468c0defe1505303f233bc4148aea' 'passive qualification SHA-256'
Require-Equal $document.endpoint.port_name 'COM7' 'COM endpoint'
Require-Equal $document.endpoint.usb_vid '10C4' 'USB VID'
Require-Equal $document.endpoint.usb_pid 'EA60' 'USB PID'
Require-Equal $document.endpoint.usb_serial_number '52E4E1E8337FEF119E92181CEDD322A4' 'USB serial'
Require-Equal ([int]$document.endpoint.baud_rate) 115200 'baud rate'
Require-Equal ([int]$document.endpoint.data_bits) 8 'data bits'
Require-Equal $document.endpoint.parity 'NONE' 'parity'
Require-Equal ([int]$document.endpoint.stop_bits) 1 'stop bits'
Require-Equal $document.endpoint.flow_control 'NONE' 'flow control'
Require-Equal ([int]$document.request_command_type) 105 'request command'
Require-Equal ([int]$document.expected_response_type) 1051 'response command'
Require-Equal $document.request_bytes_base64 'eyJUIjoxMDV9Cg==' 'request bytes'
Require-Equal ([int]$document.request_byte_count) 10 'request byte count'
Require-Equal $document.request_sha256 '2cace64403a9db92d57acd8814d55c833529c0341468529900bd89f089e1fa3c' 'request SHA-256'
Require-Equal ([double]$document.response_timeout_s) 1.0 'response timeout'
Require-Equal ([int]$document.maximum_response_lines) 1 'response line limit'
Require-Equal ([int]$document.maximum_response_line_bytes) 2048 'response byte limit'
Require-Equal ([int]$document.open_count_limit) 1 'open limit'
Require-Equal ([int]$document.close_count_limit) 1 'close limit'
Require-Equal ([int]$document.transport_write_count_limit) 1 'write limit'
Require-Equal ([int]$document.active_request_count_limit) 1 'request limit'
Require-Equal ([int]$document.movement_command_count_limit) 0 'movement limit'
Require-Equal ([int]$document.torque_command_count_limit) 0 'torque limit'
Require-Equal ([int]$document.t102_command_count_limit) 0 'T=102 limit'
foreach ($name in @(
    'buffer_purge_allowed', 'fallback_endpoint_allowed',
    'automatic_retry_allowed', 'dtr_assertion_allowed',
    'rts_assertion_allowed', 'controller_start_allowed',
    'active_feedback_authorized', 'endpoint_open_authorized',
    'transport_write_authorized', 'execution_authorized',
    'hardware_access', 'physical_authority'
)) { Require-Equal ([bool]$document.$name) $false $name }

$expectedOperations = @(
    'VERIFY_PINNED_IDENTITY_BEFORE_OPEN', 'OPEN_EXACT_ENDPOINT_ONCE',
    'VERIFY_QUIESCENT_RECEIVE_BUFFER', 'WRITE_EXACT_T105_REQUEST_ONCE',
    'READ_ONE_BOUNDED_T1051_RESPONSE', 'CLOSE_EXACT_ENDPOINT_ONCE',
    'VERIFY_PINNED_IDENTITY_AFTER_CLOSE'
)
Require-Equal (($document.operations -join '|')) (($expectedOperations -join '|')) 'operations'
$requestBytes = [Convert]::FromBase64String($document.request_bytes_base64)
Require-Equal (Get-BytesSha256 $requestBytes) $document.request_sha256 'decoded request SHA-256'
Require-Equal ([System.Text.Encoding]::UTF8.GetString($requestBytes)) "{`"T`":105}`n" 'decoded request text'
$identityBefore = Get-ExactEndpointIdentity $document.endpoint

if ($PreflightOnly) {
    [ordered]@{
        schema = 'rocell.arm064_active_feedback_preflight.v1'
        status = 'READY_NOT_OPENED_OR_WRITTEN'
        intake_sha256 = $AuthorizedIntakeSha256
        endpoint_sha256 = $document.endpoint_sha256
        request_sha256 = $document.request_sha256
        identity = $identityBefore
        open_attempts = 0
        write_attempts = 0
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
$serialPort.WriteTimeout = 1000

$startedUtc = [DateTime]::UtcNow.ToString('yyyy-MM-ddTHH:mm:ss.fffZ')
$lifecycle = [System.Diagnostics.Stopwatch]::StartNew()
$responseClock = [System.Diagnostics.Stopwatch]::new()
$openAttempts = 0
$writeAttempts = 0
$readAttempts = 0
$closeAttempts = 0
$openSucceeded = $false
$closeConfirmed = $false
$identityAfter = $null
$preRequestBufferedBytes = $null
$responseBytes = [byte[]]@()
$responseObject = $null
$status = 'ACTIVE_FEEDBACK_COMPLETED'
$failure = $null
$outboundBytes = 0

try {
    $openAttempts = 1
    $serialPort.Open()
    $openSucceeded = $serialPort.IsOpen
    if (-not $openSucceeded) { throw 'Serial endpoint did not report open' }
    $preRequestBufferedBytes = $serialPort.BytesToRead
    if ($preRequestBufferedBytes -ne 0) {
        throw "Receive buffer contained $preRequestBufferedBytes byte(s) before T=105"
    }
    $writeAttempts = 1
    $serialPort.Write($requestBytes, 0, $requestBytes.Length)
    $outboundBytes = $requestBytes.Length
    $responseClock.Start()
    $readAttempts = 1
    $partial = [System.Collections.Generic.List[byte]]::new()
    while ($responseClock.Elapsed.TotalSeconds -lt 1.0) {
        $remainingMs = [Math]::Max(
            1, [Math]::Ceiling((1.0 - $responseClock.Elapsed.TotalSeconds) * 1000)
        )
        $serialPort.ReadTimeout = [int]$remainingMs
        try { $value = $serialPort.ReadByte() } catch [System.TimeoutException] { break }
        if ($value -lt 0) { break }
        $partial.Add([byte]$value)
        if ($partial.Count -gt 2048) { throw 'T=1051 response exceeded 2048 bytes' }
        if ($value -eq 10) { break }
    }
    $responseClock.Stop()
    if ($partial.Count -eq 0 -or $partial[$partial.Count - 1] -ne 10) {
        throw 'One newline-terminated T=1051 response was not received in time'
    }
    $responseBytes = $partial.ToArray()
    try {
        $responseText = [System.Text.Encoding]::UTF8.GetString($responseBytes)
        $responseObject = $responseText | ConvertFrom-Json
    } catch { throw 'Response was not valid T=1051 JSON' }
    Require-Equal ([int]$responseObject.T) 1051 'response type'
    foreach ($joint in @('b', 's', 'e', 't', 'r', 'g')) {
        $property = $responseObject.PSObject.Properties[$joint]
        if ($null -eq $property -or $property.Value -is [bool] -or
            $property.Value -isnot [ValueType] -or
            [double]::IsNaN([double]$property.Value) -or
            [double]::IsInfinity([double]$property.Value)) {
            throw "Response lacks finite numeric joint field $joint"
        }
    }
} catch {
    $status = 'ACTIVE_FEEDBACK_FAILED_TERMINAL'
    $failure = $_.Exception.GetType().FullName + ': ' + $_.Exception.Message
} finally {
    $responseClock.Stop()
    $lifecycle.Stop()
    $closeAttempts = 1
    try {
        $serialPort.Close()
        $closeConfirmed = -not $serialPort.IsOpen
    } catch {
        $closeConfirmed = $false
        if ($null -eq $failure) {
            $failure = $_.Exception.GetType().FullName + ': ' + $_.Exception.Message
            $status = 'ACTIVE_FEEDBACK_FAILED_TERMINAL'
        }
    }
    $serialPort.Dispose()
}
try { $identityAfter = Get-ExactEndpointIdentity $document.endpoint } catch {
    if ($null -eq $failure) {
        $failure = $_.Exception.GetType().FullName + ': ' + $_.Exception.Message
        $status = 'ACTIVE_FEEDBACK_FAILED_TERMINAL'
    }
}

$finishedUtc = [DateTime]::UtcNow.ToString('yyyy-MM-ddTHH:mm:ss.fffZ')
$receipt = [ordered]@{
    schema = 'rocell.native_t105_active_feedback_qualification.v1'
    status = $status
    intake_sha256 = $AuthorizedIntakeSha256
    intake_id = $document.intake_id
    host_id = $document.host_id
    endpoint_sha256 = $document.endpoint_sha256
    request_sha256 = $document.request_sha256
    started_utc = $startedUtc
    finished_utc = $finishedUtc
    lifecycle_elapsed_ms = [Math]::Round($lifecycle.Elapsed.TotalMilliseconds, 3)
    response_elapsed_ms = [Math]::Round($responseClock.Elapsed.TotalMilliseconds, 3)
    identity_before = $identityBefore
    identity_after = $identityAfter
    open_attempts = $openAttempts
    open_succeeded = $openSucceeded
    pre_request_buffered_bytes = $preRequestBufferedBytes
    write_attempts = $writeAttempts
    outbound_bytes = $outboundBytes
    active_requests = $(if ($outboundBytes -eq 10) { 1 } else { 0 })
    read_attempts = $readAttempts
    response_line_count = $(if ($responseBytes.Length -gt 0) { 1 } else { 0 })
    response_bytes = $responseBytes.Length
    response_base64 = $(if ($responseBytes.Length -gt 0) { [Convert]::ToBase64String($responseBytes) } else { '' })
    response_sha256 = $(if ($responseBytes.Length -gt 0) { Get-BytesSha256 $responseBytes } else { $null })
    response = $responseObject
    close_attempts = $closeAttempts
    close_confirmed = $closeConfirmed
    movement_commands = 0
    torque_commands = 0
    t102_commands = 0
    retry_count = 0
    purge_count = 0
    fallback_count = 0
    dtr_asserted = $false
    rts_asserted = $false
    controller_start_performed = $false
    failure = $failure
    execution_authorized = $false
    physical_authority = $false
}
$json = $receipt | ConvertTo-Json -Depth 12
$utf8 = [System.Text.UTF8Encoding]::new($false)
$stream = [System.IO.File]::Open(
    $resolvedOutput, [System.IO.FileMode]::CreateNew,
    [System.IO.FileAccess]::Write, [System.IO.FileShare]::None
)
try {
    $bytes = $utf8.GetBytes($json + "`n")
    $stream.Write($bytes, 0, $bytes.Length)
    $stream.Flush($true)
} finally { $stream.Dispose() }
$json
if ($status -ne 'ACTIVE_FEEDBACK_COMPLETED' -or -not $closeConfirmed) { exit 1 }
