import copy
import random

import numpy as np
import pandas as pd
import torch
import torch.nn as nn
import torch.nn.functional as F
import torch.utils.data as Data
from typing import Optional


class EncoderBlock(nn.Module):
    def __init__(self, in_dim: int, out_dim: int, dropout: float):
        super().__init__()
        self.layer = nn.Sequential(
            nn.Linear(in_dim, out_dim),
            nn.LeakyReLU(0.2, inplace=True),
            nn.Dropout(p=dropout, inplace=False),
        )

    def forward(self, x):
        return self.layer(x)


class PrototypeBank(nn.Module):
    def __init__(self, k_size: int, input_dim: int, label_dim: int, device: torch.device):
        super().__init__()
        self.register_buffer("feature", torch.zeros(k_size, input_dim, device=device))
        self.register_buffer("label", torch.zeros(k_size, label_dim, device=device))
        self.k_size = k_size

    def update(self, new_features, new_labels):
        self.feature.copy_(new_features)
        self.label.copy_(new_labels)


def _cosine_score(pred, gt):
    return torch.clamp(F.cosine_similarity(pred, gt, dim=1), 0, 1)


def _similarity_matrix(x):
    x_norm = F.normalize(x, p=2, dim=1)
    return torch.matmul(x_norm, x_norm.t())


def _cross_similarity(x, y):
    x_norm = F.normalize(x, p=2, dim=1)
    y_norm = F.normalize(y, p=2, dim=1)
    return torch.matmul(x_norm, y_norm.t())


def composition_alignment_loss(batch_embedding, batch_label, bank_embedding, bank_label):
    feature_sim = _cross_similarity(batch_embedding, bank_embedding)
    label_sim = _cross_similarity(batch_label, bank_label)
    return F.mse_loss(feature_sim, label_sim.detach())


class SupervisedDeconv:
    def __init__(
        self,
        num_epochs: int,
        batch_size: int,
        learning_rate: float,
        seed: int = 2021,
        device: Optional[str] = None,
    ):
        self.num_epochs = int(num_epochs)
        self.batch_size = int(batch_size)
        self.learning_rate = float(learning_rate)
        self.seed = int(seed)
        self.device = torch.device(device or ("cuda" if torch.cuda.is_available() else "cpu"))
        self.celltype_num = None
        self.labels = None
        self.used_features = None
        self.encoder = None
        self.predictor = None
        self.model = None
        self._set_seed()

    def _set_seed(self):
        random.seed(self.seed)
        np.random.seed(self.seed)
        torch.manual_seed(self.seed)
        if torch.cuda.is_available():
            torch.cuda.manual_seed_all(self.seed)
        torch.backends.cudnn.deterministic = True
        torch.backends.cudnn.benchmark = False

    def _build_model(self):
        feature_num = len(self.used_features)
        self.encoder = nn.Sequential(
            EncoderBlock(feature_num, 512, 0.0),
            EncoderBlock(512, 256, 0.3),
        )
        self.predictor = nn.Sequential(
            EncoderBlock(256, 128, 0.2),
            nn.Linear(128, self.celltype_num),
            nn.Softmax(dim=1),
        )
        self.model = nn.ModuleList([self.encoder, self.predictor]).to(self.device)

    def _make_loader(self, adata, batch_size: int, shuffle: bool):
        x = np.asarray(adata.X, dtype=np.float32)
        y = np.asarray([adata.obs[ctype].to_numpy() for ctype in self.labels], dtype=np.float32).T
        dataset = Data.TensorDataset(torch.FloatTensor(x), torch.FloatTensor(y))
        return Data.DataLoader(dataset=dataset, batch_size=batch_size, shuffle=shuffle)

    def prepare_dataloaders(self, source_data, target_data, valid_data):
        self.labels = list(source_data.uns["cell_types"])
        self.celltype_num = len(self.labels)
        self.used_features = list(source_data.var_names)
        self.train_source_loader = self._make_loader(source_data, self.batch_size, shuffle=True)
        self.test_target_loader = self._make_loader(target_data, self.batch_size, shuffle=False)
        self.valid_target_loader = self._make_loader(valid_data, self.batch_size, shuffle=False)

    def train(self, source_data, target_data, valid_data, patience: int):
        self.prepare_dataloaders(source_data, target_data, valid_data)
        self._build_model()

        optimizer = torch.optim.Adam(
            [{"params": self.encoder.parameters()}, {"params": self.predictor.parameters()}],
            lr=self.learning_rate,
        )
        criterion = nn.L1Loss().to(self.device)

        best_rmse = float("inf")
        best_weights = None
        counter = 0
        losses = []

        for epoch in range(self.num_epochs):
            self.model.train()
            pred_loss_epoch = 0.0
            for source_x, source_y in self.train_source_loader:
                source_x = source_x.to(self.device)
                source_y = source_y.to(self.device)
                embedding = self.encoder(source_x)
                pred = self.predictor(embedding)
                loss = criterion(pred, source_y)
                optimizer.zero_grad()
                loss.backward()
                optimizer.step()
                pred_loss_epoch += loss.item()

            avg_loss = pred_loss_epoch / max(1, len(self.train_source_loader))
            losses.append(avg_loss)
            valid_rmse = self.evaluate(self.valid_target_loader)
            print(f"[Epoch {epoch + 1}/{self.num_epochs}] pred={avg_loss:.6f} valid_rmse={valid_rmse:.6f}")

            if valid_rmse < best_rmse:
                best_rmse = valid_rmse
                counter = 0
                best_weights = {
                    "encoder": copy.deepcopy(self.encoder.state_dict()),
                    "predictor": copy.deepcopy(self.predictor.state_dict()),
                }
            else:
                counter += 1
                if counter >= patience:
                    print(f"Early stopping at epoch {epoch + 1}; best_rmse={best_rmse:.6f}")
                    break

        if best_weights is not None:
            self.encoder.load_state_dict(best_weights["encoder"])
            self.predictor.load_state_dict(best_weights["predictor"])
        return losses, best_weights

    def prediction(self, loader):
        self.model.eval()
        preds = []
        gts = []
        with torch.no_grad():
            for x, y in loader:
                x = x.to(self.device)
                logits = self.predictor(self.encoder(x)).detach().cpu().numpy()
                preds.append(logits)
                gts.append(y.detach().cpu().numpy())
        return (
            pd.DataFrame(np.concatenate(preds, axis=0), columns=self.labels),
            pd.DataFrame(np.concatenate(gts, axis=0), columns=self.labels),
        )

    def evaluate(self, loader):
        pred, gt = self.prediction(loader)
        rmses = [np.sqrt(np.mean((pred[label] - gt[label]) ** 2)) for label in self.labels]
        return float(np.mean(rmses))


