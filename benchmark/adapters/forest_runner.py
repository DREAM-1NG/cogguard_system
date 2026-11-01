#!/usr/bin/env python3
"""
FOREST benchmark adapter.
Run from FOREST/ directory. Trains the model and outputs JSON metrics on the last line.
"""
import sys
import os
import json
import argparse
from contextlib import contextmanager
import math
import time
import copy
import shutil
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
_FORCE_CPU = "--device" in sys.argv and "cpu" in sys.argv
if _FORCE_CPU or not torch.cuda.is_available():
    _orig_tensor_cuda = torch.Tensor.cuda
    _orig_module_cuda = nn.Module.cuda
    torch.Tensor.cuda = lambda self, *args, **kwargs: self
    nn.Module.cuda = lambda self, *args, **kwargs: self

sys.path.insert(0, os.getcwd())  # ensure FOREST/ modules are importable when run as subprocess

import Constants
from model import RNNModel, RRModel
from Optim import ScheduledOptim
from DataLoader import DataLoader


@contextmanager
def staged_dataset(data_name: str, data_root: str | None):
    """Expose migrated FOREST data as ./data/<dataset> for the upstream loader."""

    if not data_root:
        yield
        return
    src = os.path.join(data_root, data_name)
    dst_parent = os.path.join(os.getcwd(), "data")
    dst = os.path.join(dst_parent, data_name)
    if os.path.isdir(dst):
        yield
        return
    if not os.path.isdir(src):
        raise FileNotFoundError(f"FOREST data root does not contain {data_name}: {src}")

    os.makedirs(dst_parent, exist_ok=True)
    created = False
    try:
        try:
            os.symlink(src, dst, target_is_directory=True)
        except OSError:
            shutil.copytree(src, dst)
        created = True
        yield
    finally:
        if created:
            if os.path.islink(dst):
                os.unlink(dst)
            elif os.path.isdir(dst):
                shutil.rmtree(dst)
            try:
                os.rmdir(dst_parent)
            except OSError:
                pass


def get_performance(crit, pred, gold):
    loss = crit(pred, gold.contiguous().view(-1))
    pred = pred.max(1)[1]
    gold = gold.contiguous().view(-1)
    n_correct = pred.data.eq(gold.data)
    n_correct = n_correct.masked_select(gold.ne(Constants.PAD).data).sum().float()
    return loss, n_correct


def get_performance_rl(pred_ids, pred_log_probs, tgt, expect, device):
    """FOREST policy-gradient reward over generated cascade size.

    This mirrors the upstream train.py reward: compare the generated EOS
    position with the true EOS position in log space and weight sampled
    sequence log-probability by the centered reward.
    """

    eos_pad = torch.zeros(pred_log_probs.size(0), 1, device=device, dtype=pred_log_probs.dtype)
    pred_log_probs = torch.cat([pred_log_probs, eos_pad], dim=1)
    pred_size = torch.argmax((pred_ids == Constants.EOS).float(), dim=1)
    pred_size = pred_size + (pred_size == 0).long() * pred_ids.size(1)
    tgt_size = torch.argmax((tgt == Constants.EOS).float(), dim=1)
    tgt_size = tgt_size + (tgt_size == 0).long() * tgt.size(1)
    reward = -torch.square(torch.log(pred_size.float().clamp_min(1.0)) - torch.log(tgt_size.float().clamp_min(1.0)))

    seq_log_prob = torch.zeros(pred_log_probs.size(0), device=device, dtype=pred_log_probs.dtype)
    pred_size_cpu = pred_size.detach().cpu().numpy()
    for row_idx, size in enumerate(pred_size_cpu):
        seq_log_prob[row_idx] = pred_log_probs[row_idx, : min(int(size) + 1, pred_log_probs.size(1))].sum()

    centered_reward = reward.detach() - float(expect)
    loss = -torch.sum(seq_log_prob * centered_reward)
    expected_reward = torch.sum(torch.exp(seq_log_prob.detach()) * reward.detach()).item()
    return loss, expected_reward, float(torch.sum(reward.detach()).item())


