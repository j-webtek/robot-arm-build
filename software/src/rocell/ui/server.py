"""Small loopback-only HTTP adapter for the shared arrival wizard service.

The HTTP layer has no device/provider imports. GET requests are projections,
and the only writes are exact prepare/execute calls through the application
service. Binding a socket does not select, open, power or initialize hardware.
"""

from __future__ import annotations

import hmac
import json
import math
import re
import secrets
import threading
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any, Protocol
from urllib.parse import urlencode, urlsplit


MAX_REQUEST_BYTES = 65_536
MAX_IMAGE_BYTES = 8 * 1024 * 1024
MAX_JSON_DEPTH = 16
_IDENTIFIER = re.compile(r"[A-Za-z0-9][A-Za-z0-9_.:-]{0,127}\Z")
_ASSET_DIRECTORY = Path(__file__).with_name("static")
_ASSETS = {
    "/": ("index.html", "text/html; charset=utf-8"),
    "/assets/app.js": ("app.js", "text/javascript; charset=utf-8"),
    "/assets/app.css": ("app.css", "text/css; charset=utf-8"),
    "/input-test": ("input-test.html", "text/html; charset=utf-8"),
    "/assets/input-test.js": ("input-test.js", "text/javascript; charset=utf-8"),
}


class WizardService(Protocol):
    """Transport contract; all eligibility and effect ownership stay upstream."""

    def view(self) -> dict[str, Any]: ...

    def prepare_action(
        self, action_id: str, input: dict[str, Any], expected_revision: int
    ) -> dict[str, Any]: ...

    def execute_action(self, ticket_id: str) -> dict[str, Any]: ...

    def operation(self, operation_id: str) -> dict[str, Any]: ...

    def image(self, image_id: str) -> tuple[bytes, str]: ...

    def shutdown(self) -> None: ...


class _RequestError(ValueError):
    def __init__(self, status: HTTPStatus, code: str, message: str) -> None:
        super().__init__(message)
        self.status = status
        self.code = code


