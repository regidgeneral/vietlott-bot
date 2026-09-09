"""
Backtest walk-forward thuat toan chon so cua bot.py tren lich su that.

Voi moi ky i: train model tren draws[0:i] (dung dung logic train_model.py),
sinh bo so bang _ml_pick (dung dung logic bot.py), so voi ket qua that draws[i].

So sanh voi cac chien luoc doi chung.
"""
import json, random, sys, os
from collections import defaultdict

TEMP = os.environ.get("TEMP", ".")

CONFIGS = {
    "535": {"n": 35, "k": 5},
    "645": {"n": 45, "k": 6},
    "655": {"n": 55, "k": 6},
}

WINDOW_RECENT = 50
WINDOW_MID = 200
W_RECENT = 3.0
W_MID = 1.5
W_OLD = 1.0

N_SETS = 5          # bot sinh 5 bo moi ky
BACKTEST_LAST = 300 # backtest tren 300 ky gan nhat


def load_draws(type_key):
    path = os.path.join(TEMP, f"v{type_key}.jsonl")
    draws = []
    with open(path, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            d = json.loads(line)
            res = [int(x) for x in d.get("result", [])]
            if res:
                draws.append(res)
    return draws


# ---------- train_model.py: compute_model (rut gon phan can cho pick) ----------
def compute_model(draws, cfg):
    n_total, k = cfg["n"], cfg["k"]
    n = len(draws)
    scores = defaultdict(float)
    pair_count = defaultdict(float)

    for i, result in enumerate(draws):
        rank = n - 1 - i
        w = W_RECENT if rank < WINDOW_RECENT else (W_MID if rank < WINDOW_MID else W_OLD)
        nums = result[:k] if len(result) >= k else result
        for num in nums:
            scores[num] += w
        for ii in range(len(nums)):
            for jj in range(ii + 1, len(nums)):
                a, b = nums[ii], nums[jj]
                pair_count[(min(a, b), max(a, b))] += w

    total = sum(scores.values()) or 1
    companions = defaultdict(dict)
    for (a, b), cnt in pair_count.items():
        companions[a][b] = cnt
        companions[b][a] = cnt
    norm_pairs = {}
    for num, comp in companions.items():
        t = sum(comp.values()) or 1
        norm_pairs[str(num)] = {
            str(kk): v / t
            for kk, v in sorted(comp.items(), key=lambda x: x[1], reverse=True)[:15]
        }
    return {
        "scores": {str(x): scores[x] / total for x in range(1, n_total + 1)},
        "pair_scores": norm_pairs,
        "last_draw": list(draws[-1][:k]) if draws else [],
    }


# ---------- bot.py: weighted_pick + _ml_pick (copy nguyen van logic) ----------
def weighted_pick(pool, weights, count, exclude=None):
    exclude = exclude or set()
    picked, candidates = [], [(n, w) for n, w in zip(pool, weights) if n not in exclude]
    for _ in range(count):
        if not candidates:
            break
        total = sum(w for _, w in candidates)
        r = random.uniform(0, total)
        cumul = 0
        for i, (n, w) in enumerate(candidates):
            cumul += w
            if r <= cumul:
                picked.append(n)
                candidates.pop(i)
                break
    return picked


def ml_pick(model, n_total, n_pick, exclude_sets=None, last_draw=None):
    scores = model.get("scores", {})
    pair_scores = model.get("pair_scores", {})
    recent = set(last_draw or model.get("last_draw", []))

    mid = n_total / 2
    target_sum = round(mid * n_pick)
    sum_lo = round(target_sum * 0.7)
    sum_hi = round(target_sum * 1.3)

    for attempt in range(40):
        picked = set()
        candidates = [(n, float(scores.get(str(n), 0))) for n in range(1, n_total + 1) if n not in recent]
        candidates.sort(key=lambda x: x[1], reverse=True)
        top_pool = [n for n, _ in candidates[:20]]
        top_w = [w for _, w in candidates[:20]]
        seeds = weighted_pick(top_pool, top_w, 1)
        if seeds:
            seed = seeds[0]
            picked.add(seed)
            seed_pairs = pair_scores.get(str(seed), {})
            if seed_pairs:
                comp_pool = [int(k) for k in seed_pairs if int(k) not in picked and int(k) not in recent]
                comp_w_ = [float(seed_pairs[k]) for k in seed_pairs if int(k) not in picked and int(k) not in recent]
                if comp_pool:
                    n_pair = min(round(n_pick * 0.3), len(comp_pool))
                    picked.update(weighted_pick(comp_pool, comp_w_, n_pair, exclude=picked))

        remain = [(n, float(scores.get(str(n), 0))) for n in range(1, n_total + 1)
                  if n not in picked and n not in recent]
        remain.sort(key=lambda x: x[1], reverse=True)
        fill_pool = [n for n, _ in remain[:25]]
        fill_w = [w for _, w in remain[:25]]
        while len(picked) < n_pick and fill_pool:
            picks = weighted_pick(fill_pool, fill_w, 1, exclude=picked)
            if not picks:
                break
            picked.add(picks[0])
            idx = fill_pool.index(picks[0])
            fill_pool.pop(idx)
            fill_w.pop(idx)

        while len(picked) < n_pick:
            picked.add(random.randint(1, n_total))

        result = tuple(sorted(list(picked)[:n_pick]))
        s = sum(result)
        if sum_lo <= s <= sum_hi:
            if not exclude_sets or result not in exclude_sets:
                return list(result)
    return list(sorted(list(picked)[:n_pick]))


# ---------- Cac chien luoc doi chung ----------
def pick_random(n_total, n_pick, **kw):
    return random.sample(range(1, n_total + 1), n_pick)


def pick_hottest(model, n_total, n_pick, **kw):
    """Chon thang n_pick so co score cao nhat (khong random)."""
    scores = model["scores"]
    ranked = sorted(range(1, n_total + 1), key=lambda x: -float(scores.get(str(x), 0)))
    return ranked[:n_pick]


def pick_coldest(model, n_total, n_pick, **kw):
    scores = model["scores"]
    ranked = sorted(range(1, n_total + 1), key=lambda x: float(scores.get(str(x), 0)))
    return ranked[:n_pick]


def pick_fixed(n_total, n_pick, **kw):
    """Luon chon 1,2,3,...,k - bo so ngu ngoc nhat co the."""
    return list(range(1, n_pick + 1))


def run(type_key, seed=42):
    random.seed(seed)
    cfg = CONFIGS[type_key]
    n_total, k = cfg["n"], cfg["k"]
    draws = load_draws(type_key)
    start = max(WINDOW_MID + 50, len(draws) - BACKTEST_LAST)

    stats = defaultdict(list)
    hit3plus = defaultdict(int)
    total_sets = 0

    for i in range(start, len(draws)):
        history = draws[:i]
        actual = set(draws[i][:k])
        model = compute_model(history, cfg)
        last_draw = list(history[-1][:k])

        seen = set()
        for _ in range(N_SETS):
            nums = ml_pick(model, n_total, k, seen, last_draw)
            seen.add(tuple(nums))
            m = len(set(nums) & actual)
            stats["bot_ml"].append(m)
            if m >= 3:
                hit3plus["bot_ml"] += 1

            r = pick_random(n_total, k)
            m = len(set(r) & actual)
            stats["random"].append(m)
            if m >= 3:
                hit3plus["random"] += 1
            total_sets += 1

        for name, fn in (("hottest", pick_hottest), ("coldest", pick_coldest)):
            nums = fn(model=model, n_total=n_total, n_pick=k)
            m = len(set(nums) & actual)
            stats[name].append(m)
            if m >= 3:
                hit3plus[name] += 1

        nums = pick_fixed(n_total, k)
        m = len(set(nums) & actual)
        stats["fixed_12345"].append(m)
        if m >= 3:
            hit3plus["fixed_12345"] += 1

    baseline = k * k / n_total
    print(f"\n{'='*72}")
    print(f"  {type_key}  |  {len(draws)} ky lich su  |  backtest {len(draws)-start} ky gan nhat")
    print(f"  Ky vong ly thuyet (bat ky cach chon nao): {baseline:.4f} so trung/bo")
    print(f"{'='*72}")
    print(f"  {'Chien luoc':<16} {'so trung TB':>12} {'so bo':>8} {'>=3 so':>9} {'ty le >=3':>11}")
    print(f"  {'-'*16} {'-'*12} {'-'*8} {'-'*9} {'-'*11}")
    for name in ("bot_ml", "random", "hottest", "coldest", "fixed_12345"):
        v = stats[name]
        if not v:
            continue
        avg = sum(v) / len(v)
        h3 = hit3plus[name]
        print(f"  {name:<16} {avg:>12.4f} {len(v):>8} {h3:>9} {h3/len(v)*100:>10.2f}%")
    return stats


if __name__ == "__main__":
    for tk in sys.argv[1:] or ["535", "645", "655"]:
        run(tk)
