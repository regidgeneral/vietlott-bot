import discord
import json
import asyncio
import requests
import random
import re
import os
import time
import urllib.parse
from bs4 import BeautifulSoup
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

GIOI_HAN_NGAY = {"535": 2_500_000, "645": 2_100_000, "655": 2_100_000}

# Giới hạn MỀM: số bộ tối đa cho MỖI LỆNH (hạn mức ngày ở trên vẫn giữ nguyên).
# Hạn mức 2,5tr cho phép bd2 tới 125 bộ, nhưng khi đó nội dung SMS dài 2885 ký tự
# (~19 đoạn SMS) và URL 4678 ký tự — TinyURL dễ từ chối, người dùng mất nút bấm.
# Cap 50 kéo ca xấu nhất về 1610 ký tự (~11 đoạn). Muốn đặt thêm thì gọi lệnh nữa.
SO_BO_MOI_LENH = 50

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

MODEL_TTL = 6 * 3600  # model retrain hàng tuần; bot chạy 24/7 nên phải có hạn cache

def load_model(type_key):
    """Load model JSON từ GitHub, cache trong memory (hết hạn sau MODEL_TTL).

    Trước đây cache vĩnh viễn: bot chạy liên tục vài tháng thì mãi mãi dùng model
    của lần khởi động đầu, mọi lần retrain hàng tuần đều vô nghĩa.
    """
    cached = _model_cache.get(type_key)
    if cached and (time.time() - cached[1]) < MODEL_TTL:
        return cached[0]
    try:
        url = MODEL_BASE_URL.format(type_key)
        r = requests.get(url, headers={"User-Agent": "Mozilla/5.0"}, timeout=10)
        if r.status_code == 200:
            model = r.json()
            _model_cache[type_key] = (model, time.time())
            print(f"✅ Loaded model_{type_key} (n_draws={model.get('n_draws')})")
            return model
    except Exception as e:
        print(f"⚠️ load_model {type_key}: {e}")
    return cached[0] if cached else None  # hết hạn nhưng tải lỗi → dùng tạm bản cũ

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

def fetch_jsonl_draws(cfg):
    """[(ky, ngay|None, nums, sp)] từ JSONL GitHub. Cache theo type."""
    key = cfg["sms_prefix"]
    if key in _cache:
        return _cache[key]
    draws = []
    try:
        r = requests.get(cfg["jsonl_url"], headers={"User-Agent": "Mozilla/5.0"}, timeout=30)
        if r.status_code != 200:
            return draws
        for line in r.text.strip().split("\n"):
            line = line.strip()
            if not line: continue
            try:
                nums, sp = parse_jsonl_line(line, cfg)
                if not nums: continue
                data = json.loads(line)
                try:
                    ngay = date.fromisoformat(data.get("date", ""))
                except ValueError:
                    ngay = None
                draws.append((int(data["id"]), ngay, nums, sp))
            except: continue
        _cache[key] = draws
    except Exception as e:
        print(f"❌ Fetch error {key}: {e}")
    return draws

def load_sheet_draws(type_key):
    """[(ky, ngay|None, nums, sp)] từ Google Sheets. Chỉ đọc sheet MỘT lần."""
    cfg = CONFIGS[type_key]
    k = cfg["k"]
    draws = []
    try:
        rows = get_sheet().worksheet(type_key).get_all_values()
        for row in rows[1:]:  # bỏ header
            try:
                ky = int(str(row[1]).split(" ")[0])
                nums = [int(row[i]) for i in range(2, 2 + k)
                        if i < len(row) and row[i].strip().isdigit()]
                if len(nums) != k:
                    continue
                ngay = None
                ds = row[0].strip()
                if len(ds) == 10:
                    d, m, y = ds.split("/")
                    ngay = date(int(y), int(m), int(d))
                sp = None
                if cfg.get("has_special") and len(row) > 2 + k and row[2 + k].strip().isdigit():
                    sp = int(row[2 + k])
                draws.append((ky, ngay, nums, sp))
            except:
                continue
    except Exception as e:
        print(f"⚠️ Khong doc duoc Sheets {type_key}: {e}")
    return draws