def capped_policy_rollout(model, tgt, start_size, rollout_len):
    """FOREST RRModel rollout with an adapter-controlled max length for CPU smoke-runs."""

    rnn = model.rnn_model
    if rnn.use_network:
        # The upstream network-aware rollout samples two-hop neighbors at each
        # generated step. Keep original behavior for full runs instead of
        # maintaining a second copy of that path here.
        return model(tgt, start_size=start_size, RL_train=True)

    max_len = max(int(rollout_len), int(start_size) + 1)
    device = tgt.device
    batch_size = tgt.size(0)
    sampled_log_probs = []
    generated_tokens = []
    emb = rnn.drop(rnn.encoder(tgt))
    hidden = torch.zeros(batch_size, rnn.nhid, device=device)

    for t in range(max_len):
        if t < start_size and t < tgt.size(1):
            step_input = emb[:, t, :]
            if rnn.pos_emb:
                pos = torch.full((batch_size,), t, dtype=torch.long, device=device)
                step_input = torch.cat([step_input, rnn.drop(rnn.pos_embedding(pos))], dim=1)
            hidden = rnn.rnn(step_input, hidden)
            generated_tokens.append(tgt[:, t].long().detach())
            sampled_log_probs.append(torch.zeros(batch_size, device=device, dtype=hidden.dtype))
            continue

        prev_token = generated_tokens[-1] if generated_tokens else torch.zeros(batch_size, dtype=torch.long, device=device)
        step_input = rnn.encoder(prev_token.long())
        if rnn.pos_emb:
            pos = torch.full((batch_size,), t, dtype=torch.long, device=device)
            step_input = torch.cat([step_input, rnn.drop(rnn.pos_embedding(pos))], dim=1)
        hidden = rnn.rnn(step_input, hidden)
        decoded = rnn.decoder(hidden)
        if generated_tokens:
            previous_ids = torch.stack(generated_tokens, dim=1)
            previous_mask = torch.zeros(batch_size, rnn.user_size, device=device).scatter_(
                1,
                previous_ids.long(),
                float("-inf"),
            )
            decoded = decoded + previous_mask
        log_probs = torch.nn.functional.log_softmax(decoded, dim=1)
        top1 = torch.multinomial(torch.nn.functional.softmax(decoded, dim=1), 1).squeeze(1)
        generated_tokens.append(top1.detach())
        sampled_log_probs.append(torch.gather(log_probs, 1, top1.unsqueeze(1)).squeeze(1))

    outputs_id = torch.stack(generated_tokens, dim=1)
    outputs_prob = torch.stack(sampled_log_probs, dim=1)
    return outputs_id, outputs_prob


def train_epoch(model, training_data, crit, optimizer, max_batches=0):
    model.train()
    total_loss = 0.0
    n_total_words = 0.0
    n_total_correct = 0.0

    for batch_idx, batch in enumerate(tqdm(training_data, mininterval=2, desc="  - (Training)", leave=False)):
        if max_batches > 0 and batch_idx >= max_batches:
            break
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


def train_epoch_rl(model, training_data, optimizer, expect, device, start_size, max_batches=0, rollout_len=0):
    model.train()
    expect_new = 0.0
    reward_sum = 0.0
    batch_num = 0.0

    for batch_idx, batch in enumerate(tqdm(training_data, mininterval=2, desc="  - (RL fine-tune)", leave=False)):
        if max_batches > 0 and batch_idx >= max_batches:
            break
        tgt = batch
        optimizer.zero_grad()
        if rollout_len > 0:
            pred_ids, pred_log_probs = capped_policy_rollout(model, tgt, start_size, rollout_len)
        else:
            pred_ids, pred_log_probs = model(tgt, start_size=start_size, RL_train=True)
        loss_rl, expect_batch, reward_batch = get_performance_rl(pred_ids, pred_log_probs, tgt, expect, device)
        loss_rl.backward()
        optimizer.step()
        optimizer.update_learning_rate()
        expect_new += expect_batch
        reward_sum += reward_batch
        batch_num += tgt.size(0)

    return expect_new / max(batch_num, 1.0), reward_sum / max(batch_num, 1.0)


