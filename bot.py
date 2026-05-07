import discord
import json
import asyncio
import requests
import random
import re
import os
import urllib.parse
from discord import app_commands
from datetime import datetime, date
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
    "bc4": {"label": "BC4 – Bao 4 so chinh",    "gia": 310000, "type": "bc", "n_main": 4},
    "bc6": {"label": "BC6 – Bao 6 so chinh",    "gia": 60000,  "type": "bc", "n_main": 6},
    "bc7": {"label": "BC7 – Bao 7 so chinh",    "gia": 210000, "type": "bc", "n_main": 7},
    "bc8": {"label": "BC8 – Bao 8 so chinh",    "gia": 560000, "type": "bc", "n_main": 8},
    "bd2": {"label": "BD2 – Bao 2 so dac biet", "gia": 20000,  "type": "bd", "n_sp": 2},
    "bd3": {"label": "BD3 – Bao 3 so dac biet", "gia": 30000,  "type": "bd", "n_sp": 3},
    "bd4": {"label": "BD4 – Bao 4 so dac biet", "gia": 40000,  "type": "bd", "n_sp": 4},
    "bd5": {"label": "BD5 – Bao 5 so dac biet", "gia": 50000,  "type": "bd", "n_sp": 5},
    "bd6": {"label": "BD6 – Bao 6 so dac biet", "gia": 60000,  "type": "bd", "n_sp": 6},
    "bd7": {"label": "BD7 – Bao 7 so dac biet", "gia": 70000,  "type": "bd", "n_sp": 7},
    "bd8": {"label": "BD8 – Bao 8 so dac biet", "gia": 80000,  "type": "bd", "n_sp": 8},
    "bd9": {"label": "BD9 – Bao 9 so dac biet", "gia": 90000,  "type": "bd", "n_sp": 9},
    "bd10":{"label": "BD10 – Bao 10 so dac biet","gia": 100000, "type": "bd", "n_sp": 10},
    "bd11":{"label": "BD11 – Bao 11 so dac biet","gia": 110000, "type": "bd", "n_sp": 11},
    "bd12":{"label": "BD12 – Bao 12 so dac biet","gia": 120000, "type": "bd", "n_sp": 12},
}

BAO_645_655 = {
    "b5":  {"label": "B5  – Bao 5 so",  "gia_645": 400000,  "gia_655": 500000,  "n": 5},
    "b7":  {"label": "B7  – Bao 7 so",  "gia_645": 70000,   "gia_655": 70000,   "n": 7},
    "b8":  {"label": "B8  – Bao 8 so",  "gia_645": 280000,  "gia_655": 280000,  "n": 8},
    "b9":  {"label": "B9  – Bao 9 so",  "gia_645": 840000,  "gia_655": 840000,  "n": 9},
    "b10": {"label": "B10 – Bao 10 so", "gia_645": 2100000, "gia_655": 2100000, "n": 10},
}

LICH_XO = {
    "535": [(0, 21, 5), (2, 21, 5), (4, 21, 5)],
    "645": [(2, 18, 5), (4, 18, 5), (6, 18, 5)],
    "655": [(1, 18, 5), (3, 18, 5), (5, 18, 5)],
}

