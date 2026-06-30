import json
import os
import base64
import gspread
from google.oauth2.service_account import Credentials

def get_sheet():
    scopes = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
    creds_b64 = os.environ.get("GOOGLE_CREDENTIALS_B64", "")
    if not creds_b64:
        raise ValueError("Missing GOOGLE_CREDENTIALS_B64")
    creds_json = base64.b64decode(creds_b64).decode("utf-8")
    creds_dict = json.loads(creds_json)
    creds = Credentials.from_service_account_info(creds_dict, scopes=scopes)
    gc = gspread.authorize(creds)
    return gc.open_by_key(os.environ.get("GOOGLE_SHEET_ID", ""))


def backfill_performance():
    wb = get_sheet()

    # Đọc suggestions (sheet này KHÔNG có header, data bắt đầu từ row 1)
    ws_sugg = wb.worksheet("suggestions")
    sugg_rows = ws_sugg.get_all_values()
    if not sugg_rows:
        print("Khong co data suggestions")
        return
    # Detect header: nếu row đầu có "type_key" ở cột A thì có header, ngược lại không
    if sugg_rows[0] and sugg_rows[0][0].strip().lower() == "type_key":
        sugg_data = sugg_rows[1:]
        print("  Phat hien co header, bo qua row 1")
    else:
        sugg_data = sugg_rows
        print("  Khong co header, dung toan bo data")

    # Đọc performance hiện có để tránh duplicate
    ws_perf = wb.worksheet("performance")
    perf_rows = ws_perf.get_all_values()
    if not perf_rows:
        ws_perf.append_row(["date", "type_key", "ky", "source", "avg_matched", "total_sets", "details"])
        perf_rows = [["date", "type_key", "ky", "source", "avg_matched", "total_sets", "details"]]
    has_perf_header = perf_rows[0] and perf_rows[0][0].strip().lower() == "date"
    perf_data = perf_rows[1:] if has_perf_header else perf_rows
    existing_keys = set()
    for r in perf_data:
        if len(r) >= 4:
            existing_keys.add((r[1], r[2].strip(), r[3]))  # (type_key, ky, source)

    # Đọc kết quả thực tế từ 3 sheet 535/645/655
    results_by_type = {}
    for type_key in ["535", "645", "655"]:
        ws = wb.worksheet(type_key)
        rows = ws.get_all_values()
        if not rows:
            results_by_type[type_key] = {}
            continue
        # Detect header: cột A chứa "Ngày" (text) thay vì ngày dạng dd/mm/yyyy
        first_cell = rows[0][0].strip() if rows[0] else ""
        has_header = first_cell.lower() in ("ngày", "ngay", "date")
        result_data = rows[1:] if has_header else rows
        print(f"  {type_key}: has_header={has_header}, first_cell='{first_cell}'")
        k = 5 if type_key == "535" else 6
        ky_to_result = {}
        for row in result_data:
            if len(row) < 2 + k:
                continue
            ky = row[1].strip().zfill(5)
            nums = []
            for i in range(2, 2 + k):
                if i < len(row) and row[i].strip().isdigit():
                    nums.append(int(row[i]))
            if len(nums) == k:
                ky_to_result[ky] = nums
        results_by_type[type_key] = ky_to_result
        print(f"  Loaded {len(ky_to_result)} ky ket qua cho {type_key}")

    # Group suggestions theo (type_key, ky)
    grouped = {}
    for row in sugg_data:
        if len(row) < 5:
            continue
        type_key = row[0].strip()
        ky_raw = row[1].strip()
        # ky co the dang "00677 (02/06/2026)" hoac chi "00677"
        ky = ky_raw.split(" ")[0].zfill(5)
        date_str = row[2].strip() if len(row) > 2 else ""
        key = (type_key, ky)
        grouped.setdefault(key, []).append((date_str, row))

    written = 0
    debug_count = 0
    for (type_key, ky), entries in grouped.items():
        result_nums = results_by_type.get(type_key, {}).get(ky)
        if not result_nums:
            if debug_count < 5:
                sample_keys = list(results_by_type.get(type_key, {}).keys())[:3]
                print(f"  [DEBUG] Khong tim thay ky='{ky}' (type={type_key}) trong ket qua. Sample keys: {sample_keys}")
                debug_count += 1
            continue  # chua co ket qua thuc te cho ky nay

        result_set = set(result_nums)
        ngay = entries[0][0]

        # Group theo source trong cung 1 ky
        by_source = {}
        for date_str, row in entries:
            src = row[4] if len(row) > 4 else "unknown"
            by_source.setdefault(src, [])
            for col in row[5:]:
                if not col.strip():
                    continue
                nums = [int(x) for x in col.split("|")[0].split() if x.isdigit()]
                if nums:
                    matched = len(set(nums) & result_set)
                    by_source[src].append(matched)

        for src, scores in by_source.items():
            if not scores:
                continue
            if (type_key, ky, src) in existing_keys:
                continue  # da co roi, bo qua
            avg = round(sum(scores) / len(scores), 2)
            details = ",".join(str(s) for s in scores)
            ws_perf.append_row([ngay, type_key, ky, src, avg, len(scores), details])
            written += 1
            print(f"  + {type_key} ky {ky} ({src}): avg={avg} ({len(scores)} bo)")

    print(f"\nDa ghi {written} dong moi vao performance")


if __name__ == "__main__":
    backfill_performance()
