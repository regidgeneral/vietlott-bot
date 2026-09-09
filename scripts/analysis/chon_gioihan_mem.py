"""Chon nguong 'so bo moi lenh' dua tren do dai SMS / URL thuc te."""
import urllib.parse

BAO_535 = {
    "bc4": (310000, "bc", 4), "bc6": (60000, "bc", 6),
    "bc7": (210000, "bc", 7), "bc8": (560000, "bc", 8),
    **{f"bd{i}": (i * 10000, "bd", i) for i in range(2, 13)},
}
HAN_NGAY = 2_500_000
SMS_SEG = 153          # 1 doan SMS ghep (GSM-7)

def sms_text(key, typ, n, so_bo):
    if typ == "bc":
        parts = [f"S {' '.join(f'{v:02d}' for v in range(1, n))} {n:02d}-01"] * so_bo
    else:
        sp = " ".join(f"{v:02d}" for v in range(1, n + 1))
        parts = [f"S {' '.join(f'{v:02d}' for v in range(1, 6))}-{sp}"] * so_bo
    return f"535 K1 {key.upper()} " + " ".join(parts)

print(f"{'nguong':>7} | {'SMS dai nhat':>13} {'doan SMS':>9} {'URL dai nhat':>13} {'can TinyURL':>12}")
print("-" * 66)
for nguong in (20, 25, 30, 40, 50, 60, 125):
    mx_sms = mx_url = 0
    loai_mx = ""
    can_tiny = 0
    for key, (gia, typ, n) in BAO_535.items():
        so_bo = min(max(1, HAN_NGAY // gia), nguong)
        s = sms_text(key, typ, n, so_bo)
        u = len(f"https://vietlott-sms.netlify.app/?body={urllib.parse.quote(s)}")
        if u > 512:
            can_tiny += 1
        if len(s) > mx_sms:
            mx_sms, mx_url, loai_mx = len(s), u, key
    print(f"{nguong:>7} | {mx_sms:>13} {mx_sms//SMS_SEG + 1:>9} {mx_url:>13} {str(can_tiny) + '/15':>12}"
          f"   (dai nhat: {loai_mx})")

print()
print("Chi tiet tung loai o nguong 50:")
print(f"  {'loai':<6} {'ban dau':>8} {'sau cap':>8} {'SMS':>6} {'doan':>5} {'URL':>6} {'so lenh de dat het han muc':>28}")
for key, (gia, typ, n) in sorted(BAO_535.items(), key=lambda x: -(HAN_NGAY // x[1][0])):
    hard = max(1, HAN_NGAY // gia)
    soft = min(hard, 50)
    s = sms_text(key, typ, n, soft)
    u = len(f"https://vietlott-sms.netlify.app/?body={urllib.parse.quote(s)}")
    n_lenh = -(-hard // soft)
    print(f"  {key:<6} {hard:>8} {soft:>8} {len(s):>6} {len(s)//SMS_SEG + 1:>5} {u:>6} {n_lenh:>28}")
