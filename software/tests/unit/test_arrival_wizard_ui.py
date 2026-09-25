"""Transport tests use a recording service and never import hardware adapters."""

from __future__ import annotations

import http.client
import json
from collections.abc import Iterator
from typing import Any
from urllib.parse import parse_qs, urlsplit

import pytest

from rocell.ui.server import MAX_REQUEST_BYTES, WizardHTTPServer, create_wizard_server


class RecordingService:
    def __init__(self) -> None:
        self.calls: list[tuple[Any, ...]] = []
        self.shutdown_count = 0
        self.error: Exception | None = None
        self.image_type = "image/png"

    def view(self) -> dict[str, Any]:
        self.calls.append(("view",))
        return {"revision": 3, "mode": "rehearsal", "actions": []}

    def prepare_action(
        self, action_id: str, input: dict[str, Any], expected_revision: int
    ) -> dict[str, Any]:
        self.calls.append(("prepare", action_id, input, expected_revision))
        if self.error:
            raise self.error
        return {"ticket_id": "ticket-1", "label": "Camera preview"}

    def execute_action(self, ticket_id: str) -> dict[str, Any]:
        self.calls.append(("execute", ticket_id))
        return {"operation_id": "operation-1", "status": "QUEUED"}

    def operation(self, operation_id: str) -> dict[str, Any]:
        self.calls.append(("operation", operation_id))
        return {"operation_id": operation_id, "status": "SUCCEEDED"}

    def image(self, image_id: str) -> tuple[bytes, str]:
        self.calls.append(("image", image_id))
        return b"png-fixture", self.image_type

    def shutdown(self) -> None:
        self.shutdown_count += 1


@pytest.fixture
def running_server() -> Iterator[tuple[WizardHTTPServer, RecordingService]]:
    service = RecordingService()
    server = create_wizard_server(service)
    thread = server.start_in_thread()
    try:
        yield server, service
    finally:
        server.close()
        thread.join(timeout=3)


def request(
    server: WizardHTTPServer,
    path: str = "/api/view",
    *,
    method: str = "GET",
    body: str | bytes | dict[str, Any] | None = None,
    headers: dict[str, str] | None = None,
    authenticated: bool = True,
) -> tuple[int, dict[str, str], bytes]:
    values = {"Host": server.expected_host}
    if authenticated:
        values["X-RoCell-Token"] = server.session_token
    if method == "POST":
        values.update(
            {
                "Origin": server.origin,
                "X-RoCell-CSRF": server.csrf_token,
                "Content-Type": "application/json",
            }
        )
    if headers:
        values.update(headers)
    if isinstance(body, dict):
        body = json.dumps(body)
    connection = http.client.HTTPConnection("127.0.0.1", server.server_port, timeout=3)
    try:
        connection.request(method, path, body=body, headers=values)
        response = connection.getresponse()
        return response.status, dict(response.getheaders()), response.read()
    finally:
        connection.close()


def test_server_construction_and_launch_information_are_inert() -> None:
    service = RecordingService()
    server = create_wizard_server(service)
    try:
        assert service.calls == []
        assert server.url == server.origin + "/"
        parsed = urlsplit(server.launch_url)
        assert not parsed.query
        assert parse_qs(parsed.fragment) == {
            "session": [server.session_token],
            "csrf": [server.csrf_token],
        }
        assert len(server.session_token) >= 40
        assert server.session_token != server.csrf_token
    finally:
        server.close()
        server.close()
    assert service.shutdown_count == 1


@pytest.mark.parametrize(
    "host", ["0.0.0.0", "localhost", "192.168.1.2", "::", "::1", "127.0.0.2"]
)
def test_noncanonical_listener_is_rejected_without_service_calls(host: str) -> None:
    service = RecordingService()
    with pytest.raises(ValueError, match="127.0.0.1"):
        create_wizard_server(service, host=host)
    assert not service.calls


@pytest.mark.parametrize("port", [-1, 65536, True, "8080"])
def test_invalid_port_is_rejected(port: Any) -> None:
    with pytest.raises(ValueError, match="Port"):
        create_wizard_server(RecordingService(), port=port)


def test_static_assets_are_local_and_never_call_service(running_server: Any) -> None:
    server, service = running_server
    for path in ("/", "/assets/app.js", "/assets/app.css"):
        status, headers, body = request(server, path, authenticated=False)
        assert status == 200
        assert body
        assert headers["Cache-Control"] == "no-store"
        assert headers["X-Frame-Options"] == "DENY"
        assert headers["X-Content-Type-Options"] == "nosniff"
        assert "frame-ancestors 'none'" in headers["Content-Security-Policy"]
        assert "Access-Control-Allow-Origin" not in headers
        assert server.session_token.encode() not in body
    assert service.calls == []


