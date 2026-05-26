import requests
from bs4 import BeautifulSoup
import re
import json
import os
from datetime import datetime
import pytz

VN_TZ = pytz.timezone("Asia/Ho_Chi_Minh")

URLS = {
    "535": "https://www.minhchinh.com/xo-so-dien-toan-lotto-535.html",
    "645": "https://www.minhchinh.com/xo-so-dien-toan-mega-645.html",
    "655": "https://www.minhchinh.com/xo-so-dien-toan-power-655.html",
}

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "vi-VN,vi;q=0.9",
    "Referer": "https://www.minhchinh.com/",
}

def parse_lotto535(soup, today_str):
    """Parse Lotto 5/35 — có số đặc biệt (số thứ 6), xổ 2 lần/ngày"""
    results = []
    # Mỗi kỳ có block: "Kết quả QSMT kỳ #XXX ngày DD/MM/YYYY - Lúc HH:MM"
    # Theo sau là dòng số: "N1 N2 N3 N4 N5 N6"
    text = soup.get_text("\n", strip=True)
    
    # Tìm tất cả block kết quả trong ngày hôm nay
    pattern = re.compile(
        r'kỳ\s+#?(\d+)\s+ngày\s+(' + re.escape(today_str) + r')\s*-\s*Lúc\s+(\d+:\d+)\s*\n([\d\s]+)',
        re.IGNORECASE
    )
    for m in pattern.finditer(text):
        ky = m.group(1).zfill(5)
        date = m.group(2)
        time = m.group(3)
        nums_raw = [int(x) for x in m.group(4).split() if x.isdigit()]
        if len(nums_raw) >= 6:
            nums = nums_raw[:5]
            special = nums_raw[5]
            # Convert date DD/MM/YYYY → YYYY-MM-DD
            d, mo, y = date.split("/")
            iso_date = f"{y}-{mo}-{d}"
            results.append({
                "id": ky,
                "date": iso_date,
                "time": time,
                "result": nums + [special]
            })
    return results

def parse_645_655(soup, today_str, type_key):
    """Parse Mega 6/45 và Power 6/55"""
    results = []
    text = soup.get_text("\n", strip=True)
    
    # 655 có 7 số (6 chính + 1 power), 645 có 6 số
    num_count = 7 if type_key == "655" else 6
    
    pattern = re.compile(
        r'kỳ\s+#?(\d+)\s+ngày\s+(' + re.escape(today_str) + r')\s*-\s*Lúc\s+(\d+:\d+)\s*\n([\d\s]+)',
        re.IGNORECASE
    )
    for m in pattern.finditer(text):
        ky = m.group(1).zfill(5)
        date = m.group(2)
        time = m.group(3)
        nums_raw = [int(x) for x in m.group(4).split() if x.isdigit()]
        if len(nums_raw) >= num_count:
            nums = nums_raw[:6]
            special = nums_raw[6] if type_key == "655" and len(nums_raw) >= 7 else None
            d, mo, y = date.split("/")
            iso_date = f"{y}-{mo}-{d}"
            entry = {"id": ky, "date": iso_date, "time": time, "result": nums}
            if special is not None:
                entry["result"] = nums + [special]
            results.append(entry)
    return results

def fetch_today():
    now = datetime.now(VN_TZ)
    today_str = now.strftime("%d/%m/%Y")  # DD/MM/YYYY để match với site
    print(f"Fetching results for {today_str}...")

    output = {"date": now.strftime("%Y-%m-%d"), "fetched_at": now.isoformat(), "results": {}}

    for type_key, url in URLS.items():
        print(f"  Fetching {type_key}...")
        try:
            r = requests.get(url, headers=HEADERS, timeout=15)
            if r.status_code != 200:
                print(f"  ❌ {type_key}: HTTP {r.status_code}")
                output["results"][type_key] = []
                continue

            soup = BeautifulSoup(r.text, "html.parser")

            if type_key == "535":
                results = parse_lotto535(soup, today_str)
            else:
                results = parse_645_655(soup, today_str, type_key)

            output["results"][type_key] = results
            print(f"  ✅ {type_key}: {len(results)} kỳ hôm nay")
            for r_item in results:
                print(f"     Kỳ {r_item['id']} {r_item['time']}: {r_item['result']}")

        except Exception as e:
            print(f"  ❌ {type_key}: {e}")
            output["results"][type_key] = []

    # Ghi ra data/today.json
    os.makedirs("data", exist_ok=True)
    with open("data/today.json", "w", encoding="utf-8") as f:
        json.dump(output, f, ensure_ascii=False, indent=2)

    print(f"\nSaved to data/today.json")
    return output

if __name__ == "__main__":
    fetch_today()
