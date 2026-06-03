import discord
import json
import asyncio
import requests
import random
import re
import os
import urllib.parse
from discord import app_commands
from datetime import datetime, date, timezone
import pytz
import gspread
from google.oauth2.service_account import Credentials
import base64

TOKEN = os.environ.get("DISCORD_TOKEN", "")
DISCORD_CHANNEL_ID = int(os.environ.get("DISCORD_CHANNEL_ID", "0"))
VN_TZ = pytz.timezone("Asia/Ho_Chi_Minh")

# ==========================================
# CONFIG
# ==========================================
CONFIGS = {
    "535": {"n": 35, "k": 5, "has_special": True,  "special_n": 12, "label": "Lotto 5/35",  "sms_prefix": "535",
            "jsonl_url": "https://raw.githubusercontent.com/vietvudanh/vietlott-data/master/data/power535.jsonl"},
    "645": {"n": 45, "k": 6, "has_special": False, "label": "Mega 6/45",  "sms_prefix": "645",
            "jsonl_url": "https://raw.githubusercontent.com/vietvudanh/vietlott-data/master/data/power645.jsonl"},
    "655": {"n": 55, "k": 6, "has_special": True,  "special_n": 55, "label": "Power 6/55", "sms_prefix": "655",
            "jsonl_url": "https://raw.githubusercontent.com/vietvudanh/vietlott-data/master/data/power655.jsonl"},
}

GIOI_HAN_NGAY = {"535": 1_000_000, "645": 2_100_000, "655": 2_100_000}

BAO_535 = {
    "bc4": {"label": "BC4 – Bao 4 số chính",    "gia": 310000, "type": "bc", "n_main": 4},
    "bc6": {"label": "BC6 – Bao 6 số chính",    "gia": 60000,  "type": "bc", "n_main": 6},
    "bc7": {"label": "BC7 – Bao 7 số chính",    "gia": 210000, "type": "bc", "n_main": 7},
    "bc8": {"label": "BC8 – Bao 8 số chính",    "gia": 560000, "type": "bc", "n_main": 8},
    "bd2": {"label": "BD2 – Bao 2 số đặc biệt", "gia": 20000,  "type": "bd", "n_sp": 2},
    "bd3": {"label": "BD3 – Bao 3 số đặc biệt", "gia": 30000,  "type": "bd", "n_sp": 3},
    "bd4": {"label": "BD4 – Bao 4 số đặc biệt", "gia": 40000,  "type": "bd", "n_sp": 4},
    "bd5": {"label": "BD5 – Bao 5 số đặc biệt", "gia": 50000,  "type": "bd", "n_sp": 5},
    "bd6": {"label": "BD6 – Bao 6 số đặc biệt", "gia": 60000,  "type": "bd", "n_sp": 6},
    "bd7": {"label": "BD7 – Bao 7 số đặc biệt", "gia": 70000,  "type": "bd", "n_sp": 7},
    "bd8": {"label": "BD8 – Bao 8 số đặc biệt", "gia": 80000,  "type": "bd", "n_sp": 8},
    "bd9": {"label": "BD9 – Bao 9 số đặc biệt", "gia": 90000,  "type": "bd", "n_sp": 9},
    "bd10":{"label": "BD10 – Bao 10 số đặc biệt", "gia": 100000, "type": "bd", "n_sp": 10},
    "bd11":{"label": "BD11 – Bao 11 số đặc biệt", "gia": 110000, "type": "bd", "n_sp": 11},
    "bd12":{"label": "BD12 – Bao 12 số đặc biệt", "gia": 120000, "type": "bd", "n_sp": 12},
}

BAO_645_655 = {
    "b5":  {"label": "B5  – Bao 5 số",  "gia_645": 400000,  "gia_655": 500000,  "n": 5},
    "b7":  {"label": "B7  – Bao 7 số",  "gia_645": 70000,   "gia_655": 70000,   "n": 7},
    "b8":  {"label": "B8  – Bao 8 số",  "gia_645": 280000,  "gia_655": 280000,  "n": 8},
    "b9":  {"label": "B9  – Bao 9 số",  "gia_645": 840000,  "gia_655": 840000,  "n": 9},
    "b10": {"label": "B10 – Bao 10 số", "gia_645": 2100000, "gia_655": 2100000, "n": 10},
}

LICH_XO = {
    # 535: hàng ngày 13:00 và 21:00 → trigger lúc 13:35 và 21:35
    "535": [(d, 13, 35) for d in range(7)] + [(d, 21, 35) for d in range(7)],
    # 645: Thứ 4 (2), Thứ 6 (4), Chủ Nhật (6) lúc 18:00 → trigger 18:35
    "645": [(2, 18, 35), (4, 18, 35), (6, 18, 35)],
    # 655: Thứ 3 (1), Thứ 5 (3), Thứ 7 (5) lúc 18:00 → trigger 18:35
    "655": [(1, 18, 35), (3, 18, 35), (5, 18, 35)],
}

intents = discord.Intents.all()
client = discord.Client(intents=intents)
tree = app_commands.CommandTree(client)
_cache = {}
_model_cache = {}

MODEL_BASE_URL = "https://raw.githubusercontent.com/regidgeneral/vietlott-bot/main/models/model_{}.json"

def load_model(type_key):
    """Load model JSON từ GitHub, cache trong memory"""
    if type_key in _model_cache:
        return _model_cache[type_key]
    try:
        url = MODEL_BASE_URL.format(type_key)
        r = requests.get(url, headers={"User-Agent": "Mozilla/5.0"}, timeout=10)
        if r.status_code == 200:
            model = r.json()
            _model_cache[type_key] = model
            print(f"✅ Loaded model_{type_key} (n_draws={model.get('n_draws')})")
            return model
    except Exception as e:
        print(f"⚠️ load_model {type_key}: {e}")
    return None

