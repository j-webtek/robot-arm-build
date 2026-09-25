"""Local Ollama and llama.cpp adapters for the scene-observation contract."""

from __future__ import annotations

import base64
import json
from typing import Any, Callable
from urllib.error import HTTPError, URLError
from urllib.parse import urlparse
from urllib.request import Request, urlopen

from .scene_observation import (
    FrameEvidence, build_observation, model_output_schema, validate_model_output,
)


PROMPT = """Inspect this single overhead robot-workcell image. Classify only what is visibly supported.
Use uncertainty and abstain when the device, layout, phone state, image quality, occlusion, or critical
targets cannot be established. Estimate occlusion_fraction from 0 to 1 for the relevant device surface.
Return exactly the requested JSON object. Do not return coordinates, robot motion, servo commands, prose,
Markdown, or facts from previous images."""

PostJson = Callable[[str, dict[str, Any], float], dict[str, Any]]


def _endpoint(value: str) -> str:
    parsed = urlparse(value)
    if parsed.scheme not in {"http", "https"} or not parsed.netloc or parsed.query or parsed.fragment:
        raise ValueError("vision endpoint must be an HTTP(S) origin or base path")
    return value.rstrip("/")


def _post_json(url: str, payload: dict[str, Any], timeout_seconds: float) -> dict[str, Any]:
    request = Request(
        url,
        data=json.dumps(payload, separators=(",", ":"), allow_nan=False).encode("utf-8"),
        headers={"Content-Type": "application/json", "Accept": "application/json"},
        method="POST",
    )
    with urlopen(request, timeout=timeout_seconds) as response:
        if getattr(response, "status", 200) != 200:
            raise RuntimeError(f"vision runtime returned HTTP {response.status}")
        body = response.read(4 * 1024 * 1024 + 1)
    if len(body) > 4 * 1024 * 1024:
        raise RuntimeError("vision runtime response exceeds 4 MiB")
    value = json.loads(body)
    if not isinstance(value, dict):
        raise ValueError("vision runtime response must be an object")
    return value


def _mime_type(image: bytes) -> str:
    if image.startswith(b"\xff\xd8\xff"):
        return "image/jpeg"
    if image.startswith(b"\x89PNG\r\n\x1a\n"):
        return "image/png"
    if image.startswith((b"GIF87a", b"GIF89a")):
        return "image/gif"
    if image.startswith(b"RIFF") and image[8:12] == b"WEBP":
        return "image/webp"
    return "application/octet-stream"


def _content_json(content: Any) -> dict[str, Any]:
    if isinstance(content, str):
        decoded = json.loads(content)
    elif isinstance(content, dict):
        decoded = content
    else:
        raise ValueError("vision model content must be JSON text or an object")
    return validate_model_output(decoded)


def _abstention(reason: str) -> dict[str, Any]:
    return {
        "device_presence": "uncertain",
        "keyboard_layout": "unknown",
        "phone_state": "unknown",
        "lighting": "unknown",
        "blur": "unknown",
        "glare": "unknown",
        "occlusion_source": "unknown",
        "occlusion_fraction": 1.0,
        "critical_targets_visible": False,
        "confidence": 0.0,
        "abstain": True,
        "abstain_reasons": [reason],
    }


class _RuntimeObserver:
    runtime = "unknown"

    def __init__(self, *, endpoint: str, model: str, model_identity: str,
                 timeout_seconds: float = 60.0, post_json: PostJson | None = None) -> None:
        self.endpoint = _endpoint(endpoint)
        for label, value in (("model", model), ("model_identity", model_identity)):
            if not isinstance(value, str) or not value.strip() or len(value) > 256:
                raise ValueError(f"{label} must be nonempty and bounded")
        if not isinstance(timeout_seconds, (int, float)) or isinstance(timeout_seconds, bool) or not 0 < timeout_seconds <= 600:
            raise ValueError("timeout_seconds must be greater than zero and at most 600")
        self.model = model
        self.model_identity = model_identity
        self.timeout_seconds = float(timeout_seconds)
        self._post = post_json or _post_json

    def _request(self, frame: FrameEvidence) -> dict[str, Any]:
        raise NotImplementedError

    def observe(self, frame: FrameEvidence) -> dict[str, Any]:
        try:
            model_output = self._request(frame)
        except (ValueError, KeyError, TypeError, json.JSONDecodeError):
            model_output = _abstention("invalid_output")
        except (HTTPError, URLError, TimeoutError, OSError, RuntimeError):
            model_output = _abstention("runtime_error")
        return build_observation(
            frame=frame,
            runtime=self.runtime,
            model=self.model,
            model_identity=self.model_identity,
            model_output=model_output,
        )


class OllamaVisionObserver(_RuntimeObserver):
    runtime = "ollama"

    def _request(self, frame: FrameEvidence) -> dict[str, Any]:
        payload = {
            "model": self.model,
            "messages": [{
                "role": "user",
                "content": PROMPT,
                "images": [base64.b64encode(frame.image_bytes).decode("ascii")],
            }],
            "format": model_output_schema(),
            "stream": False,
            "options": {"temperature": 0},
        }
        response = self._post(f"{self.endpoint}/api/chat", payload, self.timeout_seconds)
        message = response.get("message")
        if not isinstance(message, dict) or "content" not in message:
            raise ValueError("Ollama response is missing message.content")
        return _content_json(message["content"])


class LlamaCppVisionObserver(_RuntimeObserver):
    runtime = "llama.cpp"

    def _request(self, frame: FrameEvidence) -> dict[str, Any]:
        encoded = base64.b64encode(frame.image_bytes).decode("ascii")
        payload = {
            "model": self.model,
            "messages": [{
                "role": "user",
                "content": [
                    {"type": "text", "text": PROMPT},
                    {"type": "image_url", "image_url": {
                        "url": f"data:{_mime_type(frame.image_bytes)};base64,{encoded}",
                    }},
                ],
            }],
            "temperature": 0,
            "response_format": {
                "type": "json_schema",
                "json_schema": {
                    "name": "rocell_scene_observation",
                    "strict": True,
                    "schema": model_output_schema(),
                },
            },
        }
        response = self._post(f"{self.endpoint}/v1/chat/completions", payload, self.timeout_seconds)
        choices = response.get("choices")
        if not isinstance(choices, list) or len(choices) != 1 or not isinstance(choices[0], dict):
            raise ValueError("llama.cpp response must contain one choice")
        message = choices[0].get("message")
        if not isinstance(message, dict) or "content" not in message:
            raise ValueError("llama.cpp response is missing choice message content")
        return _content_json(message["content"])

