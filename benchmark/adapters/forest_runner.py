#!/usr/bin/env python3
"""
FOREST benchmark adapter.
Run from FOREST/ directory. Trains the model and outputs JSON metrics on the last line.
"""
import sys
import os
import json
import argparse
import math
import time
import copy
import numpy as np
import torch
import torch.nn as nn
import torch.optim as optim
import torch.autograd
from tqdm import tqdm

# Patch: FOREST DataLoader.py uses Variable(data, volatile=True) which errors in modern PyTorch.
def _variable_compat(data, **kwargs):
    kwargs.pop('volatile', None)
    requires_grad = kwargs.pop('requires_grad', False)
    if isinstance(data, torch.Tensor):
        return data.requires_grad_(requires_grad)
    return torch.tensor(data, requires_grad=requires_grad)

torch.autograd.Variable = _variable_compat

# Patch: FOREST model.py uses .cuda() unconditionally. Make it a no-op on CPU.
if not torch.cuda.is_available():
    _orig_cuda = torch.Tensor.cuda
    torch.Tensor.cuda = lambda self, *args, **kwargs: self

sys.path.insert(0, os.getcwd())  # ensure FOREST/ modules are importable when run as subprocess

import Constants
from model import RNNModel, RRModel
from Optim import ScheduledOptim
from DataLoader import DataLoader


def get_performance(crit, pred, gold):
    loss = crit(pred, gold.contiguous().view(-1))
    pred = pred.max(1)[1]
    gold = gold.contiguous().view(-1)
    n_correct = pred.data.eq(gold.data)
    n_correct = n_correct.masked_select(gold.ne(Constants.PAD).data).sum().float()
    return loss, n_correct


def train_epoch(model, training_data, crit, optimizer):
    model.train()
    total_loss = 0.0
    n_total_words = 0.0
    n_total_correct = 0.0

    for batch in tqdm(training_data, mininterval=2, desc="  - (Training)", leave=False):
        tgt = batch
        gold = tgt[:, 1:]
        n_words = gold.data.ne(Constants.PAD).sum().float()
        n_total_words += n_words

        optimizer.zero_grad()
        pred, *_ = model(tgt, RL_train=False)
        loss, n_correct = get_performance(crit, pred, gold)
        loss.backward()
        optimizer.step()
        optimizer.update_learning_rate()

        n_total_correct += n_correct
        total_loss += loss.item()

    return total_loss / n_total_words, n_total_correct / n_total_words


