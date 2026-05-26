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

def parse_results(soup, today_str, type_key):
    text = soup.get_text(" ", strip=True)
    results = []

    # Format: "ky ́ #662 nga ̀y 25/05/2026 - Lu ́c 21:00 01 06 09 15 23 08"
    pattern = re.compile(
        r'kỳ\s+#(\d+)\s+ngày\s+(\d{2}/\d{2}/\d{4})\s*-\s*Lúc\s+(\d+:\d+)\s+((?:\d+\s*){4,8})',
        re.IGNORECASE
    )
    num_count = {"535": 6, "645": 6, "655": 7}[type_key]

    for m in pattern.finditer(text):
        ky = m.group(1).zfill(5)
        date_raw = m.group(2)
        time_raw = m.group(3)
        nums_raw = [int(x) for x in m.group(4).split() if x.isdigit()]
        if len(nums_raw) < num_count:
            continue
        d, mo, y = date_raw.split("/")
        iso_date = f"{y}-{mo}-{d}"
        results.append({"id": ky, "date": iso_date, "time": time_raw, "result": nums_raw[:num_count]})
        print(f"     Found ky {ky} {date_raw} {time_raw}: {nums_raw[:num_count]}")

    today_iso = datetime.strptime(today_str, "%d/%m/%Y").strftime("%Y-%m-%d")
    today_results = [r for r in results if r["date"] == today_iso]

    if not today_results and results:
        latest = sorted(results, key=lambda x: x["id"], reverse=True)[0]
        print(f"     No today results, using latest: {latest['id']} {latest['date']}")
        return [latest]

    return today_results

def fetch_today():
    now = datetime.now(VN_TZ)
    today_str = now.strftime("%d/%m/%Y")
    print(f"Fetching results for {today_str}...")
    output = {"date": now.strftime("%Y-%m-%d"), "fetched_at": now.isoformat(), "results": {}}

    for type_key, url in URLS.items():
        print(f"  Fetching {type_key}...")
        try:
            r = requests.get(url, headers=HEADERS, timeout=15)
            if r.status_code != 200:
                print(f"  X {type_key}: HTTP {r.status_code}")
                output["results"][type_key] = []
                continue
            soup = BeautifulSoup(r.text, "html.parser")
            results = parse_results(soup, today_str, type_key)
            output["results"][type_key] = results
            print(f"  OK {type_key}: {len(results)} results")
        except Exception as e:
            print(f"  X {type_key}: {e}")
            output["results"][type_key] = []

    os.makedirs("data", exist_ok=True)
    with open("data/today.json", "w", encoding="utf-8") as f:
        json.dump(output, f, ensure_ascii=False, indent=2)
    print(f"Saved to data/today.json")
    return output

if __name__ == "__main__":
    fetch_today()