intents = discord.Intents.default()
client = discord.Client(intents=intents)
tree = app_commands.CommandTree(client)
_cache = {}

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
    Dùng Google Sheets làm primary nếu có, fallback sang GitHub
    """
    cfg = CONFIGS[type_key]

    # Lấy data từ Google Sheets trước
    sheets_nums, sheets_sp, _ = load_from_sheets(type_key)

    # Lấy data từ GitHub JSONL
    jsonl_text, jsonl_nums, jsonl_sp = fetch_jsonl(cfg)

    # Merge: ưu tiên Sheets (mới hơn), bổ sung từ JSONL
    if sheets_nums:
        # Tính days_since từ Sheets (có ngày chính xác)
        days_since = compute_days_since_from_sheets(type_key)
        # Kết hợp số từ cả 2 nguồn
        all_nums = jsonl_nums + sheets_nums
        all_sp   = jsonl_sp + sheets_sp
        print(f"✅ {type_key}: {len(jsonl_nums)//cfg['k']} ky JSONL + {len(sheets_nums)//cfg['k']} ky Sheets")
    else:
        # Fallback: chỉ dùng JSONL
        all_nums = jsonl_nums
        all_sp   = jsonl_sp
        days_since = compute_days_since(jsonl_text, cfg) if jsonl_text else {}
        print(f"⚠️ {type_key}: Chi dung JSONL ({len(jsonl_nums)//cfg['k']} ky)")

    return all_nums, all_sp, days_since

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

def generate_nums(freq, n_total, n_pick, exclude_sets=None, days_since=None):
    """40% hot + 30% due (lâu chưa ra) + 30% cold"""
    avg = sum(freq.values()) / n_total
    sorted_f = sorted(freq.items(), key=lambda x: x[1], reverse=True)
    hot   = [n for n, _ in sorted_f[:15]]
    hot_w = [freq[n] for n in hot]
    cold   = [n for n, _ in sorted_f[-15:]]
    cold_w = [max(1, avg * 2 - freq[n]) for n in cold]
    if days_since:
        due_sorted = sorted(days_since.items(), key=lambda x: x[1], reverse=True)
        due   = [n for n, _ in due_sorted[:15]]
        due_w = [days_since[n] for n in due]
    else:
        due, due_w = cold, cold_w

    n_hot  = max(1, round(n_pick * 0.4))
    n_due  = max(1, round(n_pick * 0.3))
    n_cold = n_pick - n_hot - n_due

    for _ in range(20):
        picked = set()
        picked.update(weighted_pick(hot, hot_w, n_hot))
        picked.update(weighted_pick(due, due_w, n_due, exclude=picked))
        picked.update(weighted_pick(cold, cold_w, n_cold, exclude=picked))
        while len(picked) < n_pick:
            picked.add(random.randint(1, n_total))
        result = tuple(sorted(picked))
        if not exclude_sets or result not in exclude_sets:
            return list(result)
    return list(sorted(picked))

def fmt_gia(gia):
    return f"{gia:,}d".replace(",", ".")

def max_bo(gia, type_key):
    return max(1, GIOI_HAN_NGAY[type_key] // gia)

def make_sms_link(sms_text):
    return f"https://vietlott-sms.netlify.app/?body={urllib.parse.quote(sms_text)}"

def make_button(sms_text):
    view = discord.ui.View()
    view.add_item(discord.ui.Button(
        label="📱 Mo SMS → gui 9969",
        url=make_sms_link(sms_text),
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
            print(f"⚠️ Ky {ky} da ton tai, bo qua!")
            return False
        row = [ngay, ky] + [str(n) for n in numbers]
        if special: row.append(str(special))
        ws.append_row(row)
        return True
    except Exception as e:
        print(f"❌ Loi luu Sheets: {e}")
        return False

def fetch_latest_result(type_key):
    cfg = CONFIGS[type_key]
    try:
        r = requests.get(cfg["jsonl_url"], headers={"User-Agent": "Mozilla/5.0"}, timeout=30)
        if r.status_code != 200: return None, None, None
        lines = [l.strip() for l in r.text.strip().split("\n") if l.strip()]
        if not lines: return None, None, None
        data = json.loads(lines[-1])
        ky   = str(data.get("id", "?")).zfill(5)
        d    = data.get("date", "")
        if d and len(d) == 10:
            y, m, dd = d.split("-")
            d = f"{dd}/{m}/{y}"
        nums, special = parse_jsonl_line(lines[-1], cfg)
        return f"{ky} ({d})", nums, special
    except Exception as e:
        print(f"❌ Loi fetch latest {type_key}: {e}")
    return None, None, None

# ==========================================
# HANDLERS
# ==========================================
async def run_pick(interaction, type_key, so_luong):
    cfg = CONFIGS[type_key]
    await interaction.response.defer(thinking=True)
    try:
        numbers, specials, days_since = get_combined_data(type_key)
        if len(numbers) < cfg["k"] * 5:
            await interaction.followup.send("⚠️ Khong lay duoc du lieu!")
            return
        freq = compute_freq(numbers, cfg["n"])
        sp_freq = compute_freq(specials, cfg.get("special_n", 55)) if specials else None
        draws = len(numbers) // cfg["k"]

        embed = discord.Embed(title=f"🎰 {cfg['label']} — {so_luong} bo so", color=0x1D9E75)
        embed.add_field(name="Phan tich tu", value=f"{draws} ky lich su", inline=True)

        all_sets, seen = [], set()
        for i in range(so_luong):
            nums = generate_nums(freq, cfg["n"], cfg["k"], seen, days_since)
            seen.add(tuple(nums))
            sp = None
            if cfg.get("has_special") and sp_freq:
                sp_sorted = sorted(sp_freq.items(), key=lambda x: x[1], reverse=True)
                sp = weighted_pick([n for n, _ in sp_sorted], [c for _, c in sp_sorted], 1)[0]
            all_sets.append((nums, sp))
            disp = " ".join(f"`{n:02d}`" for n in nums)
            extra = f"  |  DB: `{sp:02d}`" if sp and type_key == "535" else (f"  |  Power: `{sp:02d}`" if sp else "")
            embed.add_field(name=f"Bo {i+1}", value=disp + extra, inline=False)

        tong = so_luong * 10000
        embed.add_field(name="Tong tien", value=fmt_gia(tong), inline=False)
        sms = sms_basic_535(all_sets) if type_key == "535" else sms_basic_645_655(cfg["sms_prefix"], all_sets)
        embed.set_footer(text="Chi de vui — khong dam bao trung thuong!")
        embed.timestamp = datetime.utcnow()
        await interaction.followup.send(embed=embed, view=make_button(sms))
    except Exception as e:
        await interaction.followup.send(f"❌ Loi: {str(e)}")

async def run_bao535(interaction, bao_key, so_bo):
    info = BAO_535[bao_key]
    so_bo_max = max_bo(info["gia"], "535")
    if so_bo > so_bo_max:
        await interaction.response.send_message(
            f"⚠️ {info['label']} gia {fmt_gia(info['gia'])}/bo → toi da **{so_bo_max} bo** ({fmt_gia(GIOI_HAN_NGAY['535'])}/ngay)",
            ephemeral=True)
        return
    await interaction.response.defer(thinking=True)
    try:
        numbers, specials, days_since = get_combined_data("535")
        freq = compute_freq(numbers, 35)
        sp_freq = compute_freq(specials, 12) if specials else {i: 1 for i in range(1, 13)}
        sorted_sp = sorted(sp_freq.items(), key=lambda x: x[1], reverse=True)

        embed = discord.Embed(title=f"🎰 {info['label']} — Lotto 5/35", color=0x9B59B6)
        embed.add_field(name="Gioi han ngay", value=f"Toi da {so_bo_max} bo ({fmt_gia(GIOI_HAN_NGAY['535'])} / {fmt_gia(info['gia'])})", inline=False)

        seen, s_parts = set(), []
        for i in range(so_bo):
            if info["type"] == "bc":
                main_nums = generate_nums(freq, 35, info["n_main"], seen, days_since)
                seen.add(tuple(main_nums))
                sp_pool = [n for n, _ in sorted_sp]
                sp_w = [c for _, c in sorted_sp]
                special = weighted_pick(sp_pool, sp_w, 1)[0]
                main_str = " ".join(f"{n:02d}" for n in main_nums[:-1])
                last = f"{main_nums[-1]:02d}-{special:02d}"
                s_parts.append(f"S {main_str} {last}")
                embed.add_field(name=f"Bo {i+1}", value=f"{' '.join(f'`{n:02d}`' for n in main_nums)}  |  DB: `{special:02d}`", inline=False)
            else:
                main_nums = generate_nums(freq, 35, 5, seen, days_since)
                seen.add(tuple(main_nums))
                specials_picked = [n for n, _ in sorted_sp[:info["n_sp"]]]
                main_str = " ".join(f"{n:02d}" for n in main_nums)
                sp_str = f"{specials_picked[0]:02d}" + (" " + " ".join(f"{n:02d}" for n in specials_picked[1:]) if len(specials_picked) > 1 else "")
                s_parts.append(f"S {main_str}-{sp_str}")
                embed.add_field(name=f"Bo {i+1}", value=f"{' '.join(f'`{n:02d}`' for n in main_nums)}  |  DB: {' '.join(f'`{n:02d}`' for n in specials_picked)}", inline=False)

        tong = so_bo * info["gia"]
        embed.add_field(name="Tong tien", value=f"{fmt_gia(tong)} / {fmt_gia(GIOI_HAN_NGAY['535'])} han muc ngay", inline=False)
        sms = f"535 K1 {bao_key.upper()} " + " ".join(s_parts)
        embed.set_footer(text="Chi de vui — khong dam bao trung thuong!")
        embed.timestamp = datetime.utcnow()
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
            f"⚠️ {info['label']} gia {fmt_gia(gia)}/bo → toi da **{so_bo_max} bo** ({fmt_gia(GIOI_HAN_NGAY[type_key])}/ngay)",
            ephemeral=True)
        return
    await interaction.response.defer(thinking=True)
    try:
        numbers, _, days_since = get_combined_data(type_key)
        freq = compute_freq(numbers, cfg["n"])

        embed = discord.Embed(title=f"🎰 {info['label']} — {cfg['label']}", color=0x9B59B6)
        embed.add_field(name="Gioi han ngay", value=f"Toi da {so_bo_max} bo ({fmt_gia(GIOI_HAN_NGAY[type_key])} / {fmt_gia(gia)})", inline=False)

        seen, s_parts = set(), []
        for i in range(so_bo):
            nums = generate_nums(freq, cfg["n"], info["n"], seen, days_since)
            seen.add(tuple(nums))
            s_parts.append("S " + " ".join(f"{n:02d}" for n in nums))
            embed.add_field(name=f"Bo {i+1}", value=" ".join(f"`{n:02d}`" for n in nums), inline=False)

        tong = so_bo * gia
        embed.add_field(name="Tong tien", value=f"{fmt_gia(tong)} / {fmt_gia(GIOI_HAN_NGAY[type_key])} han muc ngay", inline=False)
        sms = f"{cfg['sms_prefix']} K1 {bao_key.upper()} " + " ".join(s_parts)
        embed.set_footer(text="Chi de vui — khong dam bao trung thuong!")
        embed.timestamp = datetime.utcnow()
        await interaction.followup.send(embed=embed, view=make_button(sms))
    except Exception as e:
        await interaction.followup.send(f"❌ Loi: {str(e)}")

# ==========================================
# TỰ ĐỘNG BÁO KẾT QUẢ SAU GIỜ XỔ
# ==========================================
async def post_result(type_key):
    channel = client.get_channel(DISCORD_CHANNEL_ID)
    if not channel: return
    cfg = CONFIGS[type_key]
    ngay = datetime.now(VN_TZ).strftime("%d/%m/%Y")
    await channel.send(f"⏳ Dang lay ket qua **{cfg['label']}**...")

    _cache.pop(type_key, None)  # Xóa cache để fetch mới
    _cache.pop(f"text_{type_key}", None)

    ky, numbers, special = None, None, None
    for _ in range(5):
        ky, numbers, special = fetch_latest_result(type_key)
        if numbers: break
        await asyncio.sleep(120)

    if not numbers:
        await channel.send(f"⚠️ Khong lay duoc ket qua {cfg['label']}!")
        return

    save_result(type_key, ngay, ky, numbers, special)

    embed = discord.Embed(title=f"🎰 Ket qua {cfg['label']} — {ngay}", color=0xE74C3C)
    embed.add_field(name="Ky", value=f"**{ky}**", inline=True)
    embed.add_field(name="Ket qua", value=" ".join(f"`{n:02d}`" for n in numbers), inline=False)
    if special:
        embed.add_field(name="Dac biet" if type_key == "535" else "Power", value=f"`{special:02d}`", inline=True)
    embed.timestamp = datetime.utcnow()
    await channel.send(embed=embed)

    # Gợi ý 5 bộ số kỳ tiếp
    await asyncio.sleep(2)
    all_nums, all_sp, days_since = get_combined_data(type_key)
    freq = compute_freq(all_nums, cfg["n"])
    sp_freq = compute_freq(all_sp, cfg.get("special_n", 55)) if all_sp else None

    embed2 = discord.Embed(title=f"🎯 Goi y 5 bo so ky tiep — {cfg['label']}", color=0x1D9E75)
    all_sets, seen = [], set()
    for i in range(5):
        nums = generate_nums(freq, cfg["n"], cfg["k"], seen, days_since)
        seen.add(tuple(nums))
        sp = None
        if cfg.get("has_special") and sp_freq:
            sp_sorted = sorted(sp_freq.items(), key=lambda x: x[1], reverse=True)
            sp = weighted_pick([n for n, _ in sp_sorted], [c for _, c in sp_sorted], 1)[0]
        all_sets.append((nums, sp))
        disp = " ".join(f"`{n:02d}`" for n in nums)
        extra = f"  |  DB: `{sp:02d}`" if sp and type_key == "535" else (f"  |  Power: `{sp:02d}`" if sp else "")
        embed2.add_field(name=f"Bo {i+1}", value=disp + extra, inline=False)

    sms = sms_basic_535(all_sets) if type_key == "535" else sms_basic_645_655(cfg["sms_prefix"], all_sets)
    embed2.set_footer(text="Chi de vui — khong dam bao trung thuong!")
    embed2.timestamp = datetime.utcnow()
    await channel.send(embed=embed2, view=make_button(sms))

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
@tree.command(name="535", description="Go y bo so Lotto 5/35 kem SMS")
@app_commands.describe(so_luong="So bo muon mua (1-10)")
async def cmd_535(interaction, so_luong: app_commands.Range[int, 1, 10] = 1):
    await run_pick(interaction, "535", so_luong)

@tree.command(name="645", description="Go y bo so Mega 6/45 kem SMS")
@app_commands.describe(so_luong="So bo muon mua (1-10)")
async def cmd_645(interaction, so_luong: app_commands.Range[int, 1, 10] = 1):
    await run_pick(interaction, "645", so_luong)

@tree.command(name="655", description="Go y bo so Power 6/55 kem SMS")
@app_commands.describe(so_luong="So bo muon mua (1-10)")
async def cmd_655(interaction, so_luong: app_commands.Range[int, 1, 10] = 1):
    await run_pick(interaction, "655", so_luong)

# Bao 535
bao535_choices = [
    app_commands.Choice(name="BC4 – Bao 4 so chinh (310.000d) – max 3 bo",    value="bc4"),
    app_commands.Choice(name="BC6 – Bao 6 so chinh (60.000d) – max 16 bo",    value="bc6"),
    app_commands.Choice(name="BC7 – Bao 7 so chinh (210.000d) – max 4 bo",    value="bc7"),
    app_commands.Choice(name="BC8 – Bao 8 so chinh (560.000d) – max 1 bo",    value="bc8"),
    app_commands.Choice(name="BD2 – Bao 2 so dac biet (20.000d) – max 50 bo", value="bd2"),
    app_commands.Choice(name="BD3 – Bao 3 so dac biet (30.000d) – max 33 bo", value="bd3"),
    app_commands.Choice(name="BD4 – Bao 4 so dac biet (40.000d) – max 25 bo", value="bd4"),
    app_commands.Choice(name="BD5 – Bao 5 so dac biet (50.000d) – max 20 bo", value="bd5"),
    app_commands.Choice(name="BD6 – Bao 6 so dac biet (60.000d) – max 16 bo", value="bd6"),
    app_commands.Choice(name="BD7 – Bao 7 so dac biet (70.000d) – max 14 bo", value="bd7"),
    app_commands.Choice(name="BD8 – Bao 8 so dac biet (80.000d) – max 12 bo", value="bd8"),
    app_commands.Choice(name="BD9 – Bao 9 so dac biet (90.000d) – max 11 bo", value="bd9"),
    app_commands.Choice(name="BD10 – Bao 10 so dac biet (100.000d) – max 10 bo", value="bd10"),
    app_commands.Choice(name="BD11 – Bao 11 so dac biet (110.000d) – max 9 bo",  value="bd11"),
    app_commands.Choice(name="BD12 – Bao 12 so dac biet (120.000d) – max 8 bo",  value="bd12"),
]
@tree.command(name="bao535", description="Bao so Lotto 5/35 kem SMS")
@app_commands.describe(loai="Chon loai bao so", so_bo="So bo muon mua")
@app_commands.choices(loai=bao535_choices)
async def cmd_bao535(interaction, loai: app_commands.Choice[str], so_bo: app_commands.Range[int, 1, 50] = 1):
    await run_bao535(interaction, loai.value, so_bo)

bao645_choices = [
    app_commands.Choice(name="B5  – Bao 5 so (400.000d) – max 5 bo",    value="b5"),
    app_commands.Choice(name="B7  – Bao 7 so (70.000d) – max 30 bo",    value="b7"),
    app_commands.Choice(name="B8  – Bao 8 so (280.000d) – max 7 bo",    value="b8"),
    app_commands.Choice(name="B9  – Bao 9 so (840.000d) – max 2 bo",    value="b9"),
    app_commands.Choice(name="B10 – Bao 10 so (2.100.000d) – max 1 bo", value="b10"),
]
@tree.command(name="bao645", description="Bao so Mega 6/45 kem SMS")
@app_commands.describe(loai="Chon loai bao so", so_bo="So bo muon mua")
@app_commands.choices(loai=bao645_choices)
async def cmd_bao645(interaction, loai: app_commands.Choice[str], so_bo: app_commands.Range[int, 1, 30] = 1):
    await run_bao645655(interaction, "645", loai.value, so_bo)

bao655_choices = [
    app_commands.Choice(name="B5  – Bao 5 so (500.000d) – max 4 bo",    value="b5"),
    app_commands.Choice(name="B7  – Bao 7 so (70.000d) – max 30 bo",    value="b7"),
    app_commands.Choice(name="B8  – Bao 8 so (280.000d) – max 7 bo",    value="b8"),
    app_commands.Choice(name="B9  – Bao 9 so (840.000d) – max 2 bo",    value="b9"),
    app_commands.Choice(name="B10 – Bao 10 so (2.100.000d) – max 1 bo", value="b10"),
]
@tree.command(name="bao655", description="Bao so Power 6/55 kem SMS")
@app_commands.describe(loai="Chon loai bao so", so_bo="So bo muon mua")
@app_commands.choices(loai=bao655_choices)
async def cmd_bao655(interaction, loai: app_commands.Choice[str], so_bo: app_commands.Range[int, 1, 30] = 1):
    await run_bao645655(interaction, "655", loai.value, so_bo)

# ==========================================
# KHỞI ĐỘNG
# ==========================================
@client.event
async def on_ready():
    await tree.sync()
    print(f"✅ Bot da online: {client.user}")
    print("Commands: /535 /645 /655 /bao535 /bao645 /bao655")
    asyncio.create_task(scheduler())

client.run(TOKEN)
