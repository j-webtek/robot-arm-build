"""Restricted, no-retry HTTP adapter; construction performs no network I/O.

No live CLI is exposed. The caller must obtain approval and verify installed
compatibility before using this transport. HTTP responses are not authenticated.
"""
import hashlib
import math
import re
import socket
import time
from .servo_diagnostic_http import DiagnosticHTTPReader, _content_length


class ShoulderSessionHTTP:
    def __init__(self, address, port=80, *, socket_factory=socket.socket, monotonic=time.monotonic,
                 settling_capability=False, local_step_capability=False):
        checked=DiagnosticHTTPReader(address,port)
        self.address,self.port=checked.address,checked.port
        self.socket_factory,self.monotonic=socket_factory,monotonic
        self.failed=False;self.attempts=set()
        self.settling_capability=settling_capability is True
        self.local_step_capability=local_step_capability is True

    def __call__(self, method, path, body, timeout):
        if self.failed:raise ValueError('Transport faulted; no retry')
        try:
            prefix='/rocell/shoulder-session/'
            routes={'prepare':'POST','start':'POST','receipt':'POST','status':'GET','record':'GET'}
            local=isinstance(path,str) and path.startswith('/rocell/local-step/')
            if local:
                if not self.local_step_capability:raise ValueError('Local step capability not enabled')
                prefix='/rocell/local-step/'
                routes={'prepare':'POST','authorize':'POST','receipt':'POST','status':'GET','record':'GET'}
            settling=isinstance(path,str) and path.startswith('/rocell/shoulder-settling/')
            if settling:
                if not self.settling_capability:raise ValueError('Settling capability not enabled')
                prefix='/rocell/shoulder-settling/'
                routes={'start':'POST','receipt':'POST','status':'GET','record':'GET'}
            suffix=path[len(prefix):] if isinstance(path,str) and path.startswith(prefix) else ''
            if (routes.get(suffix)!=method or type(body) is not bytes
                    or type(timeout) not in (int,float) or not math.isfinite(timeout)
                    or not 0<timeout<=3):raise ValueError('Unsupported request')
            if suffix in ('prepare','status','record'):
                if body:raise ValueError('Body not allowed')
            elif not re.fullmatch(rb'[0-9a-f]+',body) or len(body)%2 or len(body)>(4400 if local and suffix=='authorize' else 1024):
                raise ValueError('Bounded hexadecimal body required')
            if (suffix=='receipt' or (settling and suffix=='start')) and len(body)!=248:raise ValueError('Exact receipt required')
            if method=='POST':
                identity=(path,hashlib.sha256(body).digest() if suffix=='receipt' else b'')
                if identity in self.attempts:raise ValueError('Request already attempted')
                self.attempts.add(identity)  # Consume before socket creation/send.
            deadline=self.monotonic()+timeout

            def remaining():
                value=deadline-self.monotonic()
                if value<=0:raise TimeoutError('Total HTTP deadline')
                return value

            with self.socket_factory(socket.AF_INET,socket.SOCK_STREAM) as connection:
                connection.settimeout(remaining());connection.connect((self.address,self.port))
                request=(f'{method} {path} HTTP/1.1\r\nHost: {self.address}:{self.port}\r\n'
                    f'Content-Length: {len(body)}\r\nContent-Type: text/plain\r\n'
                    'Accept: application/json\r\nAccept-Encoding: identity\r\nConnection: close\r\n\r\n').encode()+body
                connection.settimeout(remaining());connection.sendall(request)

                def receive(count):
                    connection.settimeout(remaining());data=connection.recv(count);remaining()
                    if not data:raise ValueError('Truncated response')
                    return data

                header=bytearray()
                while not header.endswith(b'\r\n\r\n'):
                    if len(header)>=2048:raise ValueError('Header budget')
                    header.extend(receive(1))
                length=_content_length(bytes(header),4095)
                result=bytearray()
                while len(result)<length:result.extend(receive(length-len(result)))
                return bytes(result)
        except (OSError,ValueError,TypeError):
            self.failed=True
            raise