class PrototypeDeconv(SupervisedDeconv):
    def __init__(
        self,
        num_epochs: int,
        batch_size: int,
        learning_rate: float,
        seed: int = 2021,
        device: Optional[str] = None,
        warmup_epochs: int = 6,
        align_weight: float = 0.01,
        prototype_size: Optional[int] = None,
    ):
        super().__init__(num_epochs, batch_size, learning_rate, seed=seed, device=device)
        self.warmup_epochs = int(warmup_epochs)
        self.align_weight = float(align_weight)
        self.prototype_size = int(prototype_size or batch_size)
        self.bank = None

    def _build_model(self):
        super()._build_model()
        self.bank = PrototypeBank(
            k_size=self.prototype_size,
            input_dim=len(self.used_features),
            label_dim=self.celltype_num,
            device=self.device,
        )

    def refresh_prototypes(self):
        self.model.eval()
        all_x = []
        all_y = []
        all_scores = []
        with torch.no_grad():
            for source_x, source_y in self.train_source_loader:
                source_x = source_x.to(self.device)
                source_y = source_y.to(self.device)
                pred = self.predictor(self.encoder(source_x))
                all_x.append(source_x)
                all_y.append(source_y)
                all_scores.append(_cosine_score(pred, source_y))

        full_x = torch.cat(all_x, dim=0)
        full_y = torch.cat(all_y, dim=0)
        full_scores = torch.cat(all_scores, dim=0)
        k = min(self.bank.k_size, full_scores.shape[0])
        _, top_indices = torch.topk(full_scores, k=k, largest=True)
        old_labels = self.bank.label[:k].clone()
        self.bank.feature[:k].copy_(full_x[top_indices])
        self.bank.label[:k].copy_(full_y[top_indices])
        update_magnitude = torch.mean(torch.abs(self.bank.label[:k] - old_labels)).item()
        avg_score = torch.mean(full_scores[top_indices]).item()
        return update_magnitude, avg_score

    def train(self, source_data, target_data, valid_data, patience: int):
        self.prepare_dataloaders(source_data, target_data, valid_data)
        self._build_model()

        optimizer = torch.optim.Adam(
            [{"params": self.encoder.parameters()}, {"params": self.predictor.parameters()}],
            lr=self.learning_rate,
        )
        criterion = nn.L1Loss().to(self.device)

        best_rmse = float("inf")
        best_weights = None
        counter = 0
        losses = []

        for epoch in range(self.num_epochs):
            if epoch >= self.warmup_epochs:
                up_mag, bank_score = self.refresh_prototypes()
                print(f"[Prototype] update={up_mag:.6f} score={bank_score:.6f}")

            self.model.train()
            pred_loss_epoch = 0.0
            for source_x, source_y in self.train_source_loader:
                source_x = source_x.to(self.device)
                source_y = source_y.to(self.device)
                embedding = self.encoder(source_x)
                pred = self.predictor(embedding)
                pred_loss = criterion(pred, source_y)

                if epoch >= self.warmup_epochs:
                    with torch.no_grad():
                        bank_embedding = self.encoder(self.bank.feature)
                        bank_pred = self.predictor(bank_embedding)
                    align_loss = composition_alignment_loss(
                        embedding,
                        pred,
                        bank_embedding,
                        bank_pred,
                    )
                    loss = pred_loss + self.align_weight * align_loss
                else:
                    loss = pred_loss

                optimizer.zero_grad()
                loss.backward()
                optimizer.step()
                pred_loss_epoch += pred_loss.item()

            avg_loss = pred_loss_epoch / max(1, len(self.train_source_loader))
            losses.append(avg_loss)
            valid_rmse = self.evaluate(self.valid_target_loader)
            print(f"[Epoch {epoch + 1}/{self.num_epochs}] pred={avg_loss:.6f} valid_rmse={valid_rmse:.6f}")

            if valid_rmse < best_rmse:
                best_rmse = valid_rmse
                counter = 0
                best_weights = {
                    "encoder": copy.deepcopy(self.encoder.state_dict()),
                    "predictor": copy.deepcopy(self.predictor.state_dict()),
                }
            else:
                counter += 1
                if counter >= patience:
                    print(f"Early stopping at epoch {epoch + 1}; best_rmse={best_rmse:.6f}")
                    break

        if best_weights is not None:
            self.encoder.load_state_dict(best_weights["encoder"])
            self.predictor.load_state_dict(best_weights["predictor"])
        return losses, best_weights
