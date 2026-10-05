"""PyTorch networks: CNN-LSTM for RUL and an autoencoder for anomaly detection."""
import numpy as np
import torch
from torch import nn


class CnnLstm(nn.Module):
    """1D-CNN picks out short sensor patterns, the LSTM follows them over the 30-cycle window."""

    def __init__(self, n_feat: int, hidden: int = 64):
        super().__init__()
        self.conv = nn.Sequential(
            nn.Conv1d(n_feat, 32, 3, padding=1), nn.ReLU(),
            nn.Conv1d(32, 32, 3, padding=1), nn.ReLU(),
        )
        self.lstm = nn.LSTM(32, hidden, batch_first=True)
        self.head = nn.Sequential(nn.Linear(hidden, 32), nn.ReLU(), nn.Linear(32, 1))

    def forward(self, x):  # x: (batch, window, features)
        z = self.conv(x.transpose(1, 2)).transpose(1, 2)
        out, _ = self.lstm(z)
        return self.head(out[:, -1]).squeeze(-1)


class AutoEncoder(nn.Module):
    def __init__(self, n_feat: int):
        super().__init__()
        self.enc = nn.Sequential(nn.Linear(n_feat, 10), nn.ReLU(), nn.Linear(10, 4))
        self.dec = nn.Sequential(nn.Linear(4, 10), nn.ReLU(), nn.Linear(10, n_feat))

    def forward(self, x):
        return self.dec(self.enc(x))


def recon_error(model, x):
    with torch.no_grad():
        t = torch.as_tensor(np.array(x), dtype=torch.float32)
        return ((model(t) - t) ** 2).mean(dim=1).numpy()