def evaluate_rl_reward(model, data, device, start_size, repeats=1, max_batches=0, rollout_len=0):
    model.eval()
    reward_sum = 0.0
    batch_num = 0.0
    with torch.no_grad():
        for batch_idx, batch in enumerate(tqdm(data, mininterval=2, desc="  - (RL reward)", leave=False)):
            if max_batches > 0 and batch_idx >= max_batches:
                break
            tgt = batch
            for _ in range(max(1, repeats)):
                if rollout_len > 0:
                    pred_ids, pred_log_probs = capped_policy_rollout(model, tgt, start_size, rollout_len)
                else:
                    pred_ids, pred_log_probs = model(tgt, start_size=start_size, RL_train=True)
                _loss, _expect, reward_batch = get_performance_rl(pred_ids, pred_log_probs, tgt, expect=0.0, device=device)
                reward_sum += reward_batch
                batch_num += tgt.size(0)
    return reward_sum / max(batch_num, 1.0)


def test_epoch(model, test_data, k_list, max_batches=0):
    model.eval()
    scores = {}
    for k in k_list:
        scores[f"hits@{k}"] = 0
        scores[f"map@{k}"] = 0
    n_total_words = 0

    import metrics as m

    with torch.no_grad():
        for batch_idx, batch in enumerate(tqdm(test_data, mininterval=2, desc="  - (Test)", leave=False)):
            if max_batches > 0 and batch_idx >= max_batches:
                break
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
        scores[f"hits@{k}"] /= max(n_total_words, 1)
        scores[f"map@{k}"] /= max(n_total_words, 1)

    return scores


