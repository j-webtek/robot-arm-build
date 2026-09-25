"""Deadline-bounded native HTTP feedback adapter; no motion command surface.

Nonblocking sockets avoid the per-read timeout reset of HTTPConnection. Every
connect/write/read shares one absolute deadline, including trickled headers.
Only the pinned T105 GET is accepted. Movement admission remains a separate,
unfinished integration: existing native permits are USB-identity-bound.
"""
import errno
import io
import math
import select
import socket
import time

from .arm_wifi_feedback import ADDRESS, PATH, probe

IO_BUDGET_S = .8  # Leaves room for 150-ms cooldown inside the 1-second gap policy.
HEADER_LIMIT = 8192
BODY_LIMIT = 2048


class DeadlineFeedbackConnection:
    """Minimal probe-compatible connection, never redirects, retries or uses DNS."""

    _minimum_body_length = 1

    def __init__(self, host, timeout=2, *, cancelled=lambda:False,
                 deadline=None, clock=time.perf_counter):
        if host!=ADDRESS:
            raise ValueError('Pinned feedback address required')
        self._clock=clock
        now=clock()
        if deadline is not None and (type(deadline) not in (int,float) or not math.isfinite(deadline)):
            raise ValueError('Finite absolute deadline required')
        self._deadline=min(now+IO_BUDGET_S,deadline) if deadline is not None else now+IO_BUDGET_S
        self._cancelled=cancelled
        self._socket=None;self._attempted=False;self._body=None
        self.response_metadata={}

    def _check(self):
        if self._cancelled():raise ValueError('CANCELLED')
        if self._clock()>=self._deadline:raise TimeoutError()

    def _ready(self, *, writing=False):
        while True:
            self._check()
            timeout=min(.025,max(0,self._deadline-self._clock()))
            read,write,errors=select.select([] if writing else [self._socket],
                [self._socket] if writing else [],[self._socket],timeout)
            self._check()
            if errors:raise ConnectionError()
            if read or write:return

    def request(self, method, path, headers=None):
        if self._attempted or method!='GET' or path!=PATH:
            raise ValueError('Exactly one fixed feedback request required')
        self._send_path(PATH)

    def _send_path(self, path):
        if self._attempted:raise ValueError('Request already attempted')
        self._attempted=True
        self._check()
        self._socket=socket.socket(socket.AF_INET,socket.SOCK_STREAM)
        self._socket.setblocking(False)
        error=self._socket.connect_ex((ADDRESS,80))
        if error not in (0,errno.EINPROGRESS,errno.EWOULDBLOCK,errno.EALREADY,10035,10036,10037):
            raise OSError(error,'CONNECT_FAILED')
        self._ready(writing=True)
        error=self._socket.getsockopt(socket.SOL_SOCKET,socket.SO_ERROR)
        if error:raise OSError(error,'CONNECT_FAILED')
        # Ignore caller-supplied headers. No credential or arbitrary path injection.
        payload=(f'GET {path} HTTP/1.1\r\nHost: {ADDRESS}\r\n'
                 'Connection: close\r\nCache-Control: no-cache\r\n\r\n').encode('ascii')
        view=memoryview(payload)
        while view:
            self._ready(writing=True)
            try:count=self._socket.send(view)
            except BlockingIOError:continue
            if count<=0:raise ConnectionError()
            view=view[count:]

    def getresponse(self):
        if not self._attempted or self._socket is None or self._body is not None:
            raise ValueError('Response state invalid')
        raw=bytearray();boundary=None;length=None
        while True:
            self._ready()
            try:chunk=self._socket.recv(4096)
            except BlockingIOError:continue
            if not chunk:raise ConnectionError()
            raw.extend(chunk)
            if boundary is None:
                marker=raw.find(b'\r\n\r\n')
                if marker<0:
                    if len(raw)>HEADER_LIMIT:raise ValueError('Oversized headers')
                    continue
                boundary=marker+4
                if boundary>HEADER_LIMIT:raise ValueError('Oversized headers')
                length=self._parse_headers(bytes(raw[:marker]))
            if len(raw)-boundary>length:raise ValueError('Unexpected response suffix')
            if len(raw)-boundary==length:
                self._check()
                self._body=io.BytesIO(raw[boundary:])
                return self

    def _parse_headers(self, raw):
        lines=raw.split(b'\r\n')
        parts=lines[0].split(b' ',2)
        if len(parts)>=2 and len(parts[1])==3 and parts[1].isdigit():
            self.response_metadata['http_status']=int(parts[1])
        if len(parts)<2 or parts[0] not in (b'HTTP/1.0',b'HTTP/1.1') or parts[1]!=b'200':
            raise ValueError('HTTP_STATUS_NOT_200')
        fields={}
        for line in lines[1:]:
            if b':' not in line or line[:1] in (b' ',b'\t'):raise ValueError('Invalid header')
            name,value=line.split(b':',1);name=name.lower();value=value.strip()
            if name in fields:raise ValueError('Duplicate header')
            fields[name]=value
        # Installed firmware uses Content-Length. Unsupported framing fails closed.
        if b'transfer-encoding' in fields:raise ValueError('Unsupported framing')
        value=fields.get(b'content-length',b'')
        if not value or len(value)>5 or not value.isdigit():raise ValueError('Length required')
        length=int(value)
        self.response_metadata['content_length']=length
        if not self._minimum_body_length<=length<=BODY_LIMIT:raise ValueError('Response size exceeded')
        self.status=200
        return length

    def read1(self, count):
        self._check()
        return self._body.read(count)

    def close(self):
        if self._socket is not None:
            self._socket.close();self._socket=None


def bounded_probe(*, cancelled=lambda:False, retain_response=False, deadline=None):
    report=probe(cancelled=cancelled,retain_response=retain_response,
        connection_factory=lambda host,timeout:DeadlineFeedbackConnection(host,timeout,
            cancelled=cancelled,deadline=deadline))
    report['http_io_deadline_budget_s']=IO_BUDGET_S
    if report.get('failure_phase')=='RESPONSE_HEADERS':
        report['failure_phase']='HTTP_HEADERS_OR_BODY'
    report['http_deadline_scope']='CONNECT_SEND_HEADERS_BODY_SHARED_ABSOLUTE'
    return report


def observe_bounded(*, cancelled=lambda:False):
    from .arm_wifi_observation import observe_intermediate
    report=observe_intermediate(cancelled=cancelled,run_probe=bounded_probe)
    report['transport_variant']='NONBLOCKING_ABSOLUTE_HTTP_DEADLINE'
    return report