def test_browser_shell_contains_workflow_and_accessibility_surfaces(
    running_server: Any,
) -> None:
    server, _ = running_server
    _, _, body = request(server, "/", authenticated=False)
    for label in (
        b"Overview",
        b"Camera",
        b"Arm",
        b"Board &amp; tests",
        b"Task rehearsal",
        b"Diagnostics &amp; exports",
        b"action-preview",
        b"aria-live",
        b"Skip to workspace",
    ):
        assert label in body
    assert b"https://" not in body
    _, _, script = request(server, "/assets/app.js", authenticated=False)
    assert b"innerHTML" not in script
    assert b"/api/prepare" in script
    assert b"/api/execute" in script
    assert b"expected_revision: revision" in script


def test_status_and_operation_polling_are_read_only(running_server: Any) -> None:
    server, service = running_server
    for _ in range(3):
        status, _, body = request(server)
        assert status == 200
        assert json.loads(body)["mode"] == "rehearsal"
    status, _, body = request(server, "/api/operations/operation-1")
    assert status == 200
    assert json.loads(body)["status"] == "SUCCEEDED"
    assert service.calls == [("view",)] * 3 + [("operation", "operation-1")]


def test_prepare_execute_map_exactly_to_service(running_server: Any) -> None:
    server, service = running_server
    status, _, body = request(
        server,
        "/api/prepare",
        method="POST",
        body={
            "action_id": "camera_preview",
            "input": {"candidate_id": "camera-1"},
            "expected_revision": 3,
        },
    )
    assert status == 200
    assert json.loads(body)["ticket_id"] == "ticket-1"
    assert service.calls == [
        ("prepare", "camera_preview", {"candidate_id": "camera-1"}, 3)
    ]
    status, _, _ = request(
        server, "/api/execute", method="POST", body={"ticket_id": "ticket-1"}
    )
    assert status == 200
    assert service.calls[-1] == ("execute", "ticket-1")


@pytest.mark.parametrize(
    "path", ["/api/view", "/api/images/image-1", "/api/operations/op-1"]
)
def test_api_get_requires_session_token(running_server: Any, path: str) -> None:
    server, service = running_server
    assert request(server, path, authenticated=False)[0] == 401
    assert service.calls == []


@pytest.mark.parametrize(
    "headers",
    [
        {"Host": "attacker.example"},
        {"Host": "127.0.0.1"},
        {"Origin": "https://attacker.example"},
        {"Origin": "null"},
        {"Sec-Fetch-Site": "cross-site"},
    ],
)
def test_host_origin_and_fetch_site_checks_precede_service(
    running_server: Any, headers: dict[str, str]
) -> None:
    server, service = running_server
    assert request(server, headers=headers)[0] == 403
    assert service.calls == []


@pytest.mark.parametrize(
    "headers,expected",
    [
        ({"X-RoCell-CSRF": "wrong"}, 403),
        ({"X-RoCell-Token": "wrong"}, 401),
        ({"Origin": ""}, 403),
        ({"Content-Type": "text/plain"}, 415),
        ({"Transfer-Encoding": "chunked"}, 400),
    ],
)
def test_post_requires_origin_session_csrf_and_json(
    running_server: Any, headers: dict[str, str], expected: int
) -> None:
    server, service = running_server
    status, _, _ = request(
        server,
        "/api/execute",
        method="POST",
        body={"ticket_id": "ticket-1"},
        headers=headers,
    )
    assert status == expected
    assert service.calls == []


@pytest.mark.parametrize(
    "body",
    [
        '{"ticket_id":"ticket-1","ticket_id":"ticket-2"}',
        '{"ticket_id":NaN}',
        '{"ticket_id":Infinity}',
        '{"ticket_id":1e999}',
        '{"ticket_id":',
        "[]",
        '{"ticket_id":' + "[" * 18 + "0" + "]" * 18 + "}",
    ],
)
def test_malformed_ambiguous_json_is_rejected(running_server: Any, body: str) -> None:
    server, service = running_server
    assert request(server, "/api/execute", method="POST", body=body)[0] == 400
    assert service.calls == []


def test_oversized_request_is_rejected_before_read_or_dispatch(
    running_server: Any,
) -> None:
    server, service = running_server
    status, _, _ = request(
        server,
        "/api/execute",
        method="POST",
        body="{}",
        headers={"Content-Length": str(MAX_REQUEST_BYTES + 1)},
    )
    assert status == 413
    assert service.calls == []