def get_combined_data(type_key):
    """Gộp JSONL + Google Sheets, KHỬ TRÙNG theo số kỳ.

    Trước đây nối thẳng hai list nên hầu như mọi kỳ bị đếm hai lần (6/45: 1356
    trong tổng 1362 kỳ trùng nhau) — embed báo '2718 kỳ lịch sử' trong khi thực
    tế chỉ có 1362. Sheets ghi đè JSONL vì đó là bản bot tự lưu, khớp ngày hơn.
    Trả về: all_nums, all_sp, days_since, pair_freq
    """
    cfg = CONFIGS[type_key]
    theo_ky = {}
    for ky, ngay, nums, sp in fetch_jsonl_draws(cfg):
        theo_ky[ky] = (ngay, nums, sp)
    n_jsonl = len(theo_ky)
    for ky, ngay, nums, sp in load_sheet_draws(type_key):
        theo_ky[ky] = (ngay, nums, sp)

    all_nums, all_sp, lan_cuoi = [], [], {}
    for ky in sorted(theo_ky):
        ngay, nums, sp = theo_ky[ky]
        all_nums.extend(nums)
        if cfg.get("has_special") and sp is not None:
            all_sp.append(sp)
        if ngay:
            for n in nums:
                if n not in lan_cuoi or ngay > lan_cuoi[n]:
                    lan_cuoi[n] = ngay

    # date.today() lấy theo giờ máy chủ (Railway chạy UTC) → lệch 1 ngày với VN
    hom_nay = datetime.now(VN_TZ).date()
    days_since = {n: (hom_nay - lan_cuoi[n]).days if n in lan_cuoi else 9999
                  for n in range(1, cfg["n"] + 1)}
    pair_freq = compute_pair_freq(all_nums, cfg["k"]) if all_nums else {}

    print(f"✅ {type_key}: {len(theo_ky)} kỳ duy nhất "
          f"({n_jsonl} JSONL + {len(theo_ky) - n_jsonl} kỳ chỉ có ở Sheets)")
    return all_nums, all_sp, days_since, pair_freq

def compute_freq(numbers, n):
    freq = {i: 0 for i in range(1, n + 1)}
    for num in numbers:
        if num in freq: freq[num] += 1
    return freq

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



FIELD_MAX, EMBED_BUDGET = 1024, 5500

def add_fields_chunked(embed, lines, chunk_size=10):
    """Chia bộ số thành nhiều field, gom theo ĐỘ DÀI THẬT chứ không chunk cứng.

    Chunk cứng 10 dòng/field rất sát giới hạn: bd12 (20 bộ) cho field 1019/1024,
    và sau khi hạn mức 535 lên 2,5tr thì bd2 (125 bộ) cho embed 6754/6000 → vỡ.
    """
    da_dung = len(embed.title or "") + sum(
        len(f.name or "") + len(f.value or "") for f in embed.fields)
    i, dau = 0, True
    while i < len(lines):
        buf = []
        while i < len(lines) and len(buf) < chunk_size:
            if len("\n".join(buf + [lines[i]])) > FIELD_MAX - 24:
                break
            buf.append(lines[i]); i += 1
        if not buf:  # một dòng đơn lẻ đã dài hơn cả field
            buf = [lines[i][:FIELD_MAX - 24]]; i += 1
        name, value = ("Bộ số" if dau else "Bộ số (tiếp)"), "\n".join(buf)
        if da_dung + len(name) + len(value) > EMBED_BUDGET or len(embed.fields) >= 23:
            embed.add_field(
                name="…",
                value=f"Còn {len(lines) - i + len(buf)} bộ nữa — xem đầy đủ trong SMS",
                inline=False)
            return
        da_dung += len(name) + len(value)
        embed.add_field(name=name, value=value, inline=False)
        dau = False

def fmt_gia(gia):
    return f"{gia:,}d".replace(",", ".")

def max_bo(gia, type_key):
    """Số bộ tối đa theo HẠN MỨC NGÀY (tiền)."""
    return max(1, GIOI_HAN_NGAY[type_key] // gia)

def max_bo_moi_lenh(gia, type_key):
    """Số bộ tối đa cho MỘT LỆNH = hạn mức ngày, chặn thêm bởi giới hạn mềm."""
    return min(max_bo(gia, type_key), SO_BO_MOI_LENH)

def nhan_bao(label, gia, type_key):
    """Nhãn choice: nêu rõ giới hạn mỗi lệnh, và hạn mức ngày nếu hai số khác nhau."""
    ngay, lenh = max_bo(gia, type_key), max_bo_moi_lenh(gia, type_key)
    if lenh < ngay:
        return f"{label} ({fmt_gia(gia)}) – max {lenh} bộ/lệnh (ngày: {ngay})"
    return f"{label} ({fmt_gia(gia)}) – max {lenh} bộ"

def make_sms_link(sms_text):
    return f"https://vietlott-sms.netlify.app/?body={urllib.parse.quote(sms_text)}"

def shorten_url(url):
    """Trả None nếu không rút gọn được.

    Trước đây trả url[:512] — cắt giữa chuỗi query tạo ra link HỎNG mà người dùng
    không biết. 14/25 loại bao có URL > 512 (bd2 50 bộ = 1903 ký tự) nên nhánh này
    chạy thật, không phải trường hợp hiếm.
    """
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
    return None

async def make_button(sms_text):
    """shorten_url gọi mạng nên đẩy sang thread riêng, tránh chặn event loop.
    View phải dựng trên event loop nên không gộp cả hàm vào to_thread được."""
    url = await asyncio.to_thread(shorten_url, make_sms_link(sms_text))
    if not url:
        print("⚠️ Không rút gọn được URL — bỏ nút SMS (thà không có nút còn hơn nút hỏng)")
        return discord.utils.MISSING
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

# Nguồn realtime chính. Worker chỉ còn là dự phòng: từ khoảng 09/2026 nó trả
# {"error":"Parse failed or no data","raw":""} nên bot mất luôn kết quả trong ngày
# (JSONL của vietvudanh chỉ cập nhật ~00:01 hôm sau).
MINHCHINH_URLS = {
    "535": "https://www.minhchinh.com/xo-so-dien-toan-lotto-535.html",
    "645": "https://www.minhchinh.com/xo-so-dien-toan-mega-645.html",
    "655": "https://www.minhchinh.com/xo-so-dien-toan-power-655.html",
}
MINHCHINH_HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "vi-VN,vi;q=0.9",
    "Referer": "https://www.minhchinh.com/",
}
# 535 xổ 2 lần/ngày nên có giờ: "kỳ #874 ngày 08/09/2026 - Lúc 21:00 04 07 14 16 23 10"
# 645/655 xổ 1 lần/ngày, KHÔNG có phần "- Lúc": "kỳ #1559 ngày 06/09/2026 09 14 22 26 27 40"
KY_PATTERN = re.compile(
    r'kỳ\s+#(\d+)\s+ngày\s+(\d{2}/\d{2}/\d{4})\s*(?:-\s*Lúc\s+(\d+:\d+))?\s+((?:\d+\s*){4,8})',
    re.IGNORECASE
)
JACKPOT_PATTERN = re.compile(r'Giá trị Độc Đắc\s+([\d.,]+)', re.IGNORECASE)
# Số lượng số cần lấy: 535 = 5 chính + ĐB, 645 = 6 chính, 655 = 6 chính + Power
NUM_COUNT = {"535": 6, "645": 6, "655": 7}

