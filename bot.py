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

        seen, s_parts = set(), []
        for i in range(so_bo):
            if info["type"] == "bc":
                main_nums = generate_nums(freq, 35, info["n_main"], seen)
                seen.add(tuple(main_nums))
                # Random có trọng số, không luôn lấy số nóng nhất
                sp_pool = [n for n, _ in sorted_sp]
                sp_weights = [c for _, c in sorted_sp]
                special = weighted_pick(sp_pool, sp_weights, 1)[0]
                # Chỉ lấy phần "S xx xx xx-yy" không kèm prefix
                main_str = " ".join(f"{n:02d}" for n in main_nums[:-1])
                last = f"{main_nums[-1]:02d}-{special:02d}"
                s_parts.append(f"S {main_str} {last}")
                embed.add_field(
                    name=f"Bộ {i+1}",
                    value=f"{' '.join(f'`{n:02d}`' for n in main_nums)}  |  Đặc biệt: `{special:02d}`",
                    inline=False
                )
            else:
                main_nums = generate_nums(freq, 35, 5, seen)
                seen.add(tuple(main_nums))
                specials_picked = [n for n, _ in sorted_sp[:info["n_sp"]]]
                main_str = " ".join(f"{n:02d}" for n in main_nums)
                sp_str = f"{specials_picked[0]:02d}" + (" " + " ".join(f"{n:02d}" for n in specials_picked[1:]) if len(specials_picked) > 1 else "")
                s_parts.append(f"S {main_str}-{sp_str}")
                embed.add_field(
                    name=f"Bộ {i+1}",
                    value=f"{' '.join(f'`{n:02d}`' for n in main_nums)}  |  Đặc biệt: {' '.join(f'`{n:02d}`' for n in specials_picked)}",
                    inline=False
                )

        tong = so_bo * info["gia"]
        embed.add_field(name="💰 Tổng tiền", value=f"{fmt_gia(tong)} / {fmt_gia(GIOI_HAN_NGAY['535'])} hạn mức ngày", inline=False)
        embed.set_footer(text="⚠️ Chỉ để vui, không đảm bảo trúng thưởng!")
        embed.timestamp = datetime.utcnow()

        # 1 SMS duy nhất: 535 K1 BC7 S xx xx-yy S xx xx-yy ...
        full_sms = f"535 K1 {bao_key.upper()} " + " ".join(s_parts)
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
    print("Commands: /ketqua /thongke /sosanhso")
    # Khởi động scheduler chạy nền
    asyncio.create_task(scheduler())
    print("⏰ Scheduler đã khởi động")

client.run(TOKEN)


# ==========================================
# GOOGLE SHEETS & KẾT QUẢ XỔ SỐ
# ==========================================
import json
import threading
import time
import pytz
from datetime import datetime, timedelta
import gspread
from google.oauth2.service_account import Credentials

VN_TZ = pytz.timezone("Asia/Ho_Chi_Minh")

# Lịch xổ: (weekday, hour, minute) — weekday: 0=T2, 1=T3...6=CN
LICH_XO = {
    "535": [(0, 21, 5), (2, 21, 5), (4, 21, 5)],   # T2, T4, T6 lúc 21:05
    "645": [(2, 18, 5), (4, 18, 5), (6, 18, 5)],   # T4, T6, CN lúc 18:05
    "655": [(1, 18, 5), (3, 18, 5), (5, 18, 5)],   # T3, T5, T7 lúc 18:05
}

DISCORD_CHANNEL_ID = int(os.environ.get("DISCORD_CHANNEL_ID", "0"))

def get_sheet():
    creds_json = os.environ.get("GOOGLE_CREDENTIALS", "{}")
    creds_dict = json.loads(creds_json)
    scopes = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
    creds = Credentials.from_service_account_info(creds_dict, scopes=scopes)
    gc = gspread.authorize(creds)
    sheet_id = os.environ.get("GOOGLE_SHEET_ID", "")
    return gc.open_by_key(sheet_id)

def save_result(type_key, ngay, ky, numbers, special=None):
    try:
        wb = get_sheet()
        ws = wb.worksheet(type_key)
        row = [ngay, ky] + [str(n) for n in numbers]
        if special:
            row.append(str(special))
        ws.append_row(row)
        print(f"✅ Đã lưu kết quả {type_key} kỳ {ky}")
    except Exception as e:
        print(f"❌ Lỗi lưu Sheets: {e}")

