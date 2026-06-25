#!/usr/bin/env python3
"""
MINDS benchmark adapter.
Run from MINDS/MINDS/ directory. Trains the model and outputs JSON metrics on the last line.
"""
import sys
import os
import json
import argparse
import copy
import time
import numpy as np
import torch
import torch.nn as nn
import torch.optim as optim
import torch.autograd

# Patch: MINDS DataSet.py uses Variable(data, volatile=True) which is removed in modern PyTorch.
# Replace Variable with a function that drops the 'volatile' kwarg.
def _variable_compat(data, **kwargs):
    kwargs.pop('volatile', None)
    requires_grad = kwargs.pop('requires_grad', False)
    if isinstance(data, torch.Tensor):
        return data.requires_grad_(requires_grad)
    return torch.tensor(data, requires_grad=requires_grad)

torch.autograd.Variable = _variable_compat

sys.path.insert(0, os.getcwd())  # ensure MINDS/ modules are importable when run as subprocess

from HypergraphUtil import RelationGraph, DynamicCasHypergraph
from Metrics import compute_metric
from Module import Module
from DataSet import SplitData, DataLoader
import Constants


def MAE(y, y_predicted):
    y_predicted = y_predicted.squeeze()
    return torch.mean(torch.abs(y_predicted - y))


def MSLE(y, y_predicted):
    predicted = y_predicted.cpu().detach().numpy().squeeze().copy()
    predicted[predicted < 1] = 1
    label = y.cpu().detach().numpy()
    return float(np.mean(np.square(np.log2(predicted) - np.log2(label))))


def get_previous_user_mask(seq, user_size):
    assert seq.dim() == 2
    prev_shape = (seq.size(0), seq.size(1), seq.size(1))
    seqs = seq.repeat(1, 1, seq.size(1)).view(seq.size(0), seq.size(1), seq.size(1))
    previous_mask = np.tril(np.ones(prev_shape)).astype('float32')
    previous_mask = torch.from_numpy(previous_mask)
    if seq.is_cuda:
        previous_mask = previous_mask.cuda()
    masked_seq = previous_mask * seqs.data.float()
    PAD_tmp = torch.zeros(seq.size(0), seq.size(1), 1)
    masked_seq = torch.cat([masked_seq, PAD_tmp], dim=2)
    ans_tmp = torch.zeros(seq.size(0), seq.size(1), user_size)
    masked_seq = ans_tmp.scatter_(2, masked_seq.long(), float('-inf'))
    return masked_seq


def train_epoch(model, loader, relation_graph, hypergraph_list, crit, optimizer,
                lambda_loss, gamma_loss, user_size, device):
    model.train()
    total_loss = 0.0
    n_total_words = 0.0
    for batch in loader:
        tgt, tgt_ts, tgt_idx, tgt_len = (x.to(device) for x in batch)
        gold = tgt[:, 1:]
        n_words = gold.data.ne(Constants.PAD).sum().float()
        n_total_words += n_words
        pred_micro, pred_macro, loss_adv, loss_diff = model(hypergraph_list, relation_graph, tgt)
        mask = get_previous_user_mask(tgt[:, :-1].cpu(), user_size).to(device)
        pred_flat = (pred_micro[:, :-1, :] + mask).view(-1, pred_micro.size(-1))
        micro_loss = crit(pred_flat, gold.contiguous().view(-1))
        macro_loss = MAE(tgt_len.float(), pred_macro)
        loss = (1 - lambda_loss) * micro_loss + lambda_loss * macro_loss + loss_adv + gamma_loss * loss_diff
        optimizer.zero_grad()
        loss.backward()
        optimizer.step()
        total_loss += loss.item()
    return total_loss / n_total_words