def _minhchinh_text(type_key):
    r = requests.get(MINHCHINH_URLS[type_key], headers=MINHCHINH_HEADERS, timeout=15)
    if r.status_code != 200:
        return None
    return BeautifulSoup(r.text, "html.parser").get_text(" ", strip=True)

def fetch_from_minhchinh(type_key):
    """Lấy kỳ mới nhất từ minhchinh.com. Trả về (ky_str, nums, special)."""
    cfg = CONFIGS[type_key]
    try:
        text = _minhchinh_text(type_key)
        if not text:
            return None, None, None
        need = NUM_COUNT[type_key]
        best = None
        for m in KY_PATTERN.finditer(text):
            nums_raw = [int(x) for x in m.group(4).split() if x.isdigit()]
            if len(nums_raw) < need:
                continue
            ky = int(m.group(1))
            if best is None or ky > best[0]:
                best = (ky, m.group(2), nums_raw[:need])
        if not best:
            return None, None, None
        ky, d_str, nums_raw = best
        nums, special = parse_result_list(nums_raw, cfg)
        if not nums:
            return None, None, None
        print(f"✅ {type_key}: minhchinh kỳ {ky} ({d_str})")
        return f"{str(ky).zfill(5)} ({d_str})", nums, special
    except Exception as e:
        print(f"⚠️ minhchinh fetch error {type_key}: {e}")
    return None, None, None

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

BO_MOI_DONG = 30  # sheet 'suggestions' rộng 35 cột, 5 cột đầu là metadata

def save_suggestions(type_key, ky, ngay, time_str, all_sets, source="scheduler"):
    """Lưu bộ số gợi ý vào sheet 'suggestions'
    source: 'scheduler' (tự động sau kỳ xổ) hoặc 'manual' (user gọi lệnh)
    """
    try:
        wb = get_sheet()
        ws = wb.worksheet("suggestions")
        existing = ws.get_all_values()
        if not existing:
            ws.append_row(["type_key", "ky", "date", "time", "source", "bo1", "bo2", "bo3", "bo4", "bo5"])
            existing = [["type_key", "ky", "date", "time", "source", "bo1", "bo2", "bo3", "bo4", "bo5"]]
        if source == "scheduler":
            if any(str(row[1]).strip() == str(ky).strip()
                   and str(row[0]).strip() == type_key
                   and len(row) > 4 and row[4] == "scheduler"
                   for row in existing[1:] if len(row) >= 2):
                print(f"⚠️ Suggestions scheduler kỳ {ky} đã tồn tại")
                return
        sets_to_save = all_sets[:5] if source == "scheduler" else all_sets
        # Sheet chỉ rộng 35 cột (5 metadata + 30 bộ). /bao535 bd2 sinh tới 50 bộ →
        # append_row vượt khung, gspread ném lỗi và bị except nuốt → mất gợi ý.
        # Tách thành nhiều dòng cùng (type_key, ky, source); các hàm đọc đều đã
        # gộp theo source nên nhiều dòng vẫn cho kết quả đúng.
        for i in range(0, len(sets_to_save), BO_MOI_DONG):
            row = [type_key, ky, ngay, time_str, source]
            for nums, sp in sets_to_save[i:i + BO_MOI_DONG]:
                nums_str = " ".join(f"{n:02d}" for n in nums)
                if sp:
                    nums_str += f" | {sp:02d}"
                row.append(nums_str)
            ws.append_row(row)
        print(f"✅ Saved suggestions kỳ {ky} ({source}, {len(sets_to_save)} bộ)")
    except Exception as e:
        print(f"⚠️ save_suggestions error: {e}")

