import csv, os
D = os.environ["SP"]
rows = list(csv.reader(open(os.path.join(D,"sheet_suggestions.csv"), encoding="utf-8")))
w = max(len(r) for r in rows)
print(f"  sheet 'suggestions': {len(rows)} dong, so cot toi da = {w}")
print(f"  -> chua duoc toi da {w-5} bo so moi dong")
# So bo toi da cua tung lenh
gh = {"535":2500000,"645":2100000,"655":2100000}
bao535 = {"bc4":310000,"bc6":60000,"bc7":210000,"bc8":560000,
          **{f"bd{i}": i*10000 for i in range(2,13)}}
bao_o = {"b5":(400000,500000),"b7":(70000,70000),"b8":(280000,280000),
         "b9":(840000,840000),"b10":(2100000,2100000)}
qua = []
for k,g in bao535.items():
    n = max(1, gh["535"]//g)
    if 5+n > w: qua.append((f"535/{k}", n, 5+n))
for k,(g4,g5) in bao_o.items():
    for tk,g in (("645",g4),("655",g5)):
        n = max(1, gh[tk]//g)
        if 5+n > w: qua.append((f"{tk}/{k}", n, 5+n))
print()
if qua:
    print("  Lenh sinh nhieu bo hon so cot -> append_row VUOT khung sheet:")
    for name,n,need in sorted(qua, key=lambda x:-x[1]):
        print(f"    {name:<12} {n:>3} bo -> can {need} cot (sheet chi co {w})")
else:
    print("  Khong lenh nao vuot so cot.")
