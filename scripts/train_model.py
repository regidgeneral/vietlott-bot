import requests
import json
import os
from collections import defaultdict
from datetime import datetime

# ==========================================
# CONFIG
# ==========================================
CONFIGS = {
    "535": {
        "n": 35, "k": 5, "has_special": True, "special_n": 12,
        "jsonl_url": "https://raw.githubusercontent.com/vietvudanh/vietlott-data/master/data/power535.jsonl"
    },
    "645": {
        "n": 45, "k": 6, "has_special": False,
        "jsonl_url": "https://raw.githubusercontent.com/vietvudanh/vietlott-data/master/data/power645.jsonl"
    },
    "655": {
        "n": 55, "k": 6, "has_special": True, "special_n": 55,
        "jsonl_url": "https://raw.githubusercontent.com/vietvudanh/vietlott-data/master/data/power655.jsonl"
    },
}

WINDOW_RECENT  = 50   # 50 ky gan nhat: weight cao
WINDOW_MID     = 200  # 50-200 ky: weight trung binh
WEIGHT_RECENT  = 3.0  # x3 so voi lich su cu
WEIGHT_MID     = 1.5
WEIGHT_OLD     = 1.0

def fetch_jsonl(url):
    """Fetch va parse JSONL, tra ve list of (date_str, nums, special)"""
    r = requests.get(url, headers={"User-Agent": "Mozilla/5.0"}, timeout=30)
    r.raise_for_status()
    draws = []
    for line in r.text.strip().split("\n"):
        line = line.strip()
        if not line:
            continue
        try:
            data = json.loads(line)
            result = [int(x) for x in data.get("result", [])]
            date_str = data.get("date", "")
            draws.append((date_str, result))
        except:
            continue
    return draws

def compute_model(draws, cfg):
    """
    Sliding window weighted frequency model.
    - 50 ky gan nhat: weight x3
    - 50-200 ky: weight x1.5
    - Con lai: weight x1
    Tra ve: {
        "scores": {num: score},          # xac suat co chuan hoa
        "pair_scores": {num: {num: score}}, # pair co chuan hoa
        "special_scores": {num: score},  # neu co so dac biet
        "n_draws": int,
        "last_draw": [nums],
        "trained_at": iso_str
    }
    """
    n_total   = cfg["n"]
    k         = cfg["k"]
    has_sp    = cfg.get("has_special", False)
    special_n = cfg.get("special_n", 0)

    # Draws moi nhat o cuoi
    n = len(draws)
    scores     = defaultdict(float)
    sp_scores  = defaultdict(float)
    pair_count = defaultdict(float)

    for i, (date_str, result) in enumerate(draws):
        # Xac dinh weight theo vi tri (tinh tu cuoi)
        rank = n - 1 - i  # 0 = moi nhat
        if rank < WINDOW_RECENT:
            w = WEIGHT_RECENT
        elif rank < WINDOW_MID:
            w = WEIGHT_MID
        else:
            w = WEIGHT_OLD

        nums = result[:k] if len(result) >= k else result
        if has_sp and len(result) > k:
            sp = result[k]
            sp_scores[sp] += w

        for num in nums:
            scores[num] += w

        # Pair scores
        for ii in range(len(nums)):
            for jj in range(ii + 1, len(nums)):
                a, b = nums[ii], nums[jj]
                pair_count[(min(a, b), max(a, b))] += w

    # Normalize scores thanh xac suat
    total = sum(scores.values()) or 1
    norm_scores = {n: scores[n] / total for n in range(1, n_total + 1)}

    # Pair: voi moi so, top companions
    companions = defaultdict(dict)
    for (a, b), cnt in pair_count.items():
        companions[a][b] = cnt
        companions[b][a] = cnt
    # Normalize pair
    norm_pairs = {}
    for num, comp in companions.items():
        t = sum(comp.values()) or 1
        norm_pairs[num] = {str(k): v / t for k, v in sorted(comp.items(), key=lambda x: x[1], reverse=True)[:15]}

    # Special normalize
    norm_sp = {}
    if has_sp and sp_scores:
        t = sum(sp_scores.values()) or 1
        norm_sp = {str(n): sp_scores[n] / t for n in range(1, special_n + 1)}

    # Last draw
    last_draw = list(draws[-1][1][:k]) if draws else []

    return {
        "scores": {str(n): norm_scores[n] for n in range(1, n_total + 1)},
        "pair_scores": norm_pairs,
        "special_scores": norm_sp,
        "n_draws": n,
        "last_draw": last_draw,
        "trained_at": datetime.utcnow().isoformat() + "Z"
    }

def train_all():
    os.makedirs("models", exist_ok=True)
    for type_key, cfg in CONFIGS.items():
        print(f"Training {type_key}...")
        try:
            draws = fetch_jsonl(cfg["jsonl_url"])
            print(f"  Fetched {len(draws)} draws")
            model = compute_model(draws, cfg)
            out_path = f"models/model_{type_key}.json"
            with open(out_path, "w") as f:
                json.dump(model, f, ensure_ascii=False, separators=(",", ":"))
            print(f"  Saved {out_path} (n_draws={model['n_draws']}, last={model['last_draw']})")
        except Exception as e:
            print(f"  ERROR {type_key}: {e}")

if __name__ == "__main__":
    train_all()