# ==========================================
# DATA & ANALYSIS
# ==========================================
def parse_jsonl_line(line, cfg):
    data = json.loads(line)
    result = [int(x) for x in data.get("result", [])]
    key = cfg["sms_prefix"]
    if key == "535":
        if len(result) < 6: return None, None
        nums, special = result[:5], result[5]
        if not all(1 <= n <= 35 for n in nums): return None, None
    elif key == "645":
        if len(result) != 6: return None, None
        nums, special = result[:6], None
        if not all(1 <= n <= 45 for n in nums): return None, None
    elif key == "655":
        if len(result) != 7: return None, None
        nums, special = result[:6], result[6]
        if not all(1 <= n <= 55 for n in nums): return None, None
    else:
        return None, None
    return nums, special

def fetch_jsonl(cfg):
    key = cfg["sms_prefix"]
    if key in _cache:
        return _cache[key]
    try:
        r = requests.get(cfg["jsonl_url"], headers={"User-Agent": "Mozilla/5.0"}, timeout=30)
        if r.status_code != 200:
            return "", [], []
        text = r.text
        all_nums, all_sp = [], []
        for line in text.strip().split("\n"):
            line = line.strip()
            if not line: continue
            try:
                nums, sp = parse_jsonl_line(line, cfg)
                if nums:
                    all_nums.extend(nums)
                    if cfg.get("has_special") and sp is not None:
                        all_sp.append(sp)
            except: continue
        _cache[key] = (text, all_nums, all_sp)
        return text, all_nums, all_sp
    except Exception as e:
        print(f"❌ Fetch error {key}: {e}")
        return "", [], []

def load_from_sheets(type_key):
    """Load kết quả từ Google Sheets (data mình tự lưu)"""
    cfg = CONFIGS[type_key]
    try:
        wb = get_sheet()
        ws = wb.worksheet(type_key)
        rows = ws.get_all_values()
        if len(rows) <= 1:
            return [], [], []

        all_nums, all_sp, all_dates = [], [], []
        k = cfg["k"]
        for row in rows[1:]:  # bỏ header
            try:
                date_str = row[0] if row else ""
                nums = [int(row[i]) for i in range(2, 2 + k) if i < len(row) and row[i].strip().isdigit()]
                if len(nums) == k:
                    all_nums.extend(nums)
                    all_dates.append(date_str)
                    if cfg.get("has_special") and len(row) > 2 + k:
                        sp = row[2 + k].strip()
                        if sp.isdigit():
                            all_sp.append(int(sp))
            except:
                continue
        return all_nums, all_sp, all_dates
    except Exception as e:
        print(f"⚠️ Khong doc duoc Sheets {type_key}: {e}")
        return [], [], []

def compute_days_since_from_sheets(type_key):
    """Tính days since từ Google Sheets (chính xác hơn vì có ngày)"""
    cfg = CONFIGS[type_key]
    today = date.today()
    try:
        wb = get_sheet()
        ws = wb.worksheet(type_key)
        rows = ws.get_all_values()
        if len(rows) <= 1:
            return {}

        last_seen = {}
        k = cfg["k"]
        for row in rows[1:]:
            try:
                date_str = row[0].strip()  # dd/mm/yyyy
                if not date_str or len(date_str) != 10:
                    continue
                d, m, y = date_str.split("/")
                draw_date = date(int(y), int(m), int(d))
                nums = [int(row[i]) for i in range(2, 2 + k) if i < len(row) and row[i].strip().isdigit()]
                for n in nums:
                    if n not in last_seen or draw_date > last_seen[n]:
                        last_seen[n] = draw_date
            except:
                continue

        return {n: (today - last_seen[n]).days if n in last_seen else 9999
                for n in range(1, cfg["n"] + 1)}
    except Exception as e:
        print(f"⚠️ Khong tinh duoc days_since tu Sheets: {e}")
        return {}

def get_combined_data(type_key):
    """
    Kết hợp data từ 2 nguồn:
    1. GitHub vietvudanh → lịch sử cũ (nhiều kỳ)
    2. Google Sheets → lịch sử mới bot tự cập nhật (chính xác ngày hơn)
    Trả về: all_nums, all_sp, days_since, pair_freq
    """
    cfg = CONFIGS[type_key]

    # Lấy data từ Google Sheets
    sheets_nums, sheets_sp, _ = load_from_sheets(type_key)

    # Lấy data từ GitHub JSONL
    jsonl_text, jsonl_nums, jsonl_sp = fetch_jsonl(cfg)

    if sheets_nums:
        days_since = compute_days_since_from_sheets(type_key)
        all_nums = jsonl_nums + sheets_nums
        all_sp   = jsonl_sp + sheets_sp
        print(f"✅ {type_key}: {len(jsonl_nums)//cfg['k']} ky JSONL + {len(sheets_nums)//cfg['k']} ky Sheets")
    else:
        all_nums = jsonl_nums
        all_sp   = jsonl_sp
        days_since = compute_days_since(jsonl_text, cfg) if jsonl_text else {}
        print(f"⚠️ {type_key}: Chi dung JSONL ({len(jsonl_nums)//cfg['k']} ky)")

    # Tính pair frequency từ toàn bộ lịch sử
    pair_freq = compute_pair_freq(all_nums, cfg["k"]) if all_nums else {}

    return all_nums, all_sp, days_since, pair_freq

def compute_freq(numbers, n):
    freq = {i: 0 for i in range(1, n + 1)}
    for num in numbers:
        if num in freq: freq[num] += 1
    return freq

def compute_days_since(jsonl_text, cfg):
    today = date.today()
    last_seen = {}
    for line in jsonl_text.strip().split("\n"):
        line = line.strip()
        if not line: continue
        try:
            data = json.loads(line)
            draw_date = date.fromisoformat(data.get("date", ""))
            nums, _ = parse_jsonl_line(line, cfg)
            if nums:
                for n in nums:
                    if n not in last_seen or draw_date > last_seen[n]:
                        last_seen[n] = draw_date
        except: continue
    return {n: (today - last_seen[n]).days if n in last_seen else 9999
            for n in range(1, cfg["n"] + 1)}

