"""Fit the frozen mission student v2 LoRA trajectory without confirmation data."""

from __future__ import annotations

import argparse
import hashlib
import json
import random
import sys
from pathlib import Path


AI = Path(__file__).resolve().parents[1]
ROOT = AI.parents[1]
sys.path[:0] = [str(AI), str(AI.parent / "src")]

from rocell_ai.mission_model_v2 import PROMPT_SHA256, SYSTEM_PROMPT, render_user


def verified_rows(path: Path, digest: str):
    raw = path.read_bytes()
    if hashlib.sha256(raw).hexdigest() != digest:
        raise ValueError(f"data hash mismatch: {path.name}")
    return [json.loads(line) for line in raw.decode("utf-8").splitlines()]


def run(output: Path, device: str) -> None:
    plan_path = AI / "train/mission_student_v2_plan.json"
    plan = json.loads(plan_path.read_text(encoding="utf-8"))
    for name, digest in plan["file_sha256"].items():
        if hashlib.sha256((ROOT / name).read_bytes()).hexdigest() != digest:
            raise ValueError("source mismatch: " + name)
    if output.exists():
        raise FileExistsError("output directory already exists")

    import peft
    import torch
    import transformers
    from peft import LoraConfig, TaskType, get_peft_model
    from torch.utils.data import DataLoader
    from transformers import AutoModelForCausalLM, AutoTokenizer

    if not device.startswith("cuda") or not torch.cuda.is_available():
        raise ValueError("mission student training requires CUDA")
    if plan["dtype"] == "bfloat16" and not torch.cuda.is_bf16_supported():
        raise ValueError("mission student plan requires CUDA bfloat16 support")
    manifest = json.loads((ROOT / plan["data_manifest"]).read_text(encoding="utf-8"))
    train = verified_rows(ROOT / plan["train_data"], manifest["splits"]["train"]["sha256"])
    validation = verified_rows(
        ROOT / plan["validation_data"], manifest["splits"]["validation"]["sha256"]
    )
    if len(train) != manifest["splits"]["train"]["count"]:
        raise ValueError("training count mismatch")
    if len(validation) != manifest["splits"]["validation"]["count"]:
        raise ValueError("validation count mismatch")

    random.seed(plan["seed"])
    torch.manual_seed(plan["seed"])
    torch.cuda.manual_seed_all(plan["seed"])
    tokenizer = AutoTokenizer.from_pretrained(
        plan["base_repo"], revision=plan["base_revision"], local_files_only=True
    )
    model = AutoModelForCausalLM.from_pretrained(
        plan["base_repo"],
        revision=plan["base_revision"],
        local_files_only=True,
        torch_dtype=torch.bfloat16,
    ).to(device)
    model.config.use_cache = False
    model = get_peft_model(
        model,
        LoraConfig(
            task_type=TaskType.CAUSAL_LM,
            r=plan["lora_r"],
            lora_alpha=plan["lora_alpha"],
            lora_dropout=plan["lora_dropout"],
            target_modules=plan["target_modules"],
            bias="none",
        ),
    )

    def encode(row):
        messages = [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": render_user(row)},
        ]
        prefix = tokenizer.apply_chat_template(messages, tokenize=True, add_generation_prompt=True)
        answer = json.dumps(row["target"], sort_keys=True, separators=(",", ":"))
        full = tokenizer.apply_chat_template(
            messages + [{"role": "assistant", "content": answer}], tokenize=True
        )
        if full[: len(prefix)] != prefix or len(full) > plan["maximum_sequence_length"]:
            raise ValueError("chat template mismatch or sequence too long: " + row["id"])
        return full, [-100] * len(prefix) + full[len(prefix) :]

    train_encoded = [encode(row) for row in train]
    validation_encoded = [encode(row) for row in validation]
    pad = tokenizer.pad_token_id if tokenizer.pad_token_id is not None else tokenizer.eos_token_id

    def collate(batch):
        width = max(len(ids) for ids, _ in batch)
        return {
            "input_ids": torch.tensor(
                [ids + [pad] * (width - len(ids)) for ids, _ in batch], dtype=torch.long
            ),
            "attention_mask": torch.tensor(
                [[1] * len(ids) + [0] * (width - len(ids)) for ids, _ in batch],
                dtype=torch.long,
            ),
            "labels": torch.tensor(
                [labels + [-100] * (width - len(labels)) for _, labels in batch],
                dtype=torch.long,
            ),
        }

    loader = DataLoader(
        train_encoded,
        batch_size=plan["batch_size"],
        shuffle=True,
        collate_fn=collate,
        generator=torch.Generator().manual_seed(plan["seed"]),
    )
    validation_loader = DataLoader(
        validation_encoded,
        batch_size=plan["batch_size"],
        shuffle=False,
        collate_fn=collate,
    )
    optimizer = torch.optim.AdamW(
        (parameter for parameter in model.parameters() if parameter.requires_grad),
        lr=plan["learning_rate"],
        weight_decay=plan["weight_decay"],
    )
    output.mkdir(parents=True)
    history = []
    updates = 0
    for epoch in range(1, plan["epochs"] + 1):
        model.train()
        optimizer.zero_grad(set_to_none=True)
        train_total = 0.0
        for batch_index, batch in enumerate(loader):
            batch = {key: value.to(device) for key, value in batch.items()}
            loss = model(**batch).loss
            if not torch.isfinite(loss):
                raise ValueError("nonfinite training loss")
            train_total += float(loss.detach())
            (loss / plan["gradient_accumulation"]).backward()
            if (batch_index + 1) % plan["gradient_accumulation"] == 0 or batch_index + 1 == len(loader):
                torch.nn.utils.clip_grad_norm_(model.parameters(), plan["maximum_gradient_norm"])
                optimizer.step()
                optimizer.zero_grad(set_to_none=True)
                updates += 1
        model.eval()
        validation_total = 0.0
        with torch.inference_mode():
            for batch in validation_loader:
                batch = {key: value.to(device) for key, value in batch.items()}
                validation_total += float(model(**batch).loss)
        checkpoint = output / f"epoch-{epoch}"
        model.save_pretrained(checkpoint)
        tokenizer.save_pretrained(checkpoint)
        adapter_sha256 = hashlib.sha256(
            (checkpoint / "adapter_model.safetensors").read_bytes()
        ).hexdigest()
        entry = {
            "epoch": epoch,
            "train_loss": train_total / len(loader),
            "validation_loss": validation_total / len(validation_loader),
            "adapter_sha256": adapter_sha256,
        }
        (checkpoint / "run_manifest.json").write_bytes(
            (
                json.dumps(
                    {
                        "base_revision": plan["base_revision"],
                        "adapter_sha256": adapter_sha256,
                        "epoch": epoch,
                    },
                    indent=2,
                    sort_keys=True,
                )
                + "\n"
            ).encode("utf-8")
        )
        history.append(entry)
        print(json.dumps(entry), flush=True)

    run_manifest = {
        "schema": "rocell.mission_student_training.v2",
        "plan_sha256": hashlib.sha256(plan_path.read_bytes()).hexdigest(),
        "prompt_sha256": PROMPT_SHA256,
        "base_repo": plan["base_repo"],
        "base_revision": plan["base_revision"],
        "train_sha256": manifest["splits"]["train"]["sha256"],
        "validation_sha256": manifest["splits"]["validation"]["sha256"],
        "confirmation_read": False,
        "history": history,
        "selection_pending": True,
        "optimizer_updates": updates,
        "versions": {
            "torch": torch.__version__,
            "transformers": transformers.__version__,
            "peft": peft.__version__,
        },
        "model_fits": 1,
        "hardware_writes": 0,
        "physical_movements": 0,
        "limitations": [
            "Agent-authored templated development data without independent human labels.",
            "Checkpoint selection requires frozen structured validation scorecards.",
            "No confirmation fixture exists or is read during fit or selection.",
            "LoRA training grants no runtime, motion, or physical authority.",
        ],
    }
    (output / "run_manifest.json").write_bytes(
        (json.dumps(run_manifest, indent=2, sort_keys=True) + "\n").encode("utf-8")
    )
    print(json.dumps({"epochs": plan["epochs"], "updates": updates}))


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--device", default="cuda:0")
    args = parser.parse_args()
    run(args.output, args.device)


if __name__ == "__main__":
    main()
