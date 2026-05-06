import discord
from discord import app_commands
import requests
from bs4 import BeautifulSoup
import random
import re
import os
import urllib.parse
from datetime import datetime

TOKEN = os.environ.get("DISCORD_TOKEN", "")

CONFIGS = {
    "535": {"n": 35, "k": 5, "has_special": True, "special_n": 12, "label": "Lotto 5/35",
            "sms_prefix": "535", "url": "https://www.lotto-8.com/Vietnam/listltoVM35.asp", "pages": 5},
    "645": {"n": 45, "k": 6, "has_special": False, "label": "Mega 6/45",
            "sms_prefix": "645", "url": "https://www.lotto-8.com/Vietnam/listltoVM45.asp", "pages": 5},
    "655": {"n": 55, "k": 6, "has_special": True, "special_n": 10, "label": "Power 6/55",
            "sms_prefix": "655", "url": "https://www.lotto-8.com/Vietnam/listltoVM55.asp", "pages": 5},
}

GIOI_HAN_NGAY = {"535": 1_000_000, "645": 2_100_000, "655": 2_100_000}

# Bao 535
BAO_535 = {
    "bc4": {"label": "BC4 – Bao 4 số chính",    "gia": 310000, "type": "bc", "n_main": 4,  "n_sp": 1},
    "bc6": {"label": "BC6 – Bao 6 số chính",    "gia": 60000,  "type": "bc", "n_main": 6,  "n_sp": 1},
    "bc7": {"label": "BC7 – Bao 7 số chính",    "gia": 210000, "type": "bc", "n_main": 7,  "n_sp": 1},
    "bc8": {"label": "BC8 – Bao 8 số chính",    "gia": 560000, "type": "bc", "n_main": 8,  "n_sp": 1},
    "bd2": {"label": "BD2 – Bao 2 số đặc biệt", "gia": 20000,  "type": "bd", "n_main": 5,  "n_sp": 2},
    "bd3": {"label": "BD3 – Bao 3 số đặc biệt", "gia": 30000,  "type": "bd", "n_main": 5,  "n_sp": 3},
    "bd4": {"label": "BD4 – Bao 4 số đặc biệt", "gia": 40000,  "type": "bd", "n_main": 5,  "n_sp": 4},
    "bd5": {"label": "BD5 – Bao 5 số đặc biệt", "gia": 50000,  "type": "bd", "n_main": 5,  "n_sp": 5},
    "bd6": {"label": "BD6 – Bao 6 số đặc biệt", "gia": 60000,  "type": "bd", "n_main": 5,  "n_sp": 6},
    "bd7": {"label": "BD7 – Bao 7 số đặc biệt", "gia": 70000,  "type": "bd", "n_main": 5,  "n_sp": 7},
    "bd8": {"label": "BD8 – Bao 8 số đặc biệt", "gia": 80000,  "type": "bd", "n_main": 5,  "n_sp": 8},
    "bd9": {"label": "BD9 – Bao 9 số đặc biệt", "gia": 90000,  "type": "bd", "n_main": 5,  "n_sp": 9},
    "bd10":{"label": "BD10 – Bao 10 số đặc biệt","gia": 100000, "type": "bd", "n_main": 5,  "n_sp": 10},
    "bd11":{"label": "BD11 – Bao 11 số đặc biệt","gia": 110000, "type": "bd", "n_main": 5,  "n_sp": 11},
    "bd12":{"label": "BD12 – Bao 12 số đặc biệt","gia": 120000, "type": "bd", "n_main": 5,  "n_sp": 12},
}

# Bao 645/655
BAO_645_655 = {
    "b5":  {"label": "B5  – Bao 5 số",  "gia_645": 400000,  "gia_655": 500000,  "n": 5},
    "b7":  {"label": "B7  – Bao 7 số",  "gia_645": 70000,   "gia_655": 70000,   "n": 7},
    "b8":  {"label": "B8  – Bao 8 số",  "gia_645": 280000,  "gia_655": 280000,  "n": 8},
    "b9":  {"label": "B9  – Bao 9 số",  "gia_645": 840000,  "gia_655": 840000,  "n": 9},
    "b10": {"label": "B10 – Bao 10 số", "gia_645": 2100000, "gia_655": 2100000, "n": 10},
}

