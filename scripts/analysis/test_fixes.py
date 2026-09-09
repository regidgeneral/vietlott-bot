"""Verify 3 fix - nap bot.py ma KHONG chay client.run()."""
import ast, sys, types, os

BOT = r"F:\Project\vietlott-bot-main\bot.py"

src = ast.parse(open(BOT, encoding="utf-8").read())
# Bo dong client.run(TOKEN) va cac decorator discord o cuoi
keep = []
for node in src.body:
    if isinstance(node, ast.Expr) and isinstance(node.value, ast.Call):
        f = node.value.func
        if isinstance(f, ast.Name) and f.id == "print":
            keep.append(node)
        continue  # bo client.run(...)
    if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and node.decorator_list:
        node.decorator_list = []
    keep.append(node)
src.body = keep

mod = types.ModuleType("botmod")
mod.__dict__["__name__"] = "botmod"
os.environ.setdefault("DISCORD_TOKEN", "x")
exec(compile(src, BOT, "exec"), mod.__dict__)

print("=" * 70)
print("FIX 1 — next_ky_str()")
print("=" * 70)
cases = [
    ("00874 (08/09/2026)", "00875"),
    ("00873 (08/09/2026)", "00874"),
    ("01395 (08/09/2026)", "01396"),
    ("00999 (01/01/2026)", "01000"),
    (None, "?"),
    ("? (?)", "?"),
]
ok = True
for inp, want in cases:
    got = mod.next_ky_str(inp)
    flag = "OK " if got == want else "FAIL"
    if got != want:
        ok = False
    print(f"  {flag} next_ky_str({inp!r:24}) = {got!r:10} (mong doi {want!r})")
print(f"  => {'PASS' if ok else 'CO LOI'}")

print()
print("=" * 70)
print("FIX 2 — parse_score()")
print("=" * 70)
cases2 = [("0,8", 0.8), ("0.8", 0.8), ("1", 1.0), ("0", 0.0),
          ("1,2", 1.2), ("", None), ("abc", None), (None, None)]
ok = True
for inp, want in cases2:
    got = mod.parse_score(inp)
    good = (got == want) or (got is None and want is None)
    if not good:
        ok = False
    print(f"  {'OK ' if good else 'FAIL'} parse_score({inp!r:8}) = {got!r:6} (mong doi {want!r})")
print(f"  => {'PASS' if ok else 'CO LOI'}")

print()
print("=" * 70)
print("FIX 3 — nguon du lieu realtime (goi mang that)")
print("=" * 70)
for tk in ("535", "645", "655"):
    ky, nums, sp = mod.fetch_from_minhchinh(tk)
    print(f"  {tk}: ky={ky}  nums={nums}  special={sp}")

print()
print("  fetch_latest_result (day du chuoi fallback):")
for tk in ("535", "645", "655"):
    ky, nums, sp = mod.fetch_latest_result(tk)
    print(f"  {tk}: ky={ky}  nums={nums}  special={sp}")

print()
jp = mod.get_jackpot_535()
print(f"  get_jackpot_535() = {jp:,}d" if jp else f"  get_jackpot_535() = {jp}")
