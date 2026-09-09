"""Phan tich track record THAT tu Google Sheet cua bot."""
import csv, os, statistics
from collections import defaultdict

D = os.path.dirname(os.path.abspath(__file__))
BASE = {"535": 25/35, "645": 36/45, "655": 36/55}
K = {"535": 5, "645": 6, "655": 6}


def rd(name):
    with open(os.path.join(D, f"sheet_{name}.csv"), encoding="utf-8") as f:
        return list(csv.reader(f))


print("=" * 78)
print("  PHAN 1: KIEM TRA TINH TOAN VEN CUA DU LIEU")
print("=" * 78)

perf = rd("performance")
hdr, prows = perf[0], perf[1:]
print(f"\n[performance] {len(prows)} dong")

bad_empty = [r for r in prows if len(r) > 2 and not r[0].strip()]
bad_comma = [r for r in prows if len(r) > 4 and "," in r[4]]
print(f"  - dong co cot 'date' RONG          : {len(bad_empty)}")
print(f"  - dong co avg_matched dung DAU PHAY: {len(bad_comma)}   <- float() se crash")

parse_fail = 0
for r in prows:
    if len(r) < 5:
        continue
    try:
        float(r[4])
    except ValueError:
        parse_fail += 1
print(f"  - dong ma get_adaptive_weights() KHONG doc duoc: {parse_fail}/{len(prows)}"
      f"  ({parse_fail/len(prows)*100:.0f}%)")

print("\n[ket qua xo] kiem tra ky bi thieu:")
for tk in ("535", "645", "655"):
    rows = rd(tk)[1:]
    kys = []
    for r in rows:
        if len(r) > 1 and r[1].strip():
            try:
                kys.append(int(r[1].split(" ")[0]))
            except ValueError:
                pass
    if not kys:
        continue
    full = set(range(min(kys), max(kys) + 1))
    missing = sorted(full - set(kys))
    dup = len(kys) - len(set(kys))
    print(f"  {tk}: {len(kys)} ky luu ({min(kys)}..{max(kys)}), "
          f"THIEU {len(missing)} ky, trung lap {dup}")
    if missing:
        print(f"       thieu gan day: {missing[-12:]}")


print("\n" + "=" * 78)
print("  PHAN 2: TRACK RECORD THAT - TU TINH LAI, KHONG TIN SO BOT GHI")
print("=" * 78)

# Ket qua that: ky -> set so
actual = {}
for tk in ("535", "645", "655"):
    k = K[tk]
    for r in rd(tk)[1:]:
        if len(r) < 2 + k or not r[1].strip():
            continue
        try:
            ky = int(r[1].split(" ")[0])
        except ValueError:
            continue
        nums = []
        for i in range(2, 2 + k):
            if i < len(r) and r[i].strip().lstrip("-").isdigit():
                nums.append(int(r[i]))
        if len(nums) == k:
            actual[(tk, ky)] = set(nums)

print(f"\nDa nap {len(actual)} ky ket qua that")

# suggestions -> cham diem lai
stats = defaultdict(list)
unscored = defaultdict(int)
for r in rd("suggestions"):
    if len(r) < 6 or r[0] not in K:
        continue
    tk = r[0]
    try:
        ky = int(str(r[1]).split(" ")[0])
    except ValueError:
        continue
    src = r[4].strip()
    grp = "scheduler" if src == "scheduler" else ("manual" if src == "manual" else "manual_bao")
    key = (tk, ky)
    if key not in actual:
        for col in r[5:]:
            if col.strip():
                unscored[(tk, grp)] += 1
        continue
    for col in r[5:]:
        if not col.strip():
            continue
        nums = [int(x) for x in col.split("|")[0].split() if x.isdigit()]
        if nums:
            stats[(tk, grp)].append(len(set(nums) & actual[key]))

print(f"\n  {'loai':<8} {'nguon':<12} {'so bo':>7} {'trung TB':>10} {'ky vong':>9} {'chenh':>9} {'>=3 so':>8}")
print(f"  {'-'*8} {'-'*12} {'-'*7} {'-'*10} {'-'*9} {'-'*9} {'-'*8}")
for tk in ("535", "645", "655"):
    for grp in ("scheduler", "manual", "manual_bao"):
        v = stats.get((tk, grp), [])
        if not v:
            continue
        avg = statistics.mean(v)
        b = BASE[tk]
        # bao co nhieu so hon -> ky vong khac, chi so sanh scheduler/manual
        exp = b if grp != "manual_bao" else float("nan")
        h3 = sum(1 for x in v if x >= 3)
        chenh = f"{avg-exp:+.3f}" if exp == exp else "  n/a"
        exps = f"{exp:.3f}" if exp == exp else "n/a"
        print(f"  {tk:<8} {grp:<12} {len(v):>7} {avg:>10.3f} {exps:>9} {chenh:>9} {h3:>8}")

print("\n  Bo so KHONG BAO GIO duoc cham diem (ky khong ton tai trong sheet ket qua):")
tot_un = 0
for (tk, grp), c in sorted(unscored.items()):
    print(f"    {tk} / {grp:<12}: {c} bo")
    tot_un += c
print(f"    => TONG: {tot_un} bo so bi bo roi")
