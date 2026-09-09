"""Kiem chung: vi sao manual/bao co diem gan bang 0?"""
import csv, os
from collections import defaultdict

D = os.path.dirname(os.path.abspath(__file__))
K = {"535": 5, "645": 6, "655": 6}


def rd(name):
    with open(os.path.join(D, f"sheet_{name}.csv"), encoding="utf-8") as f:
        return list(csv.reader(f))


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
        nums = [int(r[i]) for i in range(2, 2 + k)
                if i < len(r) and r[i].strip().lstrip("-").isdigit()]
        if len(nums) == k:
            actual[(tk, ky)] = set(nums)

print("=" * 78)
print("  Gia thuyet: bo so 'manual' bi gan nhan KY DA XO XONG,")
print("  ma thuat toan lai CO Y LOAI TRU dung cac so cua ky do (_ml_pick: recent)")
print("=" * 78)

groups = defaultdict(lambda: {"sets": 0, "hits": 0, "zero": 0})
examples = []
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
    if (tk, ky) not in actual:
        continue
    act = actual[(tk, ky)]
    for col in r[5:]:
        if not col.strip():
            continue
        nums = set(int(x) for x in col.split("|")[0].split() if x.isdigit())
        if not nums:
            continue
        ov = len(nums & act)
        g = groups[(tk, grp)]
        g["sets"] += 1
        g["hits"] += ov
        if ov == 0:
            g["zero"] += 1
        if grp != "scheduler" and len(examples) < 5 and tk == "655":
            examples.append((tk, ky, src, sorted(nums), sorted(act), ov))

print(f"\n  {'loai':<6} {'nguon':<12} {'so bo':>7} {'tong trung':>11} {'so bo trung 0':>15} {'% trung 0':>10}")
print(f"  {'-'*6} {'-'*12} {'-'*7} {'-'*11} {'-'*15} {'-'*10}")
for (tk, grp), g in sorted(groups.items()):
    pct = g["zero"] / g["sets"] * 100 if g["sets"] else 0
    print(f"  {tk:<6} {grp:<12} {g['sets']:>7} {g['hits']:>11} {g['zero']:>15} {pct:>9.1f}%")

print("\n  Vi du cu the (655, gợi ý thủ công so voi chinh ky bi gan nhan):")
for tk, ky, src, nums, act, ov in examples:
    print(f"    ky {ky} [{src}]")
    print(f"      bot goi y : {' '.join(f'{n:02d}' for n in nums)}")
    print(f"      ket qua   : {' '.join(f'{n:02d}' for n in act)}")
    print(f"      trung     : {ov} so")

print("\n" + "=" * 78)
print("  Kiem tra sheet 'performance' bi hong dinh dang")
print("=" * 78)
perf = rd("performance")
print(f"\n  Vai dong loi dien hinh (cot: {perf[0]}):")
n = 0
for r in perf[1:]:
    if len(r) > 4 and (not r[0].strip() or "," in r[4]):
        print(f"    {r[:7]}")
        n += 1
        if n >= 6:
            break

ok = sum(1 for r in perf[1:] if len(r) > 4 and r[0].strip() and "." in r[4])
print(f"\n  Dong doc duoc boi get_adaptive_weights(): {ok}/{len(perf)-1}")
