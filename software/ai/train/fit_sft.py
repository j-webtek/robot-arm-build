"""Train one local LoRA pilot on the checked synthetic proposal data."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import random


AI_DIR = Path(__file__).resolve().parents[1]
REPO = "meta-llama/Llama-3.2-1B-Instruct"
REVISION = "9213176726f574b556790deb65791e0c5aa438b6"
SEED = 2109


def _verified_rows(path: Path, digest: str) -> list[dict]:
    raw = path.read_bytes()
    if hashlib.sha256(raw).hexdigest() != digest:
        raise ValueError(f"data hash mismatch: {path.name}")
    return [json.loads(line) for line in raw.decode("utf-8").splitlines() if line.strip()]


def main() -> None:
    parser = argparse.ArgumentParser(description="Local, offline LoRA SFT pilot; no arm access")
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--device", default="cuda:0")
    parser.add_argument("--data-version", choices=("v0", "v1"), default="v0")
    args = parser.parse_args()
    train_seed = SEED if args.data_version == "v0" else 2110
    if args.output.exists():
        raise ValueError("output directory already exists; use a new run path")
    data_dir = AI_DIR / "data"
    data_prefix = f"synthetic_sft_{args.data_version}"
    manifest_path = data_dir / f"{data_prefix}.manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    for version, expected in manifest["benchmark_sha256"].items():
        path = AI_DIR / "eval" / f"benchmark_{version}.jsonl"
        if hashlib.sha256(path.read_bytes()).hexdigest() != expected:
            raise ValueError(f"benchmark {version} changed after data generation")
    train = _verified_rows(data_dir / f"{data_prefix}_train.jsonl", manifest["train_sha256"])
    validation = _verified_rows(data_dir / f"{data_prefix}_validation.jsonl", manifest["validation_sha256"])
    if (len(train), len(validation)) != (manifest["counts"]["train"], manifest["counts"]["validation"]):
        raise ValueError("data count mismatch")

    import torch
    from peft import LoraConfig, TaskType, get_peft_model
    from transformers import AutoModelForCausalLM, AutoTokenizer
    from torch.utils.data import DataLoader
    import transformers
    import peft

    if not args.device.startswith("cuda") or not torch.cuda.is_available() or not torch.cuda.is_bf16_supported():
        raise ValueError("this pilot requires a CUDA GPU with bfloat16 support")
    random.seed(train_seed)
    torch.manual_seed(train_seed)
    torch.cuda.manual_seed_all(train_seed)
    tokenizer = AutoTokenizer.from_pretrained(REPO, revision=REVISION, local_files_only=True)
    model = AutoModelForCausalLM.from_pretrained(
        REPO, revision=REVISION, local_files_only=True, torch_dtype=torch.bfloat16,
    ).to(args.device)
    model.config.use_cache = False
    model = get_peft_model(model, LoraConfig(
        task_type=TaskType.CAUSAL_LM, r=8, lora_alpha=16, lora_dropout=0.05,
        target_modules=["q_proj", "v_proj"], bias="none",
    ))

    from sys import path as sys_path
    sys_path.insert(0, str(AI_DIR))
    sys_path.insert(0, str(AI_DIR.parent / "src"))
    from rocell_ai.model_eval import SYSTEM_PROMPT, PROMPT_SHA256

    def encode(row: dict) -> tuple[list[int], list[int]]:
        user_content = json.dumps({"request": row["request"], "observation": row["observation"]}, ensure_ascii=False)
        messages = [{"role": "system", "content": SYSTEM_PROMPT}, {"role": "user", "content": user_content}]
        prefix = tokenizer.apply_chat_template(messages, tokenize=True, add_generation_prompt=True)
        answer = json.dumps(row["target"], separators=(",", ":"), sort_keys=True)
        full = tokenizer.apply_chat_template(messages + [{"role": "assistant", "content": answer}], tokenize=True)
        if full[:len(prefix)] != prefix or len(full) > 512:
            raise ValueError(f"chat template mismatch or sequence too long: {row['id']}")
        return full, [-100] * len(prefix) + full[len(prefix):]

    train_encoded = [encode(row) for row in train]
    valid_encoded = [encode(row) for row in validation]
    pad_id = tokenizer.pad_token_id if tokenizer.pad_token_id is not None else tokenizer.eos_token_id

    def collate(batch: list[tuple[list[int], list[int]]]) -> dict[str, torch.Tensor]:
        width = max(len(ids) for ids, _ in batch)
        return {
            "input_ids": torch.tensor([ids + [pad_id] * (width - len(ids)) for ids, _ in batch], dtype=torch.long),
            "attention_mask": torch.tensor([[1] * len(ids) + [0] * (width - len(ids)) for ids, _ in batch], dtype=torch.long),
            "labels": torch.tensor([labels + [-100] * (width - len(labels)) for _, labels in batch], dtype=torch.long),
        }

    loader = DataLoader(train_encoded, batch_size=4, shuffle=True, collate_fn=collate,
                        generator=torch.Generator().manual_seed(train_seed))
    valid_loader = DataLoader(valid_encoded, batch_size=4, shuffle=False, collate_fn=collate)
    optimizer = torch.optim.AdamW((p for p in model.parameters() if p.requires_grad), lr=2e-4, weight_decay=0.0)
    losses: list[dict[str, float]] = []
    updates = 0
    for epoch in range(2):
        model.train()
        optimizer.zero_grad(set_to_none=True)
        total_train = 0.0
        for batch_index, batch in enumerate(loader):
            batch = {key: value.to(args.device) for key, value in batch.items()}
            loss = model(**batch).loss
            if not torch.isfinite(loss):
                raise ValueError("nonfinite training loss")
            total_train += float(loss.detach())
            (loss / 4).backward()
            if (batch_index + 1) % 4 == 0 or batch_index + 1 == len(loader):
                torch.nn.utils.clip_grad_norm_(model.parameters(), 1.0)
                optimizer.step()
                optimizer.zero_grad(set_to_none=True)
                updates += 1
        model.eval()
        total_valid = 0.0
        with torch.inference_mode():
            for batch in valid_loader:
                batch = {key: value.to(args.device) for key, value in batch.items()}
                total_valid += float(model(**batch).loss)
        entry = {"epoch": epoch + 1, "train_loss": round(total_train / len(loader), 6),
                 "validation_loss": round(total_valid / len(valid_loader), 6)}
        losses.append(entry)
        print(json.dumps(entry), flush=True)

    args.output.mkdir(parents=True)
    model.save_pretrained(args.output)
    tokenizer.save_pretrained(args.output)
    adapter_path = args.output / "adapter_model.safetensors"
    run = {
        "schema": "rocell.ai_sft_run.v0",
        "base_repo": REPO,
        "base_revision": REVISION,
        "data_manifest_sha256": hashlib.sha256(manifest_path.read_bytes()).hexdigest(),
        "train_sha256": manifest["train_sha256"],
        "validation_sha256": manifest["validation_sha256"],
        "prompt_sha256": PROMPT_SHA256,
        "adapter_sha256": hashlib.sha256(adapter_path.read_bytes()).hexdigest(),
        "configuration": {"seed": train_seed, "epochs": 2, "batch_size": 4, "gradient_accumulation": 4,
                          "learning_rate": 2e-4, "max_sequence_length": 512,
                          "lora_r": 8, "lora_alpha": 16, "lora_dropout": 0.05,
                          "target_modules": ["q_proj", "v_proj"], "dtype": "bfloat16", "device": args.device},
        "versions": {"torch": torch.__version__, "transformers": transformers.__version__, "peft": peft.__version__},
        "optimizer_updates": updates,
        "losses": losses,
        "evidence_class": "offline_training_only",
        "hardware_commands": 0,
    }
    (args.output / "run_manifest.json").write_bytes((json.dumps(run, indent=2, sort_keys=True) + "\n").encode("utf-8"))
    print(json.dumps({"adapter_sha256": run["adapter_sha256"], "updates": updates}), flush=True)


if __name__ == "__main__":
    main()
