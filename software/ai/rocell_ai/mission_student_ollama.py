"""Run a frozen mission-v1 split through one pinned local Ollama model."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from typing import Any, Callable
from urllib import request

from .mission_model import PROMPT_SHA256, SYSTEM_PROMPT, render_user


OLLAMA_URL = "http://127.0.0.1:11434"


def _get(path: str, timeout: int = 10) -> dict[str, Any]:
    with request.urlopen(OLLAMA_URL + path, timeout=timeout) as response:
        return json.load(response)


def _post(path: str, payload: dict[str, Any], timeout: int = 120) -> dict[str, Any]:
    call = request.Request(
        OLLAMA_URL + path,
        data=json.dumps(payload).encode("utf-8"),
        headers={"Content-Type": "application/json"},
    )
    with request.urlopen(call, timeout=timeout) as response:
        return json.load(response)


def model_digest(model: str) -> str:
    matches = [
        item.get("digest")
        for item in _get("/api/tags").get("models", [])
        if item.get("name") == model or item.get("model") == model
    ]
    if len(matches) != 1 or not isinstance(matches[0], str) or len(matches[0]) != 64:
        raise ValueError("model tag must resolve to exactly one local Ollama digest")
    return matches[0]


def build_payload(
    model: str, row: dict[str, Any], schema: dict[str, Any], plan: dict[str, Any]
) -> dict[str, Any]:
    inference = plan["inference"]
    return {
        "model": model,
        "messages": [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": render_user(row)},
        ],
        "format": schema,
        "stream": False,
        "options": {
            "temperature": inference["temperature"],
            "seed": inference["seed"],
            "num_predict": inference["num_predict"],
            "num_ctx": inference["num_ctx"],
        },
    }


def run(
    cases_path: Path,
    plan_path: Path,
    model: str,
    output: Path,
    post: Callable[[str, dict[str, Any], int], dict[str, Any]] = _post,
) -> dict[str, Any]:
    if output.exists():
        raise FileExistsError("prediction output already exists")
    plan = json.loads(plan_path.read_text(encoding="utf-8"))
    if plan["prompt_sha256"] != PROMPT_SHA256:
        raise ValueError("frozen prompt hash mismatch")
    raw_cases = cases_path.read_bytes()
    expected_hash = plan["split_sha256"].get(cases_path.name)
    if expected_hash is None or hashlib.sha256(raw_cases).hexdigest() != expected_hash:
        raise ValueError("split is absent from the plan or its hash changed")
    schema_path = plan_path.parents[1] / plan["mission_schema_path"]
    schema = json.loads(schema_path.read_text(encoding="utf-8"))
    digest = model_digest(model)
    version = _get("/api/version").get("version")
    if not isinstance(version, str) or not version:
        raise ValueError("Ollama version unavailable")

    rows = []
    for case in [json.loads(line) for line in raw_cases.decode("utf-8").splitlines()]:
        response = post("/api/chat", build_payload(model, case, schema, plan), 120)
        content = response.get("message", {}).get("content")
        if not isinstance(content, str):
            content = ""
        rows.append(
            {
                "id": case["id"],
                "response": content,
                "model": model,
                "model_digest": digest,
                "ollama_version": version,
                "prompt_eval_count": response.get("prompt_eval_count"),
                "eval_count": response.get("eval_count"),
                "total_duration_ns": response.get("total_duration"),
            }
        )
    if model_digest(model) != digest:
        raise ValueError("local model digest changed during inference")
    payload = "".join(json.dumps(row, sort_keys=True) + "\n" for row in rows)
    temporary = output.with_suffix(output.suffix + ".tmp")
    temporary.write_text(payload, encoding="utf-8")
    temporary.replace(output)
    return {
        "count": len(rows),
        "model": model,
        "model_digest": digest,
        "ollama_version": version,
        "predictions_sha256": hashlib.sha256(payload.encode("utf-8")).hexdigest(),
        "hardware_writes": 0,
        "physical_movements": 0,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Generate frozen mission-v1 predictions")
    parser.add_argument("--cases", type=Path, required=True)
    parser.add_argument("--plan", type=Path, required=True)
    parser.add_argument("--model", required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    print(json.dumps(run(args.cases, args.plan, args.model, args.output), sort_keys=True))


if __name__ == "__main__":
    main()