def compare_with_suggestions(type_key, ky, result_nums, result_special):
    """So sánh kết quả thực tế với TẤT CẢ bộ số đã gợi cho kỳ này (mọi nguồn: scheduler, manual, bao...)"""
    try:
        wb = get_sheet()
        ws = wb.worksheet("suggestions")
        rows = ws.get_all_values()
        if len(rows) <= 1:
            return None

        ky_clean = str(ky).split(" ")[0].strip().zfill(5)

        # Lấy TẤT CẢ rows của type_key có ky khớp với kỳ vừa xổ
        matching_rows = [
            r for r in rows[1:]
            if len(r) >= 5 and r[0] == type_key
            and r[1].strip().split(" ")[0].zfill(5) == ky_clean
        ]
        if not matching_rows:
            return None

        result_set = set(result_nums)
        by_source = {}  # source -> list of (nums, matched)

        for row in matching_rows:
            source = row[4] if len(row) > 4 else "unknown"
            for col in row[5:]:
                if not col.strip():
                    continue
                nums_str = col.split("|")[0].strip()
                nums = [int(x) for x in nums_str.split() if x.isdigit()]
                if not nums:
                    continue
                matched = sorted(set(nums) & result_set)
                by_source.setdefault(source, []).append((nums, matched))

        return ky_clean, by_source
    except Exception as e:
        print(f"⚠️ compare_with_suggestions error: {e}")
        return None

def save_performance(type_key, ky, ngay, result_nums, suggestions_rows):
    """Tính điểm và lưu performance sau mỗi kỳ xổ"""
    try:
        wb = get_sheet()
        ws = wb.worksheet("performance")
        existing = ws.get_all_values()
        if not existing:
            ws.append_row(["date", "type_key", "ky", "source", "avg_matched", "total_sets", "details"])

        result_set = set(result_nums)
        by_source = {}
        for row in suggestions_rows:
            if len(row) < 6: continue
            src = row[4] if len(row) > 4 else "unknown"
            if src not in by_source:
                by_source[src] = []
            for col in row[5:]:
                if not col.strip(): continue
                nums = [int(x) for x in col.split("|")[0].split() if x.isdigit()]
                if nums:
                    matched = len(set(nums) & result_set)
                    by_source[src].append(matched)

        for src, scores in by_source.items():
            if not scores: continue
            avg = round(sum(scores) / len(scores), 2)
            details = ",".join(str(s) for s in scores)
            ws.append_row([ngay, type_key, ky, src, avg, len(scores), details])
            print(f"✅ Performance {type_key} kỳ {ky} ({src}): avg={avg} ({len(scores)} bộ)")
    except Exception as e:
        print(f"⚠️ save_performance error: {e}")

def parse_score(s):
    """Đọc số từ Sheets, chịu được cả '0.8' lẫn '0,8'.

    get_all_values() trả về chuỗi ĐÃ format theo locale của sheet (tiếng Việt
    dùng dấu phẩy thập phân), nên float('0,8') ném ValueError. Trước đây lỗi
    này bị nuốt, chỉ các giá trị NGUYÊN lọt qua — mà phần lớn là 1.0 — khiến
    avg tự tính cao hơn thực tế.
    """
    try:
        return float(str(s).strip().replace(",", "."))
    except (ValueError, TypeError):
        return None

def track_performance(type_key, ky, ngay, result_nums):
    """Đọc suggestions của đúng kỳ này rồi chấm điểm. Blocking — gọi qua to_thread."""
    try:
        ky_clean = str(ky).split(" ")[0].strip().zfill(5)
        rows = get_sheet().worksheet("suggestions").get_all_values()
        this_ky_rows = [r for r in rows[1:] if len(r) >= 5
                        and r[0] == type_key
                        and r[1].strip().split(" ")[0].zfill(5) == ky_clean]
        if this_ky_rows:
            save_performance(type_key, ky_clean, ngay, result_nums, this_ky_rows)
    except Exception as e:
        print(f"⚠️ performance tracking error: {e}")

def get_performance_weights(type_key):
    """Đọc performance 30 ngày gần nhất, tính weight tối ưu cho model"""
    try:
        wb = get_sheet()
        ws = wb.worksheet("performance")
        rows = ws.get_all_values()
        if len(rows) <= 1:
            return None
        scheduler_scores = []
        for row in rows[1:]:
            if len(row) < 6: continue
            if row[1] != type_key: continue
            if row[3] != "scheduler": continue
            avg = parse_score(row[4])
            if avg is not None:
                scheduler_scores.append(avg)
        if len(scheduler_scores) < 5:
            return None
        overall_avg = sum(scheduler_scores) / len(scheduler_scores)
        print(f"📊 {type_key}: avg_matched={round(overall_avg, 2)} over {len(scheduler_scores)} kỳ")
        return {"avg_matched": overall_avg, "n_samples": len(scheduler_scores)}
    except Exception as e:
        print(f"⚠️ get_performance_weights error: {e}")
        return None

