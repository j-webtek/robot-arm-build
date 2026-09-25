"""Stage a PEFT adapter for local Ollama import without adding weights to Git."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import shutil
import subprocess
import sys


AI_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(AI_DIR))
sys.path.insert(0, str(AI_DIR.parent / "src"))
from rocell_ai.model_eval import _model_digest  # noqa: E402


def stage(adapter_dir: Path, staging_dir: Path, base_tag: str) -> str:
    """Create a fresh ignored staging folder; Ollama expects model.safetensors."""

    root = (AI_DIR / "artifacts").resolve()
    destination = staging_dir.resolve()
    if not destination.is_relative_to(root) or destination.exists():
        raise ValueError("staging path must be a new directory under software/ai/artifacts")
    run = json.loads((adapter_dir / "run_manifest.json").read_text(encoding="utf-8"))
    weights = adapter_dir / "adapter_model.safetensors"
    digest = hashlib.sha256(weights.read_bytes()).hexdigest()
    if digest != run["adapter_sha256"]:
        raise ValueError("adapter hash mismatch")
    config = adapter_dir / "adapter_config.json"
    if not config.is_file():
        raise ValueError("adapter config missing")
    destination.mkdir(parents=True)
    shutil.copyfile(weights, destination / "model.safetensors")
    shutil.copyfile(config, destination / "adapter_config.json")
    (destination / "Modelfile").write_bytes((
        f"FROM {base_tag}\nADAPTER {destination.as_posix()}\n"
        "PARAMETER temperature 0\nPARAMETER num_ctx 4096\n"
    ).encode("utf-8"))
    return digest


def main() -> None:
    parser = argparse.ArgumentParser(description="Import a local SFT adapter into Ollama")
    parser.add_argument("--adapter-dir", type=Path, required=True)
    parser.add_argument("--staging-dir", type=Path, required=True)
    parser.add_argument("--base-tag", required=True)
    parser.add_argument("--tag", required=True)
    args = parser.parse_args()
    base_digest = _model_digest(args.base_tag)
    candidate = json.loads((AI_DIR / "train" / "llama32_1b_candidate.json").read_text(encoding="utf-8"))
    run = json.loads((args.adapter_dir / "run_manifest.json").read_text(encoding="utf-8"))
    if (args.base_tag, base_digest, run["base_revision"]) != (
        candidate["local_import"]["tag"], candidate["local_import"]["digest"], candidate["source_revision"]
    ):
        raise ValueError("adapter base does not match the pinned candidate")
    adapter_digest = stage(args.adapter_dir, args.staging_dir, args.base_tag)
    done = subprocess.run(
        ["ollama", "create", args.tag, "-f", str(args.staging_dir / "Modelfile")],
        text=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, check=False,
    )
    if done.returncode:
        raise RuntimeError("Ollama import failed: " + done.stdout[-1500:])
    result = {
        "schema": "rocell.ai_local_adapter_import.v0",
        "base_tag": args.base_tag,
        "base_digest": base_digest,
        "adapter_sha256": adapter_digest,
        "tag": args.tag,
        "digest": _model_digest(args.tag),
    }
    (args.adapter_dir / "import_manifest.json").write_bytes((json.dumps(result, indent=2, sort_keys=True) + "\n").encode("utf-8"))
    print(json.dumps(result, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
