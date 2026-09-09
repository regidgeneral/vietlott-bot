"""Kiem tra sau khi nang han muc 535 len 2.500.000d."""
import ast, types, os, sys, asyncio, random

BOT = r"F:\Project\vietlott-bot-main\bot.py"
os.environ.setdefault("DISCORD_TOKEN", "x"); os.environ.setdefault("DISCORD_CHANNEL_ID", "1")
src = ast.parse(open(BOT, encoding="utf-8").read())
keep = []
for n in src.body:
    if isinstance(n, ast.Expr) and isinstance(n.value, ast.Call): continue
    if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef)) and n.decorator_list:
        n.decorator_list = []
    keep.append(n)
src.body = keep
m = types.ModuleType("b"); exec(compile(src, BOT, "exec"), m.__dict__)

FAIL = []
def check(c, msg):
    print(("  OK   " if c else "  FAIL ") + msg)
    if not c: FAIL.append(msg)

print("=" * 74)
print("  1. Han muc & so bo toi da")
print("=" * 74)
check(m.GIOI_HAN_NGAY["535"] == 2_500_000, f"535 = {m.GIOI_HAN_NGAY['535']:,}d")
check(m.GIOI_HAN_NGAY["645"] == 2_100_000 and m.GIOI_HAN_NGAY["655"] == 2_100_000,
      "645/655 giu nguyen 2.100.000d")
check(m.SO_BO_MOI_LENH == 50, f"gioi han mem = {m.SO_BO_MOI_LENH} bo/lenh")
check(m.max_bo(20000, "535") == 125, "max_bo (han muc NGAY) bd2 = 125")
check(m.max_bo_moi_lenh(20000, "535") == 50, "max_bo_moi_lenh bd2 = 50 (bi cap)")
check(m.max_bo_moi_lenh(120000, "535") == 20, "max_bo_moi_lenh bd12 = 20 (khong bi cap)")
check(m.MAX_BO_535 == 50, f"Range /bao535 = [1, {m.MAX_BO_535}]")
check(m.MAX_BO_645 == 30 and m.MAX_BO_655 == 30, f"Range 645/655 = {m.MAX_BO_645}/{m.MAX_BO_655}")

print()
print("=" * 74)
print("  2. Nhan choice sinh tu bang gia - co khop max_bo() khong?")
print("=" * 74)
import re
for ch in m.bao535_choices:
    key = ch.value
    gia = m.BAO_535[key]["gia"]
    lenh, ngay = m.max_bo_moi_lenh(gia, "535"), m.max_bo(gia, "535")
    n = int(re.search(r"max (\d+) bộ", ch.name).group(1))
    if key in ("bc4", "bd2", "bd12"):
        print(f"       {ch.name}")
    if n != lenh: FAIL.append(f"{key}: nhan ghi {n}, dung la {lenh}")
    if lenh < ngay and f"(ngày: {ngay})" not in ch.name:
        FAIL.append(f"{key}: nhan thieu phan 'ngày: {ngay}'")
check(not [f for f in FAIL if "nhan ghi" in f], "15 nhan 535 khop max_bo_moi_lenh()")
check(not [f for f in FAIL if "nhan thieu" in f], "nhan co neu han muc ngay khi bi cap")
check(all(len(c.name) <= 100 for c in m.bao535_choices + m.bao645_choices + m.bao655_choices),
      "moi nhan <= 100 ky tu (gioi han Discord)")
check(len(m.bao535_choices) == 15 and len(m.bao645_choices) == 5, "du so luong choice")
for ch in m.bao645_choices[:1] + m.bao655_choices[:1]:
    print(f"       {ch.name}")

print()
print("=" * 74)
print("  3. add_fields_chunked o CA XAU NHAT (bd2 = 125 bo)")
print("=" * 74)
def do_embed(e):
    d = e.to_dict()
    tong = len(d.get("title","")) + len(d.get("description",""))
    for f in d.get("fields", []): tong += len(f["name"]) + len(f["value"])
    return tong, len(d.get("fields", [])), max((len(f["value"]) for f in d.get("fields", [])), default=0)

for key in ("bd2", "bd3", "bd12", "bc6"):
    info = m.BAO_535[key]
    so_bo = m.max_bo_moi_lenh(info["gia"], "535")
    lines = []
    for i in range(so_bo):
        if info["type"] == "bc":
            disp = " ".join(f"`{v:02d}`" for v in sorted(random.sample(range(1,36), info["n_main"])))
            lines.append(f"**Bộ {i+1}:** {disp} | ĐB:`01`")
        else:
            disp = " ".join(f"`{v:02d}`" for v in sorted(random.sample(range(1,36), 5)))
            sp = " ".join(f"`{v:02d}`" for v in range(1, info["n_sp"]+1))
            lines.append(f"**Bộ {i+1}:** {disp} | ĐB: {sp}")
    e = m.discord.Embed(title=f"🎰 {info['label']} — Lotto 5/35", color=1)
    e.add_field(name="Giới hạn ngày", value=f"Tối đa {so_bo} bộ (2.500.000d / {m.fmt_gia(info['gia'])})", inline=False)
    m.add_fields_chunked(e, lines)
    e.add_field(name="Tổng tiền", value=f"{m.fmt_gia(so_bo*info['gia'])} / 2.500.000d hạn mức ngày", inline=False)
    tong, nf, fmax = do_embed(e)
    print(f"    {key:<5} {so_bo:>3} bộ -> embed {tong:>4}/6000, {nf:>2} field, field dài nhất {fmax}/1024")
    check(tong <= 6000, f"{key}: embed {tong} <= 6000")
    check(nf <= 25, f"{key}: {nf} field <= 25")
    check(fmax <= 1024, f"{key}: field dài nhất {fmax} <= 1024")

print()
print("=" * 74)
print("  4. Tong tien 1 lenh khong duoc vuot han muc ngay")
print("=" * 74)
import urllib.parse
for key, info in m.BAO_535.items():
    so_bo = m.max_bo_moi_lenh(info["gia"], "535")
    if so_bo * info["gia"] > 2_500_000:
        FAIL.append(f"{key}: tong {so_bo*info['gia']} vuot han muc")
check(not [f for f in FAIL if "vuot han muc" in f], "moi loai bao: so_bo/lenh * gia <= 2.500.000d")

print()
print("  Do dai SMS o gioi han moi (ca xau nhat):")
mx = 0
for key, info in m.BAO_535.items():
    so_bo = m.max_bo_moi_lenh(info["gia"], "535")
    if info["type"] == "bc":
        n = info["n_main"]
        parts = [f"S {' '.join(f'{v:02d}' for v in range(1,n))} {n:02d}-01"] * so_bo
    else:
        sp = " ".join(f"{v:02d}" for v in range(1, info["n_sp"]+1))
        parts = [f"S {' '.join(f'{v:02d}' for v in range(1,6))}-{sp}"] * so_bo
    sms = f"535 K1 {key.upper()} " + " ".join(parts)
    if len(sms) > mx: mx, mxk, mxu = len(sms), key, len(f"https://vietlott-sms.netlify.app/?body={urllib.parse.quote(sms)}")
print(f"       dai nhat: {mxk} -> SMS {mx} ky tu (~{mx//153+1} doan), URL {mxu}")
check(mx <= 1700, f"SMS dai nhat {mx} <= 1700 (truoc cap la 2885)")

print()
print("=" * 74)
print(f"  {'TAT CA PASS' if not FAIL else str(len(FAIL)) + ' LOI'}")
for f in FAIL: print("   - " + f)
sys.exit(1 if FAIL else 0)