def load_results(type_key):
    try:
        wb = get_sheet()
        ws = wb.worksheet(type_key)
        rows = ws.get_all_values()
        if len(rows) <= 1:
            return []
        results = []
        for row in rows[1:]:  # bỏ header
            if len(row) >= 7:
                results.append(row)
        return results
    except Exception as e:
        print(f"❌ Lỗi đọc Sheets: {e}")
        return []

def fetch_latest_result(type_key):
    """Fetch kết quả mới nhất từ lotto-8.com"""
    cfg = CONFIGS[type_key]
    headers = {"User-Agent": "Mozilla/5.0"}
    try:
        r = requests.get(f"{cfg['url']}?indexpage=1&orderby=new", headers=headers, timeout=10)
        soup = BeautifulSoup(r.text, "html.parser")
        rows = soup.select("table tr")
        for row in rows:
            cells = row.find_all("td")
            if len(cells) < 2:
                continue
            nums = [int(n) for n in re.findall(r"\d+", cells[1].get_text()) if 1 <= int(n) <= cfg["n"]]
            if len(nums) == cfg["k"]:
                ky = cells[0].get_text(strip=True) if cells else "?"
                special = None
                if cfg.get("has_special") and len(cells) >= 3:
                    sp = re.findall(r"\d+", cells[2].get_text())
                    if sp and 1 <= int(sp[0]) <= cfg.get("special_n", 12):
                        special = int(sp[0])
                return ky, nums, special
    except Exception as e:
        print(f"❌ Lỗi fetch kết quả {type_key}: {e}")
    return None, None, None

def compute_freq_from_sheet(type_key):
    """Tính tần suất từ dữ liệu Google Sheets"""
    cfg = CONFIGS[type_key]
    results = load_results(type_key)
    freq = {i: 0 for i in range(1, cfg["n"] + 1)}
    sp_freq = {i: 0 for i in range(1, cfg.get("special_n", 12) + 1)}
    for row in results:
        try:
            nums = [int(row[i]) for i in range(2, 2 + cfg["k"])]
            for n in nums:
                if n in freq:
                    freq[n] += 1
            if cfg.get("has_special") and len(row) > 2 + cfg["k"]:
                sp = int(row[2 + cfg["k"]])
                if sp in sp_freq:
                    sp_freq[sp] += 1
        except:
            continue
    return freq, sp_freq, len(results)

async def post_result(type_key):
    """Fetch kết quả, lưu Sheets, báo Discord"""
    channel = client.get_channel(DISCORD_CHANNEL_ID)
    if not channel:
        print(f"❌ Không tìm thấy channel {DISCORD_CHANNEL_ID}")
        return

    cfg = CONFIGS[type_key]
    ngay = datetime.now(VN_TZ).strftime("%d/%m/%Y")

    await channel.send(f"⏳ Đang lấy kết quả **{cfg['label']}** kỳ hôm nay...")

    # Thử fetch tối đa 5 lần, cách nhau 2 phút
    ky, numbers, special = None, None, None
    for attempt in range(5):
        ky, numbers, special = fetch_latest_result(type_key)
        if numbers:
            break
        await asyncio.sleep(120)

    if not numbers:
        await channel.send(f"⚠️ Không lấy được kết quả {cfg['label']} hôm nay. Thử lại sau!")
        return

    # Lưu vào Google Sheets
    save_result(type_key, ngay, ky, numbers, special)

    # Tính thống kê từ Sheets
    freq, sp_freq, total_draws = compute_freq_from_sheet(type_key)
    sorted_f = sorted(freq.items(), key=lambda x: x[1], reverse=True)

    # Build embed kết quả
    embed = discord.Embed(
        title=f"🎰 Kết quả {cfg['label']} — {ngay}",
        color=0xE74C3C
    )
    embed.add_field(name="🎯 Kỳ", value=f"**{ky}**", inline=True)

    nums_display = " ".join(f"`{n:02d}`" for n in numbers)
    embed.add_field(name="Kết quả", value=nums_display, inline=False)
    if special:
        sp_label = "Số đặc biệt" if type_key == "535" else "Số Power"
        embed.add_field(name=sp_label, value=f"`{special:02d}`", inline=True)

    # Phân tích: số nào hot/cold so với lịch sử
    if total_draws > 0:
        avg = sum(freq.values()) / cfg["n"]
        hot_this = [n for n in numbers if freq.get(n, 0) >= avg]
        cold_this = [n for n in numbers if freq.get(n, 0) < avg]
        embed.add_field(
            name=f"📊 Phân tích (từ {total_draws} kỳ lưu)",
            value=(
                f"🔥 Số nóng ra hôm nay: {' '.join(f'`{n:02d}`' for n in hot_this) or 'Không có'}\n"
                f"🧊 Số lạnh ra hôm nay: {' '.join(f'`{n:02d}`' for n in cold_this) or 'Không có'}"
            ),
            inline=False
        )
        top3_hot = [n for n, _ in sorted_f[:3]]
        top3_cold = [n for n, _ in sorted_f[-3:]]
        embed.add_field(name="🔥 Top 3 nóng nhất (lịch sử)", value=" ".join(f"`{n:02d}`" for n in top3_hot), inline=True)
        embed.add_field(name="🧊 Top 3 lạnh nhất (lịch sử)", value=" ".join(f"`{n:02d}`" for n in top3_cold), inline=True)

    embed.set_footer(text="Dữ liệu tự lưu từ bot · Dùng /thongke để xem chi tiết")
    embed.timestamp = datetime.utcnow()
    await channel.send(embed=embed)
    print(f"✅ Đã báo kết quả {type_key}")