def compute_pair_freq(all_numbers, k):
    """
    Tính tần suất xuất hiện cùng nhau của các cặp số.
    Trả về dict: {num -> [danh sách số hay đi kèm theo thứ tự]}
    """
    from collections import defaultdict
    pair_count = defaultdict(int)

    # Chia all_numbers thành từng kỳ
    draws = [all_numbers[i:i+k] for i in range(0, len(all_numbers), k)]

    for draw in draws:
        draw = list(set(draw))  # loại trùng
        for i in range(len(draw)):
            for j in range(i+1, len(draw)):
                a, b = draw[i], draw[j]
                pair = (min(a,b), max(a,b))
                pair_count[pair] += 1

    # Với mỗi số, tìm các số hay đi kèm nhất
    companions = defaultdict(list)
    for (a, b), cnt in pair_count.items():
        companions[a].append((b, cnt))
        companions[b].append((a, cnt))

    # Sort theo tần suất giảm dần
    for num in companions:
        companions[num].sort(key=lambda x: x[1], reverse=True)

    return dict(companions)

def generate_nums(freq, n_total, n_pick, exclude_sets=None, days_since=None, pair_freq=None, last_draw=None, type_key=None):
    """
    ML model: sliding window weighted frequency.
    Fallback về thuật toán cũ nếu model chưa có.
    """
    # Load model nếu có type_key
    model = load_model(type_key) if type_key else None

    if model:
        return _ml_pick(model, n_total, n_pick, exclude_sets, last_draw)
    else:
        return _heuristic_pick(freq, n_total, n_pick, exclude_sets, days_since, pair_freq, last_draw)

def _ml_pick(model, n_total, n_pick, exclude_sets=None, last_draw=None):
    """Chọn số dựa trên ML model scores."""
    scores     = model.get("scores", {})
    pair_scores = model.get("pair_scores", {})
    recent     = set(last_draw or model.get("last_draw", []))

    # Target tổng cân bằng
    mid        = n_total / 2
    target_sum = round(mid * n_pick)
    sum_lo     = round(target_sum * 0.7)
    sum_hi     = round(target_sum * 1.3)

    for attempt in range(40):
        picked = set()

        # Bước 1: Chọn seed = số có score cao nhất (tránh recent)
        candidates = [(n, float(scores.get(str(n), 0))) for n in range(1, n_total + 1) if n not in recent]
        candidates.sort(key=lambda x: x[1], reverse=True)
        top_pool = [n for n, _ in candidates[:20]]
        top_w    = [w for _, w in candidates[:20]]
        seeds = weighted_pick(top_pool, top_w, 1)
        if seeds:
            seed = seeds[0]
            picked.add(seed)

            # Bước 2: Pair boost từ model
            seed_pairs = pair_scores.get(str(seed), {})
            if seed_pairs:
                comp_pool = [int(k) for k in seed_pairs if int(k) not in picked and int(k) not in recent]
                comp_w_   = [float(seed_pairs[k]) for k in seed_pairs if int(k) not in picked and int(k) not in recent]
                if comp_pool:
                    n_pair = min(round(n_pick * 0.3), len(comp_pool))
                    picked.update(weighted_pick(comp_pool, comp_w_, n_pair, exclude=picked))

        # Bước 3: Fill bằng score cao (tránh recent và picked)
        remain = [(n, float(scores.get(str(n), 0))) for n in range(1, n_total + 1)
                  if n not in picked and n not in recent]
        remain.sort(key=lambda x: x[1], reverse=True)
        fill_pool = [n for n, _ in remain[:25]]
        fill_w    = [w for _, w in remain[:25]]
        while len(picked) < n_pick and fill_pool:
            picks = weighted_pick(fill_pool, fill_w, 1, exclude=picked)
            if not picks: break
            picked.add(picks[0])
            idx = fill_pool.index(picks[0])
            fill_pool.pop(idx)
            fill_w.pop(idx)

        # Fill cuối nếu vẫn thiếu
        while len(picked) < n_pick:
            picked.add(random.randint(1, n_total))

        result = tuple(sorted(list(picked)[:n_pick]))
        s = sum(result)
        if sum_lo <= s <= sum_hi:
            if not exclude_sets or result not in exclude_sets:
                return list(result)

    return list(sorted(list(picked)[:n_pick]))

def _heuristic_pick(freq, n_total, n_pick, exclude_sets=None, days_since=None, pair_freq=None, last_draw=None):
    """Fallback: thuật toán heuristic cũ."""
    avg = sum(freq.values()) / n_total
    sorted_f = sorted(freq.items(), key=lambda x: x[1], reverse=True)
    cold   = [n for n, _ in sorted_f[-20:]]
    cold_w = [max(1, avg * 2 - freq[n]) for n in cold]
    if days_since:
        due_sorted = sorted(days_since.items(), key=lambda x: x[1], reverse=True)
        due   = [n for n, _ in due_sorted[:20]]
        due_w = [days_since[n] for n in due]
    else:
        due, due_w = cold, cold_w
    recent = set(last_draw) if last_draw else set()
    n_due  = max(1, round(n_pick * 0.6))
    n_cold = max(1, round(n_pick * 0.2))
    n_pair = n_pick - n_due - n_cold
    mid = n_total / 2
    sum_lo = round(mid * n_pick * 0.7)
    sum_hi = round(mid * n_pick * 1.3)
    for attempt in range(30):
        picked = set()
        due_f = [n for n in due if n not in recent]
        due_wf = [due_w[i] for i, n in enumerate(due) if n not in recent]
        seeds = weighted_pick(due_f or due, due_wf or due_w, 1)
        if seeds:
            picked.add(seeds[0])
            if pair_freq and seeds[0] in pair_freq:
                cp = [n for n, _ in pair_freq[seeds[0]][:10] if n not in picked and n not in recent]
                cw = [c for n, c in pair_freq[seeds[0]][:10] if n not in picked and n not in recent]
                if cp:
                    picked.update(weighted_pick(cp, cw, min(n_pair, len(cp)), exclude=picked))
        dr = [n for n in due_f if n not in picked]
        dwr = [due_w[i] for i, n in enumerate(due) if n not in recent and n not in picked]
        picked.update(weighted_pick(dr, dwr or [1]*len(dr), max(0, n_due - len(picked)), exclude=picked))
        cf = [n for n in cold if n not in picked and n not in recent]
        cwf = [cold_w[i] for i, n in enumerate(cold) if n not in picked and n not in recent]
        picked.update(weighted_pick(cf, cwf or [1]*len(cf), max(0, n_cold), exclude=picked))
        ap = [n for n in range(1, n_total + 1) if n not in picked and n not in recent]
        while len(picked) < n_pick and ap:
            n = random.choice(ap); picked.add(n); ap.remove(n)
        while len(picked) < n_pick:
            picked.add(random.randint(1, n_total))
        result = tuple(sorted(list(picked)[:n_pick]))
        if sum_lo <= sum(result) <= sum_hi:
            if not exclude_sets or result not in exclude_sets:
                return list(result)
    return list(sorted(list(picked)[:n_pick]))

