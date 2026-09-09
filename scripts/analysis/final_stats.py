"""Kiem dinh thong ke: goi y cua bot co khac ngau nhien khong?"""
import csv, os, math
from collections import defaultdict, Counter

D = os.path.dirname(os.path.abspath(__file__))
K = {"535": 5, "645": 6, "655": 6}
N = {"535": 35, "645": 45, "655": 55}


def rd(name):
    with open(os.path.join(D, f"sheet_{name}.csv"), encoding="utf-8") as f:
        return list(csv.reader(f))


def C(n, r):
    return math.comb(n, r) if 0 <= r <= n else 0


actual = {}
for tk in K:
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

obs = defaultdict(Counter)
for r in rd("suggestions"):
    if len(r) < 6 or r[0] not in K or r[4].strip() != "scheduler":
        continue
    tk = r[0]
    try:
        ky = int(str(r[1]).split(" ")[0])
    except ValueError:
        continue
    if (tk, ky) not in actual:
        continue
    act = actual[(tk, ky)]
    for col in r[5:]:
        if not col.strip():
            continue
        nums = [int(x) for x in col.split("|")[0].split() if x.isdigit()]
        if len(nums) == K[tk]:
            obs[tk][len(set(nums) & act)] += 1

print("=" * 78)
print("  KIEM DINH: phan bo so trung THUC TE cua bot vs phan bo NGAU NHIEN")
print("  (chi lay source=scheduler - nguon duy nhat khong dinh bug nhan ky)")
print("=" * 78)

for tk in ("535", "645", "655"):
    c = obs[tk]
    tot = sum(c.values())
    if not tot:
        continue
    n, k = N[tk], K[tk]
    print(f"\n  --- {tk}  ({tot} bo so that, xo that) ---")
    print(f"  {'trung':>6} {'thuc te':>9} {'ngau nhien':>12} {'thuc te %':>11} {'ngau nhien %':>14}")
    chi2 = 0.0
    for m in range(0, k + 1):
        p = C(k, m) * C(n - k, k - m) / C(n, k)
        e = p * tot
        o = c.get(m, 0)
        if e >= 1:
            chi2 += (o - e) ** 2 / e
        if p * 100 > 0.005 or o:
            print(f"  {m:>6} {o:>9} {e:>12.1f} {o/tot*100:>10.2f}% {p*100:>13.2f}%")
    obs_mean = sum(m * cnt for m, cnt in c.items()) / tot
    exp_mean = k * k / n
    var = k * (k / n) * (1 - k / n) * (n - k) / (n - 1)
    se = math.sqrt(var / tot)
    z = (obs_mean - exp_mean) / se
    print(f"\n   trung binh thuc te : {obs_mean:.4f}")
    print(f"   trung binh ngau nhien: {exp_mean:.4f}")
    print(f"   z = {z:+.2f}   (|z| > 1.96 moi coi la khac biet that)")
    print(f"   chi-square = {chi2:.2f} voi {k} bac tu do"
          f"   -> {'KHAC ngau nhien' if chi2 > 11.07 else 'KHONG khac ngau nhien'}")

# Loi locale
print("\n" + "=" * 78)
print("  LOI DINH DANG SO trong sheet performance")
print("=" * 78)
perf = rd("performance")[1:]
first_bad = None
for i, r in enumerate(perf):
    if len(r) > 4 and "," in r[4]:
        first_bad = (i, r)
        break
ok = [r for r in perf if len(r) > 4 and "." in r[4]]
bad = [r for r in perf if len(r) > 4 and "," in r[4]]
print(f"\n  dong dung dau CHAM (doc duoc) : {len(ok)}")
print(f"  dong dung dau PHAY (crash)    : {len(bad)}")
if first_bad:
    i, r = first_bad
    print(f"  bat dau hong tu dong {i+2}: {r[:5]}  (ngay {r[0]})")
    print(f"  dong ngay truoc do        : {perf[i-1][:5]}")
sched_ok = [r for r in ok if len(r) > 3 and r[3] == "scheduler"]
sched_bad = [r for r in bad if len(r) > 3 and r[3] == "scheduler"]
print(f"\n  Rieng source=scheduler (thu duy nhat train_model.py dung):")
print(f"    doc duoc {len(sched_ok)} / bi bo qua {len(sched_bad)}"
      f"  -> mat {len(sched_bad)/(len(sched_ok)+len(sched_bad))*100:.0f}% du lieu")