def get_jackpot_535():
    """Đọc jackpot 535 hiện tại. Trả về int (đồng) hoặc None."""
    try:
        text = _minhchinh_text("535")
        if text:
            m = JACKPOT_PATTERN.search(text)
            if m:
                jp = re.sub(r"[.,]", "", m.group(1))
                if jp.isdigit():
                    return int(jp)
    except Exception as e:
        print(f"⚠️ get_jackpot_535 minhchinh error: {e}")
    try:
        r = requests.get(f"{WORKER_URL}/?type=535",
                        headers={"User-Agent": "Mozilla/5.0"}, timeout=10)
        if r.status_code == 200:
            jp = r.json().get("result", {}).get("jackpot")
            if jp and str(jp).isdigit():
                return int(jp)
    except Exception as e:
        print(f"⚠️ get_jackpot_535 error: {e}")
    return None

def fetch_latest_result(type_key):
    """
    Thứ tự nguồn: minhchinh.com (realtime) → Cloudflare Worker → JSONL.
    JSONL chỉ cập nhật ~00:01 hôm sau nên không dùng được cho kỳ trong ngày.
    """
    cfg = CONFIGS[type_key]
    ky, nums, special = fetch_from_minhchinh(type_key)
    if nums:
        return ky, nums, special
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

def next_ky_str(ky):
    """'00874 (08/09/2026)' -> '00875'.

    Bộ số gợi ý luôn dành cho kỳ SẮP xổ, không phải kỳ vừa công bố.
    Gắn nhầm nhãn kỳ vừa xổ sẽ làm compare/performance chấm điểm sai:
    _ml_pick loại trừ đúng các số của kỳ đó nên điểm bị ép về 0.
    """
    try:
        return str(int(str(ky).split(" ")[0]) + 1).zfill(5)
    except (ValueError, TypeError, AttributeError):
        return str(ky).split(" ")[0] if ky else "?"


# ==========================================
# HANDLERS
# ==========================================
async def run_pick(interaction, type_key, so_luong):
    cfg = CONFIGS[type_key]
    await interaction.response.defer(thinking=True)
    try:
        numbers, specials, days_since, pair_freq = await asyncio.to_thread(get_combined_data, type_key)
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
        await interaction.followup.send(embed=embed, view=await make_button(sms))

        try:
            ngay_str = datetime.now(VN_TZ).strftime("%d/%m/%Y")
            time_str_m = datetime.now(VN_TZ).strftime("%H:%M")
            ky_latest, _, _ = await asyncio.to_thread(fetch_latest_result, type_key)
            ky_save = next_ky_str(ky_latest)
            await asyncio.to_thread(save_suggestions, type_key, ky_save, ngay_str,
                                    time_str_m, all_sets, "manual")
        except Exception as e2:
            print(f"⚠️ save manual suggestions: {e2}")
    except Exception as e:
        await interaction.followup.send(f"❌ Loi: {str(e)}")

async def run_bao535(interaction, bao_key, so_bo):
    info = BAO_535[bao_key]
    so_bo_ngay = max_bo(info["gia"], "535")
    so_bo_max = max_bo_moi_lenh(info["gia"], "535")
    if so_bo > so_bo_max:
        them = (f"\nHạn mức ngày cho phép {so_bo_ngay} bộ — đặt tiếp bằng lệnh khác."
                if so_bo_max < so_bo_ngay else "")
        await interaction.response.send_message(
            f"⚠️ {info['label']} giá {fmt_gia(info['gia'])}/bộ → tối đa "
            f"**{so_bo_max} bộ mỗi lệnh**{them}",
            ephemeral=True)
        return
    await interaction.response.defer(thinking=True)
    try:
        numbers, specials, days_since, pair_freq = await asyncio.to_thread(get_combined_data, "535")
        freq = compute_freq(numbers, 35)
        sp_freq = compute_freq(specials, 12) if specials else {i: 1 for i in range(1, 13)}
        sorted_sp = sorted(sp_freq.items(), key=lambda x: x[1], reverse=True)

        embed = discord.Embed(title=f"🎰 {info['label']} — Lotto 5/35", color=0x9B59B6)
        gh = f"Tối đa {so_bo_max} bộ/lệnh · hạn mức ngày {fmt_gia(GIOI_HAN_NGAY['535'])} = {so_bo_ngay} bộ"
        if so_bo_max < so_bo_ngay:
            gh += "\n💡 Muốn đặt thêm thì gọi lệnh nữa — bot KHÔNG tự cộng dồn chi tiêu trong ngày"
        embed.add_field(name="Giới hạn", value=gh, inline=False)

        last_draw = list(numbers[-5:]) if len(numbers) >= 5 else None
        # seen (set) dùng để chống trùng; bo_da_sinh (list) giữ đúng thứ tự đã hiển thị
        seen, bo_da_sinh, s_parts, lines = set(), [], [], []
        for i in range(so_bo):
            if info["type"] == "bc":
                main_nums = generate_nums(freq, 35, info["n_main"], seen, days_since, pair_freq, last_draw, type_key="535")
                seen.add(tuple(main_nums))
                bo_da_sinh.append(main_nums)
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
                bo_da_sinh.append(main_nums)
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
        print(f"📱 SMS {bao_key} x{so_bo}: {len(sms)} ký tự (~{len(sms)//153 + 1} đoạn)")
        embed.set_footer(text="Bộ số là có tính toán, nhưng không đảm bảo trúng 100%")
        embed.timestamp = datetime.now(timezone.utc)
        await interaction.followup.send(embed=embed, view=await make_button(sms))

        try:
            ngay_str = datetime.now(VN_TZ).strftime("%d/%m/%Y")
            time_str_m = datetime.now(VN_TZ).strftime("%H:%M")
            ky_latest, _, _ = await asyncio.to_thread(fetch_latest_result, "535")
            ky_save = next_ky_str(ky_latest)
            await asyncio.to_thread(save_suggestions, "535", ky_save, ngay_str, time_str_m,
                                    [(nums, None) for nums in bo_da_sinh],
                                    f"manual_bao535_{bao_key}")
        except Exception as e2:
            print(f"⚠️ save bao535 suggestions: {e2}")
    except Exception as e:
        await interaction.followup.send(f"❌ Loi: {str(e)}")