# ==========================================
# SCHEDULER
# ==========================================
import asyncio

async def scheduler():
    """Chạy nền, check giờ xổ mỗi phút"""
    print("⏰ Scheduler đã khởi động")
    while True:
        now = datetime.now(VN_TZ)
        wd = now.weekday()
        h, m = now.hour, now.minute
        for type_key, lich in LICH_XO.items():
            for (ngay_xo, gio, phut) in lich:
                if wd == ngay_xo and h == gio and m == phut:
                    print(f"🎯 Đến giờ xổ {type_key}!")
                    await post_result(type_key)
        await asyncio.sleep(60)

# ==========================================
# SLASH COMMANDS MỚI
# ==========================================
@tree.command(name="ketqua", description="Xem kết quả xổ số mới nhất")
@app_commands.describe(loai="Loại vé muốn xem")
@app_commands.choices(loai=[
    app_commands.Choice(name="Lotto 5/35", value="535"),
    app_commands.Choice(name="Mega 6/45", value="645"),
    app_commands.Choice(name="Power 6/55", value="655"),
])
async def cmd_ketqua(interaction: discord.Interaction, loai: app_commands.Choice[str]):
    cfg = CONFIGS[loai.value]
    await interaction.response.defer(thinking=True)
    try:
        ky, numbers, special = fetch_latest_result(loai.value)
        if not numbers:
            await interaction.followup.send("⚠️ Không lấy được kết quả. Thử lại sau!")
            return
        embed = discord.Embed(title=f"🎰 Kết quả mới nhất — {cfg['label']}", color=0xE74C3C)
        embed.add_field(name="Kỳ", value=f"**{ky}**", inline=True)
        embed.add_field(name="Kết quả", value=" ".join(f"`{n:02d}`" for n in numbers), inline=False)
        if special:
            embed.add_field(name="Số đặc biệt" if loai.value == "535" else "Số Power", value=f"`{special:02d}`", inline=True)
        embed.timestamp = datetime.utcnow()
        await interaction.followup.send(embed=embed)
    except Exception as e:
        await interaction.followup.send(f"❌ Lỗi: {str(e)}")

