import discord
from discord import app_commands
import requests
from bs4 import BeautifulSoup
import random
import re
import os
from datetime import datetime

# ==========================================
# TOKEN LẤY TỪ BIẾN MÔI TRƯỜNG (Railway)
# ==========================================
TOKEN = os.environ.get("DISCORD_TOKEN", "")

# ==========================================
# CẤU HÌNH LOẠI VÉ
# ==========================================
CONFIGS = {
    "535": {"n": 35, "k": 5, "has_special": True, "special_n": 12, "label": "Lotto 5/35",
            "url": "https://www.lotto-8.com/Vietnam/listltoVM35.asp", "pages": 5},
    "645": {"n": 45, "k": 6, "has_special": False, "label": "Mega 6/45",
            "url": "https://www.lotto-8.com/Vietnam/listltoVM45.asp", "pages": 5},
    "655": {"n": 55, "k": 6, "has_special": True, "special_n": 10, "label": "Power 6/55",
            "url": "https://www.lotto-8.com/Vietnam/listltoVM55.asp", "pages": 5},
}

intents = discord.Intents.default()
client = discord.Client(intents=intents)
tree = app_commands.CommandTree(client)


# ==========================================
# HÀM LẤY DỮ LIỆU LỊCH SỬ
# ==========================================
def fetch_history(cfg):
    all_numbers = []
    all_specials = []
    headers = {"User-Agent": "Mozilla/5.0"}
    for page in range(1, cfg["pages"] + 1):
        try:
            url = f"{cfg['url']}?indexpage={page}&orderby=new"
            r = requests.get(url, headers=headers, timeout=10)
            soup = BeautifulSoup(r.text, "html.parser")
            rows = soup.select("table tr")
            for row in rows:
                cells = row.find_all("td")
                if len(cells) < 2:
                    continue
                text = cells[1].get_text(strip=True)
                nums = re.findall(r"\d+", text)
                nums = [int(n) for n in nums if 1 <= int(n) <= cfg["n"]]
                if len(nums) == cfg["k"]:
                    all_numbers.extend(nums)
                    if cfg.get("has_special") and len(cells) >= 3:
                        sp_text = cells[2].get_text(strip=True)
                        sp_nums = re.findall(r"\d+", sp_text)
                        if sp_nums:
                            val = int(sp_nums[0])
                            if 1 <= val <= cfg.get("special_n", 12):
                                all_specials.append(val)
        except Exception:
            continue
    return all_numbers, all_specials


def compute_freq(numbers, n):
    freq = {i: 0 for i in range(1, n + 1)}
    for num in numbers:
        if num in freq:
            freq[num] += 1
    return freq


def weighted_pick(pool, weights, count, exclude=None):
    if exclude is None:
        exclude = set()
    picked = []
    candidates = [(n, w) for n, w in zip(pool, weights) if n not in exclude]
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


def generate_suggestion(freq, cfg, special_freq=None):
    n = cfg["n"]
    k = cfg["k"]
    avg = sum(freq.values()) / n
    sorted_nums = sorted(freq.items(), key=lambda x: x[1], reverse=True)
    hot_pool = [num for num, _ in sorted_nums[:15]]
    hot_weights = [freq[num] for num in hot_pool]
    cold_pool = [num for num, _ in sorted_nums[-15:]]
    cold_weights = [max(1, avg * 2 - freq[num]) for num in cold_pool]
    n_hot = (k + 1) // 2
    n_cold = k // 2
    picked = set()
    hot_picks = weighted_pick(hot_pool, hot_weights, n_hot)
    picked.update(hot_picks)
    cold_picks = weighted_pick(cold_pool, cold_weights, n_cold, exclude=picked)
    picked.update(cold_picks)
    while len(picked) < k:
        picked.add(random.randint(1, n))
    result = sorted(picked)
    special = None
    if cfg.get("has_special") and special_freq:
        sp_sorted = sorted(special_freq.items(), key=lambda x: x[1], reverse=True)
        sp_pool = [n for n, _ in sp_sorted]
        sp_weights = [c for _, c in sp_sorted]
        sp = weighted_pick(sp_pool, sp_weights, 1)
        special = sp[0] if sp else random.randint(1, cfg.get("special_n", 12))
    return result, special


def format_balls(numbers):
    return "  ".join(f"`{str(n).zfill(2)}`" for n in numbers)


def make_bar(count, max_count, width=10):
    filled = round(count / max_count * width) if max_count > 0 else 0
    return "█" * filled + "░" * (width - filled)