intents = discord.Intents.default()
client = discord.Client(intents=intents)
tree = app_commands.CommandTree(client)
_cache = {}

# ==========================================
# FETCH & COMPUTE
# ==========================================
def fetch_history(cfg):
    key = cfg["sms_prefix"]
    if key in _cache:
        return _cache[key]
    all_numbers, all_specials = [], []
    headers = {"User-Agent": "Mozilla/5.0"}
    for page in range(1, cfg["pages"] + 1):
        try:
            r = requests.get(f"{cfg['url']}?indexpage={page}&orderby=new", headers=headers, timeout=10)
            soup = BeautifulSoup(r.text, "html.parser")
            for row in soup.select("table tr"):
                cells = row.find_all("td")
                if len(cells) < 2:
                    continue
                nums = [int(n) for n in re.findall(r"\d+", cells[1].get_text()) if 1 <= int(n) <= cfg["n"]]
                if len(nums) == cfg["k"]:
                    all_numbers.extend(nums)
                    if cfg.get("has_special") and len(cells) >= 3:
                        sp = re.findall(r"\d+", cells[2].get_text())
                        if sp and 1 <= int(sp[0]) <= cfg.get("special_n", 12):
                            all_specials.append(int(sp[0]))
        except Exception:
            continue
    _cache[key] = (all_numbers, all_specials)
    return all_numbers, all_specials

def compute_freq(numbers, n):
    freq = {i: 0 for i in range(1, n + 1)}
    for num in numbers:
        if num in freq:
            freq[num] += 1
    return freq

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

def generate_nums(freq, n_total, n_pick, exclude_sets=None):
    avg = sum(freq.values()) / n_total
    sorted_f = sorted(freq.items(), key=lambda x: x[1], reverse=True)
    hot = [n for n, _ in sorted_f[:15]]
    cold = [n for n, _ in sorted_f[-15:]]
    hot_w = [freq[n] for n in hot]
    cold_w = [max(1, avg * 2 - freq[n]) for n in cold]
    n_hot = (n_pick + 1) // 2
    n_cold = n_pick // 2
    for _ in range(20):
        picked = set(weighted_pick(hot, hot_w, n_hot))
        picked.update(weighted_pick(cold, cold_w, n_cold, exclude=picked))
        while len(picked) < n_pick:
            picked.add(random.randint(1, n_total))
        result = tuple(sorted(picked))
        if not exclude_sets or result not in exclude_sets:
            return list(result)
    return list(sorted(picked))

def fmt_gia(gia):
    return f"{gia:,}đ".replace(",", ".")

def make_sms_link(sms_text):
    return f"https://vietlott-sms.netlify.app/?body={urllib.parse.quote(sms_text)}"

def make_button(sms_text):
    view = discord.ui.View()
    view.add_item(discord.ui.Button(label="📱 Mở SMS → gửi 9969", url=make_sms_link(sms_text), style=discord.ButtonStyle.link))
    return view