def weighted_pick(pool, weights, count, exclude=None):
    exclude = exclude or set()
    picked, candidates = [], [(n, w) for n, w in zip(pool, weights) if n not in exclude]
    for _ in range(count):
        if not candidates: break
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



def add_fields_chunked(embed, lines, chunk_size=10):
    """Chia danh sách bộ số thành nhiều field, mỗi field tối đa chunk_size bộ"""
    for i in range(0, len(lines), chunk_size):
        chunk = lines[i:i+chunk_size]
        name = 'Bộ số' if i == 0 else f'Bộ số (tiếp)'
        embed.add_field(name=name, value='\n'.join(chunk), inline=False)

def fmt_gia(gia):
    return f"{gia:,}d".replace(",", ".")

def max_bo(gia, type_key):
    return max(1, GIOI_HAN_NGAY[type_key] // gia)

def make_sms_link(sms_text):
    return f"https://vietlott-sms.netlify.app/?body={urllib.parse.quote(sms_text)}"

def shorten_url(url):
    if len(url) <= 512:
        return url
    try:
        r = requests.get(
            f"https://tinyurl.com/api-create.php?url={urllib.parse.quote(url, safe='')}",
            timeout=5
        )
        if r.status_code == 200 and r.text.strip().startswith("http"):
            return r.text.strip()
    except Exception as e:
        print(f"⚠️ TinyURL lỗi: {e}")
    return url[:512]

def make_button(sms_text):
    url = shorten_url(make_sms_link(sms_text))
    view = discord.ui.View()
    view.add_item(discord.ui.Button(
        label="📱 Mở SMS → gửi 9969",
        url=url,
        style=discord.ButtonStyle.link
    ))
    return view

# ==========================================
# SMS BUILDERS
# ==========================================
def sms_basic_535(all_sets):
    parts = []
    for nums, sp in all_sets:
        main = " ".join(f"{n:02d}" for n in nums[:-1])
        last = f"{nums[-1]:02d}-{sp:02d}" if sp else f"{nums[-1]:02d}"
        parts.append(f"S {main} {last}")
    return "535 K1 " + " ".join(parts)

def sms_basic_645_655(prefix, all_sets):
    parts = [f"S {' '.join(f'{n:02d}' for n in nums)}" for nums, _ in all_sets]
    return f"{prefix} K1 " + " ".join(parts)

def sms_bao535_bc(bao_key, main_nums, special):
    main = " ".join(f"{n:02d}" for n in main_nums[:-1])
    last = f"{main_nums[-1]:02d}-{special:02d}"
    return f"535 K1 {bao_key.upper()} S {main} {last}"

def sms_bao535_bd(bao_key, main_nums, specials):
    main = " ".join(f"{n:02d}" for n in main_nums)
    sp_str = f"{specials[0]:02d}" + (" " + " ".join(f"{n:02d}" for n in specials[1:]) if len(specials) > 1 else "")
    return f"535 K1 {bao_key.upper()} S {main}-{sp_str}"

def sms_bao_645_655(prefix, bao_key, nums):
    return f"{prefix} K1 {bao_key.upper()} S {' '.join(f'{n:02d}' for n in nums)}"

# ==========================================
# GOOGLE SHEETS
# ==========================================
def get_sheet():
    scopes = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
    creds_b64 = os.environ.get("GOOGLE_CREDENTIALS_B64", "")
    if creds_b64:
        creds_json = base64.b64decode(creds_b64).decode("utf-8")
        creds_dict = json.loads(creds_json)
        creds = Credentials.from_service_account_info(creds_dict, scopes=scopes)
    else:
        raise ValueError("Khong tim thay GOOGLE_CREDENTIALS_B64!")
    gc = gspread.authorize(creds)
    return gc.open_by_key(os.environ.get("GOOGLE_SHEET_ID", ""))

def save_result(type_key, ngay, ky, numbers, special=None):
    try:
        wb = get_sheet()
        ws = wb.worksheet(type_key)
        existing = ws.col_values(2)
        if str(ky).strip() in [str(k).strip() for k in existing[1:]]:
            print(f"⚠️ Kỳ {ky} đã tồn tại, bỏ qua!")
            return False
        row = [ngay, ky] + [str(n) for n in numbers]
        if special: row.append(str(special))
        ws.append_row(row)
        return True
    except Exception as e:
        print(f"❌ Error save Sheets: {e}")
        return False

WORKER_URL = "https://vietlott-proxy.regidgeneral.workers.dev"

def parse_result_list(result_list, cfg):
    """Parse list số từ today.json thành (nums, special)"""
    key = cfg["sms_prefix"]
    try:
        if key == "535":
            if len(result_list) < 6: return None, None
            return result_list[:5], result_list[5]
        elif key == "645":
            if len(result_list) < 6: return None, None
            return result_list[:6], None
        elif key == "655":
            if len(result_list) < 7: return None, None
            return result_list[:6], result_list[6]
    except Exception:
        pass
    return None, None

def save_suggestions(type_key, ky, ngay, time_str, all_sets):
    """Lưu 5 bộ số gợi ý vào sheet 'suggestions'"""
    try:
        wb = get_sheet()
        ws = wb.worksheet("suggestions")
        # Header nếu chưa có
        existing = ws.get_all_values()
        if not existing:
            ws.append_row(["type_key", "ky", "date", "time", "bo1", "bo2", "bo3", "bo4", "bo5"])
        # Kiểm tra kỳ đã lưu chưa
        if any(str(row[1]).strip() == str(ky).strip() and str(row[0]).strip() == type_key
               for row in existing[1:] if len(row) >= 2):
            print(f"⚠️ Suggestions kỳ {ky} đã tồn tại")
            return
        row = [type_key, ky, ngay, time_str]
        for nums, sp in all_sets[:5]:
            nums_str = " ".join(f"{n:02d}" for n in nums)
            if sp:
                nums_str += f" | {sp:02d}"
            row.append(nums_str)
        # Pad nếu < 5 bộ
        while len(row) < 9:
            row.append("")
        ws.append_row(row)
        print(f"✅ Saved suggestions kỳ {ky}")
    except Exception as e:
        print(f"⚠️ save_suggestions error: {e}")

def compare_with_suggestions(type_key, ky, result_nums, result_special):
    """So sánh kết quả thực tế với bộ số đã gợi kỳ trước"""
    try:
        wb = get_sheet()
        ws = wb.worksheet("suggestions")
        rows = ws.get_all_values()
        if len(rows) <= 1:
            return None

        # Tìm kỳ trước của type_key
        prev_rows = [r for r in rows[1:] if len(r) >= 5 and r[0] == type_key]
        if not prev_rows:
            return None

        # Lấy kỳ gần nhất (trước kỳ hiện tại)
        prev_rows_sorted = sorted(prev_rows, key=lambda r: r[1], reverse=True)
        prev = None
        for r in prev_rows_sorted:
            if r[1].strip() != str(ky).strip():
                prev = r
                break
        if not prev:
            return None

        prev_ky = prev[1]
        result_set = set(result_nums)
        comparisons = []
        for i, col in enumerate(prev[4:9], 1):
            if not col.strip():
                continue
            # Parse "01 06 09 15 23 | 08" hoặc "01 06 09 15 23"
            parts = col.split("|")
            nums_str = parts[0].strip()
            nums = [int(x) for x in nums_str.split() if x.isdigit()]
            matched = sorted(set(nums) & result_set)
            comparisons.append((i, nums, matched))

        return prev_ky, comparisons
    except Exception as e:
        print(f"⚠️ compare_with_suggestions error: {e}")
        return None

def fetch_latest_result(type_key):
    """
    Ưu tiên fetch từ Cloudflare Worker (realtime).
    Fallback về JSONL nếu Worker lỗi.
    """
    cfg = CONFIGS[type_key]
    try:
        r = requests.get(f"{WORKER_URL}/?type={type_key}",
                        headers={"User-Agent": "Mozilla/5.0"},
                        timeout=10)
        if r.status_code == 200:
            data = r.json()
            result = data.get("result", {})
            if result:
                ky_date = result.get("date", "")
                ky = result.get("id", "?").zfill(5)
                nums_raw = result.get("result", [])
                nums, special = parse_result_list(nums_raw, cfg)
                if nums:
                    y, mo, dd = ky_date.split("-")
                    d_str = f"{dd}/{mo}/{y}"
                    is_today = data.get("is_today", False)
                    status = "hôm nay" if is_today else "kỳ mới nhất"
                    print(f"✅ {type_key}: Worker kỳ {ky} ({status})")
                    return f"{ky} ({d_str})", nums, special
    except Exception as e:
        print(f"⚠️ Worker fetch error {type_key}: {e}")
    print(f"⚠️ {type_key}: fallback to JSONL")
    try:
        r = requests.get(cfg["jsonl_url"], headers={"User-Agent": "Mozilla/5.0"}, timeout=30)
        if r.status_code != 200: return None, None, None
        lines_raw = [l.strip() for l in r.text.strip().split("\n") if l.strip()]
        if not lines_raw: return None, None, None
        data = json.loads(lines_raw[-1])
        ky   = str(data.get("id", "?")).zfill(5)
        d    = data.get("date", "")
        if d and len(d) == 10:
            y, m, dd = d.split("-")
            d = f"{dd}/{m}/{y}"
        nums, special = parse_jsonl_line(lines_raw[-1], cfg)
        return f"{ky} ({d})", nums, special
    except Exception as e:
        print(f"❌ Error fetch latest {type_key}: {e}")
    return None, None, None


# ==========================================
# HANDLERS
# ==========================================
async def run_pick(interaction, type_key, so_luong):
    cfg = CONFIGS[type_key]
    await interaction.response.defer(thinking=True)
    try:
        numbers, specials, days_since, pair_freq = get_combined_data(type_key)
        if len(numbers) < cfg["k"] * 5:
            await interaction.followup.send("⚠️ Không lấy được dữ liệu!")
            return
        freq = compute_freq(numbers, cfg["n"])
        sp_freq = compute_freq(specials, cfg.get("special_n", 55)) if specials else None
        draws = len(numbers) // cfg["k"]

        embed = discord.Embed(title=f"🎰 {cfg['label']} — {so_luong} bộ số", color=0x1D9E75)
        embed.add_field(name="Phân tích từ", value=f"{draws} kỳ lịch sử", inline=True)

        # Lấy kỳ mới nhất để anti-repeat
        k = cfg["k"]
        last_draw = list(numbers[-k:]) if len(numbers) >= k else None

        all_sets, seen, lines = [], set(), []
        for i in range(so_luong):
            nums = generate_nums(freq, cfg["n"], cfg["k"], seen, days_since, pair_freq, last_draw, type_key=type_key)
            seen.add(tuple(nums))
            sp = None
            if cfg.get("has_special") and sp_freq:
                sp_sorted = sorted(sp_freq.items(), key=lambda x: x[1], reverse=True)
                sp = weighted_pick([n for n, _ in sp_sorted], [c for _, c in sp_sorted], 1)[0]
            all_sets.append((nums, sp))
            disp = " ".join(f"`{n:02d}`" for n in nums)
            extra = f" | ĐB:`{sp:02d}`" if sp and type_key == "535" else (f" | Power:`{sp:02d}`" if sp else "")
            lines.append(f"**Bộ {i+1}:** {disp}{extra}")

        tong = so_luong * 10000
        add_fields_chunked(embed, lines)
        embed.add_field(name="Tổng tiền", value=fmt_gia(tong), inline=False)
        sms = sms_basic_535(all_sets) if type_key == "535" else sms_basic_645_655(cfg["sms_prefix"], all_sets)
        embed.set_footer(text="Bộ số là có tính toán, nhưng không đảm bảo trúng 100%")
        embed.timestamp = datetime.now(timezone.utc)
        await interaction.followup.send(embed=embed, view=make_button(sms))
    except Exception as e:
        await interaction.followup.send(f"❌ Loi: {str(e)}")

async def run_bao535(interaction, bao_key, so_bo):
    info = BAO_535[bao_key]
    so_bo_max = max_bo(info["gia"], "535")
    if so_bo > so_bo_max:
        await interaction.response.send_message(
            f"⚠️ {info['label']} gia {fmt_gia(info['gia'])}/bộ → tối đa **{so_bo_max} bộ** ({fmt_gia(GIOI_HAN_NGAY['535'])}/ngày)",
            ephemeral=True)
        return
    await interaction.response.defer(thinking=True)
    try:
        numbers, specials, days_since, pair_freq = get_combined_data("535")
        freq = compute_freq(numbers, 35)
        sp_freq = compute_freq(specials, 12) if specials else {i: 1 for i in range(1, 13)}
        sorted_sp = sorted(sp_freq.items(), key=lambda x: x[1], reverse=True)

        embed = discord.Embed(title=f"🎰 {info['label']} — Lotto 5/35", color=0x9B59B6)
        embed.add_field(name="Giới hạn ngày", value=f"Tối đa {so_bo_max} bộ ({fmt_gia(GIOI_HAN_NGAY['535'])} / {fmt_gia(info['gia'])})", inline=False)

        last_draw = list(numbers[-5:]) if len(numbers) >= 5 else None
        seen, s_parts, lines = set(), [], []
        for i in range(so_bo):
            if info["type"] == "bc":
                main_nums = generate_nums(freq, 35, info["n_main"], seen, days_since, pair_freq, last_draw, type_key="535")
                seen.add(tuple(main_nums))
                sp_pool = [n for n, _ in sorted_sp]
                sp_w = [c for _, c in sorted_sp]
                special = weighted_pick(sp_pool, sp_w, 1)[0]
                main_str = " ".join(f"{n:02d}" for n in main_nums[:-1])
                last = f"{main_nums[-1]:02d}-{special:02d}"
                s_parts.append(f"S {main_str} {last}")
                disp = " ".join(f"`{n:02d}`" for n in main_nums)
                lines.append(f"**Bộ {i+1}:** {disp} | ĐB:`{special:02d}`")
            else:
                main_nums = generate_nums(freq, 35, 5, seen, days_since, pair_freq, last_draw, type_key="535")
                seen.add(tuple(main_nums))
                specials_picked = [n for n, _ in sorted_sp[:info["n_sp"]]]
                main_str = " ".join(f"{n:02d}" for n in main_nums)
                sp_str = f"{specials_picked[0]:02d}" + (" " + " ".join(f"{n:02d}" for n in specials_picked[1:]) if len(specials_picked) > 1 else "")
                s_parts.append(f"S {main_str}-{sp_str}")
                disp = " ".join(f"`{n:02d}`" for n in main_nums)
                sp_disp = " ".join(f"`{n:02d}`" for n in specials_picked)
                lines.append(f"**Bộ {i+1}:** {disp} | ĐB: {sp_disp}")

        tong = so_bo * info["gia"]
        add_fields_chunked(embed, lines)
        embed.add_field(name="Tổng tiền", value=f"{fmt_gia(tong)} / {fmt_gia(GIOI_HAN_NGAY['535'])} hạn mức ngày", inline=False)
        sms = f"535 K1 {bao_key.upper()} " + " ".join(s_parts)
        embed.set_footer(text="Bộ số là có tính toán, nhưng không đảm bảo trúng 100%")
        embed.timestamp = datetime.now(timezone.utc)
        await interaction.followup.send(embed=embed, view=make_button(sms))
    except Exception as e:
        await interaction.followup.send(f"❌ Loi: {str(e)}")

async def run_bao645655(interaction, type_key, bao_key, so_bo):
    info = BAO_645_655[bao_key]
    gia = info[f"gia_{type_key}"]
    cfg = CONFIGS[type_key]
    so_bo_max = max_bo(gia, type_key)
    if so_bo > so_bo_max:
        await interaction.response.send_message(
            f"⚠️ {info['label']} giá {fmt_gia(gia)}/bộ → tối đa **{so_bo_max} bộ** ({fmt_gia(GIOI_HAN_NGAY[type_key])}/ngày)",
            ephemeral=True)
        return
    await interaction.response.defer(thinking=True)
    try:
        numbers, _, days_since, pair_freq = get_combined_data(type_key)
        freq = compute_freq(numbers, cfg["n"])

        embed = discord.Embed(title=f"🎰 {info['label']} — {cfg['label']}", color=0x9B59B6)
        embed.add_field(name="Giới hạn ngày", value=f"Tối đa {so_bo_max} bộ ({fmt_gia(GIOI_HAN_NGAY[type_key])} / {fmt_gia(gia)})", inline=False)

        k = cfg["k"]
        last_draw = list(numbers[-k:]) if len(numbers) >= k else None
        seen, s_parts, lines = set(), [], []
        for i in range(so_bo):
            nums = generate_nums(freq, cfg["n"], info["n"], seen, days_since, pair_freq, last_draw, type_key=type_key)
            seen.add(tuple(nums))
            s_parts.append("S " + " ".join(f"{n:02d}" for n in nums))
            disp = " ".join(f"`{n:02d}`" for n in nums)
            lines.append(f"**Bộ {i+1}:** {disp}")

        tong = so_bo * gia
        add_fields_chunked(embed, lines)
        embed.add_field(name="Tổng tiền", value=f"{fmt_gia(tong)} / {fmt_gia(GIOI_HAN_NGAY[type_key])} hạn mức ngày", inline=False)
        sms = f"{cfg['sms_prefix']} K1 {bao_key.upper()} " + " ".join(s_parts)
        embed.set_footer(text="Bộ số là có tính toán, nhưng không đảm bảo trúng 100%")
        embed.timestamp = datetime.now(timezone.utc)
        await interaction.followup.send(embed=embed, view=make_button(sms))
    except Exception as e:
        await interaction.followup.send(f"❌ Lỗi: {str(e)}")

# ==========================================
# TỰ ĐỘNG BÁO KẾT QUẢ SAU GIỜ XỔ
# ==========================================
async def post_result(type_key):
    try:
        channel = client.get_channel(DISCORD_CHANNEL_ID) or await client.fetch_channel(DISCORD_CHANNEL_ID)
    except Exception as e:
        print(f"❌ Khong tim thay kenh: {e}")
        return
    cfg = CONFIGS[type_key]
    ngay = datetime.now(VN_TZ).strftime("%d/%m/%Y")
    await channel.send(f"⏳ Dang lay ket qua **{cfg['label']}**...")

    _cache.pop(type_key, None)  # Xóa cache để fetch mới
    _cache.pop(f"text_{type_key}", None)

    ky, numbers, special = None, None, None
    today_iso = datetime.now(VN_TZ).strftime("%Y-%m-%d")

    for attempt in range(6):
        ky, numbers, special = fetch_latest_result(type_key)
        if numbers:
            # Worker trả is_today qua ky string "00677 (03/06/2026)"
            m_date = re.search(r'(\d{2})/(\d{2})/(\d{4})', ky or "")
            if m_date:
                ky_date = f"{m_date.group(3)}-{m_date.group(2)}-{m_date.group(1)}"
                if ky_date == today_iso:
                    print(f"✅ {type_key}: kỳ hôm nay {ky}")
                    break
                else:
                    print(f"⚠️ {type_key}: kỳ {ky} chưa phải hôm nay ({today_iso}), retry {attempt+1}/6...")
                    numbers = None
            else:
                break
        if attempt < 5:
            await asyncio.sleep(120)

    if not numbers:
        await channel.send(f"⚠️ Không lấy được kết quả {cfg['label']}!")
        return

    save_result(type_key, ngay, ky, numbers, special)

    # So sánh với gợi ý kỳ trước
    compare_result = compare_with_suggestions(type_key, ky, numbers, special)

    embed = discord.Embed(title=f"🎰 Kết quả {cfg['label']} — {ngay}", color=0xE74C3C)
    embed.add_field(name="Kỳ", value=f"**{ky}**", inline=True)
    embed.add_field(name="Kết quả", value=" ".join(f"`{n:02d}`" for n in numbers), inline=False)
    if special:
        embed.add_field(name="Đặc biệt" if type_key == "535" else "Power", value=f"`{special:02d}`", inline=True)

    # Thêm phần so sánh nếu có
    if compare_result:
        prev_ky, comparisons = compare_result
        lines = []
        for i, nums, matched in comparisons:
            nums_disp = " ".join(f"`{n:02d}`" for n in nums)
            if matched:
                matched_disp = " ".join(f"`{n:02d}`" for n in matched)
                lines.append(f"Bộ {i}: {nums_disp} → ✅ Trúng **{len(matched)}** số: {matched_disp}")
            else:
                lines.append(f"Bộ {i}: {nums_disp} → ❌ 0 số")
        embed.add_field(
            name=f"📊 So sánh với gợi ý kỳ #{prev_ky}",
            value="\n".join(lines),
            inline=False
        )

    embed.timestamp = datetime.now(timezone.utc)
    await channel.send(embed=embed)

    # Gợi ý 5 bộ số kỳ tiếp
    await asyncio.sleep(2)
    all_nums, all_sp, days_since, pair_freq = get_combined_data(type_key)
    freq = compute_freq(all_nums, cfg["n"])
    sp_freq = compute_freq(all_sp, cfg.get("special_n", 55)) if all_sp else None

    embed2 = discord.Embed(title=f"🎯 Gợi ý 5 bộ số kì tiếp — {cfg['label']}", color=0x1D9E75)
    k = cfg["k"]
    last_draw = list(all_nums[-k:]) if len(all_nums) >= k else None
    all_sets, seen = [], set()
    for i in range(5):
        nums = generate_nums(freq, cfg["n"], cfg["k"], seen, days_since, pair_freq, last_draw, type_key=type_key)
        seen.add(tuple(nums))
        sp = None
        if cfg.get("has_special") and sp_freq:
            sp_sorted = sorted(sp_freq.items(), key=lambda x: x[1], reverse=True)
            sp = weighted_pick([n for n, _ in sp_sorted], [c for _, c in sp_sorted], 1)[0]
        all_sets.append((nums, sp))
        disp = " ".join(f"`{n:02d}`" for n in nums)
        extra = f"  |  ĐB: `{sp:02d}`" if sp and type_key == "535" else (f"  |  Power: `{sp:02d}`" if sp else "")
        embed2.add_field(name=f"Bo {i+1}", value=disp + extra, inline=False)

    sms = sms_basic_535(all_sets) if type_key == "535" else sms_basic_645_655(cfg["sms_prefix"], all_sets)
    embed2.set_footer(text="Bộ số là có tính toán, nhưng không đảm bảo trúng 100%")
    embed2.timestamp = datetime.now(timezone.utc)
    await channel.send(embed=embed2, view=make_button(sms))

    # Lưu gợi ý vào Sheets để so sánh kỳ sau
    time_str = datetime.now(VN_TZ).strftime("%H:%M")
    save_suggestions(type_key, ky, ngay, time_str, all_sets)

async def scheduler():
    print("⏰ Scheduler started")
    while True:
        now = datetime.now(VN_TZ)
        wd, h, m = now.weekday(), now.hour, now.minute
        for type_key, lich in LICH_XO.items():
            for (ngay_xo, gio, phut) in lich:
                if wd == ngay_xo and h == gio and m == phut:
                    asyncio.create_task(post_result(type_key))
        await asyncio.sleep(60)

# ==========================================
# SLASH COMMANDS
# ==========================================
@tree.command(name="535", description="Gợi ý bộ số Lotto 5/35 kèm SMS")
@app_commands.describe(so_luong="Số bộ muốn mua (1-10)")
async def cmd_535(interaction, so_luong: app_commands.Range[int, 1, 10] = 1):
    await run_pick(interaction, "535", so_luong)

@tree.command(name="645", description="Gợi ý bộ số Mega 6/45 kèm SMS")
@app_commands.describe(so_luong="Số bộ muốn mua (1-10)")
async def cmd_645(interaction, so_luong: app_commands.Range[int, 1, 10] = 1):
    await run_pick(interaction, "645", so_luong)

@tree.command(name="655", description="Gợi ý bộ số Power 6/55 kèm SMS")
@app_commands.describe(so_luong="Số bộ muốn mua (1-10)")
async def cmd_655(interaction, so_luong: app_commands.Range[int, 1, 10] = 1):
    await run_pick(interaction, "655", so_luong)

# Bao 535
bao535_choices = [
    app_commands.Choice(name="BC4 – Bao 4 số chính (310.000d) – max 3 bộ",    value="bc4"),
    app_commands.Choice(name="BC6 – Bao 6 số chính (60.000d) – max 16 bộ",    value="bc6"),
    app_commands.Choice(name="BC7 – Bao 7 số chính (210.000d) – max 4 bộ",    value="bc7"),
    app_commands.Choice(name="BC8 – Bao 8 số chính (560.000d) – max 1 bộ",    value="bc8"),
    app_commands.Choice(name="BD2 – Bao 2 số đặc biệt (20.000d) – max 50 bộ", value="bd2"),
    app_commands.Choice(name="BD3 – Bao 3 số đặc biệt (30.000d) – max 33 bộ", value="bd3"),
    app_commands.Choice(name="BD4 – Bao 4 số đặc biệt (40.000d) – max 25 bộ", value="bd4"),
    app_commands.Choice(name="BD5 – Bao 5 số đặc biệt (50.000d) – max 20 bộ", value="bd5"),
    app_commands.Choice(name="BD6 – Bao 6 số đặc biệt (60.000d) – max 16 bộ", value="bd6"),
    app_commands.Choice(name="BD7 – Bao 7 số đặc biệt (70.000d) – max 14 bộ", value="bd7"),
    app_commands.Choice(name="BD8 – Bao 8 số đặc biệt (80.000d) – max 12 bộ", value="bd8"),
    app_commands.Choice(name="BD9 – Bao 9 số đặc biệt (90.000d) – max 11 bộ", value="bd9"),
    app_commands.Choice(name="BD10 – Bao 10 số đặc biệt (100.000d) – max 10 bộ", value="bd10"),
    app_commands.Choice(name="BD11 – Bao 11 số đặc biệt (110.000d) – max 9 bộ",  value="bd11"),
    app_commands.Choice(name="BD12 – Bao 12 số đặc biệt (120.000d) – max 8 bộ",  value="bd12"),
]
@tree.command(name="bao535", description="Bao số Lotto 5/35 kèm SMS")
@app_commands.describe(loai="Chọn loại bao số", so_bo="Số bộ muốn mua")
@app_commands.choices(loai=bao535_choices)
async def cmd_bao535(interaction, loai: app_commands.Choice[str], so_bo: app_commands.Range[int, 1, 50] = 1):
    await run_bao535(interaction, loai.value, so_bo)

bao645_choices = [
    app_commands.Choice(name="B5  – Bao 5 số (400.000d) – max 5 bộ",    value="b5"),
    app_commands.Choice(name="B7  – Bao 7 số (70.000d) – max 30 bộ",    value="b7"),
    app_commands.Choice(name="B8  – Bao 8 số (280.000d) – max 7 bộ",    value="b8"),
    app_commands.Choice(name="B9  – Bao 9 số (840.000d) – max 2 bộ",    value="b9"),
    app_commands.Choice(name="B10 – Bao 10 số (2.100.000d) – max 1 bộ", value="b10"),
]
@tree.command(name="bao645", description="Bao số Mega 6/45 kèm SMS")
@app_commands.describe(loai="Chọn loại bao số", so_bo="Số bộ muốn mua")
@app_commands.choices(loai=bao645_choices)
async def cmd_bao645(interaction, loai: app_commands.Choice[str], so_bo: app_commands.Range[int, 1, 30] = 1):
    await run_bao645655(interaction, "645", loai.value, so_bo)

bao655_choices = [
    app_commands.Choice(name="B5  – Bao 5 số (500.000d) – max 4 bộ",    value="b5"),
    app_commands.Choice(name="B7  – Bao 7 số (70.000d) – max 30 bộ",    value="b7"),
    app_commands.Choice(name="B8  – Bao 8 số (280.000d) – max 7 bộ",    value="b8"),
    app_commands.Choice(name="B9  – Bao 9 số (840.000d) – max 2 bộ",    value="b9"),
    app_commands.Choice(name="B10 – Bao 10 số (2.100.000d) – max 1 bộ", value="b10"),
]
@tree.command(name="bao655", description="Bao số Power 6/55 kèm SMS")
@app_commands.describe(loai="Chọn loại bao số", so_bo="Số bộ muốn mua")
@app_commands.choices(loai=bao655_choices)
async def cmd_bao655(interaction, loai: app_commands.Choice[str], so_bo: app_commands.Range[int, 1, 30] = 1):
    await run_bao645655(interaction, "655", loai.value, so_bo)

# ==========================================
# KHỞI ĐỘNG
# ==========================================
@tree.command(name="test", description="Test bot gui tin vao kenh")
async def cmd_test(interaction: discord.Interaction):
    await interaction.response.defer(thinking=True)
    try:
        channel = client.get_channel(DISCORD_CHANNEL_ID) or await client.fetch_channel(DISCORD_CHANNEL_ID)
        await channel.send("✅ Bot test thanh cong! Scheduler se tu dong bao ket qua sau gio xo.")
        await interaction.followup.send(f"✅ Da gui tin vao kenh <#{DISCORD_CHANNEL_ID}>")
    except Exception as e:
        await interaction.followup.send(f"❌ Loi: {e}")

@client.event
async def on_ready():
    await tree.sync()
    print(f"✅ Bot da online: {client.user}")
    print("Commands: /535 /645 /655 /bao535 /bao645 /bao655")
    asyncio.create_task(scheduler())

client.run(TOKEN)