async def run_bao645655(interaction, type_key, bao_key, so_bo):
    info = BAO_645_655[bao_key]
    gia = info[f"gia_{type_key}"]
    cfg = CONFIGS[type_key]
    so_bo_ngay = max_bo(gia, type_key)
    so_bo_max = max_bo_moi_lenh(gia, type_key)
    if so_bo > so_bo_max:
        them = (f"\nHạn mức ngày cho phép {so_bo_ngay} bộ — đặt tiếp bằng lệnh khác."
                if so_bo_max < so_bo_ngay else "")
        await interaction.response.send_message(
            f"⚠️ {info['label']} giá {fmt_gia(gia)}/bộ → tối đa "
            f"**{so_bo_max} bộ mỗi lệnh**{them}",
            ephemeral=True)
        return
    await interaction.response.defer(thinking=True)
    try:
        numbers, _, days_since, pair_freq = await asyncio.to_thread(get_combined_data, type_key)
        freq = compute_freq(numbers, cfg["n"])

        embed = discord.Embed(title=f"🎰 {info['label']} — {cfg['label']}", color=0x9B59B6)
        gh = f"Tối đa {so_bo_max} bộ/lệnh · hạn mức ngày {fmt_gia(GIOI_HAN_NGAY[type_key])} = {so_bo_ngay} bộ"
        if so_bo_max < so_bo_ngay:
            gh += "\n💡 Muốn đặt thêm thì gọi lệnh nữa — bot KHÔNG tự cộng dồn chi tiêu trong ngày"
        embed.add_field(name="Giới hạn", value=gh, inline=False)

        k = cfg["k"]
        last_draw = list(numbers[-k:]) if len(numbers) >= k else None
        # seen (set) dùng để chống trùng; bo_da_sinh (list) giữ đúng thứ tự đã hiển thị
        seen, bo_da_sinh, s_parts, lines = set(), [], [], []
        for i in range(so_bo):
            nums = generate_nums(freq, cfg["n"], info["n"], seen, days_since, pair_freq, last_draw, type_key=type_key)
            seen.add(tuple(nums))
            bo_da_sinh.append(nums)
            s_parts.append("S " + " ".join(f"{n:02d}" for n in nums))
            disp = " ".join(f"`{n:02d}`" for n in nums)
            lines.append(f"**Bộ {i+1}:** {disp}")

        tong = so_bo * gia
        add_fields_chunked(embed, lines)
        embed.add_field(name="Tổng tiền", value=f"{fmt_gia(tong)} / {fmt_gia(GIOI_HAN_NGAY[type_key])} hạn mức ngày", inline=False)
        sms = f"{cfg['sms_prefix']} K1 {bao_key.upper()} " + " ".join(s_parts)
        embed.set_footer(text="Bộ số là có tính toán, nhưng không đảm bảo trúng 100%")
        embed.timestamp = datetime.now(timezone.utc)
        await interaction.followup.send(embed=embed, view=await make_button(sms))

        try:
            ngay_str = datetime.now(VN_TZ).strftime("%d/%m/%Y")
            time_str_m = datetime.now(VN_TZ).strftime("%H:%M")
            ky_latest, _, _ = await asyncio.to_thread(fetch_latest_result, type_key)
            ky_save = next_ky_str(ky_latest)
            await asyncio.to_thread(save_suggestions, type_key, ky_save, ngay_str, time_str_m,
                                    [(nums, None) for nums in bo_da_sinh],
                                    f"manual_bao{type_key}_{bao_key}")
        except Exception as e2:
            print(f"⚠️ save bao suggestions: {e2}")
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

    ky, numbers, special = None, None, None
    today_iso = datetime.now(VN_TZ).strftime("%Y-%m-%d")

    for attempt in range(6):
        ky, numbers, special = await asyncio.to_thread(fetch_latest_result, type_key)
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

    await asyncio.to_thread(save_result, type_key, ngay, ky, numbers, special)

    # So sánh với TẤT CẢ gợi ý đã lưu cho kỳ này (mọi nguồn)
    compare_result = await asyncio.to_thread(compare_with_suggestions, type_key, ky, numbers, special)

    # Tính performance từ chính các suggestions của kỳ này (label đã đúng nghĩa)
    await asyncio.to_thread(track_performance, type_key, ky, ngay, numbers)

    embed = discord.Embed(title=f"🎰 Kết quả {cfg['label']} — {ngay}", color=0xE74C3C)
    embed.add_field(name="Kỳ", value=f"**{ky}**", inline=True)
    embed.add_field(name="Kết quả", value=" ".join(f"`{n:02d}`" for n in numbers), inline=False)
    if special:
        embed.add_field(name="Đặc biệt" if type_key == "535" else "Power", value=f"`{special:02d}`", inline=True)

    # Thêm phần so sánh nếu có — hiển thị TẤT CẢ nguồn (scheduler, manual, bao...)
    SOURCE_LABELS = {
        "scheduler": "🤖 Gợi ý tự động",
        "manual": "👤 Gợi ý thủ công (/535, /645, /655)",
    }
    # Giới hạn Discord: field ≤ 1024 ký tự, TOÀN embed ≤ 6000, ≤ 25 field.
    # 535 có tới 17 nguồn khả dĩ (scheduler + manual + 15 loại bao); nếu đổ hết
    # ra thì từ 6 nguồn là vượt 6000 và cả bài báo kết quả ném HTTPException.
    if compare_result:
        _, by_source = compare_result
        MAX_EMBED, MAX_FIELD, MAX_DONG = 5200, 1000, 8
        da_dung = len(embed.title or "") + sum(
            len(f.name or "") + len(f.value or "") for f in embed.fields)
        nguon_bo_qua = 0

        for source, items in sorted(by_source.items()):
            label = SOURCE_LABELS.get(source, f"🎯 {source}")
            tong_trung = sum(len(matched) for _, matched in items)
            lines = []
            for nums, matched in items[:MAX_DONG]:
                nums_disp = " ".join(f"`{n:02d}`" for n in nums)
                if matched:
                    matched_disp = " ".join(f"`{n:02d}`" for n in matched)
                    lines.append(f"✅ {nums_disp} → trúng **{len(matched)}**: {matched_disp}")
                else:
                    lines.append(f"❌ {nums_disp} → 0 số")
            if len(items) > MAX_DONG:
                lines.append(f"… còn {len(items) - MAX_DONG} bộ nữa")
            lines.append(f"**Trung bình {tong_trung / len(items):.2f} số/bộ**")

            name = f"📊 {label} ({len(items)} bộ)"
            value = "\n".join(lines)[:MAX_FIELD]
            if da_dung + len(name) + len(value) > MAX_EMBED or len(embed.fields) >= 20:
                nguon_bo_qua += 1
                continue
            da_dung += len(name) + len(value)
            embed.add_field(name=name, value=value, inline=False)

        if nguon_bo_qua:
            embed.add_field(
                name="…",
                value=f"Còn {nguon_bo_qua} nguồn gợi ý nữa, không hiển thị hết "
                      f"(Discord giới hạn 6000 ký tự mỗi embed)",
                inline=False)

    embed.timestamp = datetime.now(timezone.utc)
    await channel.send(embed=embed)

    # Alert kỳ Chia giải Độc Đắc (chỉ 535): jackpot > 12 tỷ → kỳ 21h ngày mai chia giải
    if type_key == "535":
        jackpot = await asyncio.to_thread(get_jackpot_535)
        if jackpot and jackpot > 12_000_000_000:
            jp_ty = jackpot / 1_000_000_000
            alert = discord.Embed(
                title="🔥 SẮP CÓ KỲ CHIA GIẢI ĐỘC ĐẮC!",
                description=(
                    f"Jackpot Lotto 5/35 hiện tại: **{jp_ty:.2f} tỷ** (vượt mốc 12 tỷ)\n\n"
                    f"Nếu kỳ tối nay không ai trúng Độc Đắc, **kỳ 21:00 ngày mai** "
                    f"sẽ là kỳ **CHIA GIẢI** — toàn bộ jackpot chia cho giải Nhất → Năm.\n"
                    f"💡 Cùng xác suất trúng nhưng giá trị giải cao gấp nhiều lần — "
                    f"nếu định đánh thì đây là kỳ đáng đánh nhất."
                ),
                color=0xF39C12
            )
            alert.timestamp = datetime.now(timezone.utc)
            await channel.send(embed=alert)

    # Gợi ý 5 bộ số kỳ tiếp
    await asyncio.sleep(2)
    all_nums, all_sp, days_since, pair_freq = await asyncio.to_thread(get_combined_data, type_key)
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
    await channel.send(embed=embed2, view=await make_button(sms))

    # Lưu gợi ý vào Sheets để so sánh kỳ sau
    # QUAN TRỌNG: all_sets là gợi ý cho KỲ TIẾP THEO, không phải kỳ vừa công bố (ky)
    # Tính kỳ tiếp theo = ky + 1 (giữ định dạng zero-padded)
    time_str = datetime.now(VN_TZ).strftime("%H:%M")
    await asyncio.to_thread(save_suggestions, type_key, next_ky_str(ky),
                            ngay, time_str, all_sets, "scheduler")

