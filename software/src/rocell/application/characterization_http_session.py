"""Single-outstanding-request state; no sockets, retries, redirects or movement.

Create once for an exclusive controller boot context. Recreating at sequence zero
after uncertain delivery is not recovery; reconcile/reinitialize separately.
"""
import hashlib

from .characterization_request_auth import sign_request, verify_response
from .servo_start_authorization import _hex, _key


class CharacterizationHTTPSession:
    def __init__(self, *, key, boot):
        _key(key);_hex(boot,16)
        self._key,self._boot=key,boot
        self._sequence=0;self._pending=False;self._stopped=False
        self._pending_operation=None
        self._uncertainty=None

    def request(self, method, path, body=b''):
        if self._stopped or self._pending:
            self._stopped=True
            raise ValueError('HTTP session stopped or request outstanding')
        try:
            signature=sign_request(key=self._key,boot=self._boot,sequence=self._sequence,
                                   method=method,path=path,body=body)
            self._pending=True
            self._pending_operation=dict(method=method,path=path,sequence=self._sequence,
                                         body_sha256=hashlib.sha256(body).hexdigest())
            return dict(method=method,path=path,body=body,headers={
                'X-Rocell-Sequence':str(self._sequence),'X-Rocell-Signature':signature.hex()})
        except Exception:
            self._stopped=True
            raise

    def response(self, *, status, body, sequence, signature):
        """Consume canonical header values and exact body bytes before parsing.

        The future adapter must reject duplicate/missing auth headers rather than
        collapse them into a dictionary. Non-2xx replies stop this workflow even
        when authenticated; they do not automatically retry the operation.
        """
        if self._stopped or not self._pending:
            self._stopped=True
            raise ValueError('No active request')
        try:
            if type(sequence) is not str or sequence!=str(self._sequence):
                raise ValueError('Response sequence mismatch')
            raw_signature=_hex(signature,32)
            result=verify_response(key=self._key,boot=self._boot,sequence=self._sequence,
                                   status=status,body=body,signature=raw_signature)
            self._pending=False;self._sequence+=1
            self._pending_operation=None
            if not 200<=status<300:
                raise ValueError('Authenticated HTTP failure; session stopped')
            return result
        except Exception:
            self._stopped=True
            raise

    def delivery_uncertain(self):
        """Call on timeout/disconnect, including loss of an acknowledgement."""
        self._stopped=True
        # Preserve the first uncertain operation. A later rejected request must
        # not erase which permission may already have reached the controller.
        if self._uncertainty is None and self._pending_operation is not None:
            operation=dict(self._pending_operation)
            receipt=operation['path'] in (
                '/rocell/characterization/receipt',
                '/rocell/reviewed-hover/receipt',
                '/rocell/recovery-hover/receipt',
            )
            self._uncertainty=dict(
                operation=operation, state='DELIVERY_UNCERTAIN',
                controller_stop_confirmed=False, retry_allowed=False,
                reconciliation_required=True,
                continuation_may_have_been_authorized=receipt)

    @property
    def uncertainty(self):
        """JSON-safe evidence, not proof of position or permission to reconnect.

        No key, signature or request payload is exposed. The body digest permits
        correlation with the separately retained export/receipt record.
        """
        if self._uncertainty is None:
            return None
        return {**self._uncertainty, 'operation':dict(self._uncertainty['operation'])}

    @property
    def stopped(self):
        return self._stopped