def _unique_object(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            raise ValueError("Duplicate JSON fields are not permitted.")
        result[key] = value
    return result


def _reject_constant(value: str) -> None:
    raise ValueError(f"Nonfinite JSON number {value} is not permitted.")


def _check_depth(value: Any, depth: int = 0) -> None:
    if depth > MAX_JSON_DEPTH:
        raise ValueError("JSON input exceeds the nesting limit.")
    if isinstance(value, dict):
        for nested in value.values():
            _check_depth(nested, depth + 1)
    elif isinstance(value, list):
        for nested in value:
            _check_depth(nested, depth + 1)
    elif isinstance(value, float) and not math.isfinite(value):
        raise ValueError("Nonfinite JSON numbers are not permitted.")


class WizardHTTPServer(ThreadingHTTPServer):
    """Bound server with an unguessable launch fragment and idempotent close.

    ``shutdown()`` retains the standard HTTPServer meaning (stop serving).
    ``close()`` additionally releases the socket and calls service.shutdown()
    exactly once. No browser is opened implicitly.
    """

    daemon_threads = True
    block_on_close = False
    allow_reuse_address = False

    def __init__(self, service: WizardService, host: str, port: int) -> None:
        if host != "127.0.0.1":
            raise ValueError("The wizard can bind only to 127.0.0.1, never LAN/public.")
        if type(port) is not int or not 0 <= port <= 65_535:
            raise ValueError("Port must be an integer between 0 and 65535.")
        self.service = service
        self.session_token = secrets.token_urlsafe(32)
        self.csrf_token = secrets.token_urlsafe(32)
        self._serving = threading.Event()
        self._closed = False
        self._close_lock = threading.Lock()
        self._request_slots = threading.BoundedSemaphore(16)
        # Only these bundled assets can be served; URL text is never a path.
        self.assets = {
            route: ((_ASSET_DIRECTORY / filename).read_bytes(), content_type)
            for route, (filename, content_type) in _ASSETS.items()
        }
        super().__init__((host, port), _WizardRequestHandler)
        self.origin = f"http://127.0.0.1:{self.server_port}"
        self.expected_host = f"127.0.0.1:{self.server_port}"
        self.url = self.origin + "/"
        # Fragments never travel in HTTP requests, referrers or access logs.
        self.launch_url = (
            self.url
            + "#"
            + urlencode({"session": self.session_token, "csrf": self.csrf_token})
        )

    def get_request(self) -> Any:
        connection, address = super().get_request()
        connection.settimeout(3.0)
        return connection, address

    def process_request(self, request: Any, client_address: Any) -> None:
        if not self._request_slots.acquire(blocking=False):
            self.shutdown_request(request)
            return
        try:
            super().process_request(request, client_address)
        except BaseException:
            self._request_slots.release()
            raise

    def process_request_thread(self, request: Any, client_address: Any) -> None:
        try:
            super().process_request_thread(request, client_address)
        finally:
            self._request_slots.release()

    def serve_forever(self, poll_interval: float = 0.1) -> None:
        self._serving.set()
        try:
            super().serve_forever(poll_interval=poll_interval)
        finally:
            self._serving.clear()

    def start_in_thread(self) -> threading.Thread:
        if self._closed or self._serving.is_set():
            raise RuntimeError("Wizard server is closed or already serving.")
        thread = threading.Thread(
            target=self.serve_forever, name="rocell-wizard-http", daemon=True
        )
        thread.start()
        if not self._serving.wait(timeout=2.0):
            raise RuntimeError("Wizard HTTP server did not start.")
        return thread

    def close(self) -> None:
        """Explicitly stop HTTP and reconcile service cleanup once."""
        with self._close_lock:
            if self._closed:
                return
            self._closed = True
            if self._serving.is_set():
                self.shutdown()
            try:
                self.server_close()
            finally:
                self.service.shutdown()


class _WizardRequestHandler(BaseHTTPRequestHandler):
    server: WizardHTTPServer
    server_version = "RoCellWizard"
    sys_version = ""
    protocol_version = "HTTP/1.0"

    def log_message(self, format: str, *args: Any) -> None:
        # Service audit records actions. Do not log credentials, paths or text
        # being typed via generic HTTP request logging.
        return

    def _write(self, status: HTTPStatus, data: bytes, content_type: str) -> None:
        self.send_response(status)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(data)))
        self.send_header("Cache-Control", "no-store")
        self.send_header("X-Content-Type-Options", "nosniff")
        self.send_header("X-Frame-Options", "DENY")
        self.send_header("Referrer-Policy", "no-referrer")
        self.send_header("Cross-Origin-Resource-Policy", "same-origin")
        self.send_header("Permissions-Policy", "camera=(), microphone=(), usb=()")
        self.send_header(
            "Content-Security-Policy",
            "default-src 'none'; script-src 'self'; style-src 'self'; "
            "img-src 'self' blob:; connect-src 'self'; frame-ancestors 'none'; "
            "base-uri 'none'; form-action 'none'",
        )
        self.end_headers()
        self.wfile.write(data)

    def _json(self, status: HTTPStatus, document: dict[str, Any]) -> None:
        payload = json.dumps(document, allow_nan=False, ensure_ascii=True).encode(
            "utf-8"
        )
        self._write(status, payload, "application/json; charset=utf-8")

    def _error(self, status: HTTPStatus, code: str, message: str) -> None:
        self._json(status, {"error": {"code": code, "message": message}})

    def _route_and_access(self, *, writing: bool) -> str:
        if self.client_address[0] != "127.0.0.1":
            raise _RequestError(
                HTTPStatus.FORBIDDEN, "LOOPBACK_REQUIRED", "Local only."
            )
        if self.headers.get_all("Host") != [self.server.expected_host]:
            raise _RequestError(
                HTTPStatus.FORBIDDEN, "HOST_REJECTED", "Invalid local host."
            )
        parsed = urlsplit(self.path)
        if parsed.scheme or parsed.netloc or parsed.query or parsed.fragment:
            raise _RequestError(
                HTTPStatus.BAD_REQUEST, "ROUTE_REJECTED", "Invalid route."
            )
        origins = self.headers.get_all("Origin")
        if origins and origins != [self.server.origin]:
            raise _RequestError(
                HTTPStatus.FORBIDDEN, "ORIGIN_REJECTED", "Invalid origin."
            )
        if self.headers.get("Sec-Fetch-Site") == "cross-site":
            raise _RequestError(
                HTTPStatus.FORBIDDEN, "ORIGIN_REJECTED", "Cross-site denied."
            )
        if writing and origins != [self.server.origin]:
            raise _RequestError(
                HTTPStatus.FORBIDDEN, "ORIGIN_REQUIRED", "Local origin required."
            )
        if parsed.path.startswith("/api/"):
            supplied = self.headers.get_all("X-RoCell-Token")
            if (
                not supplied
                or len(supplied) != 1
                or not supplied[0].isascii()
                or not hmac.compare_digest(supplied[0], self.server.session_token)
            ):
                raise _RequestError(
                    HTTPStatus.UNAUTHORIZED,
                    "SESSION_REQUIRED",
                    "Use this launch's private URL.",
                )
            if writing:
                csrf = self.headers.get_all("X-RoCell-CSRF")
                if (
                    not csrf
                    or len(csrf) != 1
                    or not csrf[0].isascii()
                    or not hmac.compare_digest(csrf[0], self.server.csrf_token)
                ):
                    raise _RequestError(
                        HTTPStatus.FORBIDDEN, "CSRF_REJECTED", "Invalid action token."
                    )
        return parsed.path

    def _body(self) -> dict[str, Any]:
        if self.headers.get_all("Transfer-Encoding"):
            raise _RequestError(
                HTTPStatus.BAD_REQUEST, "BODY_ENCODING", "Chunked input is unsupported."
            )
        lengths = self.headers.get_all("Content-Length")
        if (
            not lengths
            or len(lengths) != 1
            or not lengths[0].isascii()
            or not lengths[0].isdigit()
        ):
            raise _RequestError(
                HTTPStatus.LENGTH_REQUIRED,
                "BODY_LENGTH",
                "One body length is required.",
            )
        length = int(lengths[0])
        if length > MAX_REQUEST_BYTES:
            raise _RequestError(
                HTTPStatus.REQUEST_ENTITY_TOO_LARGE,
                "BODY_LIMIT",
                "Request is too large.",
            )
        types = self.headers.get_all("Content-Type")
        if (
            not types
            or len(types) != 1
            or types[0].lower()
            not in {"application/json", "application/json; charset=utf-8"}
        ):
            raise _RequestError(
                HTTPStatus.UNSUPPORTED_MEDIA_TYPE,
                "BODY_TYPE",
                "JSON input is required.",
            )
        data = self.rfile.read(length)
        if len(data) != length:
            raise _RequestError(
                HTTPStatus.BAD_REQUEST, "BODY_INCOMPLETE", "Body was incomplete."
            )
        try:
            document = json.loads(
                data.decode("utf-8"),
                object_pairs_hook=_unique_object,
                parse_constant=_reject_constant,
            )
            if not isinstance(document, dict):
                raise ValueError("An object is required.")
            _check_depth(document)
        except (ValueError, RecursionError) as error:
            raise _RequestError(
                HTTPStatus.BAD_REQUEST, "INVALID_JSON", str(error)
            ) from error
        return document

    @staticmethod
    def _identifier(value: Any) -> str:
        if not isinstance(value, str) or not _IDENTIFIER.fullmatch(value):
            raise _RequestError(
                HTTPStatus.BAD_REQUEST, "INVALID_ID", "Invalid service identifier."
            )
        return value

    def _handle(self, *, writing: bool) -> None:
        try:
            route = self._route_and_access(writing=writing)
            if not writing:
                if route in self.server.assets:
                    data, content_type = self.server.assets[route]
                    self._write(HTTPStatus.OK, data, content_type)
                    return
                if route == "/api/view":
                    self._json(HTTPStatus.OK, self.server.service.view())
                    return
                if route.startswith("/api/operations/"):
                    identifier = self._identifier(
                        route.removeprefix("/api/operations/")
                    )
                    self._json(HTTPStatus.OK, self.server.service.operation(identifier))
                    return
                if route.startswith("/api/images/"):
                    identifier = self._identifier(route.removeprefix("/api/images/"))
                    data, mime = self.server.service.image(identifier)
                    if (
                        mime not in {"image/png", "image/jpeg", "image/webp"}
                        or len(data) > MAX_IMAGE_BYTES
                    ):
                        raise _RequestError(
                            HTTPStatus.CONFLICT,
                            "IMAGE_REJECTED",
                            "Image is not displayable.",
                        )
                    self._write(HTTPStatus.OK, data, mime)
                    return
            elif route in {"/api/prepare", "/api/execute"}:
                document = self._body()
                if route == "/api/prepare":
                    if set(document) != {"action_id", "input", "expected_revision"}:
                        raise _RequestError(
                            HTTPStatus.BAD_REQUEST,
                            "REQUEST_FIELDS",
                            "Unexpected prepare fields.",
                        )
                    if (
                        type(document["expected_revision"]) is not int
                        or document["expected_revision"] < 0
                    ):
                        raise _RequestError(
                            HTTPStatus.BAD_REQUEST,
                            "REVISION_REQUIRED",
                            "Integer revision required.",
                        )
                    if not isinstance(document["input"], dict):
                        raise _RequestError(
                            HTTPStatus.BAD_REQUEST,
                            "INPUT_OBJECT",
                            "Action input must be an object.",
                        )
                    result = self.server.service.prepare_action(
                        self._identifier(document["action_id"]),
                        document["input"],
                        document["expected_revision"],
                    )
                else:
                    if set(document) != {"ticket_id"}:
                        raise _RequestError(
                            HTTPStatus.BAD_REQUEST,
                            "REQUEST_FIELDS",
                            "Only the issued ticket is accepted.",
                        )
                    result = self.server.service.execute_action(
                        self._identifier(document["ticket_id"])
                    )
                self._json(HTTPStatus.OK, result)
                return
            raise _RequestError(
                HTTPStatus.NOT_FOUND, "ROUTE_NOT_FOUND", "Unknown wizard route."
            )
        except _RequestError as error:
            self._error(error.status, error.code, str(error))
        except (ValueError, KeyError) as error:
            # Service validation failures are expected holds, never implicit retries.
            code = getattr(error, "code", "ACTION_REJECTED")
            if not isinstance(code, str) or not _IDENTIFIER.fullmatch(code):
                code = "ACTION_REJECTED"
            self._error(HTTPStatus.CONFLICT, code, str(error))
        except (BrokenPipeError, ConnectionResetError, TimeoutError):
            # Losing HTTP never replays or cancels an unknown upstream attempt.
            return
        except Exception:
            self._error(
                HTTPStatus.INTERNAL_SERVER_ERROR,
                "SERVICE_ERROR",
                "The service could not finish this request. Inspect operations and diagnostics before retrying.",
            )

    def do_GET(self) -> None:
        self._handle(writing=False)

    def do_POST(self) -> None:
        self._handle(writing=True)

    def do_OPTIONS(self) -> None:
        self._error(
            HTTPStatus.METHOD_NOT_ALLOWED,
            "METHOD_REJECTED",
            "Cross-origin access is unavailable.",
        )

    def do_HEAD(self) -> None:
        # No secondary HTTP verb is an alternate execution route. HEAD sends
        # headers only, rather than BaseHTTPRequestHandler's HTML error page.
        self.send_response(HTTPStatus.METHOD_NOT_ALLOWED)
        self.send_header("Allow", "GET, POST")
        self.send_header("Content-Length", "0")
        self.send_header("Cache-Control", "no-store")
        self.end_headers()

    def do_PUT(self) -> None:
        self.do_OPTIONS()

    def do_PATCH(self) -> None:
        self.do_OPTIONS()

    def do_DELETE(self) -> None:
        self.do_OPTIONS()


def create_wizard_server(
    service: WizardService, *, host: str = "127.0.0.1", port: int = 0
) -> WizardHTTPServer:
    """Bind a local listener without calling the service or opening a browser."""
    return WizardHTTPServer(service, host, port)


def run_wizard_server(server: WizardHTTPServer) -> None:
    """Serve until interrupted, then perform explicit application cleanup."""
    try:
        server.serve_forever()
    finally:
        server.close()
