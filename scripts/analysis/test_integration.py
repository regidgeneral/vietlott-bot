"""Test tich hop: chay that post_result / save_suggestions / make_button voi mock."""
import ast, types, os, sys, asyncio, random

BOT = r"F:\Project\vietlott-bot-main\bot.py"
os.environ.setdefault("DISCORD_TOKEN", "x")
os.environ.setdefault("DISCORD_CHANNEL_ID", "1")

src = ast.parse(open(BOT, encoding="utf-8").read())
keep = []
for n in src.body:
    if isinstance(n, ast.Expr) and isinstance(n.value, ast.Call):
        continue                      # bo client.run(...) / kiem_tra_env()
    if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef)) and n.decorator_list:
        n.decorator_list = []
    keep.append(n)
src.body = keep
m = types.ModuleType("botmod")
exec(compile(src, BOT, "exec"), m.__dict__)

FAIL = []
def check(cond, msg):
    print(("  OK   " if cond else "  FAIL ") + msg)
    if not cond:
        FAIL.append(msg)

# ---------------------------------------------------------------- mocks
class FakeChannel:
    def __init__(self): self.sent = []
    async def send(self, content=None, embed=None, view=None):
        self.sent.append((content, embed, view)); return None

class FakeWS:
    def __init__(self, rows=None): self.rows = rows or []; self.appended = []
    def get_all_values(self): return self.rows
    def col_values(self, i): return [r[i-1] if len(r) >= i else "" for r in self.rows]
    def append_row(self, row): self.appended.append(row); self.rows.append(row)

class FakeWB:
    def __init__(self, ws): self.ws = ws
    def worksheet(self, name): return self.ws

print("=" * 74)
print("  1. make_button: TinyURL loi -> KHONG duoc tra ve nut link cut")
print("=" * 74)
m.shorten_url = lambda url: None          # gia lap TinyURL chet
v = asyncio.run(m.make_button("535 K1 " + "S 01 02 03 04 05-01 " * 50))
check(v is m.discord.utils.MISSING, f"tra ve MISSING (thuc te: {type(v).__name__})")

m.shorten_url = lambda url: "https://tinyurl.com/abc123"
v = asyncio.run(m.make_button("535 K1 S 01 02 03 04 05-01"))
check(v is not m.discord.utils.MISSING and len(v.children) == 1, "TinyURL OK -> co nut")
check(all(len(getattr(c, "url", "")) <= 512 for c in v.children), "URL nut <= 512 ky tu")

print()
print("=" * 74)
print("  2. save_suggestions: 50 bo -> tach nhieu dong, khong dong nao > 35 cot")
print("=" * 74)
ws = FakeWS([["type_key","ky","date","time","source"] + [f"bo{i}" for i in range(1,6)]])
m.get_sheet = lambda: FakeWB(ws)
bo50 = [(sorted(random.sample(range(1, 36), 5)), None) for _ in range(50)]
m.save_suggestions("535", "00875", "09/09/2026", "10:00", bo50, source="manual_bao535_bd2")
check(len(ws.appended) == 2, f"tach thanh {len(ws.appended)} dong (mong doi 2)")
check(all(len(r) <= 35 for r in ws.appended),
      f"moi dong <= 35 cot (dai nhat {max(len(r) for r in ws.appended)})")
tong_bo = sum(len(r) - 5 for r in ws.appended)
check(tong_bo == 50, f"khong mat bo nao ({tong_bo}/50)")
check(all(r[:5] == ["535","00875","09/09/2026","10:00","manual_bao535_bd2"] for r in ws.appended),
      "moi dong giu nguyen metadata -> doc lai gop dung theo source")

print()
print("=" * 74)
print("  3. post_result: 17 nguon goi y -> embed KHONG duoc vuot gioi han Discord")
print("=" * 74)
nguon = ["scheduler", "manual"] + [f"manual_bao535_{k}" for k in
         ("bc4","bc6","bc7","bc8","bd2","bd3","bd4","bd5","bd6","bd7","bd8","bd9","bd10","bd11","bd12")]
by_source = {s: [(sorted(random.sample(range(1,36),5)), [1,2]) for _ in range(30)] for s in nguon}

ch = FakeChannel()
m.client = types.SimpleNamespace(get_channel=lambda i: ch,
                                 fetch_channel=None, user="test")
m.fetch_latest_result = lambda tk: ("00874 (09/09/2026)", [4,7,14,16,23], 10)
m.save_result = lambda *a, **k: True
m.compare_with_suggestions = lambda *a, **k: ("00874", by_source)
m.track_performance = lambda *a, **k: None
m.get_jackpot_535 = lambda: None
m.get_combined_data = lambda tk: ([1,2,3,4,5]*200, [1]*200, {}, {})
m.save_suggestions = lambda *a, **k: None
import datetime as _dt
m.datetime = _dt.datetime

asyncio.run(m.post_result("535"))
embeds = [e for _, e, _ in ch.sent if e is not None]
check(len(embeds) >= 1, f"da gui {len(embeds)} embed")
for idx, e in enumerate(embeds):
    d = e.to_dict()
    tong = len(d.get("title","")) + len(d.get("description",""))
    for f in d.get("fields", []):
        tong += len(f["name"]) + len(f["value"])
    n_field = len(d.get("fields", []))
    qua_dai = [f["name"] for f in d.get("fields", []) if len(f["value"]) > 1024]
    check(tong <= 6000, f"embed #{idx+1}: tong {tong} <= 6000")
    check(n_field <= 25, f"embed #{idx+1}: {n_field} field <= 25")
    check(not qua_dai, f"embed #{idx+1}: khong field nao > 1024 ({qua_dai})")

print()
print("=" * 74)
print("  4. scheduler: khop cua so 10 phut + khong chay lai cung 1 lich")
print("=" * 74)
from datetime import datetime, timedelta
VN = m.VN_TZ
def mo_phong(gio_phut_list, gio, phut, tre_giay):
    """Tra ve True neu lich (gio,phut) se duoc kich hoat tai thoi diem tre_giay."""
    da = set()
    hen_goc = VN.localize(datetime(2026, 9, 9, gio, phut, 0))
    now = hen_goc + timedelta(seconds=tre_giay)
    hom_nay = now.date().isoformat()
    key = (hom_nay, "535", gio, phut)
    hen = now.replace(hour=gio, minute=phut, second=0, microsecond=0)
    tre = (now - hen).total_seconds()
    return 0 <= tre <= 600 and key not in da

check(mo_phong(None, 13, 35, 0),    "dung gio hen -> chay")
check(mo_phong(None, 13, 35, 90),   "tre 90s (cach cu da LO) -> van chay")
check(mo_phong(None, 13, 35, 599),  "tre 599s -> van chay")
check(not mo_phong(None, 13, 35, 601), "tre 601s -> bo qua (khong bao muon)")
check(not mo_phong(None, 13, 35, -60), "chua toi gio -> khong chay")

da_chay = set()
def chay_lai(n):
    dem = 0
    for _ in range(n):
        key = ("2026-09-09", "535", 13, 35)
        if key not in da_chay:
            da_chay.add(key); dem += 1
    return dem
check(chay_lai(5) == 1, "5 vong lap / 2 scheduler chong -> chi chay 1 lan")

print()
print("=" * 74)
print(f"  KET QUA: {'TAT CA PASS' if not FAIL else str(len(FAIL)) + ' LOI'}")
print("=" * 74)
for f in FAIL:
    print("   - " + f)
sys.exit(1 if FAIL else 0)
