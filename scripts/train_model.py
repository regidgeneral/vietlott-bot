import requests
import json
import os
import base64
from collections import defaultdict
from datetime import datetime

import gspread
from google.oauth2.service_account import Credentials

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

# Default weights
DEFAULT_WINDOW_RECENT  = 50
DEFAULT_WINDOW_MID     = 200
DEFAULT_WEIGHT_RECENT  = 3.0
DEFAULT_WEIGHT_MID     = 1.5
DEFAULT_WEIGHT_OLD     = 1.0

def get_sheet():
    scopes = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
    creds_b64 = os.environ.get("GOOGLE_CREDENTIALS_B64", "")
    if not creds_b64:
        raise ValueError("Missing GOOGLE_CREDENTIALS_B64")
    creds_json = base64.b64decode(creds_b64).decode("utf-8")
    creds_dict = json.loads(creds_json)
    creds = Credentials.from_service_account_info(creds_dict, scopes=scopes)
    gc = gspread.authorize(creds)
    return gc.open_by_key(os.environ.get("GOOGLE_SHEET_ID", ""))

def get_adaptive_weights(type_key):
    """
    Đọc performance sheet, tính weight tối ưu.
    Logic: nếu avg_matched > baseline (random) → tăng WEIGHT_RECENT
           nếu avg_matched < baseline → giảm về default
    Baseline random: k/n (xác suất trúng 1 số ngẫu nhiên)
    """
    cfg = CONFIGS[type_key]
    k = cfg["k"]
    n = cfg["n"]
    baseline = k * k / n  # expected matches nếu random

    try:
        wb = get_sheet()
        ws = wb.worksheet("performance")
        rows = ws.get_all_values()
        if len(rows) <= 1:
            print(f"  {type_key}: no performance data, using defaults")
            return DEFAULT_WEIGHT_RECENT, DEFAULT_WEIGHT_MID, DEFAULT_WEIGHT_OLD

        scheduler_rows = [r for r in rows[1:] if len(r) >= 5
                         and r[1] == type_key and r[3] == "scheduler"]
        if len(scheduler_rows) < 5:
            print(f"  {type_key}: only {len(scheduler_rows)} samples, need 5+, using defaults")
            return DEFAULT_WEIGHT_RECENT, DEFAULT_WEIGHT_MID, DEFAULT_WEIGHT_OLD

        scores = []
        for row in scheduler_rows[-30:]:  # 30 kỳ gần nhất
            try:
                scores.append(float(row[4]))
            except: continue

        avg = sum(scores) / len(scores)
        print(f"  {type_key}: avg_matched={round(avg,2)} (baseline={round(baseline,2)}, n={len(scores)} kỳ)")

        # Điều chỉnh weight dựa trên performance
        if avg > baseline * 1.2:
            # Tốt hơn random 20% → tăng weight recent mạnh hơn
            w_recent = min(5.0, DEFAULT_WEIGHT_RECENT * (avg / baseline))
            w_mid    = DEFAULT_WEIGHT_MID
            w_old    = DEFAULT_WEIGHT_OLD
            print(f"  {type_key}: GOOD performance → w_recent={round(w_recent,2)}")
        elif avg < baseline * 0.8:
            # Tệ hơn random → giảm weight recent, dùng toàn bộ lịch sử đều nhau
            w_recent = DEFAULT_WEIGHT_RECENT * 0.7
            w_mid    = DEFAULT_WEIGHT_MID
            w_old    = DEFAULT_WEIGHT_OLD
            print(f"  {type_key}: POOR performance → w_recent={round(w_recent,2)}")
        else:
            # Xấp xỉ baseline → giữ default
            w_recent = DEFAULT_WEIGHT_RECENT
            w_mid    = DEFAULT_WEIGHT_MID
            w_old    = DEFAULT_WEIGHT_OLD
            print(f"  {type_key}: NEUTRAL performance → using defaults")

        return w_recent, w_mid, w_old

    except Exception as e:
        print(f"  {type_key}: error reading performance ({e}), using defaults")
        return DEFAULT_WEIGHT_RECENT, DEFAULT_WEIGHT_MID, DEFAULT_WEIGHT_OLD

def fetch_jsonl(url):
    r = requests.get(url, headers={"User-Agent": "Mozilla/5.0"}, timeout=30)
    r.raise_for_status()
    draws = []
    for line in r.text.strip().split("\n"):
        line = line.strip()
        if not line: continue
        try:
            data = json.loads(line)
            result = [int(x) for x in data.get("result", [])]
            date_str = data.get("date", "")
            draws.append((date_str, result))
        except: continue
    return draws

def compute_model(draws, cfg, w_recent, w_mid, w_old):
    n_total   = cfg["n"]
    k         = cfg["k"]
    has_sp    = cfg.get("has_special", False)
    special_n = cfg.get("special_n", 0)

    n = len(draws)
    scores     = defaultdict(float)
    sp_scores  = defaultdict(float)
    pair_count = defaultdict(float)

    for i, (date_str, result) in enumerate(draws):
        rank = n - 1 - i
        if rank < DEFAULT_WINDOW_RECENT:
            w = w_recent
        elif rank < DEFAULT_WINDOW_MID:
            w = w_mid
        else:
            w = w_old

        nums = result[:k] if len(result) >= k else result
        if has_sp and len(result) > k:
            sp = result[k]
            sp_scores[sp] += w

        for num in nums:
            scores[num] += w

        for ii in range(len(nums)):
            for jj in range(ii + 1, len(nums)):
                a, b = nums[ii], nums[jj]
                pair_count[(min(a, b), max(a, b))] += w

    total = sum(scores.values()) or 1
    norm_scores = {n: scores[n] / total for n in range(1, n_total + 1)}

    companions = defaultdict(dict)
    for (a, b), cnt in pair_count.items():
        companions[a][b] = cnt
        companions[b][a] = cnt
    norm_pairs = {}
    for num, comp in companions.items():
        t = sum(comp.values()) or 1
        norm_pairs[num] = {str(k): v / t for k, v in sorted(comp.items(), key=lambda x: x[1], reverse=True)[:15]}

    norm_sp = {}
    if has_sp and sp_scores:
        t = sum(sp_scores.values()) or 1
        norm_sp = {str(n): sp_scores[n] / t for n in range(1, special_n + 1)}

    last_draw = list(draws[-1][1][:k]) if draws else []

    return {
        "scores": {str(n): norm_scores[n] for n in range(1, n_total + 1)},
        "pair_scores": norm_pairs,
        "special_scores": norm_sp,
        "n_draws": n,
        "last_draw": last_draw,
        "weights": {"recent": w_recent, "mid": w_mid, "old": w_old},
        "trained_at": datetime.utcnow().isoformat() + "Z"
    }

def train_all():
    os.makedirs("models", exist_ok=True)
    for type_key, cfg in CONFIGS.items():
        print(f"Training {type_key}...")
        try:
            # Lấy adaptive weights từ performance
            w_recent, w_mid, w_old = get_adaptive_weights(type_key)

            draws = fetch_jsonl(cfg["jsonl_url"])
            print(f"  Fetched {len(draws)} draws")

            model = compute_model(draws, cfg, w_recent, w_mid, w_old)
            out_path = f"models/model_{type_key}.json"
            with open(out_path, "w") as f:
                json.dump(model, f, ensure_ascii=False, separators=(",", ":"))
            print(f"  Saved {out_path} (n_draws={model['n_draws']}, weights={model['weights']})")
        except Exception as e:
            print(f"  ERROR {type_key}: {e}")

if __name__ == "__main__":
    train_all()
