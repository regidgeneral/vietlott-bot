"""Mo phong chinh xac get_adaptive_weights() cua train_model.py tren du lieu that."""
import csv, os

D = os.path.dirname(os.path.abspath(__file__))
CFG = {"535": (35, 5), "645": (45, 6), "655": (55, 6)}
DEF = (3.0, 1.5, 1.0)

with open(os.path.join(D, "sheet_performance.csv"), encoding="utf-8") as f:
    rows = list(csv.reader(f))

for tk, (n, k) in CFG.items():
    baseline = k * k / n
    scheduler_rows = [r for r in rows[1:] if len(r) >= 5 and r[1] == tk and r[3] == "scheduler"]
    print(f"\n=== {tk} === (baseline={baseline:.3f})")
    print(f"  scheduler_rows tim thay: {len(scheduler_rows)}")
    if len(scheduler_rows) < 5:
        print("  -> < 5 mau, dung default"); continue

    last30 = scheduler_rows[-30:]
    dot = sum(1 for r in last30 if "." in r[4])
    comma = sum(1 for r in last30 if "," in r[4])
    plain = len(last30) - dot - comma
    print(f"  30 dong cuoi: dau cham={dot}, dau phay={comma}, so nguyen={plain}")

    scores = []
    for row in last30:
        try:
            scores.append(float(row[4]))
        except ValueError:
            continue
    print(f"  float() doc duoc: {len(scores)}/{len(last30)}  -> {scores if len(scores)<12 else scores[:12]}")

    if not scores:
        print("  -> scores RONG => sum()/len() = ZeroDivisionError => rot ve default 3.0")
        continue

    avg = sum(scores) / len(scores)
    print(f"  avg={avg:.4f}  (chi tinh tren {len(scores)} dong doc duoc)")
    if avg > baseline * 1.2:
        w = min(5.0, DEF[0] * (avg / baseline))
        print(f"  -> 'GOOD performance' => w_recent = {w:.3f}")
    elif avg < baseline * 0.8:
        print(f"  -> 'POOR performance' => w_recent = {DEF[0]*0.7:.3f}")
    else:
        print(f"  -> NEUTRAL => w_recent = {DEF[0]:.3f}")

    # avg that neu doc duoc HET
    allv = []
    for row in last30:
        try:
            allv.append(float(row[4].replace(",", ".")))
        except ValueError:
            pass
    if allv:
        real = sum(allv) / len(allv)
        print(f"  [neu sua bug] avg that = {real:.4f} tren {len(allv)} dong"
              f"  -> {'GOOD' if real > baseline*1.2 else ('POOR' if real < baseline*0.8 else 'NEUTRAL')}")