def max_bo(gia, type_key):
    return max(1, GIOI_HAN_NGAY[type_key] // gia)

# ==========================================
# SMS BUILDERS
# ==========================================
def sms_535_multi(sets):
    parts = []
    for nums, sp in sets:
        main = " ".join(f"{n:02d}" for n in nums[:-1])
        last = f"{nums[-1]:02d}-{sp:02d}"
        parts.append(f"S {main} {last}")
    return "535 K1 " + " ".join(parts)

def sms_645_655_basic(prefix, sets):
    parts = [f"S {' '.join(f'{n:02d}' for n in nums)}" for nums, _ in sets]
    return f"{prefix} K1 " + " ".join(parts)

def sms_bao_645_655(prefix, bao_key, nums):
    return f"{prefix} K1 {bao_key.upper()} S {' '.join(f'{n:02d}' for n in nums)}"

def sms_bao535_bc(bao_key, main_nums, special):
    main = " ".join(f"{n:02d}" for n in main_nums[:-1])
    last = f"{main_nums[-1]:02d}-{special:02d}"
    return f"535 K1 {bao_key.upper()} S {main} {last}"

def sms_bao535_bd(bao_key, main_nums, specials):
    main = " ".join(f"{n:02d}" for n in main_nums)
    sp_first = f"{specials[0]:02d}"
    sp_rest = " ".join(f"{n:02d}" for n in specials[1:])
    sp_str = sp_first + (" " + sp_rest if sp_rest else "")
    return f"535 K1 {bao_key.upper()} S {main}-{sp_str}"

# ==========================================
# HANDLERS
# ==========================================
async def run_pick(interaction, type_key, so_luong):
    cfg = CONFIGS[type_key]
    await interaction.response.defer(thinking=True)
    try:
        numbers, specials = fetch_history(cfg)
        if len(numbers) < cfg["k"] * 5:
            await interaction.followup.send("⚠️ Không lấy được đủ dữ liệu.")
            return
        freq = compute_freq(numbers, cfg["n"])
        sp_freq = compute_freq(specials, cfg.get("special_n", 12)) if specials else None
        draws = len(numbers) // cfg["k"]
        sorted_f = sorted(freq.items(), key=lambda x: x[1], reverse=True)

        embed = discord.Embed(title=f"🎰 Gợi ý {so_luong} bộ số — {cfg['label']}", color=0x1D9E75)
        embed.add_field(name="📊 Phân tích từ", value=f"{draws} kỳ lịch sử", inline=True)
        embed.add_field(name="🔥 Hot", value=" ".join(f"`{n:02d}`" for n, _ in sorted_f[:3]), inline=True)
        embed.add_field(name="🧊 Cold", value=" ".join(f"`{n:02d}`" for n, _ in sorted_f[-3:]), inline=True)

        all_sets, seen = [], set()
        for i in range(so_luong):
            nums = generate_nums(freq, cfg["n"], cfg["k"], seen)
            seen.add(tuple(nums))
            sp = None
            if cfg.get("has_special") and sp_freq:
                sp_sorted = sorted(sp_freq.items(), key=lambda x: x[1], reverse=True)
                sp = weighted_pick([n for n, _ in sp_sorted], [c for _, c in sp_sorted], 1)[0]
            all_sets.append((nums, sp))
            disp = " ".join(f"`{n:02d}`" for n in nums)
            extra = f"  |  {'Đặc biệt' if type_key=='535' else 'Power'}: `{sp:02d}`" if sp else ""
            embed.add_field(name=f"Bộ {i+1}", value=disp + extra, inline=False)

        tong_tien = so_luong * 10000
        embed.add_field(name="💰 Tổng tiền", value=fmt_gia(tong_tien), inline=False)

        sms = sms_535_multi(all_sets) if type_key == "535" else sms_645_655_basic(cfg["sms_prefix"], all_sets)
        embed.set_footer(text="⚠️ Chỉ để vui, không đảm bảo trúng thưởng!")
        embed.timestamp = datetime.utcnow()
        await interaction.followup.send(embed=embed, view=make_button(sms))
    except Exception as e:
        await interaction.followup.send(f"❌ Lỗi: {str(e)}")

async def run_stat(interaction, type_key):
    cfg = CONFIGS[type_key]
    await interaction.response.defer(thinking=True)
    try:
        numbers, _ = fetch_history(cfg)
        freq = compute_freq(numbers, cfg["n"])
        draws = len(numbers) // cfg["k"]
        sorted_f = sorted(freq.items(), key=lambda x: x[1], reverse=True)
        max_c = sorted_f[0][1]
        def bar(c): return "█" * round(c/max_c*10) + "░" * (10-round(c/max_c*10))
        embed = discord.Embed(title=f"📊 Thống kê {cfg['label']}", color=0x378ADD)
        embed.add_field(name="Tổng kỳ", value=f"**{draws}** kỳ", inline=True)
        embed.add_field(name="Số nóng nhất", value=f"**{sorted_f[0][0]:02d}** ({sorted_f[0][1]}x)", inline=True)
        embed.add_field(name="Số lạnh nhất", value=f"**{sorted_f[-1][0]:02d}** ({sorted_f[-1][1]}x)", inline=True)
        embed.add_field(name="🔥 Top 5 nóng", value="\n".join(f"`{n:02d}` {bar(c)} {c}x" for n, c in sorted_f[:5]), inline=True)
        embed.add_field(name="🧊 Top 5 lạnh", value="\n".join(f"`{n:02d}` {bar(c)} {c}x" for n, c in sorted_f[-5:][::-1]), inline=True)
        embed.set_footer(text="Dữ liệu từ lotto-8.com")
        await interaction.followup.send(embed=embed)
    except Exception as e:
        await interaction.followup.send(f"❌ Lỗi: {str(e)}")

async def run_bao535(interaction, bao_key, so_bo):
    info = BAO_535[bao_key]
    so_bo_max = max_bo(info["gia"], "535")

    if so_bo > so_bo_max:
        await interaction.response.send_message(
            f"⚠️ **{info['label']}** giá {fmt_gia(info['gia'])}/bộ\n"
            f"Giới hạn ngày 5/35 là {fmt_gia(GIOI_HAN_NGAY['535'])} → tối đa **{so_bo_max} bộ**\n"
            f"Bạn nhập {so_bo} bộ, vui lòng nhập lại ≤ {so_bo_max}.",
            ephemeral=True
        )
        return

    await interaction.response.defer(thinking=True)
    try:
        numbers, specials = fetch_history(CONFIGS["535"])
        freq = compute_freq(numbers, 35)
        sp_freq = compute_freq(specials, 12) if specials else {i: 1 for i in range(1, 13)}
        sorted_sp = sorted(sp_freq.items(), key=lambda x: x[1], reverse=True)

        embed = discord.Embed(title=f"🎰 {info['label']} — Lotto 5/35", color=0x9B59B6)
        embed.add_field(
            name="📋 Giới hạn ngày",
            value=f"Tối đa **{so_bo_max} bộ** ({fmt_gia(GIOI_HAN_NGAY['535'])} / {fmt_gia(info['gia'])})",
            inline=False
        )

        all_sms = []
        seen = set()
        for i in range(so_bo):
            if info["type"] == "bc":
                main_nums = generate_nums(freq, 35, info["n_main"], seen)
                seen.add(tuple(main_nums))
                special = sorted_sp[0][0]
                sms = sms_bao535_bc(bao_key, main_nums, special)
                embed.add_field(
                    name=f"Bộ {i+1}",
                    value=f"{' '.join(f'`{n:02d}`' for n in main_nums)}  |  Đặc biệt: `{special:02d}`",
                    inline=False
                )
            else:
                main_nums = generate_nums(freq, 35, 5, seen)
                seen.add(tuple(main_nums))
                specials_picked = [n for n, _ in sorted_sp[:info["n_sp"]]]
                sms = sms_bao535_bd(bao_key, main_nums, specials_picked)
                embed.add_field(
                    name=f"Bộ {i+1}",
                    value=f"{' '.join(f'`{n:02d}`' for n in main_nums)}  |  Đặc biệt: {' '.join(f'`{n:02d}`' for n in specials_picked)}",
                    inline=False
                )
            all_sms.append(sms)

        tong = so_bo * info["gia"]
        embed.add_field(name="💰 Tổng tiền", value=f"{fmt_gia(tong)} / {fmt_gia(GIOI_HAN_NGAY['535'])} hạn mức ngày", inline=False)
        embed.set_footer(text="⚠️ Chỉ để vui, không đảm bảo trúng thưởng!")
        embed.timestamp = datetime.utcnow()

        # Gửi từng SMS riêng nếu nhiều bộ
        # Gộp tất cả bộ thành 1 tin nhắn SMS duy nhất
        full_sms = " ".join(all_sms)
        await interaction.followup.send(embed=embed, view=make_button(full_sms))

    except Exception as e:
        await interaction.followup.send(f"❌ Lỗi: {str(e)}")

async def run_bao645655(interaction, type_key, bao_key, so_bo):
    info = BAO_645_655[bao_key]
    gia = info[f"gia_{type_key}"]
    so_bo_max = max_bo(gia, type_key)
    cfg = CONFIGS[type_key]

    if so_bo > so_bo_max:
        await interaction.response.send_message(
            f"⚠️ **{info['label']}** giá {fmt_gia(gia)}/bộ\n"
            f"Giới hạn ngày {cfg['label']} là {fmt_gia(GIOI_HAN_NGAY[type_key])} → tối đa **{so_bo_max} bộ**\n"
            f"Bạn nhập {so_bo} bộ, vui lòng nhập lại ≤ {so_bo_max}.",
            ephemeral=True
        )
        return

    await interaction.response.defer(thinking=True)
    try:
        numbers, _ = fetch_history(cfg)
        freq = compute_freq(numbers, cfg["n"])

        embed = discord.Embed(title=f"🎰 {info['label']} — {cfg['label']}", color=0x9B59B6)
        embed.add_field(
            name="📋 Giới hạn ngày",
            value=f"Tối đa **{so_bo_max} bộ** ({fmt_gia(GIOI_HAN_NGAY[type_key])} / {fmt_gia(gia)})",
            inline=False
        )

        seen, s_parts = set(), []
        for i in range(so_bo):
            nums = generate_nums(freq, cfg["n"], info["n"], seen)
            seen.add(tuple(nums))
            # Chỉ lấy phần "S xx xx xx..." để gộp chung prefix
            s_parts.append("S " + " ".join(f"{n:02d}" for n in nums))
            embed.add_field(
                name=f"Bộ {i+1}",
                value=" ".join(f"`{n:02d}`" for n in nums),
                inline=False
            )

        tong = so_bo * gia
        embed.add_field(name="💰 Tổng tiền", value=f"{fmt_gia(tong)} / {fmt_gia(GIOI_HAN_NGAY[type_key])} hạn mức ngày", inline=False)
        embed.set_footer(text="⚠️ Chỉ để vui, không đảm bảo trúng thưởng!")
        embed.timestamp = datetime.utcnow()

        # 1 SMS duy nhất: 645 K1 B7 S xx xx S xx xx S xx xx
        full_sms = f"{cfg['sms_prefix']} K1 {bao_key.upper()} " + " ".join(s_parts)
        await interaction.followup.send(embed=embed, view=make_button(full_sms))

    except Exception as e:
        await interaction.followup.send(f"❌ Lỗi: {str(e)}")

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

@tree.command(name="stat535", description="Thống kê hot/cold Lotto 5/35")
async def cmd_stat535(interaction): await run_stat(interaction, "535")

@tree.command(name="stat645", description="Thống kê hot/cold Mega 6/45")
async def cmd_stat645(interaction): await run_stat(interaction, "645")

@tree.command(name="stat655", description="Thống kê hot/cold Power 6/55")
async def cmd_stat655(interaction): await run_stat(interaction, "655")

# Bao 535
bao535_choices = [
    app_commands.Choice(name="BC4 – Bao 4 số chính (310.000đ) – max 3 bộ",    value="bc4"),
    app_commands.Choice(name="BC6 – Bao 6 số chính (60.000đ) – max 16 bộ",    value="bc6"),
    app_commands.Choice(name="BC7 – Bao 7 số chính (210.000đ) – max 4 bộ",    value="bc7"),
    app_commands.Choice(name="BC8 – Bao 8 số chính (560.000đ) – max 1 bộ",    value="bc8"),
    app_commands.Choice(name="BD2 – Bao 2 số đặc biệt (20.000đ) – max 50 bộ", value="bd2"),
    app_commands.Choice(name="BD3 – Bao 3 số đặc biệt (30.000đ) – max 33 bộ", value="bd3"),
    app_commands.Choice(name="BD4 – Bao 4 số đặc biệt (40.000đ) – max 25 bộ", value="bd4"),
    app_commands.Choice(name="BD5 – Bao 5 số đặc biệt (50.000đ) – max 20 bộ", value="bd5"),
    app_commands.Choice(name="BD6 – Bao 6 số đặc biệt (60.000đ) – max 16 bộ", value="bd6"),
    app_commands.Choice(name="BD7 – Bao 7 số đặc biệt (70.000đ) – max 14 bộ", value="bd7"),
    app_commands.Choice(name="BD8 – Bao 8 số đặc biệt (80.000đ) – max 12 bộ", value="bd8"),
    app_commands.Choice(name="BD9 – Bao 9 số đặc biệt (90.000đ) – max 11 bộ", value="bd9"),
    app_commands.Choice(name="BD10 – Bao 10 số đặc biệt (100.000đ) – max 10 bộ", value="bd10"),
    app_commands.Choice(name="BD11 – Bao 11 số đặc biệt (110.000đ) – max 9 bộ",  value="bd11"),
    app_commands.Choice(name="BD12 – Bao 12 số đặc biệt (120.000đ) – max 8 bộ",  value="bd12"),
]
@tree.command(name="bao535", description="Bao số Lotto 5/35 kèm SMS (có kiểm tra giới hạn ngày)")
@app_commands.describe(loai="Chọn loại bao số", so_bo="Số bộ muốn mua")
@app_commands.choices(loai=bao535_choices)
async def cmd_bao535(interaction, loai: app_commands.Choice[str], so_bo: app_commands.Range[int, 1, 50] = 1):
    await run_bao535(interaction, loai.value, so_bo)

# Bao 645
bao645_choices = [
    app_commands.Choice(name="B5  – Bao 5 số (400.000đ) – max 5 bộ",    value="b5"),
    app_commands.Choice(name="B7  – Bao 7 số (70.000đ) – max 30 bộ",    value="b7"),
    app_commands.Choice(name="B8  – Bao 8 số (280.000đ) – max 7 bộ",    value="b8"),
    app_commands.Choice(name="B9  – Bao 9 số (840.000đ) – max 2 bộ",    value="b9"),
    app_commands.Choice(name="B10 – Bao 10 số (2.100.000đ) – max 1 bộ", value="b10"),
]
@tree.command(name="bao645", description="Bao số Mega 6/45 kèm SMS (có kiểm tra giới hạn ngày)")
@app_commands.describe(loai="Chọn loại bao số", so_bo="Số bộ muốn mua")
@app_commands.choices(loai=bao645_choices)
async def cmd_bao645(interaction, loai: app_commands.Choice[str], so_bo: app_commands.Range[int, 1, 30] = 1):
    await run_bao645655(interaction, "645", loai.value, so_bo)

# Bao 655
bao655_choices = [
    app_commands.Choice(name="B5  – Bao 5 số (500.000đ) – max 4 bộ",    value="b5"),
    app_commands.Choice(name="B7  – Bao 7 số (70.000đ) – max 30 bộ",    value="b7"),
    app_commands.Choice(name="B8  – Bao 8 số (280.000đ) – max 7 bộ",    value="b8"),
    app_commands.Choice(name="B9  – Bao 9 số (840.000đ) – max 2 bộ",    value="b9"),
    app_commands.Choice(name="B10 – Bao 10 số (2.100.000đ) – max 1 bộ", value="b10"),
]
@tree.command(name="bao655", description="Bao số Power 6/55 kèm SMS (có kiểm tra giới hạn ngày)")
@app_commands.describe(loai="Chọn loại bao số", so_bo="Số bộ muốn mua")
@app_commands.choices(loai=bao655_choices)
async def cmd_bao655(interaction, loai: app_commands.Choice[str], so_bo: app_commands.Range[int, 1, 30] = 1):
    await run_bao645655(interaction, "655", loai.value, so_bo)

# ==========================================
# KHỞI ĐỘNG
# ==========================================
@client.event
async def on_ready():
    await tree.sync()
    print(f"✅ Bot đã online: {client.user}")
    print("Commands: /535 /645 /655 /stat535 /stat645 /stat655 /bao535 /bao645 /bao655")

client.run(TOKEN)