@pytest.mark.parametrize(
    "path,body",
    [
        ("/api/execute", {"ticket_id": "ticket-1", "directory": "C:/arbitrary"}),
        ("/api/execute", {"ticket_id": "../ticket"}),
        (
            "/api/prepare",
            {"action_id": "camera_preview", "input": {}, "expected_revision": True},
        ),
        (
            "/api/prepare",
            {"action_id": "camera_preview", "input": [], "expected_revision": 1},
        ),
        (
            "/api/prepare",
            {
                "action_id": "camera_preview",
                "input": {},
                "expected_revision": 1,
                "authority": True,
            },
        ),
    ],
)
def test_closed_request_envelopes_and_identifier_validation(
    running_server: Any, path: str, body: dict[str, Any]
) -> None:
    server, service = running_server
    assert request(server, path, method="POST", body=body)[0] == 400
    assert service.calls == []


@pytest.mark.parametrize(
    "path",
    [
        "/assets/../../server.py",
        "/assets/server.py",
        "/api/execute",
        "/api/prepare",
        "/api/stop",
        "/api/files/C:/Windows/win.ini",
        "/api/images/../secret",
    ],
)
def test_no_get_actions_or_arbitrary_file_routes(
    running_server: Any, path: str
) -> None:
    server, service = running_server
    assert request(server, path)[0] in {400, 404}
    assert service.calls == []


def test_query_token_and_absolute_request_targets_are_rejected(
    running_server: Any,
) -> None:
    server, service = running_server
    assert request(server, "/api/view?token=" + server.session_token)[0] == 400
    assert request(server, server.origin + "/api/view")[0] == 400
    assert service.calls == []


def test_images_require_known_id_and_passive_mime(running_server: Any) -> None:
    server, service = running_server
    status, headers, body = request(server, "/api/images/image-1")
    assert (status, headers["Content-Type"], body) == (200, "image/png", b"png-fixture")
    service.image_type = "image/svg+xml"
    assert request(server, "/api/images/image-1")[0] == 409


def test_expected_service_hold_is_clear_and_not_retried(running_server: Any) -> None:
    server, service = running_server
    service.error = ValueError("CAMERA_IDENTITY_AMBIGUOUS: select the reviewed unit.")
    status, _, body = request(
        server,
        "/api/prepare",
        method="POST",
        body={"action_id": "camera_preview", "input": {}, "expected_revision": 3},
    )
    assert status == 409
    assert "CAMERA_IDENTITY_AMBIGUOUS" in json.loads(body)["error"]["message"]
    assert len(service.calls) == 1


def test_unexpected_error_does_not_leak_internal_paths(running_server: Any) -> None:
    server, service = running_server
    service.error = RuntimeError("SECRET internal filesystem path")
    status, _, body = request(
        server,
        "/api/prepare",
        method="POST",
        body={"action_id": "camera_preview", "input": {}, "expected_revision": 3},
    )
    assert status == 500
    assert b"SECRET" not in body
    assert len(service.calls) == 1


def test_cross_origin_preflight_has_no_cors_permission(running_server: Any) -> None:
    server, service = running_server
    status, headers, _ = request(server, "/api/execute", method="OPTIONS")
    assert status == 405
    assert "Access-Control-Allow-Origin" not in headers
    assert service.calls == []


@pytest.mark.parametrize("method", ["HEAD", "PUT", "PATCH", "DELETE"])
def test_unregistered_methods_cannot_execute_actions(
    running_server: Any, method: str
) -> None:
    server, service = running_server
    assert request(server, "/api/execute", method=method)[0] == 405
    assert service.calls == []


def test_duplicate_host_header_is_rejected(running_server: Any) -> None:
    server, service = running_server
    connection = http.client.HTTPConnection("127.0.0.1", server.server_port, timeout=3)
    try:
        connection.putrequest("GET", "/api/view", skip_host=True)
        connection.putheader("Host", server.expected_host)
        connection.putheader("Host", "attacker.example")
        connection.putheader("X-RoCell-Token", server.session_token)
        connection.endheaders()
        response = connection.getresponse()
        assert response.status == 403
        response.read()
    finally:
        connection.close()
    assert service.calls == []


def test_duplicate_length_header_is_rejected(running_server: Any) -> None:
    server, service = running_server
    connection = http.client.HTTPConnection("127.0.0.1", server.server_port, timeout=3)
    try:
        connection.putrequest("POST", "/api/execute")
        connection.putheader("X-RoCell-Token", server.session_token)
        connection.putheader("X-RoCell-CSRF", server.csrf_token)
        connection.putheader("Origin", server.origin)
        connection.putheader("Content-Type", "application/json")
        connection.putheader("Content-Length", "2")
        connection.putheader("Content-Length", "3")
        connection.endheaders(b"{}")
        response = connection.getresponse()
        assert response.status == 411
        response.read()
    finally:
        connection.close()
    assert service.calls == []