def test_epoch(model, test_data, k_list):
    model.eval()
    scores = {}
    for k in k_list:
        scores[f"hits@{k}"] = 0
        scores[f"map@{k}"] = 0
    n_total_words = 0

    import metrics as m

    with torch.no_grad():
        for batch in tqdm(test_data, mininterval=2, desc="  - (Test)", leave=False):
            tgt = batch
            gold = tgt[:, 1:]
            pred, *_ = model(tgt, RL_train=False)
            scores_batch, scores_len = m.portfolio(
                pred.detach().cpu().numpy(),
                gold.contiguous().view(-1).detach().cpu().numpy(),
                k_list,
            )
            n_total_words += scores_len
            for k in k_list:
                scores[f"hits@{k}"] += scores_batch[f"hits@{k}"] * scores_len
                scores[f"map@{k}"] += scores_batch[f"map@{k}"] * scores_len

    for k in k_list:
        scores[f"hits@{k}"] /= n_total_words
        scores[f"map@{k}"] /= n_total_words

    return scores


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--data_name", default="twitter")
    parser.add_argument("--epochs", type=int, default=30)
    parser.add_argument("--batch_size", type=int, default=32)
    parser.add_argument("--d_model", type=int, default=64)
    parser.add_argument("--k_list", nargs="+", type=int, default=[10, 50, 100])
    parser.add_argument("--device", default="cpu")
    parser.add_argument("--no_network", action="store_true")
    parser.add_argument("--n_warmup_steps", type=int, default=1000)
    args = parser.parse_args()

    torch.manual_seed(42)
    np.random.seed(42)
    use_cuda = args.device == "cuda" and torch.cuda.is_available()

    class Opt:
        pass

    opt = Opt()
    opt.d_model = args.d_model
    opt.d_word_vec = args.d_model
    opt.d_inner_hid = args.d_model
    opt.network = not args.no_network
    opt.pos_emb = True
    opt.data_name = args.data_name

    # Auto-detect missing network embeddings
    embed_path = f"data/{args.data_name}/dw{args.d_model}.txt"
    if opt.network and not os.path.exists(embed_path):
        print(f"[FOREST] WARNING: Network embeddings not found at {embed_path}, disabling network mode")
        opt.network = False

    print(f"[FOREST] Loading data: {args.data_name}")
    train_data = DataLoader(
        args.data_name, data=0, load_dict=True,
        batch_size=args.batch_size, cuda=use_cuda, loadNE=opt.network
    )
    valid_data = DataLoader(
        args.data_name, data=1,
        batch_size=args.batch_size, cuda=use_cuda, loadNE=opt.network
    )
    test_data = DataLoader(
        args.data_name, data=2,
        batch_size=args.batch_size, cuda=use_cuda, loadNE=opt.network
    )

    opt.user_size = train_data.user_size
    if opt.network:
        opt.net = train_data._adj_list
        opt.net_dict = train_data._adj_dict_list
        opt.embeds = train_data._embeds

    print(f"[FOREST] user_size={opt.user_size}, network={opt.network}")

    decoder = RNNModel("GRUCell", opt)
    model = RRModel(decoder)

    optimizer = ScheduledOptim(
        optim.Adam(model.parameters(), betas=(0.9, 0.98), eps=1e-09),
        opt.d_model, args.n_warmup_steps,
    )

    weight = torch.ones(opt.user_size)
    weight[Constants.PAD] = 0
    weight[Constants.EOS] = 1
    crit = nn.CrossEntropyLoss(weight, reduction='sum')

    if use_cuda:
        decoder = decoder.cuda()
        model = model.cuda()
        crit = crit.cuda()

    best_state = None
    best_scores = None
    best_epoch = None
    best_accu = float("-inf")

    for epoch_i in range(args.epochs):
        start = time.time()
        train_loss, train_accu = train_epoch(model, train_data, crit, optimizer)
        elapsed = (time.time() - start) / 60
        print(
            f"  Epoch {epoch_i+1}/{args.epochs} - "
            f"loss: {train_loss:.4f}, accu: {train_accu*100:.2f}%, "
            f"time: {elapsed:.1f}min"
        )

        if (epoch_i + 1) % 5 == 0 or epoch_i == args.epochs - 1:
            scores = test_epoch(model, valid_data, args.k_list)
            map_score = scores.get(f"map@{args.k_list[-1]}", 0)
            print(f"  [Valid] MAP@{args.k_list[-1]}={map_score:.4f}")
            if map_score > best_accu:
                best_accu = map_score
                best_epoch = epoch_i + 1
                best_scores = scores
                best_state = copy.deepcopy(model.state_dict())

    if best_state is not None:
        model.load_state_dict(best_state)
    test_scores = test_epoch(model, test_data, args.k_list)

    result = {
        "model": "FOREST",
        "dataset": args.data_name,
        "epochs": args.epochs,
        "selection": f"best_valid_map@{args.k_list[-1]}",
        "best_epoch": best_epoch,
        f"valid_map@{args.k_list[-1]}": float(best_scores[f"map@{args.k_list[-1]}"]) if best_scores else None,
    }
    for k in args.k_list:
        result[f"hits@{k}"] = float(test_scores[f"hits@{k}"])
        result[f"map@{k}"] = float(test_scores[f"map@{k}"])
    result["msle"] = None
    result["mae"] = None

    print(json.dumps(result))


if __name__ == "__main__":
    main()
