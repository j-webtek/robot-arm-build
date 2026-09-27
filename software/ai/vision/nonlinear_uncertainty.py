"""Small nonlinear uncertainty head; output is an uncalibrated error scale."""

import math

import numpy as np
import torch
from torch import nn
from torch.utils.data import DataLoader, TensorDataset


class NonlinearUncertaintyHead(nn.Module):
    def __init__(self):
        super().__init__()
        self.network = nn.Sequential(
            nn.Linear(512, 32),
            nn.GELU(),
            nn.Linear(32, 8),
            nn.GELU(),
            nn.Linear(8, 1),
        )

    def forward(self, features):
        if features.ndim != 2 or features.shape[1] != 512 or features.dtype != torch.float32:
            raise ValueError("expected float32 N x 512 features")
        return self.network(features).squeeze(1)


def fit_head(features, errors, *, seed, epochs, batch_size, learning_rate, weight_decay):
    x = np.asarray(features, dtype=np.float64)
    error = np.asarray(errors, dtype=np.float64)
    if (
        x.ndim != 2
        or x.shape[1] != 512
        or error.shape != (len(x),)
        or len(x) < 2
        or not np.isfinite(x).all()
        or not np.isfinite(error).all()
        or np.any(error < 0)
        or type(seed) is not int
        or type(epochs) is not int
        or epochs <= 0
        or type(batch_size) is not int
        or batch_size <= 0
        or not math.isfinite(learning_rate)
        or learning_rate <= 0
        or not math.isfinite(weight_decay)
        or weight_decay < 0
    ):
        raise ValueError("invalid uncertainty training inputs")
    mean = x.mean(0)
    std = x.std(0)
    scale = np.where(std < 1e-8, 1.0, std)
    normalized = torch.from_numpy(((x - mean) / scale).astype(np.float32))
    target = torch.from_numpy(np.log(error + 0.1).astype(np.float32))
    torch.manual_seed(seed)
    model = NonlinearUncertaintyHead()
    optimizer = torch.optim.AdamW(
        model.parameters(), lr=learning_rate, weight_decay=weight_decay
    )
    generator = torch.Generator().manual_seed(seed)
    loader = DataLoader(
        TensorDataset(normalized, target),
        batch_size=batch_size,
        shuffle=True,
        generator=generator,
    )
    updates = 0
    model.train()
    for _ in range(epochs):
        for batch, truth in loader:
            optimizer.zero_grad(set_to_none=True)
            loss = torch.mean((model(batch) - truth) ** 2)
            loss.backward()
            optimizer.step()
            updates += 1
    model.eval()
    with torch.no_grad():
        final_loss = float(torch.mean((model(normalized) - target) ** 2))
    state = {name: value.detach().cpu().tolist() for name, value in model.state_dict().items()}
    return {
        "mean": mean.tolist(),
        "scale": scale.tolist(),
        "state": state,
        "seed": seed,
        "epochs": epochs,
        "batch_size": batch_size,
        "learning_rate": learning_rate,
        "weight_decay": weight_decay,
        "optimizer_updates": updates,
        "training_log_mse": final_loss,
    }


def predict_head(fit, features):
    x = np.asarray(features, dtype=np.float64)
    if x.ndim != 2 or x.shape[1] != 512 or not np.isfinite(x).all():
        raise ValueError("invalid uncertainty inference features")
    mean = np.asarray(fit["mean"])
    scale = np.asarray(fit["scale"])
    if mean.shape != (512,) or scale.shape != (512,) or np.any(scale <= 0):
        raise ValueError("invalid uncertainty normalization")
    model = NonlinearUncertaintyHead()
    state = {name: torch.tensor(value, dtype=torch.float32) for name, value in fit["state"].items()}
    model.load_state_dict(state, strict=True)
    model.eval()
    normalized = torch.from_numpy(((x - mean) / scale).astype(np.float32))
    with torch.no_grad():
        log_scale = model(normalized).numpy().astype(np.float64)
    return np.exp(np.clip(log_scale, np.log(0.1), np.log(20.0)))