_da_chay = set()  # {(ngày, type_key, giờ, phút)} — chống chạy lại cùng một lịch

async def scheduler():
    """Khớp theo cửa sổ 10 phút thay vì đúng 1 phút.

    Cách cũ so h == gio and m == phut: chỉ cần vòng lặp trễ quá 60s (event loop
    bị chặn, hoặc bot restart ngay phút đó) là lỡ hẳn kỳ. _da_chay đảm bảo mỗi
    lịch chỉ chạy 1 lần/ngày kể cả khi có nhiều scheduler cùng sống.
    """
    print("⏰ Scheduler started")
    while True:
        now = datetime.now(VN_TZ)
        hom_nay = now.date().isoformat()
        _da_chay.difference_update([k for k in _da_chay if k[0] != hom_nay])

        for type_key, lich in LICH_XO.items():
            for (ngay_xo, gio, phut) in lich:
                if now.weekday() != ngay_xo:
                    continue
                key = (hom_nay, type_key, gio, phut)
                if key in _da_chay:
                    continue
                hen = now.replace(hour=gio, minute=phut, second=0, microsecond=0)
                tre = (now - hen).total_seconds()
                if 0 <= tre <= 600:  # trong vòng 10 phút sau giờ hẹn
                    _da_chay.add(key)
                    print(f"⏰ Trigger {type_key} ({gio:02d}:{phut:02d}, trễ {int(tre)}s)")
                    asyncio.create_task(post_result(type_key))
        await asyncio.sleep(30)

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