@tree.command(name="thongke", description="Thống kê hot/cold từ dữ liệu tự lưu")
@app_commands.describe(loai="Loại vé muốn xem")
@app_commands.choices(loai=[
    app_commands.Choice(name="Lotto 5/35", value="535"),
    app_commands.Choice(name="Mega 6/45", value="645"),
    app_commands.Choice(name="Power 6/55", value="655"),
])
async def cmd_thongke(interaction: discord.Interaction, loai: app_commands.Choice[str]):
    cfg = CONFIGS[loai.value]
    await interaction.response.defer(thinking=True)
    try:
        freq, sp_freq, total = compute_freq_from_sheet(loai.value)
        if total == 0:
            await interaction.followup.send(f"⚠️ Chưa có dữ liệu lưu cho {cfg['label']}. Đợi sau kỳ xổ đầu tiên nhé!")
            return
        sorted_f = sorted(freq.items(), key=lambda x: x[1], reverse=True)
        max_c = sorted_f[0][1]
        def bar(c): return "█" * round(c/max_c*10) + "░" * (10-round(c/max_c*10))

        embed = discord.Embed(title=f"📊 Thống kê {cfg['label']} — Dữ liệu tự lưu", color=0x9B59B6)
        embed.add_field(name="Tổng kỳ đã lưu", value=f"**{total}** kỳ", inline=True)
        embed.add_field(name="Số nóng nhất", value=f"**{sorted_f[0][0]:02d}** ({sorted_f[0][1]}x)", inline=True)
        embed.add_field(name="Số lạnh nhất", value=f"**{sorted_f[-1][0]:02d}** ({sorted_f[-1][1]}x)", inline=True)
        embed.add_field(
            name="🔥 Top 5 nóng",
            value="\n".join(f"`{n:02d}` {bar(c)} {c}x" for n, c in sorted_f[:5]),
            inline=True
        )
        embed.add_field(
            name="🧊 Top 5 lạnh",
            value="\n".join(f"`{n:02d}` {bar(c)} {c}x" for n, c in sorted_f[-5:][::-1]),
            inline=True
        )
        if cfg.get("has_special") and any(v > 0 for v in sp_freq.values()):
            sorted_sp = sorted(sp_freq.items(), key=lambda x: x[1], reverse=True)
            sp_label = "Số đặc biệt" if loai.value == "535" else "Số Power"
            embed.add_field(
                name=f"🎯 {sp_label} nóng nhất",
                value=" ".join(f"`{n:02d}`({c}x)" for n, c in sorted_sp[:5]),
                inline=False
            )
        embed.set_footer(text="Dữ liệu tự thu thập bởi bot")
        await interaction.followup.send(embed=embed)
    except Exception as e:
        await interaction.followup.send(f"❌ Lỗi: {str(e)}")

@tree.command(name="sosanhso", description="So sánh bộ số đã mua với kết quả mới nhất")
@app_commands.describe(
    loai="Loại vé",
    boSo="Nhập bộ số cách nhau bởi dấu cách (vd: 03 08 14 22 31)"
)
@app_commands.choices(loai=[
    app_commands.Choice(name="Lotto 5/35", value="535"),
    app_commands.Choice(name="Mega 6/45", value="645"),
    app_commands.Choice(name="Power 6/55", value="655"),
])
async def cmd_sosanhso(interaction: discord.Interaction, loai: app_commands.Choice[str], boSo: str):
    cfg = CONFIGS[loai.value]
    await interaction.response.defer(thinking=True)
    try:
        # Parse bộ số người dùng nhập
        input_nums = [int(n) for n in re.findall(r"\d+", boSo)]
        if len(input_nums) != cfg["k"]:
            await interaction.followup.send(f"⚠️ {cfg['label']} cần đúng **{cfg['k']} số**. Bạn nhập {len(input_nums)} số.")
            return

        ky, result_nums, special = fetch_latest_result(loai.value)
        if not result_nums:
            await interaction.followup.send("⚠️ Không lấy được kết quả. Thử lại sau!")
            return

        trung = sorted(set(input_nums) & set(result_nums))
        so_trung = len(trung)

        embed = discord.Embed(
            title=f"🔍 So sánh bộ số — {cfg['label']}",
            color=0x2ECC71 if so_trung >= 3 else 0x95A5A6
        )
        embed.add_field(name="Kỳ xổ", value=f"**{ky}**", inline=True)
        embed.add_field(name="Kết quả", value=" ".join(f"`{n:02d}`" for n in result_nums), inline=False)
        embed.add_field(name="Bộ số của bạn", value=" ".join(f"`{n:02d}`" for n in sorted(input_nums)), inline=False)

        if trung:
            embed.add_field(
                name=f"✅ Trúng {so_trung} số",
                value=" ".join(f"`{n:02d}`" for n in trung),
                inline=False
            )
        else:
            embed.add_field(name="❌ Không trúng số nào", value="Chúc may mắn lần sau!", inline=False)

        if special:
            sp_label = "Số đặc biệt" if loai.value == "535" else "Số Power"
            embed.add_field(name=sp_label, value=f"`{special:02d}`", inline=True)

        embed.timestamp = datetime.utcnow()
        await interaction.followup.send(embed=embed)
    except Exception as e:
        await interaction.followup.send(f"❌ Lỗi: {str(e)}")

