"""Scene-tail classifier over frozen descriptors; output is uncalibrated risk."""

import math

import numpy as np
import torch
from torch import nn
from torch.utils.data import DataLoader, TensorDataset


class TailRiskClassifier(nn.Module):
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


def fit_classifier(features, labels, *, seed, epochs, batch_size, learning_rate, weight_decay):
    x = np.asarray(features, dtype=np.float64)
    y = np.asarray(labels, dtype=np.float64)
    if (
        x.ndim != 2
        or x.shape[1] != 512
        or y.shape != (len(x),)
        or len(x) < 2
        or not np.isfinite(x).all()
        or not np.isin(y, [0.0, 1.0]).all()
        or y.sum() == 0
        or y.sum() == len(y)
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
        raise ValueError("invalid classifier training inputs")
    mean = x.mean(0)
    std = x.std(0)
    scale = np.where(std < 1e-8, 1.0, std)
    normalized = torch.from_numpy(((x - mean) / scale).astype(np.float32))
    target = torch.from_numpy(y.astype(np.float32))
    positive_weight = float((len(y) - y.sum()) / y.sum())
    torch.manual_seed(seed)
    model = TailRiskClassifier()
    optimizer = torch.optim.AdamW(
        model.parameters(), lr=learning_rate, weight_decay=weight_decay
    )
    loss_function = nn.BCEWithLogitsLoss(pos_weight=torch.tensor(positive_weight))
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
            loss = loss_function(model(batch), truth)
            loss.backward()
            optimizer.step()
            updates += 1
    model.eval()
    with torch.no_grad():
        training_loss = float(loss_function(model(normalized), target))
    return {
        "mean": mean.tolist(),
        "scale": scale.tolist(),
        "state": {name: value.detach().cpu().tolist() for name, value in model.state_dict().items()},
        "positive_weight": positive_weight,
        "seed": seed,
        "epochs": epochs,
        "batch_size": batch_size,
        "learning_rate": learning_rate,
        "weight_decay": weight_decay,
        "optimizer_updates": updates,
        "training_weighted_bce": training_loss,
    }


def predict_risk(fit, features):
    x = np.asarray(features, dtype=np.float64)
    if x.ndim != 2 or x.shape[1] != 512 or not np.isfinite(x).all():
        raise ValueError("invalid classifier inference features")
    mean = np.asarray(fit["mean"])
    scale = np.asarray(fit["scale"])
    if mean.shape != (512,) or scale.shape != (512,) or np.any(scale <= 0):
        raise ValueError("invalid classifier normalization")
    model = TailRiskClassifier()
    state = {name: torch.tensor(value, dtype=torch.float32) for name, value in fit["state"].items()}
    model.load_state_dict(state, strict=True)
    model.eval()
    normalized = torch.from_numpy(((x - mean) / scale).astype(np.float32))
    with torch.no_grad():
        return torch.sigmoid(model(normalized)).numpy().astype(np.float64)
