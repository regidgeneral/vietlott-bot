"""Tinh chinh xac cac gioi han Discord + do dai URL SMS, thay vi uoc luong."""
import urllib.parse

GIOI_HAN = {"535": 2_500_000, "645": 2_100_000, "655": 2_100_000}
BAO_535 = {
    "bc4": (310000, "bc", 4), "bc6": (60000, "bc", 6), "bc7": (210000, "bc", 7),
    "bc8": (560000, "bc", 8),
    **{f"bd{i}": (i * 10000, "bd", i) for i in range(2, 13)},
}
BAO_645_655 = {"b5": (400000, 500000, 5), "b7": (70000, 70000, 7),
               "b8": (280000, 280000, 8), "b9": (840000, 840000, 9),
               "b10": (2100000, 2100000, 10)}

FIELD_MAX, EMBED_MAX = 1024, 6000
print("=" * 74)
print("  A. Field 'Bộ số' co vuot 1024 ky tu khong? (chunk_size=10)")
print("=" * 74)
worst = []
for key, (gia, typ, n) in BAO_535.items():
    so_bo = max(1, GIOI_HAN["535"] // gia)
    lines = []
    for i in range(so_bo):
        if typ == "bc":
            disp = " ".join(f"`{v:02d}`" for v in range(1, n + 1))
            lines.append(f"**Bộ {i+1}:** {disp} | ĐB:`01`")
        else:
            disp = " ".join(f"`{v:02d}`" for v in range(1, 6))
            sp = " ".join(f"`{v:02d}`" for v in range(1, n + 1))
            lines.append(f"**Bộ {i+1}:** {disp} | ĐB: {sp}")
    chunks = ["\n".join(lines[i:i+10]) for i in range(0, len(lines), 10)]
    mx = max(len(c) for c in chunks)
    worst.append((f"535/{key}", so_bo, mx))
for key, (g4, g5, n) in BAO_645_655.items():
    for tk, gia in (("645", g4), ("655", g5)):
        so_bo = max(1, GIOI_HAN[tk] // gia)
        lines = [f"**Bộ {i+1}:** " + " ".join(f"`{v:02d}`" for v in range(1, n + 1))
                 for i in range(so_bo)]
        chunks = ["\n".join(lines[i:i+10]) for i in range(0, len(lines), 10)]
        worst.append((f"{tk}/{key}", so_bo, max(len(c) for c in chunks)))
for tk in ("535", "645", "655"):
    n = 5 if tk == "535" else 6
    lines = [f"**Bộ {i+1}:** " + " ".join(f"`{v:02d}`" for v in range(1, n + 1)) +
             (" | ĐB:`01`" if tk != "645" else "") for i in range(10)]
    chunks = ["\n".join(lines[i:i+10]) for i in range(0, len(lines), 10)]
    worst.append((f"{tk}/lenh chinh x10", 10, max(len(c) for c in chunks)))

worst.sort(key=lambda x: -x[2])
for name, so_bo, mx in worst[:8]:
    print(f"  {name:<22} {so_bo:>3} bộ  field dài nhất = {mx:>5} / {FIELD_MAX}"
          f"  {'!!! VUOT' if mx > FIELD_MAX else 'OK'}")
print(f"\n  => Ket luan: {'CO vuot' if worst[0][2] > FIELD_MAX else 'KHONG vuot - toi da ' + str(worst[0][2])}")

print()
print("=" * 74)
print("  B. Do dai URL SMS - co can TinyURL khong?")
print("=" * 74)
def sms_len(tk, key, so_bo, typ=None, n=0):
    if tk == "535" and typ == "bc":
        parts = [f"S {' '.join(f'{v:02d}' for v in range(1,n))} {n:02d}-01" for _ in range(so_bo)]
    elif tk == "535" and typ == "bd":
        sp = " ".join(f"{v:02d}" for v in range(1, n + 1))
        parts = [f"S {' '.join(f'{v:02d}' for v in range(1,6))}-{sp}" for _ in range(so_bo)]
    else:
        parts = [f"S {' '.join(f'{v:02d}' for v in range(1,n+1))}" for _ in range(so_bo)]
    sms = f"{tk} K1 {key.upper()} " + " ".join(parts)
    return len(f"https://vietlott-sms.netlify.app/?body={urllib.parse.quote(sms)}")

rows = []
for key, (gia, typ, n) in BAO_535.items():
    so_bo = max(1, GIOI_HAN["535"] // gia)
    rows.append((f"535/{key}", so_bo, sms_len("535", key, so_bo, typ, n)))
for key, (g4, g5, n) in BAO_645_655.items():
    for tk, gia in (("645", g4), ("655", g5)):
        so_bo = max(1, GIOI_HAN[tk] // gia)
        rows.append((f"{tk}/{key}", so_bo, sms_len(tk, key, so_bo, None, n)))
rows.sort(key=lambda x: -x[2])
vuot = [r for r in rows if r[2] > 512]
for name, so_bo, ln in rows[:6]:
    print(f"  {name:<12} {so_bo:>3} bộ  URL = {ln:>5} ky tu  {'-> CAN TinyURL' if ln > 512 else 'OK'}")
print(f"\n  => {len(vuot)}/{len(rows)} loai bao VUOT 512 -> phu thuoc TinyURL.")
print(f"     Neu TinyURL loi, url[:512] tao link CUT -> nut hong.")

print()
print("=" * 74)
print("  C. Tong embed ket qua khi CO NHIEU NGUON goi y cung 1 ky")
print("=" * 74)
print("  (sau khi sua bug nhan ky, goi y thu cong se dung don ve dung ky nay)")
base = 200
for n_src in (1, 2, 3, 4, 5, 6, 8):
    total = base + n_src * (1000 + 40)
    print(f"  {n_src} nguồn -> ~{total:>5} ky tu / {EMBED_MAX}"
          f"  {'!!! VUOT -> post_result NEM HTTPException' if total > EMBED_MAX else 'OK'}")
