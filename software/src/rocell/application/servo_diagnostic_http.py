"""Narrow, read-only LAN adapter for the reviewed diagnostic HTTP endpoints.

Construction does not connect. Callers must establish installed compatibility
before collection. HTTP provides no authenticated provenance; returned evidence
still requires contract assessment. There is no command route or fallback to /js.
"""
import ipaddress
import math
import re
import socket
import time

from .servo_transport_snapshot import STATUS, RECORD


class DiagnosticHTTPReader:
    """One connection per GET; an I/O/protocol failure latches this reader closed."""

    def __init__(self, address, port=80):
        # Numeric IPv4 avoids DNS/proxy changes and bounds connection setup.
        if type(address) is not str:
            raise ValueError('Explicit numeric LAN address required')
        ip = ipaddress.IPv4Address(address)
        networks = ('10.0.0.0/8', '172.16.0.0/12', '192.168.0.0/16', '127.0.0.0/8')
        if not any(ip in ipaddress.IPv4Network(net) for net in networks):
            raise ValueError('Only private LAN or loopback destinations supported')
        if type(port) is not int or not 1 <= port <= 65535:
            raise ValueError('Invalid port')
        self.address, self.port = str(ip), port
        self.failed = False

    def __call__(self, path, *, maximum_bytes, timeout_seconds):
        if self.failed:
            raise ValueError('Diagnostic reader faulted; no automatic retry')
        allowed = path == STATUS or (type(path) is str and path in {
            RECORD + str(index) for index in range(16)})
        if (not allowed or type(maximum_bytes) is not int
                or not 1 <= maximum_bytes <= (512 if path == STATUS else 2304)
                or type(timeout_seconds) not in (int, float)
                or not math.isfinite(timeout_seconds) or not 0 < timeout_seconds <= 3):
            self.failed = True
            raise ValueError('Unsupported diagnostic request or budget')
        return self._get(path,maximum_bytes=maximum_bytes,timeout_seconds=timeout_seconds)

    def _get(self,path,*,maximum_bytes,timeout_seconds):
        """Internal bounded exchange; public adapters enforce route permissions."""
        deadline = time.monotonic() + timeout_seconds

        def remaining():
            value = deadline - time.monotonic()
            if value <= 0:
                raise TimeoutError('Diagnostic request deadline exceeded')
            return value

        try:
            with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as connection:
                connection.settimeout(remaining())
                connection.connect((self.address, self.port))
                request = (f'GET {path} HTTP/1.0\r\nHost: {self.address}:{self.port}\r\n'
                           'Accept: application/json\r\nAccept-Encoding: identity\r\n'
                           'Connection: close\r\n\r\n').encode('ascii')
                connection.settimeout(remaining())
                connection.sendall(request)

                def receive(count):
                    connection.settimeout(remaining())
                    data = connection.recv(count)
                    remaining()  # Total deadline, not a fresh budget per byte.
                    if not data:
                        raise ValueError('Truncated diagnostic response')
                    return data

                header = bytearray()
                while not header.endswith(b'\r\n\r\n'):
                    if len(header) >= 8192:
                        raise ValueError('Diagnostic header budget exceeded')
                    header.extend(receive(1))
                length = _content_length(bytes(header), maximum_bytes)
                body = bytearray()
                while len(body) < length:
                    body.extend(receive(length-len(body)))
                return bytes(body)
        except (OSError, ValueError):
            self.failed = True
            raise


def _content_length(header, maximum, *, expected_status=200):
    """Accept the fixed-length JSON format emitted by the pinned WebServer."""
    lines = header[:-4].split(b'\r\n')
    status=str(expected_status).encode('ascii')
    if not re.fullmatch(rb'HTTP/1\.[01] '+status+rb'(?: [\x20-\x7e]*)?', lines[0]):
        raise ValueError('Diagnostic endpoint unavailable; redirects are not followed')
    fields = {}
    for line in lines[1:]:
        name, separator, value = line.partition(b':')
        if (not separator or not re.fullmatch(rb'[A-Za-z0-9-]+', name)
                or any(byte < 32 or byte > 126 for byte in value)):
            raise ValueError('Malformed diagnostic response header')
        name = name.lower()
        if name in fields:
            raise ValueError('Duplicate diagnostic response header')
        fields[name] = value.strip()
    if b'transfer-encoding' in fields or b'content-encoding' in fields:
        raise ValueError('Encoded diagnostic responses are unsupported')
    if fields.get(b'content-type', b'').split(b';')[0].strip().lower() != b'application/json':
        raise ValueError('Diagnostic JSON content type required')
    encoded = fields.get(b'content-length', b'')
    if not re.fullmatch(rb'[0-9]{1,4}', encoded) or not 1 <= int(encoded) <= maximum:
        raise ValueError('Diagnostic body budget exceeded or length absent')
    return int(encoded)