def test_epoch(model, loader, relation_graph, hypergraph_list, user_size, device, k_list):
    model.eval()
    scores = {f"hits@{k}": 0.0 for k in k_list}
    scores.update({f"map@{k}": 0.0 for k in k_list})
    msle_vals = []
    n_total_words = 0.0
    with torch.no_grad():
        for batch in loader:
            tgt, tgt_ts, tgt_idx, tgt_len = (x.to(device) for x in batch)
            gold = tgt[:, 1:].contiguous().view(-1).detach().cpu().numpy()
            pred_micro, pred_macro, _, _ = model(hypergraph_list, relation_graph, tgt)
            mask = get_previous_user_mask(tgt[:, :-1].cpu(), user_size).to(device)
            y_pred = (pred_micro[:, :-1, :] + mask).view(-1, pred_micro.size(-1)).detach().cpu().numpy()
            scores_batch, scores_len = compute_metric(y_pred, gold, k_list)
            n_total_words += scores_len
            for k in k_list:
                scores[f"hits@{k}"] += scores_batch[f"hits@{k}"] * scores_len
                scores[f"map@{k}"] += scores_batch[f"map@{k}"] * scores_len
            msle_vals.append(MSLE(tgt_len.float(), pred_macro))
    for k in k_list:
        scores[f"hits@{k}"] /= n_total_words
        scores[f"map@{k}"] /= n_total_words
    return scores, float(np.mean(msle_vals))


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--dataset_name", default="douban")
    parser.add_argument("--epochs", type=int, default=30)
    parser.add_argument("--batch_size", type=int, default=64)
    parser.add_argument("--emb_dim", type=int, default=64)
    parser.add_argument("--k_list", nargs="+", type=int, default=[10, 50, 100])
    parser.add_argument("--lambda_loss", type=float, default=0.3)
    parser.add_argument("--gamma_loss", type=float, default=0.05)
    parser.add_argument("--step_split", type=int, default=8)
    parser.add_argument("--max_seq_length", type=int, default=200)
    parser.add_argument("--lr", type=float, default=0.001)
    parser.add_argument("--device", default="cpu")
    args = parser.parse_args()

    torch.manual_seed(42)
    np.random.seed(42)
    device = torch.device("cuda" if args.device == "cuda" and torch.cuda.is_available() else "cpu")

    print(f"[MINDS] Loading data: {args.dataset_name}")
    user_size, total_cascades, timestamps, train, valid, test = SplitData(
        args.dataset_name, train_rate=0.8, valid_rate=0.1, load_dict=True
    )

    train_loader = DataLoader(train, args.batch_size, load_dict=True, cuda=False)
    valid_loader = DataLoader(valid, args.batch_size, load_dict=True, cuda=False)
    test_loader = DataLoader(test, args.batch_size, load_dict=True, cuda=False)

    print(f"[MINDS] Building graphs for {args.dataset_name}...")
    relation_graph = RelationGraph(args.dataset_name, device)
    hypergraph_list = DynamicCasHypergraph(total_cascades, timestamps, user_size, device, args.step_split)

    model = Module(user_size, args.emb_dim, args.step_split, args.max_seq_length, 2, device).to(device)
    optimizer = optim.Adam(model.parameters(), lr=args.lr)
    crit = nn.CrossEntropyLoss(reduction='sum', ignore_index=Constants.PAD)

    best_state = None
    best_epoch = None
    best_valid_scores = None
    best_valid_msle = None
    best_map = float('-inf')
    last_k = args.k_list[-1]

    for epoch_i in range(args.epochs):
        loss = train_epoch(model, train_loader, relation_graph, hypergraph_list,
                           crit, optimizer, args.lambda_loss, args.gamma_loss, user_size, device)
        print(f"  Epoch {epoch_i+1}/{args.epochs} loss={loss:.4f}")

        scores, msle = test_epoch(model, valid_loader, relation_graph, hypergraph_list,
                                  user_size, device, args.k_list)
        map_score = scores.get(f"map@{last_k}", 0.0)
        print(f"  [Valid] MAP@{last_k}={map_score:.4f} MSLE={msle:.4f}")

        if map_score > best_map:
            best_map = map_score
            best_epoch = epoch_i + 1
            best_valid_scores = scores
            best_valid_msle = msle
            best_state = copy.deepcopy(model.state_dict())

    if best_state is not None:
        model.load_state_dict(best_state)
    test_scores, test_msle = test_epoch(model, test_loader, relation_graph,
                                        hypergraph_list, user_size, device, args.k_list)

    result = {
        "model": "MINDS",
        "dataset": args.dataset_name,
        "epochs": args.epochs,
        "selection": f"best_valid_map@{last_k}",
        "best_epoch": best_epoch,
        f"valid_map@{last_k}": float(best_valid_scores[f"map@{last_k}"]) if best_valid_scores else None,
        "valid_msle": float(best_valid_msle) if best_valid_msle is not None else None,
    }
    for k in args.k_list:
        result[f"hits@{k}"] = float(test_scores[f"hits@{k}"])
        result[f"map@{k}"] = float(test_scores[f"map@{k}"])
    result["msle"] = float(test_msle)
    result["mae"] = None  # MAE not separately tracked at inference; MSLE is the primary macro metric

    print(json.dumps(result))


if __name__ == "__main__":
    main()