def main():
    run_started = time.time()

    parser = argparse.ArgumentParser()
    parser.add_argument("--data_name", default="twitter")
    parser.add_argument("--epochs", type=int, default=200)
    parser.add_argument("--batch_size", type=int, default=32)
    parser.add_argument("--d_model", type=int, default=64)
    parser.add_argument("--k_list", nargs="+", type=int, default=[10, 50, 100])
    parser.add_argument("--device", default="cpu")
    parser.add_argument("--no_network", action="store_true")
    parser.add_argument("--n_warmup_steps", type=int, default=1000)
    parser.add_argument("--rl_epochs", type=int, default=200)
    parser.add_argument("--rl_start_size", type=int, default=5)
    parser.add_argument("--rl_max_batches", type=int, default=0)
    parser.add_argument("--rl_rollout_len", type=int, default=0)
    parser.add_argument("--max_train_batches", type=int, default=0)
    parser.add_argument("--max_eval_batches", type=int, default=0)
    parser.add_argument("--data_root", default=None, help="Optional migrated FOREST data root containing <dataset>/ files")
    parser.add_argument(
        "--reproduction_level",
        default="public_code_adapter",
        choices=["public_code_adapter", "frontier_reproduction_full_run"],
    )
    parser.add_argument("--config_id", default="")
    parser.add_argument("--seed", type=int, default=42)
    args = parser.parse_args()

    torch.manual_seed(args.seed)
    np.random.seed(args.seed)
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

    with staged_dataset(args.data_name, args.data_root):
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
        rl_expect = 0.0
        rl_train_rewards = []

        for epoch_i in range(args.epochs):
            start = time.time()
            train_loss, train_accu = train_epoch(model, train_data, crit, optimizer, args.max_train_batches)
            elapsed = (time.time() - start) / 60
            print(
                f"  Epoch {epoch_i+1}/{args.epochs} - "
                f"loss: {train_loss:.4f}, accu: {train_accu*100:.2f}%, "
                f"time: {elapsed:.1f}min"
            )

            if (epoch_i + 1) % 5 == 0 or epoch_i == args.epochs - 1:
                scores = test_epoch(model, valid_data, args.k_list, args.max_eval_batches)
                map_score = scores.get(f"map@{args.k_list[-1]}", 0)
                print(f"  [Valid] MAP@{args.k_list[-1]}={map_score:.4f}")
                if map_score > best_accu:
                    best_accu = map_score
                    best_epoch = epoch_i + 1
                    best_scores = scores
                    best_state = copy.deepcopy(model.state_dict())

        if best_state is not None:
            model.load_state_dict(best_state)

        for rl_epoch in range(args.rl_epochs):
            rl_expect, rl_reward = train_epoch_rl(
                model,
                train_data,
                optimizer,
                rl_expect,
                device=torch.device("cuda" if use_cuda else "cpu"),
                start_size=args.rl_start_size,
                max_batches=args.rl_max_batches,
                rollout_len=args.rl_rollout_len,
            )
            rl_train_rewards.append(float(rl_reward))
            print(f"  RL epoch {rl_epoch+1}/{args.rl_epochs} reward={rl_reward:.6f} expect={rl_expect:.6f}")

        rl_test_reward = None
        if args.rl_epochs > 0:
            rl_test_reward = evaluate_rl_reward(
                model,
                test_data,
                device=torch.device("cuda" if use_cuda else "cpu"),
                start_size=args.rl_start_size,
                max_batches=args.rl_max_batches,
                rollout_len=args.rl_rollout_len,
            )
        test_scores = test_epoch(model, test_data, args.k_list, args.max_eval_batches)

    result = {
        "model": "FOREST",
        "dataset": args.data_name,
        "task": "multi_scale",
        "status": "ok",
        "reproduction_level": args.reproduction_level,
        "seed": args.seed,
        "config_id": args.config_id,
        "epochs": args.epochs,
        "max_train_batches": args.max_train_batches,
        "max_eval_batches": args.max_eval_batches,
        "rl_epochs": args.rl_epochs,
        "rl_max_batches": args.rl_max_batches,
        "rl_rollout_len": args.rl_rollout_len,
        "methodology": "Original FOREST public-code adapter with recurrent next-user prediction; optional RRModel policy-gradient fine-tuning uses macro cascade-size reward.",
        "selection": f"best_valid_map@{args.k_list[-1]}",
        "best_epoch": best_epoch,
        f"valid_map@{args.k_list[-1]}": float(best_scores[f"map@{args.k_list[-1]}"]) if best_scores else None,
    }
    for k in args.k_list:
        result[f"hits@{k}"] = float(test_scores[f"hits@{k}"])
        result[f"map@{k}"] = float(test_scores[f"map@{k}"])
    result["msle"] = None
    result["mae"] = None
    if args.reproduction_level == "frontier_reproduction_full_run":
        result["same_protocol"] = True
        result["full_run_protocol"] = {
            "same_protocol": True,
            "config_id": args.config_id,
            "adapter": "benchmark.adapters.forest_runner",
            "original_public_code": True,
        }
    result["forest_rl"] = {
        "enabled": args.rl_epochs > 0,
        "rl_epochs": args.rl_epochs,
        "start_size": args.rl_start_size,
        "max_batches": args.rl_max_batches,
        "rollout_len": args.rl_rollout_len,
        "train_rewards": rl_train_rewards,
        "test_reward": rl_test_reward,
        "reward_definition": "-square(log(predicted_eos_position)-log(true_eos_position))",
        "policy_loss": "-sum(sampled_step_log_probs) * centered_macro_reward",
    }
    result["elapsed_s"] = round(time.time() - run_started, 1)

    print(json.dumps(result))


if __name__ == "__main__":
    main()