async def run_pick(interaction: discord.Interaction, type_key: str):
    cfg = CONFIGS[type_key]
    await interaction.response.defer(thinking=True)
    try:
        numbers, specials = fetch_history(cfg)
        if len(numbers) < cfg["k"] * 5:
            await interaction.followup.send("⚠️ Không lấy được đủ dữ liệu. Thử lại sau nhé!")
            return
        freq = compute_freq(numbers, cfg["n"])
        special_freq = compute_freq(specials, cfg.get("special_n", 12)) if specials else None
        draws = len(numbers) // cfg["k"]
        sorted_freq = sorted(freq.items(), key=lambda x: x[1], reverse=True)
        suggestion, special = generate_suggestion(freq, cfg, special_freq)
        embed = discord.Embed(title=f"🎰 Gợi ý bộ số — {cfg['label']}", color=0x1D9E75)
        embed.add_field(name=f"Bộ {cfg['k']} số chính", value=format_balls(suggestion), inline=False)
        if special:
            label = "Số đặc biệt" if type_key == "535" else "Số Power"
            embed.add_field(name=label, value=f"`{special:02d}`", inline=True)
        embed.add_field(name="Phân tích từ", value=f"{draws} kỳ lịch sử", inline=True)
        hot_str = ", ".join(f"`{n:02d}`" for n, _ in sorted_freq[:3])
        cold_str = ", ".join(f"`{n:02d}`" for n, _ in sorted_freq[-3:])
        embed.add_field(name="🔥 Hot", value=hot_str, inline=True)
        embed.add_field(name="🧊 Cold", value=cold_str, inline=True)
        embed.set_footer(text="⚠️ Chỉ để vui, không đảm bảo trúng thưởng!")
        embed.timestamp = datetime.utcnow()
        await interaction.followup.send(embed=embed)
    except Exception as e:
        await interaction.followup.send(f"❌ Lỗi: {str(e)}")


async def run_stat(interaction: discord.Interaction, type_key: str):
    cfg = CONFIGS[type_key]
    await interaction.response.defer(thinking=True)
    try:
        numbers, specials = fetch_history(cfg)
        if len(numbers) < cfg["k"] * 5:
            await interaction.followup.send("⚠️ Không lấy được đủ dữ liệu. Thử lại sau nhé!")
            return
        freq = compute_freq(numbers, cfg["n"])
        draws = len(numbers) // cfg["k"]
        sorted_freq = sorted(freq.items(), key=lambda x: x[1], reverse=True)
        max_count = sorted_freq[0][1]
        top_hot = sorted_freq[:5]
        top_cold = sorted_freq[-5:][::-1]
        embed = discord.Embed(title=f"📊 Thống kê {cfg['label']}", color=0x378ADD)
        embed.add_field(name="Tổng kỳ phân tích", value=f"**{draws}** kỳ", inline=True)
        embed.add_field(name="Số nóng nhất", value=f"**{sorted_freq[0][0]:02d}** ({sorted_freq[0][1]}x)", inline=True)
        embed.add_field(name="Số lạnh nhất", value=f"**{sorted_freq[-1][0]:02d}** ({sorted_freq[-1][1]}x)", inline=True)
        hot_text = "\n".join(f"`{n:02d}` {make_bar(c, max_count)} {c}x" for n, c in top_hot)
        cold_text = "\n".join(f"`{n:02d}` {make_bar(c, max_count)} {c}x" for n, c in top_cold)
        embed.add_field(name="🔥 Top 5 số nóng", value=hot_text, inline=True)
        embed.add_field(name="🧊 Top 5 số lạnh", value=cold_text, inline=True)
        embed.set_footer(text="Dữ liệu từ lotto-8.com · Chỉ để tham khảo!")
        await interaction.followup.send(embed=embed)
    except Exception as e:
        await interaction.followup.send(f"❌ Lỗi: {str(e)}")


# ==========================================
# SLASH COMMANDS
# ==========================================
@tree.command(name="535", description="Gợi ý bộ số Lotto 5/35 dựa trên thống kê lịch sử")
async def cmd_535(interaction: discord.Interaction):
    await run_pick(interaction, "535")

@tree.command(name="645", description="Gợi ý bộ số Mega 6/45 dựa trên thống kê lịch sử")
async def cmd_645(interaction: discord.Interaction):
    await run_pick(interaction, "645")

@tree.command(name="655", description="Gợi ý bộ số Power 6/55 dựa trên thống kê lịch sử")
async def cmd_655(interaction: discord.Interaction):
    await run_pick(interaction, "655")

@tree.command(name="stat535", description="Xem thống kê hot/cold Lotto 5/35")
async def cmd_stat535(interaction: discord.Interaction):
    await run_stat(interaction, "535")

@tree.command(name="stat645", description="Xem thống kê hot/cold Mega 6/45")
async def cmd_stat645(interaction: discord.Interaction):
    await run_stat(interaction, "645")

@tree.command(name="stat655", description="Xem thống kê hot/cold Power 6/55")
async def cmd_stat655(interaction: discord.Interaction):
    await run_stat(interaction, "655")


# ==========================================
# KHỞI ĐỘNG
# ==========================================
@client.event
async def on_ready():
    await tree.sync()
    print(f"✅ Bot đã online: {client.user}")
    print("Slash commands đã đăng ký: /535 /645 /655 /stat535 /stat645 /stat655")

client.run(TOKEN)
