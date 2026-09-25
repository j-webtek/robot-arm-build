"""Transport-independent tests for local multimodal runtime adapters."""

from __future__ import annotations

import json
from pathlib import Path
import sys
import unittest


AI_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(AI_DIR))

from rocell_ai.scene_observation import FrameEvidence, validate_observation  # noqa: E402
from rocell_ai.vision_runtime import LlamaCppVisionObserver, OllamaVisionObserver  # noqa: E402


def output() -> dict:
    return {
        "device_presence": "keyboard", "keyboard_layout": "us_qwerty",
        "phone_state": "not_visible", "lighting": "acceptable", "blur": "low",
        "glare": "none", "occlusion_source": "arm", "occlusion_fraction": 0.1,
        "critical_targets_visible": True, "confidence": 0.91,
        "abstain": False, "abstain_reasons": [],
    }


class VisionRuntimeTests(unittest.TestCase):
    def setUp(self) -> None:
        self.frame = FrameEvidence("f-1", "2026-09-25T14:00:00Z", b"\xff\xd8\xffimage")

    def test_ollama_request_uses_schema_and_exact_image(self) -> None:
        captured = {}

        def post(url, payload, timeout):
            captured.update(url=url, payload=payload, timeout=timeout)
            return {"message": {"content": json.dumps(output())}}

        observer = OllamaVisionObserver(
            endpoint="http://127.0.0.1:11434", model="vision-model:tag",
            model_identity="sha256:configured", timeout_seconds=12, post_json=post,
        )
        result = observer.observe(self.frame)
        validate_observation(result, frame=self.frame)
        self.assertEqual(captured["url"], "http://127.0.0.1:11434/api/chat")
        self.assertFalse(captured["payload"]["stream"])
        self.assertEqual(captured["payload"]["format"]["additionalProperties"], False)
        self.assertEqual(result["runtime"], "ollama")
        self.assertFalse(result["abstain"])

    def test_llama_cpp_request_uses_data_url_and_same_contract(self) -> None:
        captured = {}

        def post(url, payload, timeout):
            captured.update(url=url, payload=payload, timeout=timeout)
            return {"choices": [{"message": {"content": json.dumps(output())}}]}

        observer = LlamaCppVisionObserver(
            endpoint="http://localhost:8080", model="local-mmproj",
            model_identity="text.gguf+mmproj.gguf", post_json=post,
        )
        result = observer.observe(self.frame)
        validate_observation(result, frame=self.frame)
        image_url = captured["payload"]["messages"][0]["content"][1]["image_url"]["url"]
        self.assertTrue(image_url.startswith("data:image/jpeg;base64,"))
        self.assertEqual(captured["url"], "http://localhost:8080/v1/chat/completions")
        self.assertEqual(result["runtime"], "llama.cpp")

    def test_malformed_model_output_becomes_bound_abstention(self) -> None:
        observer = OllamaVisionObserver(
            endpoint="http://localhost:11434", model="bad", model_identity="bad-v1",
            post_json=lambda *_: {"message": {"content": '{"device_presence":"keyboard"}'}},
        )
        result = observer.observe(self.frame)
        validate_observation(result, frame=self.frame)
        self.assertTrue(result["abstain"])
        self.assertEqual(result["abstain_reasons"], ["invalid_output"])
        self.assertEqual(result["confidence"], 0.0)

    def test_transport_failure_becomes_bound_abstention(self) -> None:
        def fail(*_):
            raise TimeoutError("timeout")

        observer = LlamaCppVisionObserver(
            endpoint="http://localhost:8080", model="offline", model_identity="offline-v1",
            post_json=fail,
        )
        result = observer.observe(self.frame)
        self.assertEqual(result["abstain_reasons"], ["runtime_error"])
        self.assertEqual(result["image_sha256"], self.frame.image_sha256)

    def test_endpoint_and_timeout_are_bounded(self) -> None:
        with self.assertRaises(ValueError):
            OllamaVisionObserver(endpoint="file:///tmp/socket", model="m", model_identity="i")
        with self.assertRaises(ValueError):
            OllamaVisionObserver(endpoint="http://localhost", model="m", model_identity="i", timeout_seconds=0)


if __name__ == "__main__":
    unittest.main()
