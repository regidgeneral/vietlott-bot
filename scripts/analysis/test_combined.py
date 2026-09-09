"""Kiem tra get_combined_data sau khi khu trung, dung du lieu THAT."""
import ast, types, os, csv, json
from datetime import date

BOT = r"F:\Project\vietlott-bot-main\bot.py"
os.environ.setdefault("DISCORD_TOKEN", "x"); os.environ.setdefault("DISCORD_CHANNEL_ID", "1")
src = ast.parse(open(BOT, encoding="utf-8").read())
keep = []
for n in src.body:
    if isinstance(n, ast.Expr) and isinstance(n.value, ast.Call):
        continue
    if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef)) and n.decorator_list:
        n.decorator_list = []
    keep.append(n)
src.body = keep
m = types.ModuleType("b"); exec(compile(src, BOT, "exec"), m.__dict__)

D, T = os.environ["SP"], os.environ["TEMP"]

class WS:
    def __init__(self, rows): self.rows = rows
    def get_all_values(self): return self.rows
class WB:
    def __init__(self, mp): self.mp = mp
    def worksheet(self, n): return WS(self.mp[n])

sheets = {tk: list(csv.reader(open(os.path.join(D, f"sheet_{tk}.csv"), encoding="utf-8")))
          for tk in ("535", "645", "655")}
m.get_sheet = lambda: WB(sheets)

# JSONL doc tu file local thay vi goi mang
def fake_fetch(cfg):
    key = cfg["sms_prefix"]
    if key in m._cache: return m._cache[key]
    draws = []
    for line in open(os.path.join(T, f"v{key}.jsonl"), encoding="utf-8"):
        line = line.strip()
        if not line: continue
        nums, sp = m.parse_jsonl_line(line, cfg)
        if not nums: continue
        d = json.loads(line)
        try: ngay = date.fromisoformat(d.get("date", ""))
        except ValueError: ngay = None
        draws.append((int(d["id"]), ngay, nums, sp))
    m._cache[key] = draws
    return draws
m.fetch_jsonl_draws = fake_fetch

FAIL = []
def check(c, msg):
    print(("  OK   " if c else "  FAIL ") + msg)
    if not c: FAIL.append(msg)

MONG_DOI = {"535": 803, "645": 1362, "655": 1395}
CU       = {"535": 1533, "645": 2718, "655": 2783}

for tk in ("535", "645", "655"):
    cfg = m.CONFIGS[tk]; k = cfg["k"]
    m._cache.clear()
    nums, sps, days, pairs = m.get_combined_data(tk)
    n_ky = len(nums) // k
    print(f"\n  --- {tk} ---")
    check(n_ky == MONG_DOI[tk], f"so ky = {n_ky} (mong doi {MONG_DOI[tk]}, truoc khi sua: {CU[tk]})")
    check(len(nums) % k == 0, f"do dai chia het cho k ({len(nums)} % {k} = {len(nums)%k})")
    check(all(1 <= x <= cfg["n"] for x in nums), "moi so nam trong 1..n")
    check(len(days) == cfg["n"], f"days_since du {cfg['n']} so")
    hop_le = [v for v in days.values() if v != 9999]
    check(hop_le and max(hop_le) < 400, f"days_since hop ly (max {max(hop_le) if hop_le else '-'})")
    check(min(days.values()) >= 0, f"khong co days_since AM (min {min(days.values())})")
    if cfg.get("has_special"):
        lim = cfg["special_n"]
        check(sps and all(1 <= s <= lim for s in sps), f"special trong 1..{lim} ({len(sps)} gia tri)")
    else:
        check(not sps, "645 khong co special")
    # last_draw phai la ky moi nhat
    check(len(pairs) > 0, f"pair_freq co {len(pairs)} so")
    print(f"       last_draw = {nums[-k:]}")

print()
print("=" * 70)
print(f"  {'TAT CA PASS' if not FAIL else str(len(FAIL)) + ' LOI'}")
for f in FAIL: print("   - " + f)
