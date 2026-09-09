import csv, json, os
D = os.environ["SP"]; T = os.environ["TEMP"]
for tk,k in (("535",5),("645",6),("655",6)):
    js = set()
    for line in open(os.path.join(T,f"v{tk}.jsonl"), encoding="utf-8"):
        line=line.strip()
        if line: js.add(int(json.loads(line)["id"]))
    sh = set()
    for r in list(csv.reader(open(os.path.join(D,f"sheet_{tk}.csv"), encoding="utf-8")))[1:]:
        if len(r)>1 and r[1].strip():
            try: sh.add(int(r[1].split(" ")[0]))
            except ValueError: pass
    trung = js & sh
    print(f"  {tk}: JSONL {len(js)} ky + Sheets {len(sh)} ky = {len(js)+len(sh)} (bot dang cong don)")
    print(f"       thuc te chi co {len(js|sh)} ky duy nhat, TRUNG {len(trung)} ky")
    print(f"       -> embed hien thi '{len(js)+len(sh)} ky lich su', thoi phong {(len(js)+len(sh))/len(js|sh)*100-100:.0f}%")