# Sinh choice từ chính bảng giá thay vì gõ tay — nhãn "max N bộ" hardcode đã lệch
# một lần khi hạn mức 535 đổi từ 1tr lên 2,5tr.
bao535_choices = [
    app_commands.Choice(name=nhan_bao(v["label"], v["gia"], "535"), value=k)
    for k, v in BAO_535.items()
]
MAX_BO_535 = max(max_bo_moi_lenh(v["gia"], "535") for v in BAO_535.values())
@tree.command(name="bao535", description="Bao số Lotto 5/35 kèm SMS")
@app_commands.describe(loai="Chọn loại bao số", so_bo="Số bộ muốn mua")
@app_commands.choices(loai=bao535_choices)
async def cmd_bao535(interaction, loai: app_commands.Choice[str],
                     so_bo: app_commands.Range[int, 1, MAX_BO_535] = 1):
    await run_bao535(interaction, loai.value, so_bo)

bao645_choices = [
    app_commands.Choice(name=nhan_bao(v["label"], v["gia_645"], "645"), value=k)
    for k, v in BAO_645_655.items()
]
MAX_BO_645 = max(max_bo_moi_lenh(v["gia_645"], "645") for v in BAO_645_655.values())
@tree.command(name="bao645", description="Bao số Mega 6/45 kèm SMS")
@app_commands.describe(loai="Chọn loại bao số", so_bo="Số bộ muốn mua")
@app_commands.choices(loai=bao645_choices)
async def cmd_bao645(interaction, loai: app_commands.Choice[str],
                     so_bo: app_commands.Range[int, 1, MAX_BO_645] = 1):
    await run_bao645655(interaction, "645", loai.value, so_bo)

bao655_choices = [
    app_commands.Choice(name=nhan_bao(v["label"], v["gia_655"], "655"), value=k)
    for k, v in BAO_645_655.items()
]
MAX_BO_655 = max(max_bo_moi_lenh(v["gia_655"], "655") for v in BAO_645_655.values())
@tree.command(name="bao655", description="Bao số Power 6/55 kèm SMS")
@app_commands.describe(loai="Chọn loại bao số", so_bo="Số bộ muốn mua")
@app_commands.choices(loai=bao655_choices)
async def cmd_bao655(interaction, loai: app_commands.Choice[str],
                     so_bo: app_commands.Range[int, 1, MAX_BO_655] = 1):
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

_khoi_dong_xong = False

@client.event
async def on_ready():
    """on_ready fire lại sau MỖI lần reconnect. Không chặn thì mỗi lần reconnect
    lại tạo thêm 1 scheduler → báo kết quả trùng, và tree.sync() dễ dính rate limit."""
    global _khoi_dong_xong
    print(f"✅ Bot da online: {client.user}")
    if _khoi_dong_xong:
        print("↩️ Reconnect — scheduler đã chạy rồi, bỏ qua")
        return
    _khoi_dong_xong = True
    await tree.sync()
    print("Commands: /535 /645 /655 /bao535 /bao645 /bao655")
    asyncio.create_task(scheduler())

def kiem_tra_env():
    """Báo lỗi rõ ràng thay vì để discord.py ném 'Improper token' khó hiểu."""
    thieu = []
    if not TOKEN:
        thieu.append("DISCORD_TOKEN")
    if not DISCORD_CHANNEL_ID:
        thieu.append("DISCORD_CHANNEL_ID")
    if thieu:
        raise SystemExit(f"❌ Thiếu biến môi trường: {', '.join(thieu)}")
    for ten in ("GOOGLE_CREDENTIALS_B64", "GOOGLE_SHEET_ID"):
        if not os.environ.get(ten):
            print(f"⚠️ Thiếu {ten} — bot vẫn chạy nhưng KHÔNG lưu/đọc được Google Sheets")

kiem_tra_env()
client.run(TOKEN)
